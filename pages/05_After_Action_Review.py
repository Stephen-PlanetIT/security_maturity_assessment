import streamlit as st
from core import LLMEngine
from prompts import build_tabletop_aar_prompt, SYSTEM_PERSONA_TABLETOP, TabletopAAR
from config import get_config, ConfigKey
from consultation_helpers import load_latest_tabletop_session

st.set_page_config(page_title="After-Action Review (AAR)", layout="wide")

# Auth-aware guard: if login is enabled and user not signed-in, route to app.py sign-in
def _is_auth_enabled():
    try:
        return str(get_config("AUTH_ENABLED", "false")).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        return False
if _is_auth_enabled() and not st.session_state.get("_auth_user"):
    st.warning("Sign in required to access the AAR page.")
    st.page_link("app.py", label="🔐 Go to Sign In")
    st.stop()

# Branding header
st.title("Planet IT Advisory Engine")
# Top navigation CSS for uniform anchors
st.markdown(
    """
    <style>
    #topnav a, #topnav a:visited {
        display: inline-block;
        width: 100%;
        box-sizing: border-box;
        padding: 0.4rem 0.8rem;
        border: 1px solid #c8d6df;
        border-radius: 8px;
        text-align: center;
        color: #1e3a4c;
        text-decoration: none;
        background: white;
    }
    #topnav a:hover { background: #f5f9fb; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Top navigation (no sidebar)
with st.container():
    st.markdown("<div id='topnav'></div>", unsafe_allow_html=True)
    colh1, colh2, colh3, colh4 = st.columns([1, 1, 1, 1])
    with colh1:
        st.page_link("app.py", label="🏠 Home")
    with colh2:
        st.page_link("pages/01_Maturity_Relay.py", label="📈 Maturity")
    with colh3:
        st.page_link("pages/03_Tabletop_Designer.py", label="🎯 Tabletop", icon=None)
    with colh4:
        st.page_link("pages/02_Threats_Relay.py", label="🔥 Threats")

st.header("📋 After-Action Review (AAR)")
# Attempt to load a persisted session snapshot if session state is empty
try:
    if not st.session_state.get("tabletop_plan") or not st.session_state.get("tabletop_notes"):
        saved = load_latest_tabletop_session()
        if isinstance(saved, dict):
            st.session_state["tabletop_plan"] = saved.get("plan", {})
            st.session_state["tabletop_notes"] = saved.get("notes", [])
            st.session_state["client_inputs"] = saved.get("client_inputs", {})
            st.session_state["tabletop_audience"] = saved.get("audience", "Blended")
            st.session_state["immediate_injects"] = saved.get("immediate_injects", [])
except Exception:
    pass

# Ensure a generated tabletop plan exists
if not st.session_state.get("tabletop_plan"):
    st.info("No tabletop plan in session. Generate a plan in the Designer page first.")
    st.stop()

# Capture AAR from notes if available
if not st.session_state.get("tabletop_notes"):
    st.info("No exercise notes captured yet. Use the Live Facilitation page to populate findings.")
else:
    if st.button("Generate After-Action Review (AAR)", type="primary"):
        with st.spinner("Evaluating room performance and synthesising AAR..."):
            client = LLMEngine.get_client()
            deployment = get_config(ConfigKey.AZURE_DEPLOYMENT, "gpt-4o")
            aar_prompt = build_tabletop_aar_prompt(
                st.session_state["tabletop_plan"],
                st.session_state["tabletop_notes"],
                st.session_state.get("client_inputs", {}),
                audience=st.session_state.get("tabletop_audience", "Blended"),
                immediate_injects=st.session_state.get("immediate_injects", []),
            )
            aar_obj = LLMEngine.generate_structured_report(
                client,
                deployment,
                SYSTEM_PERSONA_TABLETOP,
                aar_prompt,
                TabletopAAR,
            )
            if aar_obj:
                st.session_state["aar_result"] = aar_obj
                st.success("After-Action Review generated!")

# Display AAR if present
if st.session_state.get("aar_result"):
    aar = st.session_state["aar_result"]
    st.markdown(f"### Evaluated Performance: `{getattr(aar, 'overall_maturity_observed', 'Unknown')}`")
    st.write(getattr(aar, "executive_summary", ""))
    with st.expander("Client Feeders", expanded=False):
        try:
            client = getattr(aar, "customer_name", "") or ""
            ex_title = getattr(aar, "exercise_title", "") or ""
            ex_id = getattr(aar, "exercise_id", "") or ""
            ex_date = getattr(aar, "exercise_date", "") or ""
            stime = getattr(aar, "start_time", "") or ""
            etime = getattr(aar, "end_time", "") or ""
            loc = getattr(aar, "exercise_location", "") or ""
            delivery = getattr(aar, "delivery_mode", "") or ""
            audience = getattr(aar, "audience_profile", "") or ""
            report_status = getattr(aar, "report_status", "") or ""
            report_version = getattr(aar, "report_version", "") or ""
            info_class = getattr(aar, "information_classification", "") or ""
            feeders = [
                f"Client\t{client}",
                f"Exercise\t{ex_title} ({ex_id})",
                f"Date, time and location\t{ex_date} | {stime}–{etime} | {loc}",
                f"Delivery and audience\t{delivery} | {audience}",
            ]
            # Facilitators
            try:
                facs = []
                for p in getattr(aar, "facilitators", []) or []:
                    try:
                        name = getattr(p, "name", None) or (p.get("name") if isinstance(p, dict) else "")
                        role = getattr(p, "role", None) or (p.get("role") if isinstance(p, dict) else "")
                        func = getattr(p, "function", None) or (p.get("function") if isinstance(p, dict) else "")
                        facs.append(f"{name} — {role} ({func})")
                    except Exception:
                        continue
                if facs:
                    feeders.append("Facilitators\t" + "; ".join(facs))
            except Exception:
                pass
            # Functions represented
            try:
                funcs = []
                for p in getattr(aar, "participants", []) or []:
                    try:
                        func = getattr(p, "function", None) or (p.get("function") if isinstance(p, dict) else "")
                        if func:
                            funcs.append(func)
                    except Exception:
                        continue
                if funcs:
                    feeders.append("Functions represented\t" + ", ".join(funcs))
            except Exception:
                pass
            # Scenarios exercised
            try:
                scns = []
                for s in getattr(aar, "scenarios", []) or []:
                    try:
                        sid = getattr(s, "id", None) or (s.get("id") if isinstance(s, dict) else "")
                        title = getattr(s, "title", None) or (s.get("title") if isinstance(s, dict) else "")
                        if sid or title:
                            scns.append(f"{sid} — {title}" if sid and title else (sid or title))
                    except Exception:
                        continue
                if scns:
                    feeders.append("Scenarios exercised\t" + "; ".join(scns))
            except Exception:
                pass
            feeders.append(f"Overall maturity observed\t{getattr(aar, 'overall_maturity_observed', 'Unknown')}")
            if report_status or report_version or info_class:
                feeders.append(f"Report control\t{report_status} | Version {report_version} | {info_class}")
            st.code("\n".join(feeders), language="text")
        except Exception:
            st.info("Client feeder fields are unavailable or incomplete in the AAR object.")

    col_res1, col_res2 = st.columns(2)
    with col_res1:
        st.markdown("#### ✅ Demonstrated Strengths")
        for s in getattr(aar, "key_strengths", []) or []:
            st.markdown(f"- {s}")
    with col_res2:
        st.markdown("#### ⚠️ Identified Critical Gaps")
        for g in getattr(aar, "critical_gaps_identified", []) or []:
            st.markdown(f"- {g}")

    # Export AAR (DOCX)
    try:
        from export import create_tabletop_aar_docx
    except Exception:
        create_tabletop_aar_docx = None
    aar_docx = None
    try:
        import datetime
        if callable(create_tabletop_aar_docx):
            aar_docx = create_tabletop_aar_docx(
                st.session_state.get("tabletop_plan", {}),
                st.session_state.get("tabletop_notes", []),
                aar,
                st.session_state.get("immediate_injects", []),
            )
    except Exception:
        aar_docx = None
    if aar_docx:
        safe_client = ""
        try:
            safe_client = str(st.session_state.get("client_inputs", {}).get("customer_name", "Client")).strip() or "Client"
        except Exception:
            safe_client = "Client"
        fname = f"AAR_{safe_client}_{datetime.date.today().isoformat()}.docx"
        st.download_button(
            "Download After-Action Review (DOCX)",
            data=aar_docx,
            file_name=fname,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    st.divider()
    st.subheader("🔄 Sync Insights into Client Profile")
    st.caption("Update the client's master profile with these findings to inform future maturity assessments and tabletops.")
    if st.button("Apply Delta to Client Profile"):
        import datetime
        today_str = datetime.date.today().isoformat()
        try:
            st.session_state["client_inputs"]["incident_response_assurance_profile"]["tabletop_status"] = "Within the past year"
            existing_notes = st.session_state["client_inputs"]["incident_response_assurance_profile"].get("notes", "")
            delta = getattr(aar, "delta_notes_for_profile", "")
            st.session_state["client_inputs"]["incident_response_assurance_profile"]["notes"] = (
                f"{existing_notes}\n[{today_str} Tabletop AAR]: {delta}".strip()
            )
            st.success(
                f"Profile updated! The incident_response_assurance_profile now reflects the exercise conducted on {today_str}."
            )
        except Exception:
            st.warning(
                "Failed to sync delta into client profile; ensure client_inputs structure is present."
            )