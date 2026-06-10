import streamlit as st
import random
from core import LLMEngine
from prompts import build_scenario_prompt, build_mdr_case_prompt, build_vciso_prompt, ScenarioReport, MaturityReport, SYSTEM_PERSONA
from data import ATTACK_VECTORS, SIMULATED_OSINT
from export import create_pdf, create_pptx, create_vciso_docx, create_vciso_pptx
from catalog import PLANET_IT_PORTFOLIO

class CyberScenarioGenerator:
    def generate_recommendations(self, inputs):
        recs = []
        
        # Extract variables for cleaner evaluation
        mdr = inputs.get('mdr_provider', 'None')
        in_house = inputs.get('in_house_team', 'No')
        users = inputs.get('users', 0)
        firewall = inputs.get('firewall', 'Unknown')
        industry = inputs.get('industry', 'Other')
        email = inputs.get('email', 'Unknown')
        identity = inputs.get('identity', 'Unknown')
        vuln_scan = inputs.get('vuln_scanning', 'None')
        culture = inputs.get('savviness', '')
        cloud = inputs.get('cloud_env', 'None (Fully On-Prem)')

        # 1. Managed Detection and Response (MDR)
        if in_house != "Yes (24/7)" and mdr not in ["Sophos MDR", "Planet IT Managed SOC"]:
            item = PLANET_IT_PORTFOLIO["Managed_Detection_and_Response"][0]
            recs.append(f"**{item['vendor']} ({item['category']}):** {item['planet_it_value_add']}")

        # 2. Network & Edge Security
        if users < 1000 and firewall != "Sophos":
            item = PLANET_IT_PORTFOLIO["Network_and_Edge_Security"][0] # Sophos Firewall
            recs.append(f"**{item['vendor']} ({item['category']}):** {item['planet_it_value_add']}")
        elif users >= 1000 and firewall != "Fortinet":
            item = PLANET_IT_PORTFOLIO["Network_and_Edge_Security"][1] # FortiGate
            recs.append(f"**{item['vendor']} ({item['category']}):** {item['planet_it_value_add']}")

        # 3. Email Security & Compliance
        if industry in ["Finance", "Healthcare", "Legal"] and email != "Mimecast":
            item = PLANET_IT_PORTFOLIO["Email_Security"][1] # Mimecast
            recs.append(f"**{item['vendor']} ({item['category']}):** {item['planet_it_value_add']}")
        elif industry not in ["Finance", "Healthcare", "Legal"] and email != "Sophos":
            item = PLANET_IT_PORTFOLIO["Email_Security"][0] # Sophos Email
            recs.append(f"**{item['vendor']} ({item['category']}):** {item['planet_it_value_add']}")

        # 4. Identity & Access Management
        if identity in ["Microsoft Entra ID (Azure AD)", "Okta"]:
            item = PLANET_IT_PORTFOLIO["Identity_and_Access_Management"][0] # Sophos ITDR
            recs.append(f"**{item['vendor']} ({item['category']}):** {item['planet_it_value_add']}")

        # 5. Attack Surface Management
        if vuln_scan != "Continuous":
            item = PLANET_IT_PORTFOLIO["Vulnerability_and_Exposure_Management"][0] # Managed Risk
            recs.append(f"**{item['vendor']} ({item['category']}):** {item['planet_it_value_add']}")

        # 6. Security Culture & Phishing
        if "Phase 1" in culture:
            item = PLANET_IT_PORTFOLIO["Security_Awareness_and_Training"][0] # Phish Threat
            recs.append(f"**{item['vendor']} ({item['category']}):** {item['planet_it_value_add']}")

        # 7. Cloud Posture
        if "AWS" in cloud or "Microsoft Azure" in cloud or "GCP" in cloud:
            item = PLANET_IT_PORTFOLIO["Cloud_Security_and_Posture"][0] # Cloud Optix
            recs.append(f"**{item['vendor']} ({item['category']}):** {item['planet_it_value_add']}")

        # Fallback for highly mature environments
        if not recs:
            recs.append("**Internal SOC Optimisation:** Leverage your existing 24/7 team for proactive threat hunting, as baseline controls are currently saturated.")

        return recs

# --- HELPER: EXPORT GENERATORS ---
def update_exports():
    """Generates the PDF and PPTX for the Threat Simulator."""
    if st.session_state.get('scenario_obj'):
        try:
            st.session_state['pdf_bytes'] = create_pdf(
                st.session_state['client_inputs'], 
                st.session_state['scenario_obj'], 
                st.session_state['recs'], 
                st.session_state['mdr_case']
            )
            st.session_state['pptx_bytes'] = create_pptx(
                st.session_state['client_inputs'], 
                st.session_state['scenario_obj'], 
                st.session_state['recs'], 
                st.session_state['mdr_case']
            )
        except Exception as e:
            st.error(f"Export Generation Failed: {e}")

def update_vciso_exports():
    """Generates the Word Doc and PPTX for the vCISO Assessment."""
    if st.session_state.get('vciso_obj'):
        try:
            st.session_state['vciso_docx_bytes'] = create_vciso_docx(
                st.session_state['client_inputs'], 
                st.session_state['vciso_obj']
            )
            st.session_state['vciso_pptx_bytes'] = create_vciso_pptx(
                st.session_state['client_inputs'], 
                st.session_state['vciso_obj']
            )
        except Exception as e:
            st.error(f"vCISO Export Generation Failed: {e}")

# --- UI CONFIGURATION ---
st.set_page_config(page_title="Security Use Case Generator", layout="wide")

# --- SIDEBAR & ENGINE CONFIGURATION ---
with st.sidebar:
    st.markdown("## 🛡️ Advisory Engine")
    st.markdown("### ⚙️ Engine Configuration")
    
    ai_engine = st.radio(
        "AI Engine Provider:", 
        options=["☁️ Cloud (Azure OpenAI)", "🖥️ Local (Ollama)"], 
        index=0
    )
    st.session_state['ai_engine'] = ai_engine
    
    st.divider()
    
    workflow = st.radio(
        "Select Workflow:", 
        options=["📈 vCISO Assessment", "🔥 Tactical Threat Simulator"], 
        index=0
    )
    st.session_state['workflow'] = workflow
    
    st.divider()

# --- MAIN PAGE HEADER ---
st.title("Security Use Case & vCISO Generator")

# --- UI INPUTS ---
with st.expander("Customer Estate & Engagement Profile", expanded=True):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Organisational Profile")
        customer_name = st.text_input("Customer Name", value="Acme Corp")
        consultant_name = st.text_input("Consultant Name", value="Jane Doe")
        industry = st.selectbox("Industry", ["Healthcare", "Finance", "Manufacturing", "Retail", "Technology", "Other"])
        users = st.number_input("Headcount", min_value=1, value=500)
        critical_infra = st.text_input("Crown Jewels", value="Patient Records Database")
        
    with col2:
        st.subheader("Technology Stack")
        endpoints = st.number_input("Number of Endpoints", min_value=1, value=600)
        servers = st.number_input("Number of Servers", min_value=1, value=50)
        operating_systems = st.multiselect("Operating Systems in Use", ["Windows 10/11", "Windows Server", "macOS", "Linux", "ChromeOS"], default=["Windows 10/11", "Windows Server"])
        mdr_provider = st.selectbox("Current MDR / SOC Provider", ["None", "Sophos MDR", "CrowdStrike Falcon Complete", "Arctic Wolf", "Expel", "Red Canary", "Local Partner SOC", "Other"])
        endpoint = st.selectbox("Endpoint Security", ["Sophos", "Microsoft Defender", "CrowdStrike", "SentinelOne", "Trend Micro", "Symantec", "N-able", "Other"])
        firewall = st.selectbox("Firewall Vendor", ["Fortinet", "Palo Alto", "Cisco", "Sophos", "Check Point", "SonicWall", "Other"])
        
    with col3:
        st.subheader("Cloud & Identity")
        identity = st.selectbox("Identity Provider", ["Microsoft Entra ID (Azure AD)", "Okta", "On-Prem Active Directory", "None"])
        m365_license = st.selectbox("Microsoft 365 Licensing", ["None / On-Prem Only", "M365 Business Premium", "Microsoft 365 E5", "Office 365 E3 / M365 E3"])
        email = st.selectbox("Email Security", ["Sophos", "Mimecast", "Proofpoint", "Microsoft Defender", "Barracuda", "Other"])
        cloud_env = st.multiselect("Cloud Infrastructure", ["AWS", "Microsoft Azure", "GCP", "Oracle Cloud", "None (Fully On-Prem)"], default=["AWS"])

    st.divider()
    st.subheader("Operations & Validation")
    col_ops1, col_ops2 = st.columns(2)
    with col_ops1:
        in_house_team = st.selectbox("Internal SOC Team", ["No", "Yes (9-to-5)", "Yes (24/7)"])
        pentest_status = st.selectbox("Penetration Testing", ["None", "Annual", "Bi-Annual", "Quarterly"])
        vuln_scanning = st.selectbox("Vuln Scanning", ["None", "Monthly Authenticated", "Quarterly External", "Continuous"])
        public_web_apps = st.checkbox("Host Public Web Apps", value=False)
    with col_ops2:
        compliance = st.multiselect("Target Compliance", ["ISO 27001", "Cyber Essentials", "Cyber Essentials Plus", "PCI DSS", "HIPAA", "NIST CSF"])
        physical_locations = st.number_input("Physical Locations", min_value=1, value=3)
        validation_notes = st.text_area("Validation Notes")

    st.divider()
    
    ## --- SECURITY CULTURE CALCULATOR ---
    st.markdown("### 🧮 Security Culture Calculator")
    
    calc_col1, calc_col2, calc_col3, calc_col4 = st.columns(4)
    
    with calc_col1:
        q1 = st.radio("1. MFA Enforcement", ["None / Optional", "Admins Only", "Mandatory for All Users"])
    with calc_col2:
        q2 = st.radio("2. Phishing Simulations", ["Never", "Annually", "Monthly / Quarterly"])
    with calc_col3:
        q3 = st.radio("3. Security Training", ["None", "Annual Compliance Video", "Continuous with active coaching"])
    with calc_col4:
        q4 = st.radio("4. Endpoint Privileges", ["Most users are Local Admins", "Only IT/Devs are Local Admins", "Zero Trust (No Local Admins/LAPS)"])
    
    culture_score = 0
    culture_score += {"None / Optional": 0, "Admins Only": 1, "Mandatory for All Users": 3}[q1]
    culture_score += {"Never": 0, "Annually": 1, "Monthly / Quarterly": 2}[q2]
    culture_score += {"None": 0, "Annual Compliance Video": 1, "Continuous with active coaching": 2}[q3]
    culture_score += {"Most users are Local Admins": 0, "Only IT/Devs are Local Admins": 1, "Zero Trust (No Local Admins/LAPS)": 2}[q4]

    if culture_score <= 4:
        savviness_label = "Phase 1: Reactive Culture"
    elif culture_score <= 7:
        savviness_label = "Phase 2: Proactive Culture"
    else:
        savviness_label = "Phase 3: Adaptive Culture"

    savviness_profiles = {
        "Phase 1: Reactive Culture": "Currently developing baseline awareness. Focus should be placed on universally enforcing MFA and restricting local administrator privileges.",
        "Phase 2: Proactive Culture": "Strong baseline awareness. Users complete regular training and foundational identity controls are actively enforced.",
        "Phase 3: Adaptive Culture": "Highly optimised, zero-trust mindset. Users actively report threats, supported by strict access controls and continuous coaching."
    }
    
    st.info(f"**Calculated Score: {culture_score}/9** | Result: {savviness_label} — *{savviness_profiles[savviness_label]}*")
    savviness = f"{savviness_label} - {savviness_profiles[savviness_label]}"

    st.divider()

    ## --- OPERATIONAL & RISK TELEMETRY ---
    st.markdown("### ⚙️ Operational & Risk Telemetry")
    
    op_col1, op_col2 = st.columns(2)
    
    with op_col1:
        mfa_status = st.selectbox("MFA Enforcement", ["None", "Privileged Accounts Only", "Universal / Conditional Access"], index=1)
        patching = st.selectbox("Patch Management", ["Manual / Ad-hoc", "Automated (OS Only)", "Automated (OS & Third-Party)"], index=0)
        backups = st.selectbox("Backup Strategy", ["No Formal Backups", "On-Premise Only", "Cloud/Offsite (Standard)", "Immutable / Air-Gapped"], index=1)
        
    with op_col2:
        insurance = st.selectbox("Cyber Insurance Status", ["None", "Exploring Requirements", "Active Policy"], index=0)
        rto = st.selectbox("Downtime Tolerance", ["< 4 Hours (Critical)", "12-24 Hours", "48+ Hours"], index=1)

# --- GLOBAL INPUTS DICTIONARY ---
client_inputs = {
    "customer_name": customer_name, 
    "consultant_name": consultant_name, 
    "industry": industry, 
    "users": users, 
    "savviness": savviness, 
    "endpoints": endpoints, 
    "servers": servers, 
    "operating_systems": ", ".join(operating_systems) if operating_systems else "None", 
    "critical_infra": critical_infra, 
    "mdr_provider": mdr_provider, 
    "endpoint": endpoint, 
    "firewall": firewall, 
    "identity": identity, 
    "m365_license": m365_license, 
    "email": email, 
    "cloud_env": ", ".join(cloud_env) if cloud_env else "None (Fully On-Prem)",
    "in_house_team": in_house_team, 
    "physical_locations": physical_locations, 
    "public_web_apps": public_web_apps,
    "compliance": ", ".join(compliance) if compliance else "None",
    "pentest_status": pentest_status, 
    "vuln_scanning": vuln_scanning, 
    "validation_notes": validation_notes,
    "mfa_status": mfa_status,
    "patching": patching,
    "backups": backups,
    "insurance": insurance,
    "rto": rto
}

st.session_state['client_inputs'] = client_inputs
cached_customer_name = st.session_state['client_inputs'].get('customer_name', 'Client')

st.divider()

# --- WORKFLOW ROUTING ---
if st.session_state['workflow'] == "🔥 Tactical Threat Simulator":
    st.header("Tactical Threat Simulator")
    
    if st.button("Generate Threat Scenario", type="primary"):
        with st.spinner("Simulating Attack & MDR Response..."):
            provider_flag = "ollama" if "Local" in st.session_state['ai_engine'] else "azure"
            client = LLMEngine.get_client(provider_flag)
            if provider_flag == "ollama":
                deployment = st.secrets.get("OLLAMA_MODEL", "deepseek-r1:14b")
            else:
                deployment = st.secrets.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
            
            selected_vector = random.choice(ATTACK_VECTORS)
            osint_list = []
            stack_selections = [endpoint, firewall, identity, email] + cloud_env
            for item in stack_selections:
                if item in SIMULATED_OSINT:
                    osint_list.extend(SIMULATED_OSINT[item])
            osint_data = " ".join(osint_list)
            
            scenario_prompt = build_scenario_prompt(st.session_state['client_inputs'], osint_data, selected_vector)
            scenario_obj = LLMEngine.generate_structured_report(client, deployment, SYSTEM_PERSONA, scenario_prompt, ScenarioReport)
            
            if scenario_obj:
                st.session_state['scenario_obj'] = scenario_obj
                st.session_state['recs'] = CyberScenarioGenerator().generate_recommendations(st.session_state['client_inputs'])
                
                mdr_prompt = build_mdr_case_prompt(st.session_state['client_inputs'], scenario_obj.narrative)
                mdr_response = client.chat.completions.create(
                    model=deployment,
                    messages=[{"role": "system", "content": SYSTEM_PERSONA}, {"role": "user", "content": mdr_prompt}],
                    temperature=0.7
                )
                st.session_state['mdr_case'] = mdr_response.choices[0].message.content
                
                update_exports()
                st.success("Threat Simulation Generated Successfully.")
            else:
                st.error("Engine failed to generate the scenario.")
        
    if st.session_state.get('pdf_bytes'):
        st.download_button(
            "📄 Download Threat Simulation (PDF)", 
            data=st.session_state['pdf_bytes'], 
            file_name=f"{cached_customer_name.replace(' ', '_')}_Threat_Simulation.pdf", 
            mime="application/pdf"
        )

elif st.session_state['workflow'] == "📈 vCISO Assessment":
    st.header("vCISO Assessment")
    
    if st.button("Generate vCISO Roadmap", type="primary"):
        with st.spinner("Compiling vCISO Assessment..."):
            provider_flag = "ollama" if "Local" in st.session_state['ai_engine'] else "azure"
            client = LLMEngine.get_client(provider_flag)
            if provider_flag == "ollama":
                deployment = st.secrets.get("OLLAMA_MODEL", "deepseek-r1:14b") 
            else:
                deployment = st.secrets.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
            
            vciso_prompt = build_vciso_prompt(st.session_state['client_inputs'])
            vciso_obj = LLMEngine.generate_structured_report(client, deployment, SYSTEM_PERSONA, vciso_prompt, MaturityReport)
            
            if vciso_obj:
                st.session_state['vciso_obj'] = vciso_obj
                update_vciso_exports()
                st.success("vCISO Roadmap Generated Successfully.")
            else:
                st.error("Engine failed to generate the roadmap.")
        
    if st.session_state.get('vciso_docx_bytes') or st.session_state.get('vciso_pptx_bytes'):
        st.subheader("📥 Export Deliverables")
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            if st.session_state.get('vciso_docx_bytes'):
                st.download_button(
                    "📄 Download vCISO Report (Word)", 
                    data=st.session_state['vciso_docx_bytes'], 
                    file_name=f"{cached_customer_name.replace(' ', '_')}_vCISO_Report.docx", 
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
        with dl_col2:
            if st.session_state.get('vciso_pptx_bytes'):
                st.download_button(
                    "📊 Download PowerPoint Deck", 
                    data=st.session_state['vciso_pptx_bytes'], 
                    file_name=f"{cached_customer_name.replace(' ', '_')}_vCISO_Deck.pptx", 
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                )

    if st.session_state.get('vciso_obj'):
        st.divider()
        st.subheader("📊 Strategic Assessment Preview")
        
        vciso = st.session_state['vciso_obj']
        
        tab1, tab2, tab3 = st.tabs(["Executive Brief", "Domain Assessments", "Strategic Roadmap"])
        
        with tab1:
            st.markdown("### Executive Summary")
            st.markdown(vciso.executive_summary)
            
            st.markdown("### Resiliency Matrix Mapping")
            st.info(vciso.resiliency_matrix_mapping)
            
            col_impact, col_comp = st.columns(2)
            with col_impact:
                st.markdown("### The Cost of Inaction")
                st.error(vciso.cost_of_inaction)
            with col_comp:
                st.markdown("### Compliance Alignment")
                st.success(vciso.compliance_alignment)
                
        with tab2:
            st.markdown("### Security Domain Analysis")
            for domain in vciso.domain_assessments:
                with st.expander(f"{domain.domain_name} — {domain.current_maturity_level}"):
                    st.markdown("**Technical Analysis:**")
                    st.markdown(domain.current_state_analysis)
                    
                    st.markdown("**Business Impact:**")
                    st.markdown(domain.business_impact_narrative)
                    
                    st.markdown("**Critical Gaps:**")
                    for gap in domain.critical_gaps:
                        st.markdown(f"- {gap}")
                        
                    st.markdown("**Remediation Rationale:**")
                    st.markdown(domain.remediation_rationale)
                    
        with tab3:
            st.markdown("### Phased Implementation")
            for phase in vciso.phased_roadmap:
                st.markdown(f"#### {phase.phase_name}: {phase.primary_objective}")
                for milestone in phase.milestones:
                    st.markdown(f"- {milestone}")
                st.markdown(f"**Value Delivered:** {phase.business_value_delivered}")
                st.markdown(f"**Resources:** {phase.resource_requirements}")
                st.divider()