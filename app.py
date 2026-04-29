# app.py
import streamlit as st
import random
from openai import AzureOpenAI

# Import data configurations
from data import ATTACK_VECTORS, SIMULATED_OSINT

# Import prompts and Pydantic schemas
from prompts import (
    SYSTEM_PERSONA, 
    build_scenario_prompt, 
    build_mdr_case_prompt, 
    build_vciso_prompt,
    ScenarioReport, 
    MaturityReport 
)

# Import all export generators
from export import create_pdf, create_pptx, create_vciso_pdf, create_vciso_pptx

# --- INITIALISATION BLOCK ---
st.set_page_config(page_title="Strategic Advisory Platform", page_icon="🛡️", layout="wide")

keys_to_init = ['vciso_obj', 'vciso_pdf', 'vciso_pptx', 'scenario_obj', 'mdr_case', 'pdf_bytes', 'pptx_bytes', 'recs', 'report_ready', 'selected_mode']
for key in keys_to_init:
    if key not in st.session_state:
        st.session_state[key] = None
if 'report_ready' not in st.session_state:
    st.session_state['report_ready'] = False

def return_to_dashboard():
    st.session_state['selected_mode'] = None
    st.session_state['report_ready'] = False
    st.session_state['vciso_obj'] = None
    st.session_state['scenario_obj'] = None

# --- BACKEND LOGIC ---
class CyberScenarioGenerator:
    def __init__(self, api_key, endpoint, deployment, api_version):
        self.deployment = deployment
        self.client = AzureOpenAI(api_key=api_key, api_version=api_version, azure_endpoint=endpoint) if api_key else None
    
    def fetch_osint(self, vendor):
        options = SIMULATED_OSINT.get(vendor, [])
        return random.choice(options) if options else ""

    def generate_recommendations(self, inputs):
        recs = ["🛡️ **SECURITY ASSESSMENTS & ADVISORY**"]
        
        if inputs.get('ir_plan_review') in ["No formal plan", "Over 12 months ago"] or inputs.get('last_tabletop') in ["Never", "Over 12 months ago"]:
             recs.append("• [Secureworks Incident Response Preparedness](https://www.secureworks.com/services/incident-response-readiness): Update your IR plan and conduct tabletop exercises to align with compliance requirements.")
        
        if inputs.get('ir_retainer') == "None / Ad-Hoc":
             recs.append("• [Sophos Incident Response Retainer](https://www.sophos.com/en-us/services/incident-response-retainer): Establish a formal retainer to guarantee response SLAs.")
             
        if inputs.get('insurance_status') == "Policy Exists (Untested)":
             recs.append("• **Insurance Readiness Assessment:** Map your current controls against your policy to prevent payout denials.")

        if inputs.get('target_compliance') and "None specified" not in inputs['target_compliance']:
             recs.append(f"• **Compliance Gap Assessment:** Engage our advisory team for a formal audit against your target frameworks: {inputs['target_compliance']}.")

        recs.append("\n⚙️ **RECOMMENDED SOPHOS SOLUTIONS**")
        if inputs.get('mdr_provider', 'None') != "Sophos MDR":
            recs.append("• [Sophos MDR](https://www.sophos.com/en-us/products/mdr): Replace your fragmented approach with a fully managed, 24/7 threat hunting service.")
        if inputs.get('m365_license', 'None') != "None / On-Prem Only":
            recs.append(f"• [Sophos MDR for Microsoft 365](https://www.sophos.com/en-us/products/mdr): Maximise your {inputs.get('m365_license')} investment.")
        recs.append("• [Sophos Managed Risk](https://www.sophos.com/en-us/products/managed-risk): Implement continuous external attack surface management.")
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

# --- API SETUP ---
try:
    az_key = st.secrets["AZURE_OPENAI_API_KEY"]
    az_endpoint = st.secrets["AZURE_OPENAI_ENDPOINT"]
    az_deployment = st.secrets["AZURE_OPENAI_DEPLOYMENT"]
    az_api_version = st.secrets.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
except Exception:
    st.error("⚠️ Missing API Credentials! Check `.streamlit/secrets.toml`.")
    az_key, az_endpoint, az_deployment, az_api_version = None, None, None, None

app_engine = CyberScenarioGenerator(api_key=az_key, endpoint=az_endpoint, deployment=az_deployment, api_version=az_api_version)

# ==========================================
# MODERN FRONTEND ARCHITECTURE
# ==========================================

# Minimalist Sidebar strictly for global navigation
with st.sidebar:
    st.title("🛡️ Platform Menu")
    if st.session_state['selected_mode'] is not None:
        st.button("🏠 Return to Dashboard", on_click=return_to_dashboard, use_container_width=True)
    st.divider()
    st.caption("Powered by Azure OpenAI & Sophos Threat Intelligence")

# ---------------------------------------------------------
# VIEW 1: TOP-LEVEL DASHBOARD
# ---------------------------------------------------------
if st.session_state['selected_mode'] is None:
    st.markdown("<br>", unsafe_allow_html=True)
    st.title("Strategic Advisory Platform")
    st.markdown("Select an advisory engine below to begin building your engagement deliverables.")
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        with st.container(border=True):
            st.markdown("### 📈 vCISO Strategic Assessment")
            st.markdown("Generate a comprehensive maturity assessment, gap analysis, and 3-phase strategic roadmap aligned to frameworks like NIS2, DORA, and ISO27001.")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Launch vCISO Assessment ➔", type="primary", use_container_width=True):
                st.session_state['selected_mode'] = "📈 vCISO Assessment"
                st.rerun()
                
    with col2:
        with st.container(border=True):
            st.markdown("### 🔥 Tactical Threat Simulator")
            st.markdown("Generate a rapid, highly technical breach narrative and mock MDR case log based specifically on the client's current technology stack vulnerabilities.")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Launch Threat Simulator ➔", type="primary", use_container_width=True):
                st.session_state['selected_mode'] = "🔥 Threat Simulator"
                st.rerun()

# ---------------------------------------------------------
# VIEW 2: DRILL-DOWN CONFIGURATION & REPORTS
# ---------------------------------------------------------
else:
    app_mode = st.session_state['selected_mode']
    st.title(app_mode)
    
    # Initialize default inputs to prevent KeyErrors across different modes
    client_inputs = {
        "mfa_status": "None", "phishing_frequency": "None", "training_maturity": "None", "admin_rights": "None",
        "backup_strategy": "None", "last_tabletop": "None", "asset_visibility": "None", "data_classification": "No",
        "tprm_status": "None", "ir_retainer": "None", "insurance_status": "None", "current_cert": "None",
        "ir_plan_review": "None", "target_compliance": "None specified", "custom_scenario": "", "savviness": "Tier 2: Basic Compliance"
    }

    # The expander auto-collapses if a report has been successfully generated.
    with st.expander("⚙️ Client Discovery & Estate Configuration", expanded=not st.session_state['report_ready']):
        
        # COMMON TIER 1: Engagement & Tech Stack
        col1, col2 = st.columns(2)
        
        with col1:
            with st.container(border=True):
                st.subheader("🏢 Engagement Profile")
                c1, c2 = st.columns(2)
                with c1:
                    client_inputs["customer_name"] = st.text_input("Customer Name", "Acme Corp")
                    client_inputs["industry"] = st.selectbox("Industry Vertical", ["Healthcare", "Finance", "Manufacturing", "Retail", "Technology", "Education"])
                    client_inputs["users"] = st.number_input("Number of Users", min_value=1, value=500)
                with c2:
                    client_inputs["consultant_name"] = st.text_input("Consultant Name", "Jane Doe")
                    client_inputs["critical_infra"] = st.text_input("Crown Jewels", "Patient Records Database")
                    client_inputs["in_house_team"] = st.selectbox("In-House SecOps Team?", ["No", "Yes (9-to-5)", "Yes (24/7)"])
        
        with col2:
            with st.container(border=True):
                st.subheader("💻 Technology Stack")
                c3, c4 = st.columns(2)
                with c3:
                    client_inputs["endpoints"] = st.number_input("Endpoints", min_value=1, value=600)
                    client_inputs["mdr_provider"] = st.selectbox("Current MDR", ["None", "Sophos MDR", "CrowdStrike", "Arctic Wolf", "Other"])
                    client_inputs["endpoint"] = st.selectbox("Endpoint Protection", ["Sophos", "Microsoft Defender", "CrowdStrike", "SentinelOne", "Other"])
                    client_inputs["firewall"] = st.selectbox("Firewall Vendor", ["Fortinet", "Palo Alto", "Cisco", "Sophos", "Other"])
                with c4:
                    client_inputs["servers"] = st.number_input("Servers", min_value=1, value=50)
                    client_inputs["identity"] = st.selectbox("Identity Provider", ["Microsoft Entra ID (Azure AD)", "Okta", "On-Prem AD", "None"])
                    client_inputs["m365_license"] = st.selectbox("M365 Licensing", ["None", "M365 Business Premium", "Microsoft 365 E5", "Office 365 E3"])
                    client_inputs["cloud_env"] = st.selectbox("Cloud Infrastructure", ["AWS", "Microsoft Azure", "GCP", "None (On-Prem)"])
                    client_inputs["email"] = st.selectbox("Email Gateway", ["Sophos", "Mimecast", "Proofpoint", "Microsoft Defender", "Other"])

        # SPECIFIC TIER 2: Only show deep GRC questions for vCISO
        if app_mode == "📈 vCISO Assessment":
            col3, col4 = st.columns(2)
            
            with col3:
                with st.container(border=True):
                    st.subheader("🧮 Security Culture & Hygiene")
                    q1 = st.selectbox("MFA Enforcement", ["None / Optional", "Admins Only", "Mandatory for All Users"])
                    q2 = st.selectbox("Phishing Simulations", ["Never", "Annually", "Monthly / Quarterly"])
                    q3 = st.selectbox("Security Training", ["None", "Annual Compliance Video", "Continuous with active coaching"])
                    q4 = st.selectbox("Endpoint Privileges", ["Most users are Local Admins", "Only IT/Devs are Local Admins", "Zero Trust (No Local Admins/LAPS)"])
                    
                    culture_score = {"None / Optional": 0, "Admins Only": 1, "Mandatory for All Users": 3}[q1] + {"Never": 0, "Annually": 1, "Monthly / Quarterly": 2}[q2] + {"None": 0, "Annual Compliance Video": 1, "Continuous with active coaching": 2}[q3] + {"Most users are Local Admins": 0, "Only IT/Devs are Local Admins": 1, "Zero Trust (No Local Admins/LAPS)": 2}[q4]
                    savviness_label = "Tier 1: High Risk" if culture_score <= 3 else "Tier 2: Basic Compliance" if culture_score <= 6 else "Tier 3: Conscious" if culture_score <= 8 else "Tier 4: Highly Technical"
                    st.caption(f"**Calculated Behavioural Savviness:** {savviness_label}")
                    
                    client_inputs.update({"mfa_status": q1, "phishing_frequency": q2, "training_maturity": q3, "admin_rights": q4, "savviness": savviness_label})

            with col4:
                with st.container(border=True):
                    st.subheader("⚖️ GRC, Compliance & Resilience")
                    grc_1, grc_2 = st.columns(2)
                    with grc_1:
                        target_compliance = st.multiselect("Target Frameworks", ["ISO27001", "NIS2 Directive", "PCI:DSS", "NIST CSF 2.0", "DORA", "Cyber Essentials Plus"])
                        client_inputs["current_cert"] = st.selectbox("Current Baseline Cert", ["None", "Cyber Essentials (CE)", "Cyber Essentials Plus (CE+)", "ISO27001"])
                        client_inputs["backup_strategy"] = st.selectbox("Backup Strategy", ["On-prem Only", "Cloud (Non-Immutable)", "Immutable Cloud Backup", "None"])
                        client_inputs["ir_retainer"] = st.selectbox("IR Retainer", ["None / Ad-Hoc", "Basic Retainer (No SLA)", "Formal Retainer with SLA"])
                        client_inputs["tprm_status"] = st.selectbox("Third-Party Vendor Risk", ["No formal vetting", "Annual Questionnaires", "Continuous ZTNA"])
                    with grc_2:
                        client_inputs["ir_plan_review"] = st.selectbox("IR Plan Review", ["No formal plan", "Over 12 months ago", "Within last 12 months"])
                        client_inputs["last_tabletop"] = st.selectbox("Tabletop Exercise", ["Never", "Over 12 months ago", "Within last 12 months"])
                        client_inputs["asset_visibility"] = st.selectbox("Asset Inventory", ["Manual (Excel/None)", "Point-in-time Scan", "Continuous/Automated"])
                        client_inputs["insurance_status"] = st.selectbox("Cyber Insurance", ["None", "Policy Exists (Untested)", "Policy mapped to active IR Plan"])
                        client_inputs["data_classification"] = "Yes" if st.checkbox("Formal Data Classification?") else "No"
                        client_inputs["target_compliance"] = ", ".join(target_compliance) if target_compliance else "None specified"

        # SPECIFIC TIER 2: Only show Tactical options for Threat Simulator
        elif app_mode == "🔥 Threat Simulator":
            with st.container(border=True):
                st.subheader("🎯 Tactical Simulation Parameters")
                sim_1, sim_2 = st.columns(2)
                with sim_1:
                    client_inputs["savviness"] = st.selectbox("Assumed Security Culture / Maturity", ["Tier 1: High Risk", "Tier 2: Basic Compliance", "Tier 3: Conscious", "Tier 4: Highly Technical"])
                with sim_2:
                    client_inputs["custom_scenario"] = st.text_input("Custom Threat Scenario Override (Optional)", placeholder="e.g., BlackBasta ransomware deployment via compromised MSP")

        # Generate Button at the bottom of the active view
        st.markdown("<br>", unsafe_allow_html=True)
        generate_btn = st.button(f"🚀 Generate {app_mode.split()[1]}", type="primary", use_container_width=True)

    # ==========================================
    # REPORT GENERATION & RENDERING
    # ==========================================
    if generate_btn:
        st.session_state['client_inputs'] = client_inputs
        st.session_state['report_ready'] = False 
        
        with st.spinner("Analysing estate and generating insights..."):
            if app_mode == "📈 vCISO Assessment":
                vciso_obj = app_engine.call_llm_structured(build_vciso_prompt(client_inputs), MaturityReport)
                if vciso_obj:
                    st.session_state['vciso_obj'] = vciso_obj
                    st.session_state['vciso_pdf'] = create_vciso_pdf(client_inputs, vciso_obj)
                    st.session_state['vciso_pptx'] = create_vciso_pptx(client_inputs, vciso_obj)
                    st.session_state['report_ready'] = True
                    
            elif app_mode == "🔥 Threat Simulator":
                selected_vector = random.choice(ATTACK_VECTORS)
                osint_data = f"{app_engine.fetch_osint(client_inputs['endpoint'])} {app_engine.fetch_osint(client_inputs['firewall'])}"
                scenario_obj = app_engine.call_llm_structured(build_scenario_prompt(client_inputs, osint_data, selected_vector, client_inputs["custom_scenario"]), ScenarioReport)
                if scenario_obj:
                    mdr_case = app_engine.call_llm_text(build_mdr_case_prompt(client_inputs, scenario_obj.narrative))
                    st.session_state['scenario_obj'] = scenario_obj
                    st.session_state['mdr_case'] = mdr_case
                    st.session_state['recs'] = app_engine.generate_recommendations(client_inputs)
                    st.session_state['pdf_bytes'] = create_pdf(client_inputs, scenario_obj, st.session_state['recs'], mdr_case)
                    st.session_state['pptx_bytes'] = create_pptx(client_inputs, scenario_obj, st.session_state['recs'], mdr_case)
                    st.session_state['report_ready'] = True
        st.rerun()

    # --- RENDER RESULTS ---
    if st.session_state['report_ready']:
        
        if app_mode == "📈 vCISO Assessment" and st.session_state['vciso_obj']:
            vciso_report = st.session_state['vciso_obj']
            tab_exec, tab_gaps, tab_roadmap = st.tabs(["👔 Exec & Risk", "🔍 Gap Analysis", "🗺️ Roadmap"])
            
            with tab_exec:
                st.subheader("Executive Risk Summary")
                st.write(vciso_report.executive_summary)
                
                st.subheader("The Cost of Inaction")
                st.error(vciso_report.cost_of_inaction)
                
                st.subheader("🏅 Compliance & Framework Alignment")
                st.info(vciso_report.compliance_alignment)
                
            with tab_gaps:
                for domain in vciso_report.domain_assessments:
                    with st.expander(f"{domain.domain_name} — Score: {domain.numeric_maturity_score}/5.0", expanded=False):
                        st.markdown(f"**Current State:** {domain.current_state_analysis}")
                        st.markdown("**Critical Gaps:**")
                        for gap in domain.critical_gaps: st.markdown(f"- {gap}")
                        st.markdown("**Recommended Solutions:**")
                        for sol in domain.recommended_solutions: st.markdown(f"- 🛡️ {sol}")
                            
            with tab_roadmap:
                for phase in vciso_report.phased_roadmap:
                    st.markdown(f"#### {phase.phase_name}")
                    for ms in phase.milestones: st.markdown(f"✅ {ms}")
                        
            st.divider()
            col1, col2 = st.columns(2)
            with col1: st.download_button("📄 Download PDF Assessment", data=st.session_state['vciso_pdf'], file_name=f"{client_inputs['customer_name'].replace(' ', '_')}_vCISO.pdf", mime="application/pdf", use_container_width=True)
            with col2: st.download_button("📊 Download PowerPoint Deck", data=st.session_state['vciso_pptx'], file_name=f"{client_inputs['customer_name'].replace(' ', '_')}_vCISO.pptx", use_container_width=True)

        elif app_mode == "🔥 Threat Simulator" and st.session_state['scenario_obj']:
            tab1, tab2, tab3 = st.tabs(["📝 Threat Narrative", "🛡️ MDR Log", "🎯 Recommendations"])
            with tab1: st.write(st.session_state['scenario_obj'].narrative)
            with tab2: st.write(st.session_state['mdr_case'])
            with tab3:
                for rec in st.session_state['recs']: st.markdown(f"#### {rec}" if "🛡️" in rec else rec)
                        
            st.divider()
            col1, col2 = st.columns(2)
            with col1: st.download_button("📄 Download PDF Report", data=st.session_state['pdf_bytes'], file_name=f"{client_inputs['customer_name'].replace(' ', '_')}_MDR.pdf", mime="application/pdf", use_container_width=True)
            with col2: st.download_button("📊 Download PPTX Deck", data=st.session_state['pptx_bytes'], file_name=f"{client_inputs['customer_name'].replace(' ', '_')}_MDR.pptx", use_container_width=True)