import streamlit as st
import os
import random
import time
import re as _re
from core import LLMEngine
from prompts import build_scenario_prompt, build_mdr_case_prompt, build_maturity_prompt, ScenarioReport, MaturityReport, SYSTEM_PERSONA
from data import FULLY_MANAGED_URL, CO_MANAGED_URL
from data import MDR_COMPARISON, choose_mdr_recommendation
from data import ATTACK_VECTORS, SIMULATED_OSINT
from export import create_pdf, create_maturity_docx, create_threat_docx
from catalog import PLANET_IT_PORTFOLIO
from config import get_config, validate_config, ConfigKey

_SANITISE_REPLACEMENTS = [
    (_re.compile(r'["]{3,}'), '"'),
    (_re.compile(r"'{3,}"), "'"),
    (_re.compile(r'`{3,}'), '`'),
    (_re.compile(r'(?:\r?\n){3,}'), '\n\n'),
]


def _sanitise_input(value):
    """Strip prompt injection vectors from a single input string.

    Removes triple-quotes, triple-backticks, and excessive newlines that
    could be used to break out of the LLM prompt context.  Returns the
    sanitised string (or the original if it is not a string).
    """
    if not isinstance(value, str):
        return value
    sanitised = value
    for pattern, replacement in _SANITISE_REPLACEMENTS:
        sanitised = pattern.sub(replacement, sanitised)
    return sanitised.strip()


def _sanitise_client_inputs(inputs: dict) -> dict:
    """Sanitise all string values in the client_inputs dictionary."""
    return {
        k: _sanitise_input(v) if isinstance(v, str) else v
        for k, v in inputs.items()
    }

def _safe_get(item, key, default=None):
    """Access a key from a dict or attribute from an object safely."""
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)

# --- VERSION TRACKER ---
with open(os.path.join(os.path.dirname(__file__), "VERSION"), "r") as f:
    APP_VERSION = f.read().strip()

def validate_platform_config():
    """Validates that necessary Azure secrets exist before runtime."""
    try:
        validate_config("azure")
    except ValueError as e:
        st.warning(f"⚠️ {e}")

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
        managed_status = inputs.get('managed_service_status', 'None')
        co_units = inputs.get('co_managed_units', 0)

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

        # Managed service status acknowledgement (non-inflationary, advisory only)
        if isinstance(managed_status, str):
            if managed_status == "Planet IT Fully Managed (Active)":
                recs.append("**Existing Planet IT Fully Managed engagement:** Alignment to the Planet stack is likely, but not guaranteed. Prioritise configuration verification, health checks, and optimisation over duplicative procurement.")
            elif managed_status == "Planet IT Co-Managed (Active)":
                try:
                    units = int(co_units or 0)
                except Exception:
                    units = 0
                if units > 0:
                    recs.append("**Co-Managed Entitlements:** Consider executing priority hardening tasks via existing co‑managed service units where appropriate. Treat as entitlements subject to account validation.")
                else:
                    recs.append("**Co-Managed Operations:** Acknowledge the co‑managed model and explore whether service units are available to accelerate remediation without net‑new spend.")
            elif isinstance(managed_status, str) and managed_status.startswith("Other MSP"):
                recs.append("**Existing Third‑Party MSP:** Maintain awareness of current MSP responsibilities. Avoid redundant managed‑support recommendations; propose an optional migration path to Planet IT only if it provides clear value.")

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
            import logging
            logging.getLogger(__name__).error("PDF export failed: %s", e, exc_info=True)
            st.error("PDF export failed. Please try regenerating the report.")
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
            import logging
            logging.getLogger(__name__).error("Word export failed: %s", e, exc_info=True)
            st.error("Word export failed. Please try regenerating the report.")
    return st.session_state.get('threat_docx_bytes')

def get_maturity_docx_bytes():
    """Lazy-generate and cache Cybersecurity Maturity Assessment Word Doc bytes."""
    if st.session_state.get('maturity_docx_bytes') is None and st.session_state.get('maturity_obj'):
        # Re-attach threat scenarios from session state (survives pickle round-trip)
        ts_data = st.session_state.get('maturity_threat_scenarios')
        if ts_data is not None:
            st.session_state['maturity_obj'].threat_scenarios = ts_data
        try:
            st.session_state['maturity_docx_bytes'] = create_maturity_docx(
                st.session_state['client_inputs'], 
                st.session_state['maturity_obj']
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("Maturity Word export failed: %s", e, exc_info=True)
            st.error("Maturity report export failed. Please try regenerating the report.")
    return st.session_state.get('maturity_docx_bytes')

def _display_cost_of_inaction_section():
    """Safely render the GBP cost of inaction if available in the current report."""
    report = None
    if 'maturity_report' in getattr(st, 'session_state', {}):
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

# Inject Content Security Policy header via meta tag (static string, no user input)
_CSP_META = (
    '<meta http-equiv="Content-Security-Policy" '
    'content="default-src \'self\'; '
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "script-src 'self' 'unsafe-eval' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "connect-src 'self' https://*.azure.com https://*.openai.azure.com; "
    'frame-ancestors \'none\';">'
)
st.markdown(_CSP_META, unsafe_allow_html=True)
validate_platform_config() # Fails fast if keys are missing
# [PLANET BRANDING LOAD] Inject branding palette if provided (Azure/Env based)
try:
    from config import get_planet_branding_palette
    _palette = get_planet_branding_palette()
    if _palette:
        brand_css = (
            "<style>"
            ":root {"
            f"  --primary-color: {_palette['primaryColor']};"
            f"  --background-color: {_palette['backgroundColor']};"
            f"  --secondary-background-color: {_palette['secondaryBackgroundColor']};"
            f"  --text-color: {_palette['textColor']};"
            "}"
            "</style>"
        )
        st.markdown(brand_css, unsafe_allow_html=True)
except Exception:
    pass

# --- SIDEBAR & ENGINE CONFIGURATION ---
with st.sidebar:
    st.markdown("## 🛡️ Advisory Engine")
    
    # Engine is strictly Azure (Ollama support removed per July 2026 hardening)
    st.session_state['ai_engine'] = "azure"
    
    st.divider()
    
    workflow = st.radio(
        "Select Workflow:", 
        options=["📈 Cybersecurity Maturity Assessment", "🔥 Tactical Threat Simulator"], 
        index=0
    )
    st.session_state['workflow'] = workflow
    
    st.divider()

    # Threat Scenarios in Maturity Assessment toggle (non-disruptive) for ACT MODE wiring
    if workflow == "📈 Cybersecurity Maturity Assessment":
        enable_threats = st.checkbox("Enable Threat Scenarios in Maturity Assessment", value=True)
        st.session_state['enable_threat_scenarios_in_maturity'] = enable_threats

# --- MAIN PAGE HEADER ---
st.title("Security Use Case & Cybersecurity Maturity Assessment Generator")

with st.expander("Profile: Export / Import", expanded=False):
    import json as _json
    col_e1, col_e2 = st.columns([1, 1])
    # Export uses the sanitised, canonical client_inputs if available
    export_profile = st.session_state.get('client_inputs', {})
    file_customer_name = st.session_state.get('client_inputs', {}).get('customer_name', 'Client')
    with col_e1:
        if export_profile:
            st.download_button(
                "⬇️ Export current options (.json)",
                data=_json.dumps({"version": APP_VERSION, "profile": export_profile}, ensure_ascii=False, indent=2),
                file_name=f"{file_customer_name.replace(' ', '_')}_options.json",
                mime="application/json"
            )
        else:
            st.info("Provide inputs to enable export.")
    with col_e2:
        uploaded = st.file_uploader("Import options (.json)", type=["json"])
        if uploaded is not None:
            try:
                raw = uploaded.read()
                data = _json.loads(raw.decode("utf-8")) if isinstance(raw, (bytes, bytearray)) else _json.loads(raw)
                profile = data.get("profile") if isinstance(data, dict) and "profile" in data else data
                if not isinstance(profile, dict):
                    st.error("Invalid file format: expected a JSON object with a 'profile' object or a flat object of fields.")
                else:
                    # Minimal validation: ensure required fields exist
                    required_keys = ["customer_name", "industry", "users"]
                    if not all(k in profile for k in required_keys):
                        st.warning("Profile loaded, but some keys are missing. Defaults will be used where absent.")
                    st.session_state['_imported_profile'] = profile
                    st.session_state['use_imported_profile'] = True
                    st.session_state['use_test_data'] = False
                    st.success("Profile imported. Applying to UI...")
                    st.rerun()
            except Exception as e:
                st.error(f"Failed to import profile: {e}")

# --- DEV FLAG (computed early; UI moved to bottom) ---
dev = st.session_state.get('use_test_data', False) or st.session_state.get('use_imported_profile', False)

TEST_DATA = {
    "customer_name": "Acme Corp",
    "consultant_name": "Jane Doe",
    "industry": "Technology",
    "users": 500,
    "critical_infra": "Patient Records Database",
    "endpoints": 600,
    "servers": 50,
    "operating_systems": ["Windows 10/11", "Windows Server"],
    "mdr_provider": "Sophos MDR",
    "endpoint": "Sophos",
    "endpoint_posture": "EDR Deployed (Endpoint Detection & Response)",
    "firewall": "Fortinet",
    "remote_access": "Legacy VPN (Client-based)",
    "saas_backup": "None (Relying on Microsoft/Google)",
    "identity": "Microsoft Entra ID (Azure AD)",
    "m365_license": "M365 Business Premium",
    "email": "Mimecast",
    "cloud_env": ["AWS"],
    "in_house_team": "No",
    "pentest_status": "Annual",
    "vuln_scanning": "Monthly Authenticated",
    "public_web_apps": False,
    "compliance": ["ISO 27001", "Cyber Essentials"],
    "physical_locations": 3,
    "advanced_controls": [],
    "validation_notes": "",
    "context_notes": "",
    "mfa_status": "Privileged Accounts Only",
    "patching": "Manual / Ad-hoc",
    "backups": "On-Premise Only",
    "insurance": "None",
    "rto": "12-24 Hours",
    "ir_readiness": "No Formal Plan",
    "ir_retainer": "None",
    "managed_service_status": "None (No managed service in place)",
    "co_managed_units": 0,
    "partnership_type": "Fully Managed",
    "banned_vendors": [],
}

# Apply imported profile override for UI defaults
if st.session_state.get('use_imported_profile') and st.session_state.get('_imported_profile'):
    TEST_DATA = st.session_state['_imported_profile']

# --- UI INPUTS ---
# [Moved] Profile: Export / Import expander relocated after inputs are initialised to avoid NameError

st.divider()
with st.expander("Customer Estate & Engagement Profile", expanded=True):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Organisational Profile")
        customer_name = st.text_input("Customer Name", value=(TEST_DATA['customer_name'] if dev else ""), placeholder="e.g., Acme Corp")
        consultant_name = st.text_input("Consultant Name", value=(TEST_DATA['consultant_name'] if dev else ""), placeholder="e.g., Jane Doe")
        industry_options = [
            "Select Industry...",
            "Healthcare",
            "Finance",
            "Manufacturing",
            "Retail & eCommerce",
            "Technology",
            "Education",
            "Legal",
            "Local Government",
            "Central Government",
            "Non-profit / Charity",
            "Energy & Utilities",
            "Construction",
            "Logistics & Supply Chain",
            "Media & Entertainment",
            "Hospitality & Leisure",
            "Pharmaceuticals & Life Sciences",
            "Professional Services",
            "Real Estate & Facilities",
            "Transportation",
            "Aviation",
            "Defence & Aerospace",
            "Critical National Infrastructure (CNI)",
            "Insurance",
            "Telecommunications",
            "Automotive",
            "Agriculture & Food",
            "Mining & Natural Resources",
            "Other",
        ]
        industry = st.selectbox("Industry", industry_options, index=(industry_options.index(TEST_DATA['industry']) if dev else 0), help="Example: Technology")
        users = st.number_input("Headcount", min_value=0, value=(TEST_DATA['users'] if dev else 0), help="Example: 500")
        critical_infra = st.text_input("Crown Jewels", value=(TEST_DATA['critical_infra'] if dev else ""), placeholder="e.g., Patient Records Database")
        
    with col2:
        st.subheader("Technology Stack")
        endpoints = st.number_input("Number of Endpoints", min_value=0, value=(TEST_DATA['endpoints'] if dev else 0), help="Example: 600")
        servers = st.number_input("Number of Servers", min_value=0, value=(TEST_DATA['servers'] if dev else 0), help="Example: 50")
        operating_systems = st.multiselect("Operating Systems in Use", ["Windows 10/11", "Windows Server", "macOS", "Linux", "ChromeOS"], default=(TEST_DATA['operating_systems'] if dev else []), help="Example: Windows 10/11, Windows Server")
        mdr_options = ["Select MDR / SOC Provider...", "None", "Sophos MDR", "Sophos MDR Plus", "Microsoft Defender Experts", "CrowdStrike Falcon Complete", "Arctic Wolf", "Expel", "Red Canary", "Local Partner SOC", "Other"]
        mdr_provider = st.selectbox("Current MDR / SOC Provider", mdr_options, index=(mdr_options.index(TEST_DATA['mdr_provider']) if dev else 0), help="Example: Sophos MDR")
        
        endpoint_options = ["Select Endpoint Vendor...", "Sophos", "Microsoft Defender", "CrowdStrike", "SentinelOne", "Trend Micro", "Symantec", "N-able", "Other"]
        endpoint = st.selectbox("Endpoint Security Vendor", endpoint_options, index=(endpoint_options.index(TEST_DATA['endpoint']) if dev else 0), help="Example: Sophos")
        
        # --- NEW FIELD: ENDPOINT CAPABILITY ---
        endpoint_posture_options = ["Select Endpoint Capability...", "Legacy AV Only (Signatures/Heuristics)", "Next-Gen AV (NGAV / Deep Learning)", "EDR Deployed (Endpoint Detection & Response)", "XDR Deployed (Cross-Domain Telemetry)", "Full ZTNA / Device Control Enforced"]
        endpoint_posture = st.selectbox("Endpoint Capability (Licensing)", endpoint_posture_options, index=(endpoint_posture_options.index(TEST_DATA['endpoint_posture']) if dev else 0), help="Example: EDR Deployed (Endpoint Detection & Response)")
        
        firewall_options = ["Select Firewall Vendor...", "Fortinet", "Palo Alto", "Cisco", "Sophos", "Check Point", "SonicWall", "Other"]
        firewall = st.selectbox("Firewall Vendor", firewall_options, index=(firewall_options.index(TEST_DATA['firewall']) if dev else 0), help="Example: Fortinet")

        remote_access_options = ["Select Remote Access Strategy...", "None / Cloud Only", "Legacy VPN (Client-based)", "Always-On VPN", "Zero Trust Network Access (ZTNA) / SASE"]
        remote_access = st.selectbox("Remote Access Strategy", remote_access_options, index=(remote_access_options.index(TEST_DATA['remote_access']) if dev else 0), help="Example: Legacy VPN (Client-based)")
        
        saas_backup_options = ["Select SaaS Backup...", "None (Relying on Microsoft/Google)", "Basic Retention Policies Only", "Dedicated Third-Party SaaS Backup"]
        saas_backup = st.selectbox("M365 / SaaS Backup", saas_backup_options, index=(saas_backup_options.index(TEST_DATA['saas_backup']) if dev else 0), help="Example: None (Relying on Microsoft/Google)")
        
    with col3:
        st.subheader("Cloud & Identity")
        identity_options = ["Select Identity Provider...", "Microsoft Entra ID (Azure AD)", "Okta", "On-Prem Active Directory", "None"]
        identity = st.selectbox("Identity Provider", identity_options, index=(identity_options.index(TEST_DATA['identity']) if dev else 0), help="Example: Microsoft Entra ID (Azure AD)")
        m365_license_options = ["Select Microsoft 365 Licensing...", "None / On-Prem Only", "M365 Business Premium", "Microsoft 365 E5", "Office 365 E3 / M365 E3"]
        m365_license = st.selectbox("Microsoft 365 Licensing", m365_license_options, index=(m365_license_options.index(TEST_DATA['m365_license']) if dev else 0), help="Example: M365 Business Premium")
        # Email security: prefer Mimecast or Barracuda; remove Sophos as a recommended option
        email_options = ["Select Email Security...", "Mimecast", "Proofpoint", "Microsoft Defender", "Barracuda", "Other"]
        email = st.selectbox("Email Security", email_options, index=(email_options.index(TEST_DATA['email']) if dev else 0), help="Example: Mimecast")
        cloud_env = st.multiselect("Cloud Infrastructure", ["AWS", "Microsoft Azure", "GCP", "Oracle Cloud", "None (Fully On-Prem)"], default=(TEST_DATA['cloud_env'] if dev else []), help="Example: AWS")

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
        default=(TEST_DATA.get('banned_vendors', []) if dev else []),
        help="Select vendors to exclude from all recommendations and LLM-generated content."
    )
    
    st.divider()
    st.subheader("Operations & Validation")
    col_ops1, col_ops2 = st.columns(2)
    with col_ops1:
        in_house_options = ["Select Internal SOC Team...", "No", "Yes (9-to-5)", "Yes (24/7)"]
        in_house_team = st.selectbox("Internal SOC Team", in_house_options, index=(in_house_options.index(TEST_DATA['in_house_team']) if dev else 0), help="Example: No")
        pentest_options = ["Select Penetration Testing Cadence...", "None", "Annual", "Bi-Annual", "Quarterly"]
        pentest_status = st.selectbox("Penetration Testing", pentest_options, index=(pentest_options.index(TEST_DATA['pentest_status']) if dev else 0), help="Example: Annual")
        vuln_options = ["Select Vulnerability Scanning...", "None", "Monthly Authenticated", "Quarterly External", "Continuous"]
        vuln_scanning = st.selectbox("Vuln Scanning", vuln_options, index=(vuln_options.index(TEST_DATA['vuln_scanning']) if dev else 0), help="Example: Monthly Authenticated")
        public_web_apps = st.checkbox("Host Public Web Apps", value=(TEST_DATA['public_web_apps'] if dev else False))
    with col_ops2:
        compliance = st.multiselect("Target Compliance", ["ISO 27001", "Cyber Essentials", "Cyber Essentials Plus", "PCI DSS", "HIPAA", "NIST CSF"], default=(TEST_DATA['compliance'] if dev else []), help="Example: ISO 27001, Cyber Essentials")
        physical_locations = st.number_input("Physical Locations", min_value=0, value=(TEST_DATA['physical_locations'] if dev else 0), help="Example: 3")
        advanced_controls = st.multiselect(
            "Advanced Adaptive Controls (Pillar 3)", 
            ["Zero-Trust Architecture (ZTA)", "Network Microsegmentation", "SOAR / Automated Remediation", "User Behaviour Analytics (UBA)", "Automated DR Orchestration", "Deception Tech (Honeypots)"],
            default=(TEST_DATA['advanced_controls'] if dev else [])
        )
        validation_notes = st.text_area("Validation Notes", value=(TEST_DATA['validation_notes'] if dev else ""), placeholder="e.g., Customer requires ISO 27001 alignment by Q4")
        context_notes = st.text_area("Consultant Context (LLM-visible)", value=(TEST_DATA['context_notes'] if dev else ""), placeholder="e.g., Nuances, constraints, or messaging to incorporate across the report")

    st.divider()

## --- PARTNERSHIP GOVERNANCE ---
st.markdown("### 🔗 Partnership Governance")
_pt_opts = ["Fully Managed", "Co-Managed"]
partnership_type = st.radio("Partnership Governance Model", _pt_opts, index=(_pt_opts.index(TEST_DATA['partnership_type']) if dev else 0))
st.session_state['partnership_type'] = partnership_type
if partnership_type == "Fully Managed":
    st.markdown(f"Official URL: {FULLY_MANAGED_URL}")
else:
    st.markdown(f"Official URL: {CO_MANAGED_URL}")

# --- Managed Service Status (Current State) ---
managed_status_options = [
    "None (No managed service in place)",
    "Planet IT Fully Managed (Active)",
    "Planet IT Co-Managed (Active)",
    "Other MSP Fully Managed (Active)",
    "Other MSP Co-Managed (Active)",
    "In Transition / Evaluating",
]
managed_service_status = st.selectbox(
    "Current Managed Service Status",
    managed_status_options,
    index=(managed_status_options.index(TEST_DATA['managed_service_status']) if dev else 0),
    help="Capture current support so recommendations and governance sections reflect reality."
)
co_units_val = 0
if "Co-Managed" in managed_service_status:
    co_units_val = st.number_input(
        "Co-Managed: Service Units Available (estimate)",
        min_value=0, value=(TEST_DATA['co_managed_units'] if dev else 0),
        help="If applicable, an indicative balance that may be exchanged for services."
    )
st.session_state['managed_service_status'] = managed_service_status
st.session_state['co_managed_units'] = co_units_val

## --- OPERATIONAL & RISK TELEMETRY ---
st.markdown("### ⚙️ Operational & Risk Telemetry")
    
op_col1, op_col2 = st.columns(2)
    
with op_col1:
    mfa_options = ["Select MFA Enforcement...", "None", "Privileged Accounts Only", "Universal / Conditional Access"]
    mfa_status = st.selectbox("MFA Enforcement", mfa_options, index=(mfa_options.index(TEST_DATA['mfa_status']) if dev else 0), help="Example: Privileged Accounts Only")
    patching_options = ["Select Patch Management...", "Manual / Ad-hoc", "Automated (OS Only)", "Automated (OS & Third-Party)"]
    patching = st.selectbox("Patch Management", patching_options, index=(patching_options.index(TEST_DATA['patching']) if dev else 0), help="Example: Manual / Ad-hoc")
    backup_options = ["Select Backup Strategy...", "No Formal Backups", "On-Premise Only", "Cloud/Offsite (Standard)", "Immutable / Air-Gapped"]
    backups = st.selectbox("Backup Strategy", backup_options, index=(backup_options.index(TEST_DATA['backups']) if dev else 0), help="Example: On-Premise Only")
    
with op_col2:
    insurance_options = ["Select Cyber Insurance Status...", "None", "Exploring Requirements", "Active Policy"]
    insurance = st.selectbox("Cyber Insurance Status", insurance_options, index=(insurance_options.index(TEST_DATA['insurance']) if dev else 0), help="Example: None")
    rto_options = ["Select Downtime Tolerance...", "< 4 Hours (Critical)", "12-24 Hours", "48+ Hours"]
    rto = st.selectbox("Downtime Tolerance", rto_options, index=(rto_options.index(TEST_DATA['rto']) if dev else 0), help="Example: 12-24 Hours")
    ir_readiness_options = ["Select Incident Response (IR) Readiness...", "No Formal Plan", "Documented IR Plan (Untested)", "Tested IR Plan with Active Retainer"]
    ir_readiness = st.selectbox("Incident Response (IR) Readiness", ir_readiness_options, index=(ir_readiness_options.index(TEST_DATA['ir_readiness']) if dev else 0), help="Example: No Formal Plan")
    
    ir_retainer_options = ["Select Elite IR Retainer / DFIR Provider...", "None", "Sophos MDR Plus / Incident Response", "Microsoft DART", "CrowdStrike Falcon Complete IR", "Mandiant / Google IR", "Unit 42 (Palo Alto)", "Kroll Cyber Risk", "Secureworks IR", "Rapid7 IR", "Other"]
    ir_retainer = st.selectbox("Elite IR Retainer / DFIR Provider", ir_retainer_options, index=(ir_retainer_options.index(TEST_DATA['ir_retainer']) if dev else 0), help="Example: None")

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
def _norm(v, unk="Unknown"):
    try:
        return v if (v and not str(v).startswith("Select")) else unk
    except Exception:
        return unk

client_inputs = {
    "customer_name": customer_name, 
    "consultant_name": consultant_name, 
    "industry": _norm(industry), 
    "users": users, 
    "savviness": savviness, 
    "endpoints": endpoints, 
    "servers": servers, 
    "remote_access": _norm(remote_access),
    "saas_backup": _norm(saas_backup, "None (Relying on Microsoft/Google)"),
    "ir_readiness": _norm(ir_readiness),
    "operating_systems": ", ".join(operating_systems) if operating_systems else "None", 
    "critical_infra": critical_infra, 
    "mdr_provider": _norm(mdr_provider, "None"), 
    "endpoint": _norm(endpoint), 
    "endpoint_posture": _norm(endpoint_posture), # NEW LINE
    "firewall": _norm(firewall), 
    "identity": _norm(identity), 
    "m365_license": _norm(m365_license, "None / On-Prem Only"), 
    "email": _norm(email), 
    "cloud_env": ", ".join(cloud_env) if cloud_env else "None (Fully On-Prem)",
    "in_house_team": _norm(in_house_team), 
    "physical_locations": physical_locations, 
    "public_web_apps": public_web_apps,
    "compliance": ", ".join(compliance) if compliance else "None",
    "pentest_status": _norm(pentest_status), 
    "vuln_scanning": _norm(vuln_scanning), 
    "validation_notes": validation_notes,
    "context_notes": context_notes,
    "mfa_status": _norm(mfa_status),
    "patching": _norm(patching),
    "backups": _norm(backups),
    "insurance": _norm(insurance, "None"),
    "rto": _norm(rto),
    "advanced_controls": ", ".join(advanced_controls) if advanced_controls else "None",
    "ir_retainer": _norm(ir_retainer, "None"),
    "banned_vendors": banned_vendors,
    "managed_service_status": _norm(st.session_state.get('managed_service_status', 'None'), "None"),
    "co_managed_units": st.session_state.get('co_managed_units', 0),
    "partnership_type": partnership_type
}

import json as _json
_client_hash = _json.dumps(client_inputs, sort_keys=True, default=str)
if st.session_state.get('_client_inputs_hash') != _client_hash:
    st.session_state['client_inputs'] = _sanitise_client_inputs(client_inputs)
    st.session_state['_client_inputs_hash'] = _client_hash
    # Inject reference sample from configuration (tone-only; non-UI)
    try:
        from config import get_reference_sample
        _ref = get_reference_sample()
        if _ref:
            st.session_state['client_inputs']['reference_sample'] = _ref
    except Exception:
        pass
cached_customer_name = st.session_state['client_inputs'].get('customer_name', 'Client')

# [Moved to top] Profile: Export / Import expander removed here to avoid duplication

# --- MDR DECISION ASSIST: Sophos MDR vs Adlumin ---
with st.expander("🧭 MDR Decision Assist (Sophos MDR vs Adlumin)", expanded=False):
    st.caption("Use this guided assistant to differentiate Sophos MDR and Adlumin MDR and generate a context-aware recommendation.")

    # Preference selectors (five decision dimensions)
    col_pref1, col_pref2, col_pref3 = st.columns(3)
    with col_pref1:
        stack_philosophy = st.selectbox(
            "Technology Stack Philosophy",
            ["No preference", "Sophos estate", "Vendor-agnostic"],
            help="Preference for a unified Sophos-led estate or a vendor-agnostic approach."
        )
    with col_pref2:
        response_style = st.selectbox(
            "Response Style",
            ["No preference", "Human-led", "Automation-first"],
            help="Hands-on-keyboard human remediation vs automation-led playbooks."
        )
    with col_pref3:
        transparency = st.selectbox(
            "Transparency & Co-Management",
            ["No preference", "Managed outcomes", "Full SIEM co-managed"],
            help="Outcome-focused SOC vs full, co-managed SIEM access and visibility."
        )

    col_pref4, col_pref5 = st.columns(2)
    with col_pref4:
        compliance_tooling = st.selectbox(
            "Compliance & Built-ins",
            ["No preference", "Separate tools", "Built-in compliance/UEBA"],
            help="Do you require native SIEM/UEBA/compliance reporting in-platform?"
        )
    with col_pref5:
        commercials = st.selectbox(
            "Commercials & TCO",
            ["No preference", "Optimise Sophos estate", "Predictable SIEM-inclusive"],
            help="Optimise an existing Sophos investment or prefer predictable SIEM-inclusive pricing?"
        )

    # Optional hygiene reminder aligned to Capability Mismatch (non-intrusive)
    _mfa = st.session_state['client_inputs'].get('mfa_status', 'Unknown')
    _patch = st.session_state['client_inputs'].get('patching', 'Unknown')
    _bkp = st.session_state['client_inputs'].get('backups', 'Unknown')
    if _mfa in ["None", "Privileged Accounts Only"] or _patch == "Manual / Ad-hoc" or _bkp in ["No Formal Backups", "On-Premise Only"]:
        st.warning("Foundational hygiene gaps detected (MFA, patching, backups). Prioritise remediation before finalising MDR provider selection to avoid Capability Mismatch and inflated costs.")

    # Build preferences and compute recommendation
    prefs = {
        "stack_philosophy": stack_philosophy,
        "response_style": response_style,
        "transparency": transparency,
        "compliance_tooling": compliance_tooling,
        "commercials": commercials,
    }
    rec = choose_mdr_recommendation(prefs, context=st.session_state['client_inputs'])
    # Persist decision for downstream prompt builders
    st.session_state['mdr_decision'] = rec.get('recommendation')
    st.session_state['mdr_decision_rationale'] = rec.get('rationale', [])
    try:
        st.session_state['client_inputs']['mdr_decision'] = st.session_state['mdr_decision']
        st.session_state['client_inputs']['mdr_decision_rationale'] = st.session_state['mdr_decision_rationale']
    except Exception:
        pass

    # Output recommendation and rationale
    if rec.get('recommendation') == 'Tie':
        st.info("Decision outcome: Tie — both providers can fit. Use the comparison below and environmental tie-breakers to decide.")
    elif rec.get('recommendation') == 'Sophos MDR':
        st.success("Recommended: Sophos MDR — aligns best with stated preferences and current environment.")
    else:
        st.success("Recommended: Adlumin MDR — aligns best with stated preferences and current environment.")

    score = rec.get('scorecard', {})
    st.caption(f"Scorecard — Sophos MDR: {score.get('Sophos MDR', 0)} | Adlumin MDR: {score.get('Adlumin MDR', 0)}")
    rationale_lines = rec.get('rationale', [])
    if rationale_lines:
        st.markdown("**Rationale:**")
        st.markdown("\n".join([f"- {r}" for r in rationale_lines]))

    st.divider()
    st.markdown("### Comparison Matrix")
    for cat in MDR_COMPARISON.get('categories', []):
        st.markdown(f"#### {cat.get('title')}")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Sophos MDR**")
            st.markdown("\n".join([f"- {item}" for item in cat.get('sophos', [])]))
        with col_b:
            st.markdown("**Adlumin MDR**")
            st.markdown("\n".join([f"- {item}" for item in cat.get('adlumin', [])]))
    dfw = MDR_COMPARISON.get('decision_framework', [])
    if dfw:
        st.info("\n".join([f"• {line}" for line in dfw]))

        st.divider()

st.divider()


# --- WORKFLOW ROUTING ---
if st.session_state['workflow'] == "🔥 Tactical Threat Simulator":
    st.header("Tactical Threat Simulator")
    
    _now_ts = time.time()
    _cooldown = 30
    _last_gen = st.session_state.get('_last_generation_ts', 0)
    _remaining = max(0, _cooldown - int(_now_ts - _last_gen))
    if _remaining > 0:
        st.info(f"⏳ Cooldown active — generation available in {_remaining} second{'s' if _remaining != 1 else ''}.")
    
    if st.button("Generate Threat Scenario", type="primary", disabled=(_remaining > 0)):
        # Clear any cached export bytes from previous runs
        for key in ['pdf_bytes', 'threat_docx_bytes', 'mdr_case']:
            st.session_state.pop(key, None)
        st.session_state['_last_generation_ts'] = time.time()
        
        with st.spinner("Simulating Attack & MDR Response..."):
            client = LLMEngine.get_client()
            deployment = get_config(ConfigKey.AZURE_DEPLOYMENT, "gpt-4o")
            
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

elif st.session_state['workflow'] == "📈 Cybersecurity Maturity Assessment":
    st.header("Cybersecurity Maturity Assessment")
    
    _now_ts2 = time.time()
    _cooldown2 = 30
    _last_gen2 = st.session_state.get('_last_generation_ts', 0)
    _remaining2 = max(0, _cooldown2 - int(_now_ts2 - _last_gen2))
    if _remaining2 > 0:
        st.info(f"⏳ Cooldown active — generation available in {_remaining2} second{'s' if _remaining2 != 1 else ''}.")
    
    if st.button("Generate Maturity Roadmap", type="primary", disabled=(_remaining2 > 0)):
        st.session_state['_last_generation_ts'] = time.time()
        with st.spinner("Compiling Cybersecurity Maturity Assessment..."):
            client = LLMEngine.get_client()
            deployment = get_config(ConfigKey.AZURE_DEPLOYMENT, "gpt-4o")
            
            maturity_prompt = build_maturity_prompt(st.session_state['client_inputs'])
            maturity_obj = LLMEngine.generate_structured_report(client, deployment, SYSTEM_PERSONA, maturity_prompt, MaturityReport)
            
            if maturity_obj:
                st.session_state['maturity_obj'] = maturity_obj
                # Generate maturity-aligned threat scenario via streaming LLM (mirrors Threat Simulator)
                try:
                    # Build gap summary from domain assessments for the threat prompt
                    gaps_summary = []
                    for domain in getattr(maturity_obj, 'domain_assessments', []):
                        name = getattr(domain, 'domain_name', 'Unknown')
                        critical = getattr(domain, 'critical_gaps', [])
                        if critical:
                            gaps_summary.append(f"  - {name}: {', '.join(critical)}")
                    gap_text = '\n'.join(gaps_summary) if gaps_summary else 'No critical gaps identified.'
                    
                    # Derive attack vector from operational telemetry gaps (prioritised)
                    mfa_status = client_inputs.get('mfa_status', 'Unknown')
                    patching = client_inputs.get('patching', 'Unknown')
                    backups = client_inputs.get('backups', 'Unknown')
                    ir_readiness = client_inputs.get('ir_readiness', 'Unknown')
                    remote_access = client_inputs.get('remote_access', 'Unknown')
                    saas_backup = client_inputs.get('saas_backup', 'Unknown')
                    endpoint_posture = client_inputs.get('endpoint_posture', 'Unknown')
                    savviness = client_inputs.get('savviness', '')
                    endpoint_capability = client_inputs.get('endpoint_posture', 'Unknown')
                    
                    # Compound gap scenario: no MFA + manual patching + no backups = worst case
                    if mfa_status in ['None', 'Privileged Accounts Only'] and patching == 'Manual / Ad-hoc' and backups in ['No Formal Backups', 'On-Premise Only']:
                        attack_vector = "Compound Breach via Phishing + Unpatched VPN + Ransomware — Multi-stage attack exploiting credential theft (no universal MFA), privilege escalation through an unpatched CVE on VPN infrastructure (ad-hoc patch management), culminating in enterprise-wide ransomware deployment against non-immutable backups"
                    # MFA gaps
                    elif mfa_status in ['None']:
                        attack_vector = "Credential Stuffing / Brute-Force Attack — Initial access through automated credential attacks against internet-facing authentication portals without any MFA enforcement. Threat actor exploits known breached credentials from dark-web dumps to authenticate directly"
                    elif mfa_status in ['Privileged Accounts Only']:
                        attack_vector = "Spear-Phishing + Session Hijacking — Initial access via targeted phishing campaign against standard users. Once foothold established, lateral movement to privileged accounts leverages absence of universal MFA to escalate without additional authentication challenges"
                    # Patching gaps
                    elif patching == 'Manual / Ad-hoc':
                        attack_vector = "Exploitation of Known Unpatched CVE — Initial access via publicly disclosed vulnerability (CVE with known PoC exploit) on externally exposed infrastructure. Ad-hoc patch management leaves a 30+ day window between disclosure and remediation, enabling opportunistic exploitation"
                    # Backup gaps
                    elif backups in ['No Formal Backups']:
                        attack_vector = "Ransomware via Supply Chain / Island Hopping — Initial access through compromised software update or third-party managed service provider. Absence of any formal backup strategy leaves the organisation with zero recovery capability, maximising extortion leverage"
                    elif backups in ['On-Premise Only']:
                        attack_vector = "Ransomware with Targeted Backup Destruction — Initial access through RDP brute-force on exposed management interfaces. Threat actor enumerates and encrypts on-premise backup repositories before deploying ransomware, eliminating local recovery options"
                    # IR Readiness gaps
                    elif ir_readiness in ['No Formal Plan']:
                        attack_vector = "Extended Dwell-Time Data Exfiltration — Initial access via a zero-day vulnerability in an externally facing web application. With no formal incident response plan, the threat actor maintains undetected persistence for 90+ days, exfiltrating sensitive data in small, scheduled batches to avoid anomaly detection thresholds"
                    elif ir_readiness in ['Documented IR Plan (Untested)']:
                        attack_vector = "Ransomware or Data Destruction via Insider Threat — Initial access through a compromised privileged account. The untested IR plan fails during execution due to undocumented dependencies and stale contact lists, extending containment time from hours to days"
                    # Remote Access gaps
                    elif remote_access in ['Legacy VPN (Client-based)', 'None / Cloud Only']:
                        attack_vector = "VPN Exploitation + Lateral Movement — Initial access through exploitation of a legacy VPN appliance with known vulnerabilities. Once inside the network perimeter, the flat internal network architecture enables unrestricted lateral movement toward critical assets"
                    # SaaS Backup gaps
                    elif saas_backup == 'None (Relying on Microsoft/Google)':
                        attack_vector = "Microsoft 365 Tenant Compromise — Initial access through OAuth consent phishing or token replay. Absence of third-party SaaS backup means threat actor can permanently delete or encrypt Exchange Online, SharePoint, and Teams data beyond Microsoft's native retention windows"
                    # Endpoint Capability gaps
                    elif endpoint_capability in ['Legacy AV Only (Signatures/Heuristics)']:
                        attack_vector = "Living-Off-the-Land (LOLBin) Attack — Initial access via a malicious Office macro or ISO payload. Legacy signature-based AV fails to detect fileless techniques leveraging PowerShell, WMI, and mshta, enabling persistent access without triggering traditional antivirus alerts"
                    # Security Culture gaps
                    elif 'Pillar 1' in savviness:
                        attack_vector = "Social Engineering + Physical Access — Initial access through a targeted vishing (voice phishing) campaign impersonating IT support, requesting remote access credentials. Low security culture awareness and absence of continuous training enable the attacker to bypass technical controls through human manipulation"
                    # Well-defended but still attackable
                    else:
                        attack_vector = "Multi-Stage Intrusion via Business Email Compromise — Initial access through a compromised executive email account (despite MFA) via adversary-in-the-middle (AiTM) proxy. Sophisticated threat actor leverages internal trust relationships to authorise fraudulent wire transfers or data exfiltration, evading standard detection through legitimate tooling"
                    
                    pillar = getattr(maturity_obj, 'resiliency_matrix_mapping', 'Pillar 1')
                    crown_jewels = client_inputs.get('critical_infra', 'Unknown')
                    rto = client_inputs.get('rto', 'Unknown')
                    insurance = client_inputs.get('insurance', 'Unknown')
                    
                    threat_prompt = f"""ENGAGEMENT DETAILS: Customer: {client_inputs['customer_name']} | Industry: {client_inputs['industry']} | Users: {client_inputs.get('users', '500')}
CLIENT ENVIRONMENT: Critical Asset: {crown_jewels} | MDR: {client_inputs.get('mdr_provider', 'None')} | Endpoint: {client_inputs.get('endpoint', 'Unknown')} | Firewall: {client_inputs.get('firewall', 'Unknown')}
MATURITY CONTEXT: {pillar}
IDENTIFIED SECURITY GAPS:
{gap_text}

OPERATIONAL TELEMETRY:
- MFA Enforcement: {mfa_status}
- Patch Management: {patching}
- Backup Strategy: {backups}
- Downtime Tolerance (RTO): {rto}
- Cyber Insurance: {insurance}

SCENARIO REQUIREMENTS:
- Section 1 (Threat Actor & Initial Access): Adapt to the identified gaps. Initial Access: "{attack_vector}". Include hyperlinked MITRE T-codes and CVEs relevant to the vector.
- Section 2 (Attacker Progression): Detail the attempted movement toward {crown_jewels}. Show how the specific gaps (MFA, patching, backups) enable lateral movement. The attacker must make initial headway due to environmental vulnerabilities.
- Section 3 (Sophos MDR Interception): CRITICAL RULE - The attack MUST NOT succeed against the final objective. Sophos MDR must identify behavioural anomalies mid-chain and actively neutralise the threat before exfiltration, encryption, or final objective completion. Detail the specific detection, isolation, and neutralisation actions taken.
- Section 4 (Recommended Solutions): Summarise the defence strategy in a consultative, third-person tone tied directly to the identified gaps. Do NOT use first-person ('we', 'our') or second-person ('you', 'your').

Act as ROLE 1 (Tactical Threat Analyst). Write a highly technical, narrative-driven breach scenario in British English. Use Markdown for hyperlinks. Do not use bullet points in narrative sections — write flowing paragraphs."""

                    # Stream the threat narrative
                    ref_sample = st.session_state['client_inputs'].get('reference_sample', '')
                    if ref_sample:
                        threat_prompt += f"""

REFERENCE SAMPLE (TONE ONLY — DO NOT COPY)
{ref_sample}

ANTI-MIMICRY DIRECTIVE
You MUST NOT replicate phrasing, sentence structure, paragraph ordering, or section wording from the reference sample. Target high stylistic dissimilarity and vary sentence length and cadence. If any sentence would share more than 8 consecutive words with the sample, rewrite it.
"""
                    accumulated = ""
                    for token in LLMEngine.generate_text_report_streaming(client, deployment, SYSTEM_PERSONA, threat_prompt, temperature=0.7):
                        accumulated += token
                    
                    if accumulated.strip():
                        from prompts import ThreatScenarioItem
                        threat_scenarios = [
                            ThreatScenarioItem(
                                id="ts-maturity-1",
                                name=f"{pillar} Maturity-Aligned Threat Scenario",
                                incident_type=pillar,
                                narrative=accumulated.strip(),
                            )
                        ]
                        maturity_obj.threat_scenarios = threat_scenarios
                        st.session_state['maturity_threat_scenarios'] = threat_scenarios
                        st.session_state['maturity_obj'] = maturity_obj
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(
                        f"Threat scenario LLM generation failed; building fallback from maturity data. Error: {e}"
                    )
                    # Fallback: build a lightweight threat scenario from the maturity report itself
                    if maturity_obj:
                        from prompts import ThreatScenarioItem
                        threat_scenarios = [
                            ThreatScenarioItem(
                                id="ts-maturity-1",
                                name=f"{maturity_obj.resiliency_matrix_mapping} Threat Scenario",
                                incident_type=maturity_obj.resiliency_matrix_mapping,
                                narrative=maturity_obj.cost_of_inaction,
                            )
                        ]
                        maturity_obj.threat_scenarios = threat_scenarios
                        st.session_state['maturity_threat_scenarios'] = threat_scenarios
                        st.session_state['maturity_obj'] = maturity_obj
                # Clear any cached export bytes from previous runs
                for key in ['maturity_docx_bytes']:
                    st.session_state.pop(key, None)
                st.success("Cybersecurity Maturity Roadmap Generated Successfully.")
            else:
                st.error("Engine failed to generate the roadmap.")
        
    if st.session_state.get('maturity_obj'):
        st.subheader("📥 Export Deliverables")
        docx_data = get_maturity_docx_bytes()
        if docx_data:
            st.download_button(
                "📄 Download Cybersecurity Maturity Report (Word)", 
                data=docx_data, 
                file_name=f"{cached_customer_name.replace(' ', '_')}_Cybersecurity_Maturity_Report.docx", 
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

    if st.session_state.get('maturity_obj'):
        st.divider()
        st.subheader("📊 Strategic Assessment Preview")
        
        maturity = st.session_state['maturity_obj']
        
        tab1, tab2, tab3 = st.tabs(["Executive Brief", "Domain Assessments", "Strategic Roadmap"])
        
        with tab1:
            st.markdown("### Executive Summary")
            st.markdown(maturity.executive_summary)
            
            st.markdown("### Resiliency Matrix Mapping")
            st.info(maturity.resiliency_matrix_mapping)
            
            col_impact, col_comp = st.columns(2)
            with col_impact:
                st.markdown("### The Cost of Inaction")
                st.error(maturity.cost_of_inaction)
            with col_comp:
                st.markdown("### Compliance Alignment")
                st.success(maturity.compliance_alignment)
            # Additional cost & partnership details (optional, enriched by LLM)
            if getattr(maturity, 'monetary_cost_of_inaction', None):
                mv = maturity.monetary_cost_of_inaction
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
            if getattr(maturity, 'partnership_outline', None):
                outline = maturity.partnership_outline
                if outline:
                    st.markdown("### Partnership Outline (Co-/Fully Managed)")
                    st.write(outline)
            if getattr(maturity, 'microsoft_healthchecks_recommendations', None):
                rec = maturity.microsoft_healthchecks_recommendations
                if rec:
                    st.markdown("### Microsoft Healthchecks & Hardening")
                    st.write(rec)
                
        with tab2:
            st.markdown("### Security Domain Analysis")
            for domain in maturity.domain_assessments:
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
            for phase in maturity.phased_roadmap:
                st.markdown(f"#### {phase.phase_title}: {phase.primary_objective}")
                for milestone in phase.milestones:
                    st.markdown(f"- {milestone}")
                st.markdown(f"**Value Delivered:** {phase.business_value_delivered}")
                st.markdown(f"**Resources:** {phase.resource_requirements}")
                st.divider()
        # Threat Scenarios (auto-generated) rendering
        if getattr(maturity, 'threat_scenarios', None):
            try:
                threats = maturity.threat_scenarios
            except Exception:
                threats = None
            if threats:
                st.divider()
                st.subheader("Threat Scenarios (Auto-generated)")
                for ts in threats:
                    ts_name = _safe_get(ts, 'name', 'Threat Scenario')
                    ts_type = _safe_get(ts, 'incident_type', '')
                    st.markdown(f"**{ts_name}** ({ts_type})")
                    narrative = _safe_get(ts, 'narrative', '')
                    if narrative:
                        st.write(narrative)
                    # Triggers
                    triggers = _safe_get(ts, 'triggers', []) or []
                    if triggers:
                        st.markdown("- Triggers: " + ", ".join(triggers))
                    # Timelines
                    timelines = _safe_get(ts, 'timelines', None)
                    if timelines:
                        st.markdown("**Timelines:**")
                        if isinstance(timelines, list):
                            for t in timelines:
                                st.write(str(t))
                        else:
                            st.write(str(timelines))
                    # Assets & Impacts
                    assets = _safe_get(ts, 'assets_at_risk', []) or []
                    if assets:
                        st.markdown("**Assets At Risk:** " + ", ".join(assets))
                    impacts = _safe_get(ts, 'potential_impacts', []) or []
                    if impacts:
                        st.markdown("**Potential Impacts:**" )
                        for imp in impacts:
                            st.write(f"- {imp}")
                    # MDR Case Log
                    mdr_log = _safe_get(ts, 'mdr_case_log', None)
                    if mdr_log:
                        st.markdown("**MDR Case Log:**")
                        st.write(mdr_log)
                    # Recommendations
                    recs = _safe_get(ts, 'recommended_actions', []) or []
                    if recs:
                        st.markdown("**Recommended Actions:**")
                        for r in recs:
                            st.write(f"- {r}")
        # Display Cost of Inaction (GBP) if available in the maturity report
        _display_cost_of_inaction_section()

with st.expander("Developer Utilities (Test Data Injection)", expanded=False):
    col_dev1, col_dev2 = st.columns(2)
    if col_dev1.button("Fill with Test Data"):
        st.session_state['use_test_data'] = True
        st.rerun()
    if col_dev2.button("Clear All Fields"):
        st.session_state['use_test_data'] = False
        st.rerun()

st.divider()
st.markdown(
    "<div style='text-align: center; color: #23506A; font-size: 0.8rem;'>"
    f"Security Use Case & Cybersecurity Maturity Assessment Generator — v{APP_VERSION}"
    "</div>",
    unsafe_allow_html=True
)
st.markdown(
    "<div style='text-align: center; color: #23506A; font-size: 0.7rem; margin-top: 4px;'>"
    "&copy; 2026 Bradley Collis. All rights reserved."
    "</div>",
    unsafe_allow_html=True
)