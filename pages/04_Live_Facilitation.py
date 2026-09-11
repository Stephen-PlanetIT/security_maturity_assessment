import streamlit as st
from core import LLMEngine
from prompts import build_tabletop_pivot_prompt, SYSTEM_PERSONA_TABLETOP, TabletopPivotResponse
from config import get_config, ConfigKey

st.set_page_config(page_title="Live Facilitation Console", layout="wide")

# Auth-aware guard: if login is enabled and user not signed-in, route to app.py sign-in
def _is_auth_enabled():
    try:
        return str(get_config("AUTH_ENABLED", "false")).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        return False
if _is_auth_enabled() and not st.session_state.get("_auth_user"):
    st.warning("Sign in required to access the Live Facilitation console.")
    st.page_link("app.py", label="🔐 Go to Sign In")
    st.stop()

# Keepalive to avoid idle timeouts during workshops
st.markdown(
    "<script>setInterval(()=>{fetch(window.location.href,{cache:'no-store'}).catch(()=>{})},60000);</script>",
    unsafe_allow_html=True,
)

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

st.header("🎙️ Live Facilitation Console")

if not st.session_state.get("tabletop_plan"):
    st.info("Please generate or load a tabletop scenario in the Designer page before facilitating.")
    st.stop()

plan = st.session_state["tabletop_plan"]
scenarios = plan.get("scenarios", [])
if not scenarios:
    st.info("No scenarios present. Generate a plan first in the Designer page.")
    st.stop()

# Ensure facilitator indices exist
if "live_scenario_idx" not in st.session_state:
    st.session_state["live_scenario_idx"] = 0
if "live_inject_idx" not in st.session_state:
    st.session_state["live_inject_idx"] = 0

s_idx = st.session_state["live_scenario_idx"]
i_idx = st.session_state["live_inject_idx"]

current_scenario = scenarios[s_idx]
injects = current_scenario.get("injects", [])
i_idx = min(i_idx, max(0, len(injects) - 1))
st.session_state["live_inject_idx"] = i_idx
current_inject = injects[i_idx] if injects else {}

st.subheader(f"Scenario {s_idx + 1}: {current_scenario.get('scenario_title')}")
col_stat1, col_stat2 = st.columns([3, 1])
with col_stat1:
    total = max(1, len(injects))
    st.progress((i_idx + 1) / total, text=f"Inject {i_idx + 1} of {total}: {current_inject.get('phase_title')}")
with col_stat2:
    st.caption(f"Clock: **{current_inject.get('simulated_timestamp')}**")

narrative = current_inject.get("scenario_narrative")
if narrative:
    st.info(f"### Situation Brief:\n{narrative}")

if current_inject.get("technical_indicators"):
    st.markdown("**Technical Indicators & Telemetry:**")
    for ind in current_inject.get("technical_indicators"):
        st.code(ind, language="bash")

with st.expander("🕵️ Facilitator Guidance & Evaluation Benchmark", expanded=True):
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        st.markdown("**🎯 What Good Looks Like:**")
        st.write(current_inject.get("expected_mature_response"))
    with col_f2:
        st.markdown("**⚠️ Pitfalls to Probe:**")
        for pit in current_inject.get("common_pitfalls", []):
            st.markdown(f"- {pit}")

st.markdown("### 📝 Record Room Consensus & Action")
room_decision = st.text_area(
    "What was the client's decision/response?",
    key=f"rec_dec_{s_idx}_{i_idx}",
    placeholder="e.g., Client decided not to isolate the endpoint; contacted user on personal phone...",
)
facilitator_notes = st.text_input(
    "Facilitator assessment notes (for AAR)",
    key=f"rec_eval_{s_idx}_{i_idx}",
    placeholder="e.g., Hesitated for 25 mins on declaring severity...",
)

with st.expander("🎲 Need a Dynamic Pivot? (Inject Consequence)", expanded=False):
    st.caption("If the room acted poorly or solved the problem too quickly, trigger an immediate adaptive consequence.")
    if st.button("Generate Immediate Consequence"):
        with st.spinner("Calculating environmental consequence..."):
            client = LLMEngine.get_client()
            deployment = get_config(ConfigKey.AZURE_DEPLOYMENT, "gpt-4o")
            p_prompt = build_tabletop_pivot_prompt(current_scenario, current_inject, room_decision, audience=st.session_state.get("tabletop_audience", "Blended"))
            pivot = LLMEngine.generate_structured_report(
                client, deployment, SYSTEM_PERSONA_TABLETOP, p_prompt, TabletopPivotResponse
            )
            if pivot:
                try:
                    st.warning(f"**CONSEQUENCE:** {pivot.consequence_narrative}")
                    st.markdown("**Urgent Probes:**")
                    for q in pivot.urgent_pivot_questions:
                        st.write(f"- {q}")
                except Exception:
                    # Fallback if pivot is dict-like
                    st.warning("**CONSEQUENCE:** See generated pivot above.")

col_b1, col_b2, col_b3 = st.columns([1, 1, 2])
with col_b1:
    if st.button("⬅️ Previous Inject", disabled=(i_idx == 0 and s_idx == 0)):
        if i_idx > 0:
            st.session_state["live_inject_idx"] -= 1
        elif s_idx > 0:
            st.session_state["live_scenario_idx"] -= 1
            st.session_state["live_inject_idx"] = len(scenarios[s_idx - 1]["injects"]) - 1
        st.rerun()
with col_b2:
    if st.button("Save & Next ➡️", type="primary"):
        st.session_state.setdefault("tabletop_notes", [])
        st.session_state["tabletop_notes"].append(
            {
                "scenario": current_scenario.get("scenario_title"),
                "phase": current_inject.get("phase_title"),
                "decision": room_decision,
                "notes": facilitator_notes,
            }
        )
        if i_idx < len(injects) - 1:
            st.session_state["live_inject_idx"] += 1
        elif s_idx < len(scenarios) - 1:
            st.session_state["live_scenario_idx"] += 1
            st.session_state["live_inject_idx"] = 0
        else:
            st.success("Exercise completed! Proceed to AAR page.")
            st.page_link("pages/05_After_Action_Review.py", label="Proceed to AAR ➡️", icon="📋")
        st.rerun()
