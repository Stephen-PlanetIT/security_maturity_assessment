# app.py
import streamlit as st
import random
from openai import AzureOpenAI
from data import ATTACK_VECTORS, SIMULATED_OSINT
from prompts import SYSTEM_PERSONA, build_scenario_prompt, build_mdr_case_prompt, build_vciso_prompt, ScenarioReport, MaturityReport 
from export import create_pdf, create_pptx, create_vciso_pdf, create_vciso_pptx

# --- INITIALISATION BLOCK ---
keys_to_init = ['vciso_obj', 'vciso_pdf', 'vciso_pptx', 'scenario_obj', 'mdr_case', 'pdf_bytes', 'pptx_bytes', 'recs']
for key in keys_to_init:
    if key not in st.session_state:
        st.session_state[key] = None

class CyberScenarioGenerator:
    def __init__(self, api_key, endpoint, deployment, api_version):
        self.deployment = deployment
        self.client = AzureOpenAI(api_key=api_key, api_version=api_version, azure_endpoint=endpoint) if api_key else None
    
    def fetch_osint(self, vendor):
        options = SIMULATED_OSINT.get(vendor, [])
        return random.choice(options) if options else ""

    def generate_recommendations(self, inputs):
        recs = []
        recs.append("🛡️ **SECURITY ASSESSMENTS & ADVISORY**")
        
        if inputs['last_tabletop'] in ["Never", "Over 12 months ago"]:
             recs.append("• [Secureworks Tabletop Exercises](https://www.secureworks.com/services/incident-response-readiness): Ensure leadership is aligned on communication, legal, and operational procedures during a crisis.")
        
        if inputs['ir_retainer'] == "None / Ad-Hoc":
             recs.append("• [Sophos Incident Response Retainer](https://www.sophos.com/en-us/services/incident-response-retainer): Establish a formal retainer to guarantee 45-minute response SLAs during an active breach.")
             
        if inputs['insurance_status'] == "Policy Exists (Untested)":
             recs.append("• **Insurance Readiness Assessment:** Engage our advisory team to map your current controls against your policy to prevent payout denials.")

        if inputs['in_house_team'] == "Yes (24/7)" and ("Tier 3" in inputs['savviness'] or "Tier 4" in inputs['savviness']):
             recs.append("• [Secureworks Adversary Exercises (Red Teaming)](https://www.secureworks.com/services/offensive-security): Emulate a sophisticated adversary to stress-test your mature 24/7 SOC.")
             recs.append("• [Secureworks Threat Hunting Assessment](https://www.secureworks.com/services/threat-hunting): Proactively search your environment for undetected threats.")
        elif inputs['in_house_team'] != "No":
             recs.append("• [Sophos Internal Penetration Testing](https://www.sophos.com/en-us/services/penetration-testing): Simulate an attacker who has bypassed the perimeter.")

        recs.append("\n⚙️ **RECOMMENDED SOPHOS SOLUTIONS**")
        
        if inputs.get('mdr_provider', 'None') != "Sophos MDR":
            recs.append("• [Sophos MDR](https://www.sophos.com/en-us/products/mdr): Replace your fragmented approach with a fully managed, 24/7 threat hunting service.")
        if inputs['m365_license'] != "None / On-Prem Only":
            recs.append(f"• [Sophos MDR for Microsoft 365](https://www.sophos.com/en-us/products/mdr): Maximise your {inputs['m365_license']} investment.")
        recs.append("• [Sophos Managed Risk](https://www.sophos.com/en-us/products/managed-risk): Implement continuous external attack surface management.")
        if inputs['identity'] not in ["None / Local Only", "On-Prem Active Directory"]:
            recs.append(f"• [Sophos ITDR](https://www.sophos.com/en-us/products/mdr): Integrate telemetry directly from {inputs['identity']}.")
        if inputs['firewall'] != "Sophos" or inputs['servers'] > 20:
            recs.append("• [Sophos NDR](https://www.sophos.com/en-us/products/network-detection-and-response): Analyse network traffic for rogue devices.")
        if inputs['endpoint'] != "Sophos":
             recs.append(f"• [Sophos Intercept X Advanced with XDR](https://www.sophos.com/en-us/products/endpoint-antivirus): Consolidate your endpoint stack.")

        return recs

    def call_llm_structured(self, prompt, response_model):
        if not self.client: return None
        try:
            response = self.client.beta.chat.completions.parse(
                model=self.deployment, messages=[{"role": "system", "content": SYSTEM_PERSONA}, {"role": "user", "content": prompt}],
                response_format=response_model, temperature=0.7
            )
            return response.choices[0].message.parsed
        except Exception as e:
            st.error(f"LLM Error: {e}")
            return None

    def call_llm_text(self, prompt):
        if not self.client: return None
        response = self.client.chat.completions.create(
            model=self.deployment, messages=[{"role": "system", "content": SYSTEM_PERSONA}, {"role": "user", "content": prompt}], temperature=0.7
        )
        return response.choices[0].message.content

st.set_page_config(page_title="Security Advisory Platform", page_icon="🛡️", layout="wide")

try:
    az_key = st.secrets["AZURE_OPENAI_API_KEY"]
    az_endpoint = st.secrets["AZURE_OPENAI_ENDPOINT"]
    az_deployment = st.secrets["AZURE_OPENAI_DEPLOYMENT"]
    az_api_version = st.secrets.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
except Exception:
    st.error("⚠️ Missing API Credentials! Check `.streamlit/secrets.toml`.")
    az_key, az_endpoint, az_deployment, az_api_version = None, None, None, None

app_engine = CyberScenarioGenerator(api_key=az_key, endpoint=az_endpoint, deployment=az_deployment, api_version=az_api_version)

with st.sidebar:
    st.title("🛡️ Advisory Engine")
    app_mode = st.radio("Select Workflow:", ["📈 vCISO Assessment", "🔥 Threat Simulator"])
    st.divider()

    st.header("📋 Engagement Details")
    customer_name = st.text_input("Customer Name", "Acme Corp")
    consultant_name = st.text_input("Consultant Name", "Jane Doe")
    
    st.header("🏢 Client Estate Details")
    industry = st.selectbox("Industry Vertical", ["Healthcare", "Finance", "Manufacturing", "Retail", "Technology", "Education"])
    critical_infra = st.text_input("Crown Jewels", "Patient Records Database")
    
    st.subheader("👥 The Human Element")
    users = st.number_input("Number of Users", min_value=1, value=500)
    in_house_team = st.radio("In-House Security Team?", ["No", "Yes (9-to-5)", "Yes (24/7)"])
    
    with st.expander("🧮 Security Culture Calculator", expanded=True):
        q1 = st.radio("MFA Enforcement", ["None / Optional", "Admins Only", "Mandatory for All Users"])
        q2 = st.radio("Phishing Simulations", ["Never", "Annually", "Monthly / Quarterly"])
        q3 = st.radio("Security Training", ["None", "Annual Compliance Video", "Continuous with active coaching"])
        q4 = st.radio("Endpoint Privileges", ["Most users are Local Admins", "Only IT/Devs are Local Admins", "Zero Trust (No Local Admins/LAPS)"])

    culture_score = 0
    culture_score += {"None / Optional": 0, "Admins Only": 1, "Mandatory for All Users": 3}[q1]
    culture_score += {"Never": 0, "Annually": 1, "Monthly / Quarterly": 2}[q2]
    culture_score += {"None": 0, "Annual Compliance Video": 1, "Continuous with active coaching": 2}[q3]
    culture_score += {"Most users are Local Admins": 0, "Only IT/Devs are Local Admins": 1, "Zero Trust (No Local Admins/LAPS)": 2}[q4]

    if culture_score <= 3: savviness_label = "Tier 1: High Risk / Unaware"
    elif culture_score <= 6: savviness_label = "Tier 2: Basic Compliance"
    elif culture_score <= 8: savviness_label = "Tier 3: Cautious / Conscious"
    else: savviness_label = "Tier 4: Highly Technical / Optimised"

    st.info(f"Calculated Score: {culture_score}/9\n\nResult: {savviness_label}")
    savviness = f"{savviness_label}"

    with st.expander("⚖️ GRC & Resilience Discovery", expanded=True):
        backup_strategy = st.selectbox("Backup Strategy", ["On-prem Only", "Cloud (Non-Immutable)", "Immutable Cloud Backup", "None"])
        last_tabletop = st.selectbox("Last IR Test", ["Never", "Over 12 months ago", "Within last 12 months"])
        asset_visibility = st.radio("Asset Inventory Method", ["Manual (Excel/None)", "Point-in-time Scan", "Continuous/Automated"])
        data_class = st.checkbox("Formal Data Classification Policy in place?")
        cloud_posture = st.selectbox("Cloud Security Posture", ["None / Ad-hoc", "Basic Native Tools", "Dedicated CSPM/CWPP"])
        tprm_status = st.radio("Third-Party Vendor Risk", ["No formal vetting", "Annual Questionnaires", "Continuous ZTNA"])
        
        st.markdown("**Incident Preparedness**")
        ir_retainer = st.radio("IR Retainer Status", ["None / Ad-Hoc", "Basic Retainer (No SLA)", "Formal Retainer with SLA"])
        oob_comms = st.checkbox("Secure Out-of-Band Comms (e.g., Signal/Wickr) established?")
        insurance = st.selectbox("Cyber Insurance", ["None", "Policy Exists (Untested)", "Policy mapped to active IR Plan"])
    
    st.subheader("💻 Technology Stack")
    endpoints = st.number_input("Number of Endpoints", min_value=1, value=600)
    servers = st.number_input("Number of Servers", min_value=1, value=50)
    mdr_provider = st.selectbox("Current MDR / SOC", ["None", "Sophos MDR", "CrowdStrike Falcon Complete", "Arctic Wolf", "Expel", "Other"])
    endpoint = st.selectbox("Endpoint Security", ["Sophos", "Microsoft Defender", "CrowdStrike", "SentinelOne", "Other"])
    firewall = st.selectbox("Firewall Vendor", ["Fortinet", "Palo Alto", "Cisco", "Sophos", "Check Point", "Other"])
    identity = st.selectbox("Identity Provider", ["Microsoft Entra ID (Azure AD)", "Okta", "On-Prem Active Directory", "None"])
    m365_license = st.selectbox("Microsoft 365 Licensing", ["None / On-Prem Only", "M365 Business Premium", "Microsoft 365 E5", "Office 365 E3 / M365 E3"])
    email = st.selectbox("Email Security", ["Sophos", "Mimecast", "Proofpoint", "Microsoft Defender", "Other"])
    cloud_env = st.selectbox("Cloud Infrastructure", ["AWS", "Microsoft Azure", "GCP", "Multi-Cloud", "None (Fully On-Prem)"])
    physical_locations = st.number_input("Physical Locations", min_value=1, value=3)
    public_web_apps = st.checkbox("Host Public Web Apps?")

client_inputs = {
    "customer_name": customer_name, "consultant_name": consultant_name, "industry": industry, 
    "users": users, "savviness": savviness, "endpoints": endpoints, "servers": servers, 
    "critical_infra": critical_infra, "mdr_provider": mdr_provider, "endpoint": endpoint, "firewall": firewall, 
    "identity": identity, "m365_license": m365_license, "email": email, "cloud_env": cloud_env,
    "in_house_team": in_house_team, "physical_locations": physical_locations, "public_web_apps": public_web_apps,
    "mfa_status": q1, "phishing_frequency": q2, "training_maturity": q3, "admin_rights": q4,
    "backup_strategy": backup_strategy, "last_tabletop": last_tabletop, "asset_visibility": asset_visibility, 
    "data_classification": "Yes" if data_class else "No", "cloud_posture": cloud_posture, "tprm_status": tprm_status,
    "ir_retainer": ir_retainer, "oob_comms": "Yes" if oob_comms else "No", "insurance_status": insurance
}

if app_mode == "📈 vCISO Assessment":
    st.title("📈 vCISO Strategic Assessment")
    
    if st.button("Generate vCISO Roadmap", type="primary"):
        st.session_state['client_inputs'] = client_inputs
        with st.spinner("Analysing estate and building maturity roadmap..."):
            vciso_obj = app_engine.call_llm_structured(build_vciso_prompt(client_inputs), MaturityReport)
            
            if vciso_obj:
                st.session_state['vciso_obj'] = vciso_obj
                st.session_state['vciso_pdf'] = create_vciso_pdf(client_inputs, vciso_obj)
                st.session_state['vciso_pptx'] = create_vciso_pptx(client_inputs, vciso_obj)
                st.rerun()

    if st.session_state['vciso_obj']:
        vciso_report = st.session_state['vciso_obj']
        
        tab_exec, tab_gaps, tab_roadmap = st.tabs(["👔 Exec & Risk", "🔍 Gap Analysis", "🗺️ Roadmap"])
        
        with tab_exec:
            st.subheader("Executive Risk Summary")
            st.write(vciso_report.executive_summary)
            st.subheader("The Cost of Inaction")
            st.error(vciso_report.cost_of_inaction)
            
        with tab_gaps:
            for domain in vciso_report.domain_assessments:
                with st.expander(f"{domain.domain_name} — Score: {domain.numeric_maturity_score}/5.0", expanded=True):
                    st.markdown(f"**Budget Estimate:** {domain.budgetary_estimate}")
                    st.markdown(f"**Current State:** {domain.current_state_analysis}")
                    st.markdown("**Critical Gaps:**")
                    for gap in domain.critical_gaps: st.markdown(f"- {gap}")
                    st.markdown("**Personalised Quick Wins:**")
                    for win in domain.vendor_agnostic_quick_wins: st.markdown(f"- 🟢 {win}")
                    st.markdown("**Recommended Solutions:**")
                    for sol in domain.recommended_solutions: st.markdown(f"- 🛡️ {sol}")
                        
        with tab_roadmap:
            st.subheader("Success Metrics (KPIs)")
            for kpi in vciso_report.success_metrics: st.markdown(f"- 🎯 {kpi}")
            st.subheader("Phased Roadmap")
            for phase in vciso_report.phased_roadmap:
                st.markdown(f"#### {phase.phase_name}")
                for ms in phase.milestones: st.markdown(f"✅ {ms}")
                    
        st.divider()
        if st.session_state['vciso_pdf'] is not None:
            st.subheader("📥 Export Deliverables")
            dl_col1, dl_col2 = st.columns(2)
            with dl_col1: st.download_button("📄 Download PDF Assessment", data=st.session_state['vciso_pdf'], file_name=f"{customer_name.replace(' ', '_')}_vCISO.pdf", mime="application/pdf")
            with dl_col2: st.download_button("📊 Download PowerPoint Deck", data=st.session_state['vciso_pptx'], file_name=f"{customer_name.replace(' ', '_')}_vCISO.pptx")

elif app_mode == "🔥 Threat Simulator":
    st.title("🔥 Threat Simulation Engine")
    custom_scenario = st.text_input("Custom Scenario Override (Optional)")
    
    if st.button("Generate Threat Scenario", type="primary"):
        selected_vector = random.choice(ATTACK_VECTORS)
        osint_list = [app_engine.fetch_osint(endpoint), app_engine.fetch_osint(firewall), app_engine.fetch_osint(identity), app_engine.fetch_osint(email), app_engine.fetch_osint(cloud_env)]
        osint_data = " ".join([x for x in osint_list if x])
        
        st.session_state['client_inputs'] = client_inputs
        
        with st.spinner("Generating tactical breach narrative..."):
            scenario_obj = app_engine.call_llm_structured(build_scenario_prompt(client_inputs, osint_data, selected_vector, custom_scenario), ScenarioReport)
            
            if scenario_obj:
                mdr_case = app_engine.call_llm_text(build_mdr_case_prompt(client_inputs, scenario_obj.narrative))
                st.session_state['scenario_obj'] = scenario_obj
                st.session_state['mdr_case'] = mdr_case
                st.session_state['recs'] = app_engine.generate_recommendations(client_inputs)
                st.session_state['pdf_bytes'] = create_pdf(client_inputs, scenario_obj, st.session_state['recs'], mdr_case)
                st.session_state['pptx_bytes'] = create_pptx(client_inputs, scenario_obj, st.session_state['recs'], mdr_case)
                st.rerun()

    if st.session_state['scenario_obj']:
        scenario_obj = st.session_state['scenario_obj']
        tab1, tab2, tab3 = st.tabs(["📝 Threat Narrative", "🛡️ MDR Log", "🎯 Recommendations"])
        
        with tab1:
            st.write(scenario_obj.narrative)
            for t_event in scenario_obj.timeline: st.markdown(f"**{t_event.timestamp}** | {t_event.event_description}")
        with tab2:
            st.write(st.session_state['mdr_case'])
        with tab3:
            for rec in st.session_state['recs']:
                if rec.startswith("🛡️") or rec.startswith("⚙️"): st.markdown(f"#### {rec}")
                else: st.markdown(rec)
                    
        st.divider()
        if st.session_state['pdf_bytes'] is not None:
            st.subheader("📥 Export Deliverables")
            dl_col1, dl_col2 = st.columns(2)
            with dl_col1: st.download_button("📄 Download PDF Report", data=st.session_state['pdf_bytes'], file_name=f"{customer_name.replace(' ', '_')}_MDR.pdf", mime="application/pdf")
            with dl_col2: st.download_button("📊 Download PowerPoint Deck", data=st.session_state['pptx_bytes'], file_name=f"{customer_name.replace(' ', '_')}_MDR.pptx")