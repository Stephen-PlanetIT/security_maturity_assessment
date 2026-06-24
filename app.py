import streamlit as st
import random
from core import LLMEngine
from prompts import build_scenario_prompt, build_mdr_case_prompt, build_vciso_prompt, ScenarioReport, MaturityReport, SYSTEM_PERSONA
from data import ATTACK_VECTORS, SIMULATED_OSINT
from export import create_pdf, create_vciso_docx, create_threat_docx
from catalog import PLANET_IT_PORTFOLIO
from config import get_config, validate_config, ConfigKey

# --- VERSION TRACKER ---
with open("VERSION", "r") as f:
    APP_VERSION = f.read().strip()

def validate_platform_config():
    """Validates that necessary secrets exist before runtime."""
    provider = "ollama" if "Local" in st.session_state.get('ai_engine', '') else "azure"
    try:
        validate_config(provider)
    except ValueError as e:
        st.warning(f"⚠️ {e}")

def get_optimal_deployment_name(provider_flag):
    """Fetches the correct deployment string based on the active provider."""
    if provider_flag == "ollama":
        return get_config(ConfigKey.OLLAMA_MODEL, "deepseek-r1:14b")
    else:
        return get_config(ConfigKey.AZURE_DEPLOYMENT, "gpt-4o")

class CyberScenarioGenerator:
    def generate_recommendations(self, inputs):
        recs = []
        banned = set(inputs.get('banned_vendors', []))
        
        def is_banned(vendor_name):
            """Check if a vendor name (or any part of it) is in the banned set."""
            return any(b.lower() in vendor_name.lower() for b in banned)
        
        def safe_append(category_key, vendor_name, fallback_msg=None):
            """Append a catalog recommendation by vendor name, skipping if banned.
            
            Looks up the product by vendor name rather than index position, making
            the recommendation engine immune to catalogue reordering.
            """
            items = PLANET_IT_PORTFOLIO.get(category_key, [])
            for item in items:
                if item['vendor'] == vendor_name and not is_banned(item['vendor']):
                    recs.append(f"**{item['vendor']} ({item['category']}):** {item['planet_it_value_add']}")
                    return True
            if fallback_msg:
                recs.append(fallback_msg)
            return False
        
        # Extract variables
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
        m365_license = inputs.get('m365_license', 'None / On-Prem Only')
        
        # Extract new telemetry
        patching = inputs.get('patching', 'Unknown')
        backups = inputs.get('backups', 'Unknown')
        mfa_status = inputs.get('mfa_status', 'Unknown')
        ir_retainer = inputs.get('ir_retainer', 'None')

        strong_ms_investment = m365_license in ["Microsoft 365 E5", "M365 Business Premium"]

        # 1. MDR & The Capability Mismatch (Endpoint)
        if mdr in ["Sophos MDR", "Sophos MDR Plus", "Planet IT Managed SOC"] and patching == "Manual / Ad-hoc":
            recs.append("**Capability Mismatch (MDR vs Hygiene):** Investment in advanced MDR (Pillar 2) without automated patch management (Pillar 1) generates excessive, preventable noise in the estate. A managed patching (RMM) deployment is recommended to secure the operational foundation before layering advanced detection.")
        elif mdr == "Microsoft Defender Experts":
            # Defender Experts provides Microsoft-native hunting but lacks cross-vendor visibility
            if not is_banned("Sophos"):
                recs.append("**Microsoft Defender Experts + Sophos MDR Overlay:** Microsoft Defender Experts delivers excellent Microsoft-native threat hunting. Planet IT recommends layering Sophos MDR (powered by the AI-Native Cyber Defense System) to add cross-vendor telemetry integration for firewalls, OT, and non-Microsoft identity—closing visibility gaps that Microsoft alone cannot address. This provides 24/7 human-led response across the entire estate, not just the Microsoft stack.")
            else:
                recs.append("**Microsoft Defender Experts (Cross-Vendor Gap):** Microsoft Defender Experts provides strong Microsoft-native hunting. However, cross-vendor telemetry (firewalls, OT, non-Microsoft identity) remains unmonitored. Planet IT can advise on suitable alternatives to close these visibility gaps.")
        elif in_house != "Yes (24/7)":
            if strong_ms_investment and mdr not in ["Sophos MDR", "Sophos MDR Plus", "Planet IT Managed SOC"]:
                if not is_banned("Microsoft") and not is_banned("Sophos"):
                    recs.append("**Microsoft / Sophos (MDR):** Optimisation of Microsoft Defender XDR with Sophos MDR overlay provides 24/7 human-led threat hunting without duplicating endpoint licensing costs.")
                else:
                    safe_append("Managed_Detection_and_Response", "Sophos MDR",
                        "**MDR Service:** A managed detection and response service is recommended. Planet IT can advise on suitable alternatives.")
            elif not strong_ms_investment and mdr not in ["Sophos MDR", "Sophos MDR Plus", "Planet IT Managed SOC"]:
                safe_append("Managed_Detection_and_Response", "Sophos MDR",
                    "**MDR Service:** A managed detection and response service is recommended. Planet IT can advise on suitable alternatives.")

        # 1b. IR Retainer Awareness
        if ir_retainer != "None" and mdr == "None":
            recs.append(f"**IR Retainer vs Proactive MDR:** The client holds an active {ir_retainer} retainer, which provides reactive incident response capability (hours-to-days MTTR). This is a valuable Pillar 2 capability, but it does not replace 24/7 proactive threat detection and neutralisation. A managed detection and response service (e.g., Sophos MDR) is recommended to achieve sub-hour MTTR and prevent incidents before they escalate to IR activation.")
        elif ir_retainer == "Sophos MDR Plus / Incident Response" and mdr == "Sophos MDR Plus":
            recs.append("**IR Retainer Redundancy:** Sophos MDR Plus already includes full-scale incident response with a dedicated IR lead, root cause analysis, and direct call-in support. A separate IR retainer is redundant unless specifically required by cyber insurance policy mandates. Planet IT can advise on consolidation.")
        elif ir_retainer == "Microsoft DART" and mdr == "Sophos MDR Plus":
            recs.append("**DART vs MDR Plus IR:** Microsoft DART provides elite reactive IR capability, but Sophos MDR Plus already includes full-scale incident response as part of the service. Consider consolidating to eliminate retainer overlap while maintaining 24/7 proactive coverage via Sophos MDR.")

        # 2. Foundational Hygiene (Patching & Backups)
        if backups in ["No Formal Backups", "On-Premise Only"]:
            recs.append("**Data Resilience (Immutable Backups):** The current backup strategy presents significant vulnerability to ransomware encryption. Deployment of an offsite, air-gapped immutable backup solution (e.g., Veeam/Cove) is recommended to ensure recoverability.")
        if mfa_status in ["None", "Privileged Accounts Only"]:
            recs.append("**Identity Hardening (MFA):** Universal MFA enforcement via Conditional Access is a mandatory Pillar 1 requirement. Immediate remediation is required to close the most prevalent credential-based attack vector.")

        # 3. Network & Edge Security (Ignore Rip-and-Replace for Palo Alto/Check Point)
        if firewall not in ["Palo Alto", "Check Point", "Fortinet", "Sophos"]:
            if users < 1000:
                safe_append("Network_and_Edge_Security", "Sophos Firewall",
                    "**Network Security:** A next-generation firewall is recommended. Planet IT can advise on suitable options.")
            else:
                safe_append("Network_and_Edge_Security", "Fortinet FortiGate",
                    "**Network Security:** An enterprise-grade firewall with SD-WAN is recommended. Planet IT can advise on suitable options.")

        # 4. Email Security
        if industry in ["Finance", "Healthcare", "Legal"] and email != "Mimecast":
            safe_append("Email_Security", "Mimecast",
                "**Email Security:** An advanced email security gateway with immutable archiving is recommended for regulated industries.")
        elif strong_ms_investment and email not in ["Microsoft Defender", "Mimecast", "Barracuda"]:
            if not is_banned("Microsoft"):
                recs.append("**Microsoft (Email Security):** Configure Defender for Office 365 natively for anti-phishing before procuring third-party gateways.")
            else:
                safe_append("Email_Security", "Barracuda",
                    "**Email Security:** A cross-vendor email security gateway is recommended. Planet IT can advise on suitable alternatives.")
        elif not strong_ms_investment and email not in ["Mimecast", "Barracuda"]:
            safe_append("Email_Security", "Barracuda",
                "**Email Security:** A cloud email security gateway (e.g., Barracuda) is recommended, with Mimecast as an alternative if required.")

        # 5. Attack Surface Management
        if vuln_scan != "Continuous":
            safe_append("Vulnerability_and_Exposure_Management", "Sophos Managed Risk",
                "**Attack Surface Management:** Continuous external attack surface monitoring is recommended. Planet IT can advise on suitable solutions.")

        # 6. Security Culture
        if "Pillar 1" in culture:
            safe_append("Security_Awareness_and_Training", "Hoxhunt",
                "**Security Awareness Training:** A phishing simulation and training programme is recommended. Planet IT can advise on suitable platforms.")

        if not recs:
            recs.append("**Internal SOC Optimisation:** Leverage the existing 24/7 team for proactive threat hunting, as baseline controls are currently saturated.")

        return recs

# --- HELPER: LAZY EXPORT GENERATORS ---
# Exports are generated on-demand (when the user clicks download) rather than eagerly.
# This shaves 5-15 seconds off the post-generation wait time.

def get_threat_pdf_bytes():
    """Lazy-generate and cache PDF bytes for the Threat Simulator."""
    if st.session_state.get('pdf_bytes') is None and st.session_state.get('scenario_obj'):
        try:
            st.session_state['pdf_bytes'] = create_pdf(
                st.session_state['client_inputs'], 
                st.session_state['scenario_obj'], 
                st.session_state['recs'], 
                st.session_state['mdr_case']
            )
        except Exception as e:
            st.error(f"PDF Export Failed: {e}")
    return st.session_state.get('pdf_bytes')

def get_threat_docx_bytes():
    """Lazy-generate and cache Word Doc bytes for the Threat Simulator."""
    if st.session_state.get('threat_docx_bytes') is None and st.session_state.get('scenario_obj'):
        try:
            st.session_state['threat_docx_bytes'] = create_threat_docx(
                st.session_state['client_inputs'],
                st.session_state['scenario_obj'],
                st.session_state['recs'],
                st.session_state['mdr_case']
            )
        except Exception as e:
            st.error(f"Word Export Failed: {e}")
    return st.session_state.get('threat_docx_bytes')

def get_vciso_docx_bytes():
    """Lazy-generate and cache vCISO Word Doc bytes."""
    if st.session_state.get('vciso_docx_bytes') is None and st.session_state.get('vciso_obj'):
        try:
            st.session_state['vciso_docx_bytes'] = create_vciso_docx(
                st.session_state['client_inputs'], 
                st.session_state['vciso_obj']
            )
        except Exception as e:
            st.error(f"vCISO Word Export Failed: {e}")
    return st.session_state.get('vciso_docx_bytes')

def _display_cost_of_inaction_section():
    """Safely render the GBP cost of inaction if available in the current report."""
    report = None
    if 'vciso_report' in getattr(st, 'session_state', {}):
        report = st.session_state.get('vciso_report')
    elif 'maturity_report' in getattr(st, 'session_state', {}):
        report = st.session_state.get('maturity_report')
    if not report:
        return
    cost = getattr(report, 'monetary_cost_of_inaction', None)
    amount = getattr(cost, 'amount_gbp', None) if cost else None
    if amount is None:
        return
    st.subheader("Cost of Inaction (GBP)")
    st.write(f"Estimated annual cost of inaction: £{amount:,.2f}")
    rationale = getattr(cost, 'rationale', None)
    if rationale:
        st.write(rationale)

# --- UI CONFIGURATION ---
st.set_page_config(page_title="Security Use Case Generator", layout="wide")
validate_platform_config() # Fails fast if keys are missing

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
        mdr_provider = st.selectbox("Current MDR / SOC Provider", ["None", "Sophos MDR", "Sophos MDR Plus", "Microsoft Defender Experts", "CrowdStrike Falcon Complete", "Arctic Wolf", "Expel", "Red Canary", "Local Partner SOC", "Other"])
        
        endpoint = st.selectbox("Endpoint Security Vendor", ["Sophos", "Microsoft Defender", "CrowdStrike", "SentinelOne", "Trend Micro", "Symantec", "N-able", "Other"])
        
        # --- NEW FIELD: ENDPOINT CAPABILITY ---
        endpoint_posture = st.selectbox("Endpoint Capability (Licensing)", [
            "Legacy AV Only (Signatures/Heuristics)", 
            "Next-Gen AV (NGAV / Deep Learning)", 
            "EDR Deployed (Endpoint Detection & Response)", 
            "XDR Deployed (Cross-Domain Telemetry)",
            "Full ZTNA / Device Control Enforced"
        ], index=2)
        
        firewall = st.selectbox("Firewall Vendor", ["Fortinet", "Palo Alto", "Cisco", "Sophos", "Check Point", "SonicWall", "Other"])

        remote_access = st.selectbox("Remote Access Strategy", [
            "None / Cloud Only", 
            "Legacy VPN (Client-based)", 
            "Always-On VPN", 
            "Zero Trust Network Access (ZTNA) / SASE"
        ], index=1)
        
        saas_backup = st.selectbox("M365 / SaaS Backup", [
            "None (Relying on Microsoft/Google)", 
            "Basic Retention Policies Only", 
            "Dedicated Third-Party SaaS Backup"
        ], index=0)
        
    with col3:
        st.subheader("Cloud & Identity")
        identity = st.selectbox("Identity Provider", ["Microsoft Entra ID (Azure AD)", "Okta", "On-Prem Active Directory", "None"])
        m365_license = st.selectbox("Microsoft 365 Licensing", ["None / On-Prem Only", "M365 Business Premium", "Microsoft 365 E5", "Office 365 E3 / M365 E3"])
        # Email security: prefer Mimecast or Barracuda; remove Sophos as a recommended option
        email = st.selectbox("Email Security", ["Mimecast", "Proofpoint", "Microsoft Defender", "Barracuda", "Other"])
        cloud_env = st.multiselect("Cloud Infrastructure", ["AWS", "Microsoft Azure", "GCP", "Oracle Cloud", "None (Fully On-Prem)"], default=["AWS"])

    st.divider()
    
    ## --- VENDOR BAN LIST ---
    st.markdown("### 🚫 Ban Vendors from Recommendations")
    st.caption("Select any vendors your customer has explicitly ruled out. They will not appear in any generated recommendations or reports.")
    all_vendors = sorted(set(
        item["vendor"] for category in PLANET_IT_PORTFOLIO.values() for item in category
    ))
    banned_vendors = st.multiselect(
        "Excluded Vendors",
        options=all_vendors,
        default=[],
        help="Select vendors to exclude from all recommendations and LLM-generated content."
    )
    
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
        advanced_controls = st.multiselect(
            "Advanced Adaptive Controls (Pillar 3)", 
            ["Zero-Trust Architecture (ZTA)", "Network Microsegmentation", "SOAR / Automated Remediation", "User Behaviour Analytics (UBA)", "Automated DR Orchestration", "Deception Tech (Honeypots)"]
        )
        validation_notes = st.text_area("Validation Notes")

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
        ir_readiness = st.selectbox("Incident Response (IR) Readiness", [
            "No Formal Plan", 
            "Documented IR Plan (Untested)", 
            "Tested IR Plan with Active Retainer"
        ], index=0)
        
        ir_retainer = st.selectbox("Elite IR Retainer / DFIR Provider", [
            "None",
            "Sophos MDR Plus / Incident Response",
            "Microsoft DART",
            "CrowdStrike Falcon Complete IR",
            "Mandiant / Google IR",
            "Unit 42 (Palo Alto)",
            "Kroll Cyber Risk",
            "Secureworks IR",
            "Rapid7 IR",
            "Other"
        ], index=0)

    st.divider()
    
    ## --- SECURITY CULTURE CALCULATOR ---
    st.markdown("### 🧮 Security Culture Calculator")
    
    calc_col1, calc_col2, calc_col3 = st.columns(3)
    
    with calc_col1:
        q1 = st.radio("1. Phishing Simulations", ["Never", "Annually", "Monthly / Quarterly"])
    with calc_col2:
        q2 = st.radio("2. Security Training", ["None", "Annual Compliance Video", "Continuous with active coaching"])
    with calc_col3:
        q3 = st.radio("3. Endpoint Privileges", ["Most users are Local Admins", "Only IT/Devs are Local Admins", "Zero Trust (No Local Admins/LAPS)"])
    
    # Derive MFA score from the Operational Telemetry mfa_status field (avoids duplicate question)
    mfa_score_map = {"None": 0, "Privileged Accounts Only": 1, "Universal / Conditional Access": 3}
    mfa_score = mfa_score_map.get(mfa_status, 0)
    
    culture_score = 0
    culture_score += mfa_score
    culture_score += {"Never": 0, "Annually": 1, "Monthly / Quarterly": 2}[q1]
    culture_score += {"None": 0, "Annual Compliance Video": 1, "Continuous with active coaching": 2}[q2]
    culture_score += {"Most users are Local Admins": 0, "Only IT/Devs are Local Admins": 1, "Zero Trust (No Local Admins/LAPS)": 2}[q3]

    if culture_score <= 4:
        savviness_label = "Pillar 1: Reactive Culture"
    elif culture_score <= 7:
        savviness_label = "Pillar 2: Proactive Culture"
    else:
        savviness_label = "Pillar 3: Adaptive Culture"

    savviness_profiles = {
        "Pillar 1: Reactive Culture": "Currently developing baseline awareness. Focus should be placed on universally enforcing MFA and restricting local administrator privileges.",
        "Pillar 2: Proactive Culture": "Strong baseline awareness. Users complete regular training and foundational identity controls are actively enforced.",
        "Pillar 3: Adaptive Culture": "Highly optimised, zero-trust mindset. Users actively report threats, supported by strict access controls and continuous coaching."
    }
    
    st.info(f"**Calculated Score: {culture_score}/8** | Result: {savviness_label} — *{savviness_profiles[savviness_label]}*")
    savviness = f"{savviness_label} - {savviness_profiles[savviness_label]}"

# --- GLOBAL INPUTS DICTIONARY ---
client_inputs = {
    "customer_name": customer_name, 
    "consultant_name": consultant_name, 
    "industry": industry, 
    "users": users, 
    "savviness": savviness, 
    "endpoints": endpoints, 
    "servers": servers, 
    "remote_access": remote_access,
    "saas_backup": saas_backup,
    "ir_readiness": ir_readiness,
    "operating_systems": ", ".join(operating_systems) if operating_systems else "None", 
    "critical_infra": critical_infra, 
    "mdr_provider": mdr_provider, 
    "endpoint": endpoint, 
    "endpoint_posture": endpoint_posture, # NEW LINE
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
    "rto": rto,
    "advanced_controls": ", ".join(advanced_controls) if advanced_controls else "None",
    "ir_retainer": ir_retainer,
    "banned_vendors": banned_vendors
}

st.session_state['client_inputs'] = client_inputs
cached_customer_name = st.session_state['client_inputs'].get('customer_name', 'Client')

st.divider()

# --- WORKFLOW ROUTING ---
if st.session_state['workflow'] == "🔥 Tactical Threat Simulator":
    st.header("Tactical Threat Simulator")
    
    if st.button("Generate Threat Scenario", type="primary"):
        # Clear any cached export bytes from previous runs
        for key in ['pdf_bytes', 'threat_docx_bytes', 'mdr_case']:
            st.session_state.pop(key, None)
        
        with st.spinner("Simulating Attack & MDR Response..."):
            provider_flag = "ollama" if "Local" in st.session_state['ai_engine'] else "azure"
            client = LLMEngine.get_client(provider_flag)
            deployment = get_optimal_deployment_name(provider_flag)
            
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
                
                # --- STREAMING MDR CASE GENERATION ---
                mdr_prompt = build_mdr_case_prompt(st.session_state['client_inputs'], scenario_obj.narrative)
                mdr_placeholder = st.empty()
                accumulated = ""
                for token in LLMEngine.generate_text_report_streaming(client, deployment, SYSTEM_PERSONA, mdr_prompt, temperature=0.7):
                    accumulated += token
                    mdr_placeholder.markdown(f"### 📋 MDR Case Log (Streaming...)\n\n{accumulated}▌")
                mdr_placeholder.markdown(f"### 📋 MDR Case Log\n\n{accumulated}")
                st.session_state['mdr_case'] = accumulated
                
                # Exports are now lazy — generated on first download click
                st.success("Threat Simulation Generated Successfully.")
            else:
                st.error("Engine failed to generate the scenario.")
        
    if st.session_state.get('scenario_obj'):
        st.subheader("📥 Export Deliverables")
        dl_threat_col1, dl_threat_col2 = st.columns(2)
        with dl_threat_col1:
            pdf_data = get_threat_pdf_bytes()
            if pdf_data:
                st.download_button(
                    "📄 Download Threat Simulation (PDF)", 
                    data=pdf_data, 
                    file_name=f"{cached_customer_name.replace(' ', '_')}_Threat_Simulation.pdf", 
                    mime="application/pdf"
                )
        with dl_threat_col2:
            docx_data = get_threat_docx_bytes()
            if docx_data:
                st.download_button(
                    "📄 Download Threat Report (Word)", 
                    data=docx_data, 
                    file_name=f"{cached_customer_name.replace(' ', '_')}_Threat_Report.docx", 
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

elif st.session_state['workflow'] == "📈 vCISO Assessment":
    st.header("vCISO Assessment")
    
    if st.button("Generate vCISO Roadmap", type="primary"):
        with st.spinner("Compiling vCISO Assessment..."):
            provider_flag = "ollama" if "Local" in st.session_state['ai_engine'] else "azure"
            client = LLMEngine.get_client(provider_flag)
            deployment = get_optimal_deployment_name(provider_flag)
            
            vciso_prompt = build_vciso_prompt(st.session_state['client_inputs'])
            vciso_obj = LLMEngine.generate_structured_report(client, deployment, SYSTEM_PERSONA, vciso_prompt, MaturityReport)
            
            if vciso_obj:
                st.session_state['vciso_obj'] = vciso_obj
                # Clear any cached export bytes from previous runs
                for key in ['vciso_docx_bytes']:
                    st.session_state.pop(key, None)
                st.success("vCISO Roadmap Generated Successfully.")
            else:
                st.error("Engine failed to generate the roadmap.")
        
    if st.session_state.get('vciso_obj'):
        st.subheader("📥 Export Deliverables")
        docx_data = get_vciso_docx_bytes()
        if docx_data:
            st.download_button(
                "📄 Download vCISO Report (Word)", 
                data=docx_data, 
                file_name=f"{cached_customer_name.replace(' ', '_')}_vCISO_Report.docx", 
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
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
            # Additional cost & partnership details (optional, enriched by LLM)
            if getattr(vciso, 'monetary_cost_of_inaction', None):
                mv = vciso.monetary_cost_of_inaction
                if mv:
                    amount = getattr(mv, 'amount_gbp', None)
                    src = getattr(mv, 'source', None)
                    rationale = getattr(mv, 'rationale', None)
                    parts = []
                    if amount is not None:
                        parts.append(f"GBP {amount:,.2f}")
                    if src:
                        parts.append(f"Source: {src}")
                    if rationale:
                        parts.append(f"Rationale: {rationale}")
                    st.markdown("### Monetary Cost of Inaction (GBP)")
                    st.write(" | ".join(parts))
            if getattr(vciso, 'partnership_outline', None):
                outline = vciso.partnership_outline
                if outline:
                    st.markdown("### Partnership Outline (Co-/Fully Managed)")
                    st.write(outline)
            if getattr(vciso, 'microsoft_healthchecks_recommendations', None):
                rec = vciso.microsoft_healthchecks_recommendations
                if rec:
                    st.markdown("### Microsoft Healthchecks & Hardening")
                    st.write(rec)
                
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
                st.markdown(f"#### {phase.phase_title}: {phase.primary_objective}")
                for milestone in phase.milestones:
                    st.markdown(f"- {milestone}")
                st.markdown(f"**Value Delivered:** {phase.business_value_delivered}")
                st.markdown(f"**Resources:** {phase.resource_requirements}")
                st.divider()
        # Display Cost of Inaction (GBP) if available in VCISO maturity report
        _display_cost_of_inaction_section()

st.divider()
st.markdown(
    "<div style='text-align: center; color: #23506A; font-size: 0.8rem;'>"
    f"Security Use Case & vCISO Generator — v{APP_VERSION}"
    "</div>",
    unsafe_allow_html=True
)
st.markdown(
    "<div style='text-align: center; color: #23506A; font-size: 0.7rem; margin-top: 4px;'>"
    "&copy; 2026 Bradley Collis. All rights reserved."
    "</div>",
    unsafe_allow_html=True
)
