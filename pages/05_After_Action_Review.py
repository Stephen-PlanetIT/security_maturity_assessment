import streamlit as st
from core import LLMEngine
from prompts import build_tabletop_aar_prompt, SYSTEM_PERSONA_TABLETOP, TabletopAAR
from config import get_config, ConfigKey

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

    col_res1, col_res2 = st.columns(2)
    with col_res1:
        st.markdown("#### ✅ Demonstrated Strengths")
        for s in getattr(aar, "key_strengths", []) or []:
            st.markdown(f"- {s}")
    with col_res2:
        st.markdown("#### ⚠️ Identified Critical Gaps")
        for g in getattr(aar, "critical_gaps_identified", []) or []:
            st.markdown(f"- {g}")

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