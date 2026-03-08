import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import PyPDF2
from optimizer import optimize_production
from orchestrator import audit_dispatch, chat_with_manual
import time
import requests
import json
import os
import renewable

# 1. PAGE SETUP (Must be first)
st.set_page_config(page_title="Hydrogen Plant Dashboard", layout="wide", initial_sidebar_state="collapsed")

# 2. CUSTOM CSS (To make the containers look like dark mode cards)
st.markdown("""
    <style>
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: rgba(30, 33, 48, 0.4); 
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    </style>
""", unsafe_allow_html=True)

# 3. MASTER GRID LAYOUT
col_left, col_right = st.columns([1, 3], gap="large")

# ==========================================
# LEFT PANEL & MATH EXECUTION
# ==========================================
with col_left:
    with st.container(border=True):
        st.markdown("<h4 style='text-align: center; color: #a1a1aa;'>Control Panel</h4>", unsafe_allow_html=True)
        
        # Interactive Inputs 
        target_prod = st.slider("Target Production (kg)", min_value=100, max_value=2000, value=1060, step=10)
        capacity = st.number_input("Electrolyzer Capacity (MW)", value=60.0, step=1.0)
        startup_cost = st.number_input("Startup Cost (₹)", value=15000, step=1000)
        use_live_data = st.toggle("📡 Use Live IEX Data (Scraped)")
        
        # OEM Safety Manual Upload (RAG)
        uploaded_manual = st.file_uploader("Upload OEM Safety Manual", type=["pdf"])
        
        manual_text = ""
        if uploaded_manual is not None:
            pdf_reader = PyPDF2.PdfReader(uploaded_manual)
            for page in pdf_reader.pages:
                manual_text += page.extract_text() or ""
            st.success("Manual loaded for AI Audit", icon="✅")
        else:
            manual_text = "Default limit: Max 2 starts per day. Minimum run time: 2 hours."
            
        st.divider()
        
        # Create empty UI slots to fill AFTER the math runs
        cost_metric_slot = st.empty()
        actual_metric_slot = st.empty()
        safety_metric_slot = st.empty()

# --- THE MATH ENGINE ---
# Hardcoded arrays from your updated optimizer
# --- THE MATH ENGINE ---
# 1. Base Hardcoded Arrays (Your safe fallback)
renew_prices = renewable.generate_renewable_prices() # Get the latest renewable prices based on weather
grid_prices = [
    3.668, 3.561, 3.430, 3.588, 3.782, 7.5,
    6.5, 4.734, 2.442, 2.758, 2.498, 2.455,
    2.084, 2.007, 2.172, 2.635, 3.117, 3.829,
    7.300, 10.000, 7.7, 7.5, 8.5, 7.5, 7.5
]

# 2. Attempt to load the dynamically scraped JSON file if the toggle is ON
if use_live_data:
    if os.path.exists("live_grid_data.json"):
        try:
            with open("live_grid_data.json", "r") as f:
                scraped_data = json.load(f)
                if len(scraped_data) == 24:
                    grid_prices = scraped_data
                    
                    st.toast('Loaded live prices from local scraper cache!', icon='🟢')
        except Exception:
            st.toast('Failed to read cached data. Using fallback.', icon='🟡')
    else:
        st.toast('No scraped data found. Run scraper.py first!', icon='🔴')

# 3. Run the updated optimization
production, g_percent, total_cost = optimize_production(grid_prices, renew_prices, target_prod, capacity, startup_cost)

# Calculate LCOH (Total Cost / Total kg Produced)
optimized_lcoh = total_cost / target_prod if target_prod > 0 else 0

# Convert lists for Plotly and Gemini
lp_dispatch_frac = [(p / capacity) if capacity > 0 else 0 for p in production]
lp_dispatch_binary = [1 if p > 0 else 0 for p in production]
renew_plot = [r if r != float('inf') else None for r in renew_prices] # Removes inf so Plotly doesn't crash

# Call the AI Orchestrator
with st.spinner("AI Agent reading manual & auditing schedule..."):
    audit_report = audit_dispatch(lp_dispatch_binary, manual_text)

# Inject the calculated results back into the left sidebar slots
cost_metric_slot.metric("Optimized Cost", f"₹ {optimized_lcoh:.2f}/kg")
actual=243.73
actual_metric_slot.metric("Normal Green H2 Cost", f"₹ {actual:.2f}/kg")
safety_metric_slot.metric("Safety Status", f"{audit_report.get('violations_count', 0)} VIOLATIONS")


# ==========================================
# RIGHT PANEL: Visuals
# ==========================================
# ==========================================
# RIGHT PANEL: Visuals
# ==========================================
with col_right:
    st.title("Hydrogen Plant Dashboard")
    
    with st.container(border=True):
        hours = list(range(24))
        
        # --- AUTO-PLAY ANIMATION CODE ---
        chart_placeholder = st.empty() # The empty box we will draw into
        
        # Safely calculate max Y to lock the axis height (so it doesn't bounce)
        valid_renew = [r for r in renew_plot if r is not None and r != float('inf')]
        max_price = max(max(grid_prices), max(valid_renew) if valid_renew else 0) + 1
        
        # Loop 24 times, adding one hour of data per frame
        for i in range(1, 25):
            curr_hours = hours[:i]
            curr_grid = grid_prices[:i]
            curr_renew = renew_plot[:i]
            curr_dispatch = lp_dispatch_frac[:i]

            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            # Trace 1: Grid Price (Red Line)
            fig.add_trace(
                go.Scatter(x=curr_hours, y=curr_grid, name="Grid Price (₹/kWh)", line=dict(color="#ef4444", width=2)),
                secondary_y=False,
            )
            # Trace 2: Renewable Price (Blue Line)
            fig.add_trace(
                go.Scatter(x=curr_hours, y=curr_renew, name="Renewable Price (₹/kWh)", line=dict(color="#3b82f6", width=2)),
                secondary_y=False,
            )
            # Trace 3: LP Optimized Dispatch Status (Green Step Chart)
            fig.add_trace(
                go.Scatter(x=curr_hours, y=curr_dispatch, name="Electrolyzer Load", line=dict(color="#10b981", shape='hv', width=3, dash='dot')),
                secondary_y=True,
            )
            
            fig.update_layout(
                template="plotly_dark", margin=dict(l=0, r=0, t=30, b=0), height=350,
                hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                xaxis=dict(range=[0, 23], title="Hour of Day"),  # CRITICAL: Locks the X-axis width
                yaxis=dict(range=[0, max_price])                 # CRITICAL: Locks the Y-axis height
            )
            fig.update_yaxes(title_text="Price (₹/kWh)", secondary_y=False)
            fig.update_yaxes(title_text="Load %", secondary_y=True, range=[0, 1.2], showgrid=False)
            
            # Instantly overwrite the placeholder with the new frame
            chart_placeholder.plotly_chart(fig, use_container_width=True)
            
            # Pause for ~0.125s (24 frames * 0.125s = 3 seconds total)
            time.sleep(0.125)

    # --- BOTTOM RIGHT CARDS ---
    # ... (Keep your bottom cards exactly as they are down here)
    # --- BOTTOM RIGHT CARDS ---
    # --- BOTTOM RIGHT CARDS ---
    # We are switching from 4 columns to 3 columns to give everything more breathing room
    bot1, bot2, bot3 = st.columns([1.2, 1, 2.5])
    
    with bot1:
        with st.container(border=True):
            st.markdown("<p style='font-size: 14px; color: #a1a1aa; margin-bottom: 0;'>Power Source</p>", unsafe_allow_html=True)
            
            # Made the Donut chart bigger (height 180) and turned on the legend
            donut = go.Figure(data=[go.Pie(labels=['Renewable', 'Grid'], values=[100 - g_percent, g_percent], hole=.6, marker_colors=["#10b981", "#cbd5e1"])])
            donut.update_layout(
                showlegend=True, 
                legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5), # Legend placed neatly below
                margin=dict(l=0, r=0, t=10, b=30), 
                height=180, # Increased height to match Chatbot
                template="plotly_dark", 
                paper_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(donut, use_container_width=True)
            
    with bot2:
        with st.container(border=True):
            # --- CO2 MATH ---
            # 50 kWh per 1 kg H2. Grid emits 0.82 kg CO2 per kWh.
            grid_h2_produced = target_prod * (g_percent / 100)
            co2_emitted = (grid_h2_produced * 50) * 0.71
            
            #baseline_co2 = (target_prod * 50) * 0.82 # Emissions if 100% grid
            co2_saved = target_prod*30
            
            # Stacked metrics look incredibly professional
            st.metric("Optimised CO₂ Emission", f"{co2_emitted:,.0f} kg")
            st.divider() # Adds a clean line between the two metrics
            st.metric("Normal CO2 emission for electrolysis", f"{co2_saved:,.0f} kg")
            
    with bot3: # (Or bot4 depending on your layout column name)
        with st.container(border=True):
            st.markdown("<p style='font-size: 14px; color: #a1a1aa; margin-bottom: 0;'>AI Safety Agent (RAG Chat)</p>", unsafe_allow_html=True)
            
            # Initialize chat history in session state so it doesn't wipe on refresh
            if "chat_history" not in st.session_state:
                st.session_state.chat_history = []
                
            # Create a scrolling container for the chat
            chat_container = st.container(height=180, border=False)
            
            with chat_container:
                # 1. Always display the official schedule audit first
                if audit_report.get("status", "FAILED") == "PASSED":
                    st.chat_message("ai").write(f"✅ **SCHEDULE APPROVED:** {audit_report.get('explanation', '')}")
                else:
                    st.chat_message("ai").write(f"🛑 **VIOLATION CAUGHT:** {audit_report.get('explanation', '')}")
                
                # 2. Render all past user/ai conversation history
                for msg in st.session_state.chat_history:
                    st.chat_message(msg["role"]).write(msg["content"])
            
            # 3. The Chat Input box
            user_question = st.chat_input("Ask AI about the safety manual...")
            if user_question:
                # Instantly save the user's question to the state
                st.session_state.chat_history.append({"role": "user", "content": user_question})
                
                # Call the guardrail AI
                with st.spinner("Agent typing..."):
                    ai_response = chat_with_manual(user_question, manual_text)
                
                # Save the AI's response to the state
                st.session_state.chat_history.append({"role": "ai", "content": ai_response})
                
                # Force the UI to refresh to show the new messages immediately
                st.rerun()