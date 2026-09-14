import streamlit as st
from core import LLMEngine
from prompts import build_tabletop_pivot_prompt, SYSTEM_PERSONA_TABLETOP, TabletopPivotResponse
from config import get_config, ConfigKey
from consultation_helpers import persist_tabletop_session

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

# --- Client Feeders (Inputs) ---
with st.expander("Client Feeders (Inputs)", expanded=False):
    # Initialise client_inputs dict
    st.session_state.setdefault("client_inputs", {})
    ci = st.session_state["client_inputs"]

    # Basic identifiers
    col_a, col_b = st.columns(2)
    with col_a:
        ci["customer_name"] = st.text_input("Client name", value=str(ci.get("customer_name", "")))
        ci["exercise_title"] = st.text_input("Exercise title", value=str(ci.get("exercise_title", "")))
        ci["exercise_id"] = st.text_input("Exercise ID", value=str(ci.get("exercise_id", "")))
    with col_b:
        ci["exercise_date"] = st.text_input("Exercise date (YYYY-MM-DD)", value=str(ci.get("exercise_date", "")))
        ci["start_time"] = st.text_input("Start time (HH:MM)", value=str(ci.get("start_time", "")))
        ci["end_time"] = st.text_input("End time (HH:MM)", value=str(ci.get("end_time", "")))

    # Logistics
    col_c, col_d = st.columns(2)
    with col_c:
        ci["exercise_location"] = st.text_input("Location", value=str(ci.get("exercise_location", "")))
        dm_options = ["In person", "Remote", "Hybrid"]
        dm_value = ci.get("delivery_mode", "Hybrid")
        try:
            dm_index = dm_options.index(dm_value) if dm_value in dm_options else 2
        except Exception:
            dm_index = 2
        ci["delivery_mode"] = st.selectbox("Delivery mode", options=dm_options, index=dm_index)
    with col_d:
        ap_options = ["Board", "Technical", "Blended"]
        ap_value = ci.get("audience_profile", "Blended")
        try:
            ap_index = ap_options.index(ap_value) if ap_value in ap_options else 2
        except Exception:
            ap_index = 2
        ci["audience_profile"] = st.selectbox("Audience profile", options=ap_options, index=ap_index)

    st.caption("Enter participants/facilitators one per line as 'Name | Role | Function | Organisation (optional)'.")
    fac_text = st.text_area(
        "Facilitators (Name | Role | Function | Organisation)",
        value="\n".join(ci.get("facilitators_raw", "").splitlines()) if ci.get("facilitators_raw") else "",
        placeholder="Jane Smith | IR Lead | Security Operations | Planet IT\nJohn Roe | Facilitator | Governance | Planet IT"
    )
    par_text = st.text_area(
        "Participants (Name | Role | Function | Organisation)",
        value="\n".join(ci.get("participants_raw", "").splitlines()) if ci.get("participants_raw") else "",
        placeholder="John Doe | IT Manager | IT Operations | Example Co\nEmily Johnson | Finance Director | Finance | Example Co"
    )

    def _parse_people(raw: str):
        out = []
        for line in (raw or "").splitlines():
            parts = [p.strip() for p in line.split("|")]
            if not parts or len([p for p in parts if p]) == 0:
                continue
            name = parts[0] if len(parts) >= 1 else ""
            role = parts[1] if len(parts) >= 2 else ""
            function = parts[2] if len(parts) >= 3 else ""
            org = parts[3] if len(parts) >= 4 else ""
            out.append({"name": name, "role": role, "function": function, "organisation": org})
        return out

    # Store raw then parsed versions
    ci["facilitators_raw"] = fac_text
    ci["participants_raw"] = par_text

    facilitators_list = []
    participants_list = []
    for p in _parse_people(fac_text):
        p["participation_type"] = "Facilitator"
        facilitators_list.append(p)
    for p in _parse_people(par_text):
        p["participation_type"] = "Participant"
        participants_list.append(p)

    # Save lists into session for optional downstream use
    st.session_state["client_facilitators"] = facilitators_list
    st.session_state["client_participants"] = participants_list

    # Optional: show a quick preview block
    if st.checkbox("Show feeder preview", value=False):
        preview = []
        preview.append(f"Client\t{ci.get('customer_name','')}")
        preview.append(f"Exercise\t{ci.get('exercise_title','')} ({ci.get('exercise_id','')})")
        preview.append(f"Date, time and location\t{ci.get('exercise_date','')} | {ci.get('start_time','')}–{ci.get('end_time','')} | {ci.get('exercise_location','')}")
        preview.append(f"Delivery and audience\t{ci.get('delivery_mode','')} | {ci.get('audience_profile','')}")
        if facilitators_list:
                preview.append("Facilitators\t" + "; ".join([f"{p.get('name','')} — {p.get('role','')} ({p.get('function','')})" for p in facilitators_list]))
        if participants_list:
            funcs = [p.get('function','') for p in participants_list if p.get('function')]
            if funcs:
                preview.append("Functions represented\t" + ", ".join(funcs))
        st.code("\n".join(preview), language="text")

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
                    # Persist immediate inject for AAR/export
                    try:
                        st.session_state.setdefault("immediate_injects", [])
                        st.session_state["immediate_injects"].append({
                            "scenario_index": s_idx,
                            "inject_index": i_idx,
                            "scenario_title": current_scenario.get("scenario_title"),
                            "phase_title": current_inject.get("phase_title"),
                            "consequence_narrative": pivot.consequence_narrative,
                            "new_technical_indicators": getattr(pivot, "new_technical_indicators", []),
                            "urgent_pivot_questions": getattr(pivot, "urgent_pivot_questions", []),
                            "facilitator_guidance": getattr(pivot, "facilitator_guidance", "")
                        })
                    except Exception:
                        pass
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
            # Persist complete session (if configured) and redirect to AAR
            try:
                saved_path = persist_tabletop_session(
                    st.session_state.get("tabletop_plan", {}),
                    st.session_state.get("tabletop_notes", []),
                    st.session_state.get("client_inputs", {}),
                    st.session_state.get("tabletop_audience", "Blended"),
                    st.session_state.get("immediate_injects", []),
                )
            except Exception:
                saved_path = None
            st.session_state["tabletop_saved_file"] = saved_path
            try:
                st.success("Exercise completed! Redirecting to AAR...")
                st.switch_page("pages/05_After_Action_Review.py")
            except Exception:
                # Fallback: provide a link if switch_page is unavailable
                st.success("Exercise completed! Proceed to AAR page.")
                st.page_link("pages/05_After_Action_Review.py", label="Proceed to AAR ➡️", icon="📋")
        st.rerun()
