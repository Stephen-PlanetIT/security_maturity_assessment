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

# --- BACKEND LOGIC ---
class CyberScenarioGenerator:
    def __init__(self, api_key, endpoint, deployment, api_version):
        self.deployment = deployment
        if api_key and endpoint:
            self.client = AzureOpenAI(
                api_key=api_key,  
                api_version=api_version,
                azure_endpoint=endpoint
            )
        else:
            self.client = None
    
    def fetch_osint(self, vendor):
        options = SIMULATED_OSINT.get(vendor, [])
        return random.choice(options) if options else ""

    def generate_recommendations(self, inputs):
        """Generates recommendations strictly for the tactical Threat Simulator tab."""
        recs = []
        recs.append("🛡️ **SECURITY ASSESSMENTS & ADVISORY**")
        
        if inputs['in_house_team'] == "Yes (24/7)" and ("Tier 3" in inputs['savviness'] or "Tier 4" in inputs['savviness']):
             recs.append("• [Secureworks Adversary Exercises (Red Teaming)](https://www.secureworks.com/services/offensive-security): Emulate a sophisticated adversary to stress-test your mature 24/7 SOC and validate detection capabilities across the kill chain.")
             recs.append("• [Secureworks Threat Hunting Assessment](https://www.secureworks.com/services/threat-hunting): Proactively search your environment for undetected threats or persistence mechanisms that may have bypassed your existing defenses.")
        elif inputs['in_house_team'] != "No":
             recs.append("• [Sophos Internal Penetration Testing](https://www.sophos.com/en-us/services/penetration-testing): Simulate an attacker who has bypassed the perimeter to test domain compromise, internal lateral movement, and existing defenses.")
             recs.append("• [Secureworks Tabletop Exercises](https://www.secureworks.com/services/incident-response-readiness): Ensure leadership and the internal security team are aligned on communication, legal, and operational procedures during a crisis.")
        else:
            recs.append("• [Sophos Emergency Incident Response Retainer](https://www.sophos.com/en-us/services/incident-response-retainer): Crucial for organizations without dedicated internal IR teams to guarantee SLAs and immediate assistance during a live breach.")

        if inputs['public_web_apps']:
            recs.append("• [Sophos Web Application Security Assessment](https://www.sophos.com/en-us/services/penetration-testing): Identify coding flaws (e.g., SQLi, XSS) in your public-facing web applications before attackers exploit them to access backend databases.")

        if inputs['physical_locations'] > 1:
             recs.append("• [Sophos Wireless Network Penetration Testing](https://www.sophos.com/en-us/services/penetration-testing): Evaluate wireless security across your physical locations, testing for rogue access points and weak encryption.")

        recs.append("\n⚙️ **RECOMMENDED SOPHOS SOLUTIONS**")
        
        # MDR Consolidation Pitch
        if inputs.get('mdr_provider', 'None') != "Sophos MDR":
            recs.append("• [Sophos MDR](https://www.sophos.com/en-us/products/mdr): Replace your current fragmented SOC/MDR approach with a fully managed, 24/7 threat hunting service backed by first-party telemetry to eliminate vendor blind spots.")

        if inputs['m365_license'] != "None / On-Prem Only":
            recs.append(f"• [Sophos MDR for Microsoft 365](https://www.sophos.com/en-us/products/mdr): Maximize your {inputs['m365_license']} investment. Sophos ingests telemetry directly from Microsoft to correlate alerts with cross-domain threat intelligence.")

        recs.append("• [Sophos Managed Risk](https://www.sophos.com/en-us/products/managed-risk): Implement continuous external attack surface management to discover and prioritize exposed vulnerabilities across your evolving tech stack.")

        if inputs['identity'] not in ["None / Local Only", "On-Prem Active Directory"]:
            recs.append(f"• [Sophos ITDR (Identity Threat Detection and Response)](https://www.sophos.com/en-us/products/mdr): Integrate telemetry directly from {inputs['identity']} to detect compromised credentials and anomalous logins.")

        if inputs['firewall'] != "Sophos" or inputs['servers'] > 20:
            recs.append("• [Sophos NDR (Network Detection and Response)](https://www.sophos.com/en-us/products/network-detection-and-response): Analyze network traffic for rogue devices, unprotected assets, and insider threats.")

        if inputs['endpoint'] != "Sophos":
             recs.append(f"• [Sophos Intercept X Advanced with XDR](https://www.sophos.com/en-us/products/endpoint-antivirus): Consolidate your endpoint stack by replacing {inputs['endpoint']} to provide deep-level native remediation capabilities.")

        return recs

    def call_llm_structured(self, prompt, response_model):
        if not self.client: return None
        try:
            response = self.client.beta.chat.completions.parse(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": SYSTEM_PERSONA},
                    {"role": "user", "content": prompt}
                ],
                response_format=response_model,
                temperature=0.7
            )
            return response.choices[0].message.parsed
        except Exception as e:
            st.error(f"Azure OpenAI Parsing Error: {e}")
            return None

    def call_llm_text(self, prompt):
        if not self.client: return "⚠️ Error: Please enter valid Azure OpenAI credentials."
        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": SYSTEM_PERSONA},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"⚠️ An error occurred: {e}"


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
    """Generates the PDF and PPTX for the vCISO Assessment."""
    if st.session_state.get('vciso_obj'):
        try:
            st.session_state['vciso_pdf_bytes'] = create_vciso_pdf(
                st.session_state['client_inputs'], 
                st.session_state['vciso_obj']
            )
            st.session_state['vciso_pptx_bytes'] = create_vciso_pptx(
                st.session_state['client_inputs'], 
                st.session_state['vciso_obj']
            )
        except Exception as e:
            st.error(f"vCISO Export Generation Failed: {e}")


# --- STREAMLIT FRONTEND ---
st.set_page_config(page_title="Security Advisory Platform", page_icon="🛡️", layout="wide")

try:
    az_key = st.secrets["AZURE_OPENAI_API_KEY"]
    az_endpoint = st.secrets["AZURE_OPENAI_ENDPOINT"]
    az_deployment = st.secrets["AZURE_OPENAI_DEPLOYMENT"]
    az_api_version = st.secrets.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
except Exception:
    st.error("⚠️ Missing API Credentials! Please ensure your `.streamlit/secrets.toml` file is mounted.")
    az_key, az_endpoint, az_deployment, az_api_version = None, None, None, None

app_engine = CyberScenarioGenerator(api_key=az_key, endpoint=az_endpoint, deployment=az_deployment, api_version=az_api_version)


# --- PURE NAVIGATION SIDEBAR ---
with st.sidebar:
    st.title("🛡️ Advisory Engine")
    app_mode = st.radio("Select Workflow:", ["📈 vCISO Assessment", "🔥 Tactical Threat Simulator"], index=0)
    st.divider()
    st.caption("Enter client data on the main page. It will persist between workflows.")


# --- MAIN PAGE DATA ENTRY (COLLAPSIBLE) ---
st.title(app_mode)

with st.expander("📋 Client Estate & Engagement Data", expanded=True):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Engagement Details")
        customer_name = st.text_input("Customer Name", "Acme Corp")
        consultant_name = st.text_input("Consultant Name", "Jane Doe")
        industry = st.selectbox("Industry Vertical", ["Healthcare", "Finance", "Manufacturing", "Retail", "Technology", "Education"])
        critical_infra = st.text_input("Crown Jewels", "Patient Records Database")
        
        st.subheader("The Human Element")
        users = st.number_input("Number of Users", min_value=1, value=500)
        in_house_team = st.radio("In-House Security Team?", ["No", "Yes (9-to-5)", "Yes (24/7)"])
        
    with col2:
        st.subheader("Technology Stack")
        endpoints = st.number_input("Number of Endpoints", min_value=1, value=600)
        servers = st.number_input("Number of Servers", min_value=1, value=50)
        mdr_provider = st.selectbox("Current MDR / SOC Provider", ["None", "Sophos MDR", "CrowdStrike Falcon Complete", "Arctic Wolf", "Expel", "Red Canary", "Local Partner SOC", "Other"])
        endpoint = st.selectbox("Endpoint Security", ["Sophos", "Microsoft Defender", "CrowdStrike", "SentinelOne", "Trend Micro", "Symantec", "N-able", "Other"])
        firewall = st.selectbox("Firewall Vendor", ["Fortinet", "Palo Alto", "Cisco", "Sophos", "Check Point", "SonicWall", "Other"])
        
    with col3:
        st.subheader("Cloud & Identity")
        identity = st.selectbox("Identity Provider", ["Microsoft Entra ID (Azure AD)", "Okta", "On-Prem Active Directory", "None"])
        m365_license = st.selectbox("Microsoft 365 Licensing", ["None / On-Prem Only", "M365 Business Premium", "Microsoft 365 E5", "Office 365 E3 / M365 E3"])
        email = st.selectbox("Email Security", ["Sophos", "Mimecast", "Proofpoint", "Microsoft Defender", "Barracuda", "Other"])
        cloud_env = st.selectbox("Cloud Infrastructure", ["AWS", "Microsoft Azure", "GCP", "Multi-Cloud", "None (Fully On-Prem)"])
        
        st.subheader("Governance & Additional Surfaces")
        compliance = st.multiselect("Target Compliance Frameworks", ["Cyber Essentials / CE+", "ISO 27001", "SOC 2 Type II", "HIPAA", "PCI-DSS", "NIST CSF", "DORA", "CIS Controls"])
        physical_locations = st.number_input("Physical Locations", min_value=1, value=3)
        public_web_apps = st.checkbox("Host Public Web Apps?")

    st.divider()
    st.subheader("Security Validation & Testing")
    col_v1, col_v2 = st.columns(2)
    with col_v1:
        pentest_status = st.selectbox("Penetration Testing Frequency", ["None", "Ad-hoc / Compliance Driven", "Annual", "Continuous / Red Teaming"])
    with col_v2:
        vuln_scanning = st.selectbox("Vulnerability Scanning", ["None", "Quarterly External", "Monthly Authenticated", "Continuous Agent-Based"])
    validation_notes = st.text_area("Additional Validation Context (e.g., remediation times, recent audit findings)")

    st.divider()
    st.subheader("🧮 Security Culture Calculator")
    calc_c1, calc_c2, calc_c3, calc_c4 = st.columns(4)
    with calc_c1:
        q1 = st.radio("1. MFA Enforcement", ["None / Optional", "Admins Only", "Mandatory for All Users"])
    with calc_c2:
        q2 = st.radio("2. Phishing Simulations", ["Never", "Annually", "Monthly / Quarterly"])
    with calc_c3:
        q3 = st.radio("3. Security Training", ["None", "Annual Compliance Video", "Continuous with active coaching"])
    with calc_c4:
        q4 = st.radio("4. Endpoint Privileges", ["Most users are Local Admins", "Only IT/Devs are Local Admins", "Zero Trust (No Local Admins/LAPS)"])

    culture_score = 0
    culture_score += {"None / Optional": 0, "Admins Only": 1, "Mandatory for All Users": 3}[q1]
    culture_score += {"Never": 0, "Annually": 1, "Monthly / Quarterly": 2}[q2]
    culture_score += {"None": 0, "Annual Compliance Video": 1, "Continuous with active coaching": 2}[q3]
    culture_score += {"Most users are Local Admins": 0, "Only IT/Devs are Local Admins": 1, "Zero Trust (No Local Admins/LAPS)": 2}[q4]

    if culture_score <= 3:
        savviness_label = "Tier 1: High Risk / Unaware"
    elif culture_score <= 6:
        savviness_label = "Tier 2: Basic Compliance"
    elif culture_score <= 8:
        savviness_label = "Tier 3: Cautious / Conscious"
    else:
        savviness_label = "Tier 4: Highly Technical / Optimised"

    savviness_profiles = {
        "Tier 1: High Risk / Unaware": "Highly susceptible to basic phishing, poor password hygiene, and excessive local admin rights.",
        "Tier 2: Basic Compliance": "Completes basic training but falls for urgency tactics. MFA is not universally enforced.",
        "Tier 3: Cautious / Conscious": "Strong culture. Actively reports suspicious emails. Good baseline of MFA and privilege restriction.",
        "Tier 4: Highly Technical / Optimised": "Zero-trust identity posture. Hard to phish, strict local admin controls, and continuous user coaching."
    }
    
    st.info(f"**Calculated Score: {culture_score}/9** | Result: {savviness_label} — *{savviness_profiles[savviness_label]}*")
    savviness = f"{savviness_label} - {savviness_profiles[savviness_label]}"

# Global dictionary updated seamlessly
client_inputs = {
    "customer_name": customer_name, "consultant_name": consultant_name, "industry": industry, 
    "users": users, "savviness": savviness, "endpoints": endpoints, "servers": servers, 
    "critical_infra": critical_infra, "mdr_provider": mdr_provider, "endpoint": endpoint, "firewall": firewall, 
    "identity": identity, "m365_license": m365_license, "email": email, "cloud_env": cloud_env,
    "in_house_team": in_house_team, "physical_locations": physical_locations, "public_web_apps": public_web_apps,
    "compliance": compliance,
    "pentest_status": pentest_status, "vuln_scanning": vuln_scanning, "validation_notes": validation_notes
}

# ==========================================
# ROUTE 1: VCISO ASSESSMENT
# ==========================================
if app_mode == "📈 vCISO Assessment":
    st.markdown("Generate a high-level maturity assessment and 3-phase strategic roadmap.")
    
    if st.button("Generate vCISO Roadmap", type="primary"):
        st.session_state['client_inputs'] = client_inputs
        with st.spinner("Analyzing estate and building maturity roadmap..."):
            vciso_prompt = build_vciso_prompt(client_inputs)
            vciso_obj = app_engine.call_llm_structured(vciso_prompt, MaturityReport)
            
            if vciso_obj:
                st.session_state['vciso_obj'] = vciso_obj
                update_vciso_exports()
                st.success("Assessment Complete!")

    if 'vciso_obj' in st.session_state and st.session_state['vciso_obj']:
        vciso_report = st.session_state['vciso_obj']
        cached_customer_name = st.session_state['client_inputs']['customer_name']
        
        st.info("💡 **Consultant Discovery Guide (For Your Eyes Only - Not Exported)**")
        st.markdown("*Use these provocative questions to expose blind spots and drive the conversation:*")
        for i, question in enumerate(vciso_report.consultant_discovery_guide, 1):
            st.markdown(f"**{i}.** {question}")
        st.divider()
        
        tab_exec, tab_gaps, tab_roadmap = st.tabs(["👔 Exec & Risk", "🔍 Gap Analysis", "🗺️ Roadmap & Partnership"])
        
        with tab_exec:
            st.subheader("Executive Risk Summary")
            st.write(vciso_report.executive_summary)
            
            st.subheader("Compliance & Framework Alignment")
            st.info(vciso_report.compliance_alignment)
            
            st.subheader("The Cost of Inaction")
            st.error(vciso_report.cost_of_inaction)
            
        with tab_gaps:
            st.subheader("Domain Gap Analysis")
            for domain in vciso_report.domain_assessments:
                with st.expander(f"{domain.domain_name} — {domain.current_maturity_level}", expanded=True):
                    st.markdown(f"**Current State:** {domain.current_state_analysis}")
                    
                    st.markdown("**Critical Gaps:**")
                    for gap in domain.critical_gaps:
                        st.markdown(f"- {gap}")
                        
                    st.markdown("**Zero-Cost Quick Wins:**")
                    for win in domain.vendor_agnostic_quick_wins:
                        st.markdown(f"- 🟢 {win}")
                        
                    st.markdown("**Recommended Solutions:**")
                    for sol in domain.recommended_solutions:
                        st.markdown(f"- 🛡️ {sol}")
                        
        with tab_roadmap:
            st.subheader("12-Month Success Metrics (KPIs)")
            for kpi in vciso_report.success_metrics:
                st.markdown(f"- 🎯 {kpi}")
            
            st.subheader("Phased Deployment Roadmap")
            for phase in vciso_report.phased_roadmap:
                st.markdown(f"#### {phase.phase_name}")
                for milestone in phase.milestones:
                    st.markdown(f"✅ {milestone}")

            st.subheader("Ongoing Advisory Cadence")
            for meeting in vciso_report.engagement_cadence:
                st.markdown(f"- 🗓️ {meeting}")
                    
        st.divider()
        if st.session_state.get('vciso_pdf_bytes') or st.session_state.get('vciso_pptx_bytes'):
            st.subheader("📥 Export Deliverables")
            dl_col1, dl_col2 = st.columns(2)
            with dl_col1:
                if st.session_state.get('vciso_pdf_bytes'):
                    st.download_button("📄 Download PDF Assessment", data=st.session_state['vciso_pdf_bytes'], file_name=f"{cached_customer_name.replace(' ', '_')}_vCISO_Report.pdf", mime="application/pdf")
            with dl_col2:
                if st.session_state.get('vciso_pptx_bytes'):
                    st.download_button("📊 Download PowerPoint Deck", data=st.session_state['vciso_pptx_bytes'], file_name=f"{cached_customer_name.replace(' ', '_')}_vCISO_Deck.pptx", mime="application/vnd.openxmlformats-officedocument.presentationml.presentation")


# ==========================================
# ROUTE 2: THREAT SIMULATOR
# ==========================================
elif app_mode == "🔥 Tactical Threat Simulator":
    st.markdown("Generate a tactical breach narrative based on the client's current vulnerabilities.")
    
    custom_scenario = st.text_input("Custom Scenario Override (Optional)", placeholder="e.g., BlackBasta ransomware deployment via compromised MSP")
    
    if st.button("Generate Threat Scenario", type="primary"):
        selected_vector = random.choice(ATTACK_VECTORS)
        
        osint_list = [
            app_engine.fetch_osint(endpoint),
            app_engine.fetch_osint(firewall),
            app_engine.fetch_osint(identity),
            app_engine.fetch_osint(email),
            app_engine.fetch_osint(cloud_env)
        ]
        osint_data = " ".join([x for x in osint_list if x])
        
        st.session_state['client_inputs'] = client_inputs
        st.session_state['selected_vector'] = selected_vector
        st.session_state['osint_data'] = osint_data
        st.session_state['custom_scenario'] = custom_scenario
        
        with st.spinner("Generating tactical breach narrative..."):
            prompt = build_scenario_prompt(client_inputs, osint_data, selected_vector, custom_scenario)
            scenario_obj = app_engine.call_llm_structured(prompt, ScenarioReport)
            
            if scenario_obj:
                mdr_case = app_engine.call_llm_text(build_mdr_case_prompt(client_inputs, scenario_obj.narrative))
                st.session_state['scenario_obj'] = scenario_obj
                st.session_state['mdr_case'] = mdr_case
                st.session_state['recs'] = app_engine.generate_recommendations(client_inputs)
                update_exports()
                st.success("Simulation Complete!")

    if 'scenario_obj' in st.session_state and st.session_state['scenario_obj']:
        scenario_obj = st.session_state['scenario_obj']
        cached_customer_name = st.session_state['client_inputs']['customer_name']
        
        tab1, tab2, tab3 = st.tabs(["📝 Threat Narrative", "🛡️ MDR Log", "🎯 Recommendations"])
        
        with tab1:
            st.subheader(f"Threat Narrative for {cached_customer_name}")
            st.write(scenario_obj.narrative)
            st.markdown("#### Attack Timeline")
            for t_event in scenario_obj.timeline:
                st.markdown(f"**{t_event.timestamp}** | {t_event.event_description}")
            
            st.divider()
            if st.button("🔄 Regenerate Narrative & Timeline", use_container_width=True):
                with st.spinner("Regenerating a new narrative path..."):
                    n_prompt = build_scenario_prompt(
                        st.session_state['client_inputs'], 
                        st.session_state['osint_data'], 
                        st.session_state['selected_vector'], 
                        st.session_state['custom_scenario']
                    )
                    new_scenario = app_engine.call_llm_structured(n_prompt, ScenarioReport)
                    if new_scenario:
                        st.session_state['scenario_obj'] = new_scenario
                        update_exports()
                        st.rerun()
                        
        with tab2:
            st.subheader("Simulated MDR Investigation")
            st.write(st.session_state['mdr_case'])
            
            st.divider()
            if st.button("🔄 Regenerate MDR Log", use_container_width=True):
                with st.spinner("Regenerating the MDR case log..."):
                    c_prompt = build_mdr_case_prompt(st.session_state['client_inputs'], st.session_state['scenario_obj'].narrative)
                    new_mdr = app_engine.call_llm_text(c_prompt)
                    st.session_state['mdr_case'] = new_mdr
                    update_exports()
                    st.rerun()
                    
        with tab3:
            st.subheader("Security Testing & Advisory")
            for rec in st.session_state['recs']:
                if rec.startswith("🛡️") or rec.startswith("⚙️"):
                    st.markdown(f"#### {rec}")
                else:
                    st.markdown(rec)
                    
        st.divider()
        if st.session_state.get('pdf_bytes') or st.session_state.get('pptx_bytes'):
            st.subheader("📥 Export Deliverables")
            dl_col1, dl_col2 = st.columns(2)
            with dl_col1:
                if st.session_state.get('pdf_bytes'):
                    st.download_button("📄 Download PDF Report", data=st.session_state['pdf_bytes'], file_name=f"{cached_customer_name.replace(' ', '_')}_MDR_Report.pdf", mime="application/pdf")
            with dl_col2:
                if st.session_state.get('pptx_bytes'):
                    st.download_button("📊 Download PowerPoint Deck", data=st.session_state['pptx_bytes'], file_name=f"{cached_customer_name.replace(' ', '_')}_MDR_Deck.pptx", mime="application/vnd.openxmlformats-officedocument.presentationml.presentation")