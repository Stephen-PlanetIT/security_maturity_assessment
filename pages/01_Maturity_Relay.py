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

st.set_page_config(page_title="Cybersecurity Maturity (Redirect)", layout="wide")
# Redirect stub: unify navigation under app.py
st.session_state["workflow"] = "📈 Cybersecurity Maturity Assessment"
try:
    st.switch_page("app.py")  # type: ignore[attr-defined]
except Exception:
    st.page_link("app.py", label="📈 Switching to Maturity… (click if not redirected)")
    # Render footer in fallback view
    try:
        from ui_shared_sections import render_footer
        render_footer(show_divider=True)
    except Exception:
        pass
st.stop()

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

    # Run Report Improvement & Evidence Enforcement pipeline before export
    if st.session_state.get("maturity_obj"):
        _mr = st.session_state.get("maturity_obj")
        try:
            from services.report_improvement.integration import improve_generated_maturity_report
            import json, hashlib

            def _h(x):
                try:
                    return hashlib.sha256(json.dumps(x, sort_keys=True, default=str).encode("utf-8")).hexdigest()
                except Exception:
                    return hashlib.sha256(str(x).encode("utf-8")).hexdigest()

            raw_hash = _h(_mr.model_dump() if hasattr(_mr, "model_dump") else (_mr.dict() if hasattr(_mr, "dict") else {}))
            ci_hash = _h(client_inputs)
            transcript = st.session_state.get("meeting_transcript", "") or ""
            summary = st.session_state.get("meeting_summary", "") or ""
            tx_hash = _h(transcript)
            sm_hash = _h(summary)
            cache_key = f"{raw_hash}:{ci_hash}:{tx_hash}:{sm_hash}"

            if st.session_state.get("_improve_cache_key") != cache_key:
                with st.spinner("Applying Evidence Enforcement & Authority Reconciliation..."):
                    res = improve_generated_maturity_report(
                        raw_report=_mr,
                        client_inputs=client_inputs,
                        transcript=transcript or None,
                        meeting_summary=summary or None,
                        run_id=None,
                    )
                    st.session_state["raw_maturity_obj"] = _mr
                    if getattr(res, "improved_report", None):
                        st.session_state["improved_maturity_obj"] = res.improved_report
                        st.session_state["maturity_obj"] = res.improved_report
                        try:
                            setattr(st.session_state["maturity_obj"], "_specialist_content_validated", True)
                        except Exception:
                            pass
                    st.session_state["report_improvement_validation"] = getattr(res, "validation_result", None)
                    st.session_state["report_improvement_run_id"] = getattr(res, "run_id", None)
                    st.session_state["_improve_cache_key"] = cache_key
        except Exception as e:
            # Fall back to raw report if improvement pipeline encounters non-critical error
            pass

    # Export deliverable from page with post-render verification & dual-tier gating
    if st.session_state.get("maturity_obj"):
        try:
            from tools.diagnostics.telemetry_sidecar import get_sidecar
            sidecar = get_sidecar()
            sidecar.record_field("entry_point", "pages/01_Maturity_Relay.py")
            sidecar.record_field("export_input_id", f"{type(st.session_state['maturity_obj']).__name__}@{id(st.session_state['maturity_obj'])}")
        except Exception:
            pass
        with st.spinner("Preparing Word document..."):
            try:
                bytes_docx = create_maturity_docx(client_inputs, st.session_state["maturity_obj"])
                try:
                    from tools.diagnostics.telemetry_sidecar import get_sidecar
                    get_sidecar().record_field("final_render_status", "SUCCESS")
                except Exception:
                    pass
            except Exception as e:
                try:
                    from tools.diagnostics.telemetry_sidecar import get_sidecar
                    get_sidecar().record_field("final_render_status", f"FAILED: {e}")
                except Exception:
                    pass
                bytes_docx = b""
                st.error(f"Word export failed: {e}")

        if bytes_docx:
            # Post-render docx verification
            from services.report_improvement.post_render_docx_verifier import (
                inspect_and_verify_docx,
                repair_rendered_docx_content,
            )
            verify_res = inspect_and_verify_docx(bytes_docx, client_inputs, is_final_requested=True)
            repaired_bytes, was_repaired, _repairs = repair_rendered_docx_content(bytes_docx)
            customer_ready_bytes = repaired_bytes if was_repaired else bytes_docx

            # Re-verify repaired bytes if repairs were applied
            if was_repaired:
                verify_res = inspect_and_verify_docx(customer_ready_bytes, client_inputs, is_final_requested=True)

            fname_base = client_inputs.get("customer_name", "Client").replace(" ", "_")
            fname_review = f"{fname_base}_Cybersecurity_Maturity_Report_Review.docx"
            fname_final = f"{fname_base}_Cybersecurity_Maturity_Report.docx"

            is_customer_ready = verify_res.is_valid and verify_res.status in ("FINAL_READY", "CUSTOMER_REVIEW_DRAFT")

            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    "📄 Download Review Copy (Word)",
                    data=bytes_docx,
                    file_name=fname_review,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    help="Internal/pre-publication review copy containing diagnostic telemetry and trace sentinels.",
                )

            with col2:
                if is_customer_ready:
                    st.download_button(
                        "📄 Download Customer-Ready Deliverable (Word)",
                        data=customer_ready_bytes,
                        file_name=fname_final,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        type="primary",
                        help="Verified, sanitized customer-facing deliverable.",
                    )
                else:
                    st.button(
                        "📄 Customer-Ready Deliverable Gated",
                        disabled=True,
                        help=f"Gated due to verification findings: {', '.join(f.description for f in verify_res.findings)}",
                    )
                    st.warning(f"Publication Gated ({verify_res.status}): Please review document findings prior to customer distribution.")

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