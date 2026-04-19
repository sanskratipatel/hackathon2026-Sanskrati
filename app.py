from __future__ import annotations

import json
import pandas as pd
import streamlit as st

from src.workflow import workflow
from src.utils import safe_read_json
from src.config import settings
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

st.set_page_config(
    page_title="ShopWave AI Support Agent",
    page_icon="*"  ,
    layout="wide",
    initial_sidebar_state="expanded"
)


st.markdown(
    """
    <style>
    .main {background-color:#0e1117;color:white;}
    .stMetric {background:#111827;padding:15px;border-radius:12px;}
    .block-container {padding-top:1rem;}
    .card {
        background:#111827;
        padding:18px;
        border-radius:14px;
        margin-bottom:12px;
        border:1px solid #1f2937;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.sidebar.title("⚙️ Settings")
model_name = st.sidebar.text_input("Model", value=settings.model_name)
workers = st.sidebar.slider("Concurrent Workers", 1, 20, settings.max_workers)

page = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Process Ticket",
        "Batch Run",
        "Audit Logs"
    ]
)


def load_tickets():
    return safe_read_json(settings.tickets_file, [])


def load_results():
    return safe_read_json(settings.results_file, [])


if page == "Dashboard":
    st.title(" ShopWave AI Support Dashboard")

    results = load_results()
    metrics = workflow.metrics(results)

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Total Tickets", metrics["total"])
    c2.metric("Approved", metrics["approved"])
    c3.metric("Escalated", metrics["escalated"])
    c4.metric("Avg Confidence", metrics["avg_confidence"])

    st.divider()

    if results:
        df = pd.DataFrame(results)

        st.subheader("Recent Decisions")
        st.dataframe(
            df[
                [
                    "ticket_id",
                    "decision",
                    "confidence",
                    "priority"
                ]
            ],
            use_container_width=True
        )

        st.subheader("Decision Distribution")
        st.bar_chart(df["decision"].value_counts())


elif page == "Process Ticket":
    st.title("🎫 Process Single Ticket")

    tickets = load_tickets()

    if not tickets:
        st.warning("No tickets found.")
        st.stop()

    ticket_map = {
        str(t["ticket_id"]): t for t in tickets
    }

    selected = st.selectbox(
        "Select Ticket",
        list(ticket_map.keys())
    )

    ticket = ticket_map[selected]

    st.markdown("### Ticket Data")
    st.json(ticket)

    if st.button("🚀 Run AI Agent"):
        with st.spinner("Processing..."):
            result = workflow.run_one(ticket)

        st.success("Completed")

        c1, c2 = st.columns([2, 1])

        with c1:
            st.markdown("### Final Decision")
            st.markdown(
                f"""
                <div class="card">
                <h3>{result['decision']}</h3>
                <p>{result['reason']}</p>
                </div>
                """,
                unsafe_allow_html=True
            )

            st.markdown("### Customer Reply")
            st.write(result["customer_reply"])

            st.markdown("### Tool Outputs")
            st.json(result.get("tool_outputs", {}))

        with c2:
            st.metric("Confidence", result["confidence"])
            st.progress(float(result["confidence"]))

# =====================================================
# BATCH RUN
# =====================================================
elif page == "Batch Run":
    st.title("⚡ Batch Process Tickets")

    if st.button("Run All Tickets"):
        with st.spinner("Running concurrent batch..."):
            tickets = load_tickets()
            results = workflow.run_batch(
                tickets=tickets,
                max_workers=workers
            )

        st.success(f"Processed {len(results)} tickets")

        df = pd.DataFrame(results)

        st.dataframe(df, use_container_width=True)

        csv = df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="⬇ Download CSV Report",
            data=csv,
            file_name="ticket_results.csv",
            mime="text/csv"
        )

# =====================================================
# AUDIT LOGS
# =====================================================
elif page == "Audit Logs":
    st.title(" Audit Logs")

    logs = safe_read_json(settings.audit_log_file, [])

    if not logs:
        st.info("No logs available.")
        st.stop()

    search = st.text_input("Search by ticket id / event")

    filtered = []

    for row in logs:
        text = json.dumps(row).lower()

        if search.lower() in text:
            filtered.append(row)

    st.write(f"Found {len(filtered)} entries")

    st.json(filtered[:100])