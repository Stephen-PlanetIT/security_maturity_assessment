import streamlit as st
import time

from core import LLMEngine
from config import get_config, ConfigKey
from prompts import (
    build_maturity_prompt,
    build_maturity_header_prompt,
    MaturityReport,
    MaturityHeader,
    SYSTEM_PERSONA,
)
from export import create_maturity_docx

st.set_page_config(page_title="Cybersecurity Maturity (Page)", layout="wide")

# Page-scoped workflow intent
st.session_state["workflow"] = "📈 Cybersecurity Maturity Assessment"

st.title("Cybersecurity Maturity — Page View")
st.caption("Set the generation mode and produce the Maturity Roadmap directly from this page.")

# Simplified: no per-page engine selector; default to staged v3
st.caption("This page uses the resilient staged v3 generator with a deterministic composite fallback. Engine selection is centralised in the main maturity page.")
st.session_state["maturity_generation_engine"] = "Staged v3 (header→batched domains→exec/roadmap)"
st.session_state["staged_enabled"] = False

st.divider()
st.subheader("Generate Maturity Roadmap (Page)")

# Require client_inputs set by the main app UI; guard if absent
client_inputs = st.session_state.get("client_inputs")
if not client_inputs:
    st.warning(
        "No client inputs found. Open the main app to populate the Customer Estate & Engagement Profile, then return here."
    )
else:
    if st.button("Generate Maturity Roadmap (Page)", type="primary"):
        st.session_state["_last_generation_ts"] = time.time()
        with st.spinner("Compiling Cybersecurity Maturity Assessment..."):
            client = LLMEngine.get_client()
            deployment = get_config(ConfigKey.AZURE_DEPLOYMENT, "gpt-4o")

            # Header-first staged mode
            if bool(st.session_state.get("staged_enabled", False)):
                header_prompt = build_maturity_header_prompt(client_inputs)
                header_obj = LLMEngine.generate_structured_report(
                    client, deployment, SYSTEM_PERSONA, header_prompt, MaturityHeader
                )
                if header_obj:
                    st.session_state["maturity_obj"] = header_obj

            # Main generation path based on selected engine
            # Simplified workflow: always use the resilient staged v3 generator with a deterministic composite fallback.
            mr = LLMEngine.generate_maturity_report_staged_v3(
                client, deployment, SYSTEM_PERSONA, client_inputs, MaturityHeader, MaturityReport
            )
            if not mr:
                mr = LLMEngine.generate_maturity_report_composite(
                    client, deployment, SYSTEM_PERSONA, client_inputs, MaturityReport
                )

            if mr:
                st.session_state["maturity_obj"] = mr
                st.success("Maturity Roadmap generated (Page).")
            else:
                st.error("Engine failed to generate the roadmap.")

    # Export deliverable from page
    if st.session_state.get("maturity_obj"):
        with st.spinner("Preparing Word document..."):
            try:
                bytes_docx = create_maturity_docx(client_inputs, st.session_state["maturity_obj"])
            except Exception as e:
                bytes_docx = b""
                st.error(f"Word export failed: {e}")
        if bytes_docx:
            fname = f"{client_inputs.get('customer_name','Client').replace(' ','_')}_Cybersecurity_Maturity_Report.docx"
            st.download_button(
                "📄 Download Cybersecurity Maturity Report (Word)",
                data=bytes_docx,
                file_name=fname,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

    # Compact preview
    if st.session_state.get("maturity_obj"):
        mr = st.session_state["maturity_obj"]
        st.divider()
        st.subheader("📊 Preview")
        st.markdown("### Executive Summary")
        try:
            st.markdown(mr.executive_summary)
        except Exception:
            st.info("Executive Summary not available.")

        st.markdown("### Resiliency Matrix Mapping")
        try:
            st.info(mr.resiliency_matrix_mapping)
        except Exception:
            st.info("Matrix mapping not available.")

        st.markdown("### Domains (headlines)")
        try:
            for d in getattr(mr, "domain_assessments", [])[:5]:
                st.markdown(f"- {getattr(d, 'domain_name', 'Domain')}")
        except Exception:
            st.info("Domain assessments not available.")