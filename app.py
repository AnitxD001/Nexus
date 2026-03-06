import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

# 1. PAGE SETUP (Must be first)
st.set_page_config(page_title="Hydrogen Plant Dashboard", layout="wide", initial_sidebar_state="collapsed")

# 2. CUSTOM CSS (To make the containers look like dark mode cards)
st.markdown("""
    <style>
    /* Subtle background tint for containers to match your mockup */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: rgba(30, 33, 48, 0.4); 
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    </style>
""", unsafe_allow_html=True)

# 3. MASTER GRID LAYOUT: Left Panel (1 part) | Right Panel (3 parts)
col_left, col_right = st.columns([1, 3], gap="large")

# ==========================================
# LEFT PANEL: Controls & KPIs
# ==========================================
with col_left:
    with st.container(border=True):
        st.markdown("<h4 style='text-align: center; color: #a1a1aa;'>Control Panel</h4>", unsafe_allow_html=True)
        
        # Interactive Inputs (Replacing static text from mockup)
        target_prod = st.slider("Target Production (kg)", min_value=100, max_value=1000, value=600, step=10)
        capacity = st.number_input("Electrolyzer Capacity (MW)", value=30.0, step=1.0)
        
        st.divider()
        
        # Output Metrics
        st.metric("Optimized Cost", "₹ 159/kg")
        st.metric("Safety Status", "0 VIOLATIONS")

# ==========================================
# RIGHT PANEL: Main Chart & Bottom Row
# ==========================================
with col_right:
    st.title("Hydrogen Plant Dashboard")
    
    # --- TOP RIGHT: The Linear Programming Chart ---
    with st.container(border=True):
        # Generate dummy data representing the LP inputs/outputs
        hours = list(range(25))
        grid_price = np.random.uniform(2, 8, 25) # Price in ₹/kWh
        renewable_forecast = np.random.uniform(0, 30, 25) # Solar/Wind MW
        lp_dispatch_status = np.random.choice([0, 1], size=25, p=[0.4, 0.6]) # ON/OFF Schedule
        
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        # Trace 1: Grid Price (Red Line)
        fig.add_trace(
            go.Scatter(x=hours, y=grid_price, name="Grid Price (₹/kWh)", line=dict(color="#ef4444", width=2)),
            secondary_y=False,
        )
        # Trace 2: Renewable Forecast (Blue Area)
        fig.add_trace(
            go.Scatter(x=hours, y=renewable_forecast, name="Renewables (MW)", fill='tozeroy', line=dict(color="#3b82f6", width=0), opacity=0.3),
            secondary_y=False,
        )
        # Trace 3: LP Optimized Dispatch (Green Step Chart)
        fig.add_trace(
            go.Scatter(x=hours, y=lp_dispatch_status, name="Electrolyzer ON", line=dict(color="#10b981", shape='hv', width=3)),
            secondary_y=True,
        )
        
        fig.update_layout(
            template="plotly_dark",
            margin=dict(l=0, r=0, t=30, b=0),
            height=350,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        fig.update_yaxes(title_text="Price / Renewables", secondary_y=False)
        fig.update_yaxes(title_text="Status (ON/OFF)", secondary_y=True, range=[0, 1.2], showgrid=False)
        
        st.plotly_chart(fig, use_container_width=True)

    # --- BOTTOM RIGHT: The 4 Metric Cards ---
    # We split this row into 4 columns mirroring your image
    bot1, bot2, bot3, bot4 = st.columns([1.2, 1, 1, 1.5])
    
    with bot1:
        with st.container(border=True):
            st.markdown("<p style='font-size: 14px; color: #a1a1aa; margin-bottom: 0;'>Production Mix</p>", unsafe_allow_html=True)
            # Create the small Donut Chart
            donut = go.Figure(data=[go.Pie(labels=['Renewable', 'Grid'], values=[75, 25], hole=.6, marker_colors=["#10b981", "#cbd5e1"])])
            donut.update_layout(showlegend=False, margin=dict(l=0, r=0, t=10, b=10), height=100, template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(donut, use_container_width=True)
            
    with bot2:
        with st.container(border=True):
            st.metric("Total Savings (LCOH)", "+18.5%")
            
    with bot3:
        with st.container(border=True):
            st.metric("Hydrogen Produced", f"{target_prod} kg")
            
    with bot4:
        with st.container(border=True):
            st.markdown("<p style='font-size: 14px; color: #a1a1aa; margin-bottom: 0;'>AI Chatbot</p>", unsafe_allow_html=True)
            with st.container(height=90, border=False):
                st.chat_message("ai").write("Schedule verified against safety constraints.")
            st.chat_input("Ask AI...")