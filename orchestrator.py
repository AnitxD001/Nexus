"""AI Safety Agent (Orchestrator)

This module audits a 24-hour, day-ahead dispatch schedule using the
Google Gemini API (gemini-1.5-flash) and returns a strict JSON object
that the Streamlit UI can safely render.

Functions:
- `audit_dispatch(dispatch_status, max_starts=2)` -> dict

Technical notes:
- Loads `GEMINI_API_KEY` via python-dotenv and configures
  `google.generativeai`.
- Uses `response_mime_type="application/json"` when calling Gemini.
- Falls back to a local validator and returns a formatted JSON on
  API errors/timeouts.
"""

from __future__ import annotations

import json
import os
from typing import List, Dict

from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
_API_KEY = os.getenv("GEMINI_API_KEY")
if _API_KEY:
	try:
		genai.configure(api_key=_API_KEY)
	except Exception:
		# Best-effort: configuration failure will be handled at call time
		pass


def _local_validate(dispatch_status: List[int], max_starts: int) -> Dict:
	"""Perform a deterministic local audit of `dispatch_status`.

	Rules enforced:
	- Start-up Limit: number of 0->1 transitions <= max_starts
	- Minimum Run Time: no isolated 1-hour blocks (runs must be >=2h)

	Returns a dict matching the required JSON schema.
	"""
	if not isinstance(dispatch_status, list) or len(dispatch_status) != 24:
		return {
			"status": "FAILED",
			"violations_count": -1,
			"explanation": "Invalid input: dispatch_status must be a 24-element list.",
		}

	# normalize values to 0/1
	try:
		s = [1 if int(bool(x)) else 0 for x in dispatch_status]
	except Exception:
		return {
			"status": "FAILED",
			"violations_count": -1,
			"explanation": "Invalid input: dispatch_status contains non-integer values.",
		}

	# Count 0->1 transitions (including the initial hour)
	starts = 0
	if s[0] == 1:
		starts += 1
	for i in range(1, 24):
		if s[i - 1] == 0 and s[i] == 1:
			starts += 1

	violations = 0
	violation_msgs = []

	if starts > max_starts:
		violations += 1
		violation_msgs.append(f"startups_exceeded: {starts} > {max_starts}")

	# Check for isolated 1-hour blocks
	isolated_hours = 0
	for i in range(24):
		if s[i] == 1:
			prev_off = (i == 0) or (s[i - 1] == 0)
			next_off = (i == 23) or (s[i + 1] == 0)
			if prev_off and next_off:
				isolated_hours += 1

	if isolated_hours > 0:
		violations += 1
		violation_msgs.append(f"isolated_1h_blocks: {isolated_hours}")

	result = {
		"status": "PASSED" if violations == 0 else "FAILED",
		"violations_count": violations,
		"explanation": "Schedule meets safety constraints." if violations == 0 else "; ".join(violation_msgs)[:200],
	}
	return result


def audit_dispatch(dispatch_status: List[int], max_starts: int = 2) -> Dict:
	"""Audit `dispatch_status` using Google Gemini and return structured JSON.

	Parameters
	- dispatch_status: 24-element list of 0/1 integers
	- max_starts: integer, default 2

	Returns a Python dict matching the schema:
	{
	  "status": "PASSED" | "FAILED",
	  "violations_count": <int>,
	  "explanation": "<Short, 2-sentence explanation>"
	}

	If the Gemini API fails or times out, a deterministic local validation
	is used as a fallback and a formatted JSON dict is returned.
	"""
	# Basic local sanity check before calling API
	local_result = _local_validate(dispatch_status, max_starts)
	if local_result.get("violations_count") == -1:
		return local_result

	prompt = (
		"You are an AI safety auditor. Given a 24-element list of 0s and 1s"
		" representing hourly ON/OFF status for an electrolyzer, check the"
		" schedule against these rules:\n"
		f"1) Start-up Limit: 0->1 transitions must be <= {max_starts}.\n"
		"2) Minimum Run Time: the system may not run for isolated 1-hour"
		" blocks; any RUN must be at least 2 consecutive hours.\n\n"
		"Return only a JSON object (no extra text) with keys: `status`,"
		" `violations_count`, and `explanation` (short, max 2 sentences)."
		" Use values: `PASSED` or `FAILED` for status. Here is the schedule:\n"
		f"{dispatch_status}"
	)

	# Attempt the Gemini API call
	try:
		response = genai.responses.create(
			model="gemini-1.5-flash",
			input=prompt,
			response_mime_type="application/json",
		)

		# Attempt to extract JSON text from the response in a few common locations
		json_text = None
		# Some client versions place text at response.output[0].content[0].text
		try:
			json_text = (
				response.output[0]["content"][0]["text"]
				if hasattr(response, "output") or isinstance(response, dict)
				else None
			)
		except Exception:
			json_text = None

		if not json_text:
			# fallback to stringified response
			json_text = getattr(response, "text", None) or str(response)

		parsed = json.loads(json_text)

		# Validate shape minimally
		if not all(k in parsed for k in ("status", "violations_count", "explanation")):
			# If shape unexpected, fall back to local result
			return {
				"status": "FAILED",
				"violations_count": -1,
				"explanation": "Auditor output malformed; using local validation fallback.",
			}

		# Ensure types
		parsed["violations_count"] = int(parsed["violations_count"])
		parsed["status"] = str(parsed["status"]).upper()
		parsed["explanation"] = str(parsed["explanation"]).strip()
		return parsed

	except Exception as exc:
		# On any API error/timeouts, return a deterministic fallback JSON
		# but include the local validation as guidance.
		fallback_local = _local_validate(dispatch_status, max_starts)
		return {
			"status": fallback_local.get("status", "FAILED"),
			"violations_count": fallback_local.get("violations_count", -1),
			"explanation": (
				"API error during audit; used local fallback. "
				+ (fallback_local.get("explanation", ""))
			)[:200],
		}


if __name__ == "__main__":
	# Quick example for manual testing
	example = [0] * 24
	example[8:10] = [1, 1]
	example[18] = 1  # isolated one-hour block
	print(audit_dispatch(example, max_starts=2))

