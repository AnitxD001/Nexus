"""AI Safety Agent (Orchestrator)

This module audits a 24-hour, day-ahead dispatch schedule using the
Google Gemini API (gemini-2.5-flash) and returns a strict JSON object
that the Streamlit UI can safely render. It uses Direct RAG to read 
from an uploaded PDF manual.
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
        pass


def _local_validate(dispatch_status: List[int], max_starts: int = 2) -> Dict:
    """Perform a deterministic local audit if the API fails."""
    if not isinstance(dispatch_status, list) or len(dispatch_status) != 24:
        return {
            "status": "FAILED",
            "violations_count": -1,
            "explanation": "Invalid input: dispatch_status must be a 24-element list.",
        }

    try:
        s = [1 if int(bool(x)) else 0 for x in dispatch_status]
    except Exception:
        return {
            "status": "FAILED",
            "violations_count": -1,
            "explanation": "Invalid input: dispatch_status contains non-integer values.",
        }

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

    isolated_hours = 0
    for i in range(1, 23):
        if s[i] == 1 and s[i - 1] == 0 and s[i + 1] == 0:
            isolated_hours += 1
            
    # Edge cases for first and last hour
    if s[0] == 1 and s[1] == 0:
        isolated_hours += 1
    if s[23] == 1 and s[22] == 0:
        isolated_hours += 1

    if isolated_hours > 0:
        violations += 1
        violation_msgs.append(f"isolated_1h_blocks: {isolated_hours}")

    result = {
        "status": "PASSED" if violations == 0 else "FAILED",
        "violations_count": violations,
        "explanation": "Schedule meets safety constraints." if violations == 0 else "Local Fallback: " + "; ".join(violation_msgs)[:200],
    }
    return result


def audit_dispatch(dispatch_status: List[int], manual_text: str) -> Dict:
    """Audit `dispatch_status` using Google Gemini and RAG."""
    
    # 1. Sanity Check
    local_result = _local_validate(dispatch_status)
    if local_result.get("violations_count") == -1:
        return local_result

    # 2. Build the RAG Prompt
    prompt = f"""
    You are an AI Safety Inspector for a 30MW Green Hydrogen Electrolyzer.
    
    OEM SAFETY MANUAL PROVIDED BY USER:
    \"\"\"{manual_text}\"\"\"
    
    CURRENT 24-HOUR SCHEDULE TO AUDIT:
    {dispatch_status}
    
    TASK:
    Analyze the 24-hour schedule (0=OFF, 1=ON) strictly against the rules in the provided OEM Safety Manual.
    Count the number of cold start-ups (transitioning from 0 to 1).
    Check for any minimum run-time violations.
    
    CRITICAL INSTRUCTION FOR RAG CITATION:
    If you find a violation, you MUST explicitly cite the specific "Rule" or "Section" number from the OEM Manual in your explanation. 
    
    RESPOND STRICTLY IN JSON FORMAT EXACTLY LIKE THIS:
    {{
        "status": "PASSED" or "FAILED",
        "violations_count": <integer>,
        "explanation": "<A detailed explanation citing the specific Rule/Section from the manual.>"
    }}
    """

    # 3. Call Gemini (Using correct SDK syntax)
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        parsed = json.loads(response.text)

        if not all(k in parsed for k in ("status", "violations_count", "explanation")):
            raise ValueError("Malformed JSON from AI")

        parsed["violations_count"] = int(parsed["violations_count"])
        parsed["status"] = str(parsed["status"]).upper()
        parsed["explanation"] = str(parsed["explanation"]).strip()
        
        return parsed

    except Exception as exc:
        print(f"API Error: {exc}") # Prints to your terminal so you can debug without breaking the UI
        fallback_local = _local_validate(dispatch_status)
        return {
            "status": fallback_local.get("status", "FAILED"),
            "violations_count": fallback_local.get("violations_count", -1),
            "explanation": (
                "API offline. Using local safety fallback. "
                + (fallback_local.get("explanation", ""))
            )[:200],
        }


if __name__ == "__main__":
    example = [0] * 24
    example[8:10] = [1, 1]
    example[18] = 1  
    dummy_text = "Rule 1: Max 2 starts. Rule 2: No 1-hour runs."
    print(audit_dispatch(example, dummy_text))