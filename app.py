import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import PyPDF2
from optimizer import optimize_production
from orchestrator import audit_dispatch

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
        safety_metric_slot = st.empty()

# --- THE MATH ENGINE ---
# Hardcoded arrays from your updated optimizer
renew_prices = [3.2,5,3.0,2.9,2.8,2.6, 2.3,2.1,2.0,10,1.8,1.7, 1.7,1.8,2.0,2.2,2.5,2.9, 3.3,3.6, float('inf'),float('inf'),float('inf'),float('inf')]
grid_prices = [3.2,4,2.8,2.7,2.9,4.2, 4.2,5.0,5.5,9,5.6,5.2, 4.8,4.5,4.3,4.7,5.4,6.0, 6.5,6.2,5.6,3,2,2.5]

# Run the updated optimization
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
safety_metric_slot.metric("Safety Status", f"{audit_report.get('violations_count', 0)} VIOLATIONS")


# ==========================================
# RIGHT PANEL: Visuals
# ==========================================
with col_right:
    st.title("Hydrogen Plant Dashboard")
    
    with st.container(border=True):
        hours = list(range(24))
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        # Trace 1: Grid Price (Red Line)
        fig.add_trace(
            go.Scatter(x=hours, y=grid_prices, name="Grid Price (₹/kWh)", line=dict(color="#ef4444", width=2)),
            secondary_y=False,
        )
        # Trace 2: Renewable Price (Blue Line) - Note it breaks at night due to 'None'
        fig.add_trace(
            go.Scatter(x=hours, y=renew_plot, name="Renewable Price (₹/kWh)", line=dict(color="#3b82f6", width=2)),
            secondary_y=False,
        )
        # Trace 3: LP Optimized Dispatch Status
        fig.add_trace(
            go.Scatter(x=hours, y=lp_dispatch_frac, name="Electrolyzer Load", line=dict(color="#10b981", shape='hv', width=3, dash='dot')),
            secondary_y=True,
        )
        
        fig.update_layout(
            template="plotly_dark", margin=dict(l=0, r=0, t=30, b=0), height=350,
            hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        fig.update_yaxes(title_text="Price (₹/kWh)", secondary_y=False)
        fig.update_yaxes(title_text="Load %", secondary_y=True, range=[0, 1.2], showgrid=False)
        st.plotly_chart(fig, use_container_width=True)

    # --- BOTTOM RIGHT CARDS ---
    bot1, bot2, bot3, bot4 = st.columns([1, 1, 1, 2.5])
    
    with bot1:
        with st.container(border=True):
            st.markdown("<p style='font-size: 14px; color: #a1a1aa; margin-bottom: 0;'>Power Source</p>", unsafe_allow_html=True)
            # DYNAMIC DONUT: 100-g is Renewable%, g is Grid%
            donut = go.Figure(data=[go.Pie(labels=['Renewable', 'Grid'], values=[100 - g_percent, g_percent], hole=.6, marker_colors=["#10b981", "#cbd5e1"])])
            donut.update_layout(showlegend=False, margin=dict(l=0, r=0, t=10, b=10), height=100, template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(donut, use_container_width=True)
            
    with bot2:
        with st.container(border=True):
            # Show the absolute total cost (variable 's' from your math)
            st.metric("Total Plant Cost", f"₹ {total_cost:,.0f}")
            
    with bot3:
        with st.container(border=True):
            st.metric("Hydrogen Produced", f"{target_prod} kg")
            
    with bot4:
        with st.container(border=True):
            st.markdown("<p style='font-size: 14px; color: #a1a1aa; margin-bottom: 0;'>AI Safety Agent (RAG)</p>", unsafe_allow_html=True)
            with st.container(height=180, border=False):
                if audit_report.get("status", "FAILED") == "PASSED":
                    st.chat_message("ai").write(f"✅ **APPROVED:** {audit_report.get('explanation', '')}")
                else:
                    st.chat_message("ai").write(f"🛑 **VIOLATION CAUGHT:** {audit_report.get('explanation', '')}")
            
            st.chat_input("Ask AI about the safety constraints...")