# pages/3_🔥_Threat_Simulator.py
import streamlit as st
import random
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core import LLMEngine
from data import ATTACK_VECTORS, SIMULATED_OSINT
from prompts import SYSTEM_PERSONA, build_scenario_prompt, ScenarioReport
from export import create_pdf, create_pptx

st.set_page_config(page_title="Threat Simulator", page_icon="🔥", layout="wide")
st.title("🔥 Tactical Threat Simulator")

client_inputs = {}
if 'sim_obj' not in st.session_state: st.session_state['sim_obj'] = None

with st.expander("🎯 Simulation Parameters", expanded=not st.session_state['sim_obj']):
    client_inputs["customer_name"] = st.text_input("Customer Name", "Acme Corp")
    client_inputs["critical_infra"] = st.text_input("Crown Jewels", "Patient Records Database")
    client_inputs["endpoint"] = st.selectbox("Endpoint Protection", ["Sophos", "Microsoft Defender", "Other"])
    client_inputs["firewall"] = st.selectbox("Firewall Vendor", ["Fortinet", "Palo Alto", "Sophos", "Other"])
    client_inputs["custom_scenario"] = st.text_input("Custom Threat Scenario Override (Optional)", placeholder="e.g., Ransomware deployment via compromised MSP")

generate_btn = st.button("🚀 Generate Threat Simulation", type="primary", use_container_width=True)

if generate_btn:
    llm_client = LLMEngine.get_client()
    deployment = st.secrets.get("AZURE_OPENAI_DEPLOYMENT", "")
    
    with st.spinner("Generating tactical breach narrative..."):
        selected_vector = random.choice(ATTACK_VECTORS)
        osint_data = f"{SIMULATED_OSINT.get(client_inputs['endpoint'], [''])[0]} {SIMULATED_OSINT.get(client_inputs['firewall'], [''])[0]}"
        
        prompt = build_scenario_prompt(client_inputs, osint_data, selected_vector, client_inputs["custom_scenario"])
        scenario_obj = LLMEngine.generate_structured_report(llm_client, deployment, SYSTEM_PERSONA, prompt, ScenarioReport)
        
        if scenario_obj:
            st.session_state['sim_obj'] = scenario_obj
            # Using dummy recs for legacy export compatibility
            recs = ["• **Planet IT Managed SOC**: Implement 24/7 Threat Hunting."]
            st.session_state['sim_pdf'] = create_pdf(client_inputs, scenario_obj, recs, scenario_obj.mdr_case_log)
            st.session_state['sim_pptx'] = create_pptx(client_inputs, scenario_obj, recs, scenario_obj.mdr_case_log)

if st.session_state['sim_obj']:
    st.success("✅ Threat Simulation Ready.")
    c1, c2 = st.columns(2)
    with c1: st.download_button("📄 Download PDF Report", data=st.session_state['sim_pdf'], file_name="MDR_Simulation.pdf", mime="application/pdf", use_container_width=True)
    with c2: st.download_button("📊 Download PPTX Deck", data=st.session_state['sim_pptx'], file_name="MDR_Simulation.pptx", use_container_width=True)