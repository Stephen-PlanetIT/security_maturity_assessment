import streamlit as st
import random
from core import LLMEngine
from prompts import build_scenario_prompt, build_mdr_case_prompt, build_vciso_prompt, ScenarioReport, MaturityReport, SYSTEM_PERSONA
from data import ATTACK_VECTORS, SIMULATED_OSINT
from export import create_pdf, create_pptx, create_vciso_docx, create_vciso_pptx

class CyberScenarioGenerator:
    def generate_recommendations(self, inputs):
        recs = []
        if inputs['in_house_team'] == "Yes (24/7)" and ("Phase 2" in inputs['savviness'] or "Phase 3" in inputs['savviness']):
            recs.append("Leverage internal SOC for proactive threat hunting.")
        # Add your other recommendation logic here...
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
    st.markdown("Enter client data on the main page. It will persist between workflows.")

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

# --- GLOBAL INPUTS DICTIONARY ---
client_inputs = {
    "customer_name": customer_name, "consultant_name": consultant_name, "industry": industry, 
    "users": users, "savviness": savviness, "endpoints": endpoints, "servers": servers, 
    "operating_systems": operating_systems, 
    "critical_infra": critical_infra, "mdr_provider": mdr_provider, "endpoint": endpoint, "firewall": firewall, 
    "identity": identity, "m365_license": m365_license, "email": email, "cloud_env": cloud_env,
    "in_house_team": in_house_team, "physical_locations": physical_locations, "public_web_apps": public_web_apps,
    "compliance": compliance,
    "pentest_status": pentest_status, "vuln_scanning": vuln_scanning, "validation_notes": validation_notes
}

st.session_state['client_inputs'] = client_inputs
cached_customer_name = st.session_state['client_inputs'].get('customer_name', 'Client')

st.divider()

# --- WORKFLOW ROUTING ---
if st.session_state['workflow'] == "🔥 Tactical Threat Simulator":
    st.header("Tactical Threat Simulator")
    
    if st.button("Generate Threat Scenario", type="primary"):
        with st.spinner("Simulating Attack & MDR Response..."):
            # Determine provider from the UI sidebar toggle
            provider_flag = "ollama" if "Local" in st.session_state['ai_engine'] else "azure"
            client = LLMEngine.get_client(provider_flag)
            deployment = st.secrets.get("LLM_MODEL", "gpt-4o") # Update with your exact model deployment name
            
            # Map OSINT from data.py based on the selected tech stack
            selected_vector = random.choice(ATTACK_VECTORS)
            osint_list = []
            stack_selections = [endpoint, firewall, identity, email] + cloud_env
            for item in stack_selections:
                if item in SIMULATED_OSINT:
                    osint_list.extend(SIMULATED_OSINT[item])
            osint_data = " ".join(osint_list)
            
            # TRIGGER 1: Generate the Structured Narrative & Timeline (JSON)
            scenario_prompt = build_scenario_prompt(st.session_state['client_inputs'], osint_data, selected_vector)
            scenario_obj = LLMEngine.generate_structured_report(client, deployment, SYSTEM_PERSONA, scenario_prompt, ScenarioReport)
            
            if scenario_obj:
                st.session_state['scenario_obj'] = scenario_obj
                st.session_state['recs'] = CyberScenarioGenerator().generate_recommendations(st.session_state['client_inputs'])
                
                # TRIGGER 2: Generate the MDR Case Log (Raw Markdown, bypassing the JSON parser)
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
            # Determine provider from the UI sidebar toggle
            provider_flag = "ollama" if "Local" in st.session_state['ai_engine'] else "azure"
            client = LLMEngine.get_client(provider_flag)
            deployment = st.secrets.get("LLM_MODEL", "gpt-4o") # Update with your exact model deployment name
            
            # TRIGGER: Generate the Structured vCISO Report (JSON)
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