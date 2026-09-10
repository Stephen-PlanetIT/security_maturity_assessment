import streamlit as st
import os
import random
import time
import re as _re
import secrets
try:
    import bcrypt  # password hashing
except Exception:  # pragma: no cover
    bcrypt = None
from core import LLMEngine
from prompts import build_scenario_prompt, build_mdr_case_prompt, build_maturity_prompt, build_maturity_header_prompt, ScenarioReport, MaturityReport, SYSTEM_PERSONA, MaturityHeader
from data import FULLY_MANAGED_URL, CO_MANAGED_URL
from data import MDR_COMPARISON, choose_mdr_recommendation
from data import ATTACK_VECTORS, SIMULATED_OSINT
from export import create_pdf, create_maturity_docx, create_threat_docx
from prompts import (
    TabletopMasterPlan, TabletopPivotResponse, TabletopAAR,
    build_tabletop_plan_prompt, build_tabletop_pivot_prompt, build_tabletop_aar_prompt,
    SYSTEM_PERSONA_TABLETOP
)
from export import create_tabletop_pptx, create_tabletop_facilitator_pdf
from catalog import PLANET_IT_PORTFOLIO
from config import get_config, validate_config, ConfigKey
from consultation_schema import (
    DEFAULT_CRITICAL_ASSET_PROFILE,
    DEFAULT_SERVICE_RESILIENCE_PROFILE,
    DEFAULT_INFORMATION_PROTECTION,
    DEFAULT_IDENTITY_GOVERNANCE,
    DEFAULT_SAAS_GOVERNANCE,
    DEFAULT_ASSET_ASSURANCE,
    DEFAULT_MONITORING_ASSURANCE,
    DEFAULT_SUPPLIER_ASSURANCE,
    DEFAULT_THIRD_PARTY_ACCESS_PROFILE,
    DEFAULT_RECOVERY_ASSURANCE,
    DEFAULT_IR_ASSURANCE,
    ASSURANCE_STATUS_DEFAULT,
    BUSINESS_SERVICES_OPTIONS,
    SENSITIVE_DATA_OPTIONS,
    ASSESSMENT_STATUS_OPTIONS,
    RTO_OPTIONS,
    RPO_OPTIONS,
    MANUAL_WORKAROUND_OPTIONS,
    DEP_MAPPING_OPTIONS,
    RECOVERY_PRIORITIES_OPTIONS,
)
from consultation_helpers import migrate_profile

_SANITISE_REPLACEMENTS = [
    (_re.compile(r'["]{3,}'), '"'),
    (_re.compile(r"'{3,}"), "'"),
    (_re.compile(r'(?:\r?\n){3,}'), '\n\n'),
    (_re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]'), ''),
    (_re.compile(r'[\u200B-\u200F\u202A-\u202E\u2060-\u206F]'), ''),
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

def _coerce_list(value, options):
    """Coerce imported profile values into a valid list constrained to options."""
    try:
        if isinstance(value, list):
            return [v for v in value if v in options]
        if isinstance(value, str):
            parts = [p.strip() for p in value.split(",") if p.strip()]
            return [p for p in parts if p in options]
    except Exception:
        pass
    return []

def _safe_index(options, value):
    """Return index of value in options; 0 if missing or invalid."""
    try:
        return options.index(value) if value in options else 0
    except Exception:
        return 0

def _with_custom_prefill(value: str, options: list[str]) -> tuple[int, str]:
    """
    Return (index, custom_default) for a selectbox with 'Other / Custom...' option.
    If value matches an option, returns its index and empty custom string.
    Otherwise returns index of 'Other / Custom...' and the original value as the default for the custom field.
    """
    try:
        if value in options:
            return options.index(value), ""
    except Exception:
        pass
    try:
        idx = options.index("Other / Custom...")
    except Exception:
        idx = 0
    return idx, (value or "")

def _resolve_custom(selection: str, custom: str) -> str:
    """
    Resolve the final value for a selectbox with 'Other / Custom...'.
    If 'Other / Custom...' is selected and custom has content, returns the custom string; otherwise returns the selection.
    """
    if isinstance(selection, str) and selection == "Other / Custom..." and isinstance(custom, str) and custom.strip():
        return custom.strip()
    return selection

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

        strong_ms_investment = any(l in str(m365_license) for l in ["Microsoft 365 E5", "M365 Business Premium"])

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

        # 7. AI Usage & Security (Governance & Shadow AI)
        ai_usage_policy = inputs.get('ai_usage_policy', 'Unknown')
        shadow_ai = inputs.get('shadow_ai_monitoring', 'Unknown')
        approved_tools = str(inputs.get('approved_ai_tools', ''))
        ai_dlp = str(inputs.get('ai_dlp_controls', ''))

        if ai_usage_policy in ["None", "Unknown"]:
            recs.append("**AI Governance (Policy):** Establish a formal AI acceptable use policy and governance framework to control data exposure, set guardrails, and define approved tooling.")
        if shadow_ai in ["None", "Unknown", "Planned"]:
            safe_append(
                "AI_Governance_and_Security",
                "Sophos AI Defense",
                "**AI Governance (Shadow AI):** Enable shadow AI discovery and monitoring to identify unsanctioned AI usage and reduce sensitive data leakage risk."
            )
        # Copilot-specific baseline when Microsoft is present but DLP/CASB not configured
        if ("copilot" in approved_tools.lower()) and ("purview" not in ai_dlp.lower() or "defender for cloud apps" not in ai_dlp.lower()):
            if not is_banned("Microsoft"):
                recs.append("**Microsoft Copilot Governance:** Implement Microsoft Purview DLP and Defender for Cloud Apps app governance to enforce policy on prompts and outputs, prevent oversharing, and retain audit trails.")
            else:
                recs.append("**AI Data Loss Controls:** Apply DLP and CASB/SSE controls to govern AI prompts and outputs, with full audit logging. Planet IT can advise on allowed alternatives.")

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
                st.session_state['maturity_obj'],
                st.session_state.get('mc_llm_interpretation', ""),
                st.session_state.get('mc_summary')
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

# --- AUTHENTICATION GATE (username/password) ---
def _to_bool(val) -> bool:
    try:
        return str(val).strip().lower() in ("1", "true", "yes", "y", "on")
    except Exception:
        return False

def login_gate():
    """Simple username/password gate with bcrypt hashing, brute‑force lockout, and idle TTL.
    All configuration sourced from environment or Streamlit secrets via config.get_config.
    Keys: AUTH_ENABLED, AUTH_METHOD='password', AUTH_USERNAME, AUTH_PASSWORD_HASH,
          AUTH_SESSION_TTL_MIN (default: 60), AUTH_MAX_ATTEMPTS (default: 5), AUTH_COOLDOWN_SEC (default: 300)
    """
    from config import get_config
    if not _to_bool(get_config("AUTH_ENABLED", "false")):
        return
    now = time.time()
    try:
        ttl_min = int(get_config("AUTH_SESSION_TTL_MIN", "480"))
    except Exception:
        ttl_min = 480
    ttl_sec = max(60, ttl_min * 60)

    lock_until = st.session_state.get("_auth_lock_until", 0)
    if now < lock_until:
        wait = int(lock_until - now)
        st.error(f"Too many failed attempts. Please wait {wait} second{'s' if wait != 1 else ''} before retrying.")
        st.stop()

    issued_at = st.session_state.get("_auth_issued_at")
    user = st.session_state.get("_auth_user")
    if issued_at and user and (now - issued_at) < ttl_sec:
        return

    st.markdown("## 🔐 Sign in")
    with st.form("login", clear_on_submit=False):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        submit = st.form_submit_button("Sign in", type="primary")

    if submit:
        expected_user = get_config("AUTH_USERNAME", "")
        expected_hash = get_config("AUTH_PASSWORD_HASH", "")
        try:
            max_attempts = int(get_config("AUTH_MAX_ATTEMPTS", "5"))
        except Exception:
            max_attempts = 5
        try:
            cooldown = int(get_config("AUTH_COOLDOWN_SEC", "300"))
        except Exception:
            cooldown = 300

        fails = int(st.session_state.get("_auth_fail_count", 0))
        ok_user = secrets.compare_digest(str(u or ""), str(expected_user or ""))

        if bcrypt is None:
            st.error("Server missing bcrypt dependency. Ensure 'bcrypt' is installed.")
            st.stop()

        ok_pass = False
        if isinstance(expected_hash, str) and expected_hash.startswith("$2"):
            try:
                ok_pass = bcrypt.checkpw((p or "").encode("utf-8"), expected_hash.encode("utf-8"))
            except Exception:
                ok_pass = False
        else:
            st.error("AUTH_PASSWORD_HASH invalid. Provide a bcrypt hash beginning with $2...")
            st.stop()

        if ok_user and ok_pass:
            st.session_state["_auth_user"] = u
            st.session_state["_auth_issued_at"] = now
            st.session_state["_auth_fail_count"] = 0
            st.success("Signed in successfully.")
            st.rerun()
        else:
            fails += 1
            st.session_state["_auth_fail_count"] = fails
            if fails >= max_attempts:
                st.session_state["_auth_lock_until"] = now + cooldown
                st.error(f"Too many failed attempts. Locked for {cooldown} seconds.")
            else:
                remaining = max_attempts - fails
                st.error(f"Invalid credentials. {remaining} attempt{'s' if remaining != 1 else ''} remaining.")

    st.stop()

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
# Hide default Streamlit sidebar/navigation (landing + workflows without sidebar)
st.markdown("<style>[data-testid='stSidebar']{display:none;} [data-testid='stSidebarNav']{display:none;}</style>", unsafe_allow_html=True)
validate_platform_config() # Fails fast if keys are missing
# Authentication gate (env-driven). If AUTH_ENABLED=true, blocks UI until sign-in.
login_gate()

# (Removed query-parameter router; navigation uses Streamlit-native page links to preserve session)

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

# Minor layout tweaks: tighten radio spacing inside Programme Controls expander
try:
    st.markdown(
        "<style>div[data-testid='stExpander'] div[role='radiogroup'] > label { margin-bottom: 0.15rem; }</style>",
        unsafe_allow_html=True,
    )
except Exception:
    pass

# --- DEV/TEST DATA INITIALISATION (Moved before sidebar) ---
dev = st.session_state.get('use_test_data', False) or st.session_state.get('use_imported_profile', False)

TEST_DATA = {
    "customer_name": "Acme Corp",
    "consultant_name": "Jane Doe",
    "industry": "Technology",
    "users": 500,
    "critical_infra": "Patient Records Database",
    "endpoints": 600,
    "servers": 50,
    "operating_systems": ["Windows 10", "Windows 11", "Windows Server"],
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
    "proactive_tools": [],
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
    "ai_usage_policy": "None",
    "approved_ai_tools": [],
    "shadow_ai_monitoring": "None",
    "ai_dlp_controls": [],
    "banned_vendors": [],
}

# --- LANDING FRONT PAGE (no sidebar) ---
if not st.session_state.get('workflow'):
    # Header (consistent branding)
    st.title("Planet IT Advisory Engine")
    st.markdown("### Select a Workflow")

    # Landing CSS for uniform tiles (buttons and links)
    st.markdown(
        """
        <style>
        #landing a, #landing a:visited {
            display: inline-block;
            width: 100%;
            padding: 0.6rem 1rem;
            border: 1px solid #c8d6df;
            border-radius: 8px;
            text-align: center;
            color: #1e3a4c;
            text-decoration: none;
            background: white;
        }
        #landing a:hover {
            background: #f5f9fb;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div id='landing'></div>", unsafe_allow_html=True)

    # Centred grid: side spacers + three tiles
    colL, col1, col2, col3, colR = st.columns([1, 2, 2, 2, 1])
    with col1:
        if st.button("📈 Cybersecurity Maturity Assessment", use_container_width=True):
            st.session_state['workflow'] = "📈 Cybersecurity Maturity Assessment"
            st.rerun()
    with col2:
        if st.button("🎯 Tabletop Exercise (Designer) ➡️", use_container_width=True):
            st.session_state['workflow'] = "🎯 Tabletop Exercise & Facilitator"
            st.rerun()
    with col3:
        if st.button("🔥 Tactical Threat Simulator", use_container_width=True):
            st.session_state['workflow'] = "🔥 Tactical Threat Simulator"
            st.rerun()

    # Footer (copywriting footer, aligned to app-wide style)
    st.divider()
    st.markdown(
        "<div style='text-align: center; color: #23506A; font-size: 0.8rem;'>"
        "Security Use Case & Cybersecurity Maturity Assessment Generator"
        "</div>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<div style='text-align: center; color: #23506A; font-size: 0.7rem; margin-top: 4px;'>"
        "&copy; 2026 Bradley Collis. All rights reserved."
        "</div>",
        unsafe_allow_html=True
    )

    st.stop()

# --- SIDEBAR & ENGINE CONFIGURATION ---
if st.session_state.get('_legacy_sidebar', False):
    with st.sidebar:
        st.markdown("## 🛡️ Planet IT Advisory Engine")
        
        # Engine is strictly Azure (Ollama support removed per July 2026 hardening)
        st.session_state['ai_engine'] = "azure"
        
        

        st.divider()
        
        workflow = st.radio(
            "Select Workflow:", 
            options=[
                "📈 Cybersecurity Maturity Assessment",
                "🎯 Tabletop Exercise & Facilitator",
                "🔥 Tactical Threat Simulator"   
            ], 
            index=0
        )
        st.session_state['workflow'] = workflow
        
        st.divider()

        if workflow == "📈 Cybersecurity Maturity Assessment":
            generation_mode = st.radio(
                "Generation Mode",
                options=["Monolithic (single-pass)", "Staged (header-first)"],
                index=0,
                help="Monolithic: single LLM pass to produce full report. Staged: header-first, then follow-ups."
            )
            st.session_state['staged_enabled'] = (generation_mode == "Staged (header-first)")

# --- MAIN PAGE HEADER ---
_title_map = {
    "📈 Cybersecurity Maturity Assessment": "Cybersecurity Maturity Assessment",
    "🔥 Tactical Threat Simulator": "Tactical Threat Simulator",
    "🎯 Tabletop Exercise & Facilitator": "Tabletop Exercise Builder & Facilitator",
}
_current_workflow = st.session_state.get('workflow', "📈 Cybersecurity Maturity Assessment")
st.title(_title_map.get(_current_workflow, "Security Use Case & Cybersecurity Maturity Assessment Generator"))

# Top navigation (no sidebar) — quick links to Home and workflows
with st.container():
    colh1, colh2, colh3, colh4 = st.columns([1, 1, 1, 1])
    with colh1:
        if st.button("🏠 Home", use_container_width=True):
            st.session_state['workflow'] = None
            st.rerun()
    with colh2:
        if st.button("📈 Maturity", use_container_width=True):
            st.session_state['workflow'] = "📈 Cybersecurity Maturity Assessment"
            st.rerun()
    with colh3:
        st.page_link("pages/03_Tabletop_Designer.py", label="🎯 Tabletop", icon=None)
    with colh4:
        if st.button("🔥 Threats", use_container_width=True):
            st.session_state['workflow'] = "🔥 Tactical Threat Simulator"
            st.rerun()

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
        # Guard against infinite rerun loops by hashing the uploaded content and skipping
        # re-processing when the same file persists in the uploader across reruns.
        uploaded = st.file_uploader("Import options (.json)", type=["json"], key="profile_import_json")
        if uploaded is not None:
            try:
                raw = uploaded.getvalue() if hasattr(uploaded, "getvalue") else uploaded.read()
                import hashlib as _hashlib
                try:
                    _h = _hashlib.sha256(raw).hexdigest() if isinstance(raw, (bytes, bytearray)) else _hashlib.sha256(str(raw).encode("utf-8")).hexdigest()
                except Exception:
                    _h = f"{getattr(uploaded, 'name', 'unknown')}:{len(raw) if hasattr(raw, '__len__') else 0}"

                # If this exact file has already been applied in the current session, avoid re-import and rerun loops
                if st.session_state.get('_last_import_hash') == _h:
                    st.info("Profile already applied.")
                else:
                    data = _json.loads(raw.decode("utf-8")) if isinstance(raw, (bytes, bytearray)) else _json.loads(raw)
                    profile = data.get("profile") if isinstance(data, dict) and "profile" in data else data
                    if not isinstance(profile, dict):
                        st.error("Invalid file format: expected a JSON object with a 'profile' object or a flat object of fields.")
                    else:
                        # Minimal validation: ensure required fields exist
                        required_keys = ["customer_name", "industry", "users"]
                        if not all(k in profile for k in required_keys):
                            st.warning("Profile loaded, but some keys are missing. Defaults will be used where absent.")
                        try:
                            profile = migrate_profile(profile)
                        except Exception:
                            pass
                        st.session_state['_imported_profile'] = profile
                        st.session_state['use_imported_profile'] = True
                        st.session_state['use_test_data'] = False
                        st.session_state['_last_import_hash'] = _h
                        st.success("Profile imported. Applying to UI...")
                        st.rerun()
            except Exception as e:
                st.error(f"Failed to import profile: {e}")

# --- DEV/TEST DATA INIT MOVED ABOVE SIDEBAR ---

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
        industry = st.selectbox("Industry", industry_options, index=(_safe_index(industry_options, TEST_DATA.get('industry')) if dev else 0), help="Example: Technology")
        users = st.number_input("Headcount", min_value=0, value=(TEST_DATA['users'] if dev else 0), help="Example: 500")
        critical_infra = st.text_input("Crown Jewels", value=(TEST_DATA['critical_infra'] if dev else ""), placeholder="e.g., Patient Records Database")
        
    with col2:
        st.subheader("Technology Stack")
        endpoints = st.number_input("Number of Endpoints", min_value=0, value=(TEST_DATA['endpoints'] if dev else 0), help="Example: 600")
        servers = st.number_input("Number of Servers", min_value=0, value=(TEST_DATA['servers'] if dev else 0), help="Example: 50")
        _os_options = ["Windows 10", "Windows 11", "Windows Server", "macOS", "Linux", "ChromeOS"]
        operating_systems = st.multiselect("Operating Systems in Use", _os_options, default=(_coerce_list(TEST_DATA.get('operating_systems', []), _os_options) if dev else []), help="Example: Windows 11, Windows Server")
        mdr_options = ["Select MDR / SOC Provider...", "None", "Sophos MDR", "Sophos MDR Plus", "Microsoft Defender Experts", "CrowdStrike Falcon Complete", "Arctic Wolf", "Expel", "Red Canary", "Local Partner SOC", "Other"]
        mdr_provider = st.selectbox("Current MDR / SOC Provider", mdr_options, index=(_safe_index(mdr_options, TEST_DATA.get('mdr_provider')) if dev else 0), help="Example: Sophos MDR")
        
        endpoint_options = ["Select Endpoint Vendor...", "Sophos", "Microsoft Defender", "CrowdStrike", "SentinelOne", "Trend Micro", "Symantec", "N-able", "Other"]
        endpoint = st.selectbox("Endpoint Security Vendor", endpoint_options, index=(_safe_index(endpoint_options, TEST_DATA.get('endpoint')) if dev else 0), help="Example: Sophos")
        
        # --- NEW FIELD: ENDPOINT CAPABILITY ---
        endpoint_posture_options = ["Select Endpoint Capability...", "Legacy AV Only (Signatures/Heuristics)", "Next-Gen AV (NGAV / Deep Learning)", "EDR Deployed (Endpoint Detection & Response)", "XDR Deployed (Cross-Domain Telemetry)", "Full ZTNA / Device Control Enforced"]
        endpoint_posture = st.selectbox("Endpoint Capability (Licensing)", endpoint_posture_options, index=(_safe_index(endpoint_posture_options, TEST_DATA.get('endpoint_posture')) if dev else 0), help="Example: EDR Deployed (Endpoint Detection & Response)")
        
        firewall_options = ["Select Firewall Vendor...", "Fortinet", "Palo Alto", "Cisco", "Sophos", "Check Point", "SonicWall", "Other"]
        firewall = st.selectbox("Firewall Vendor", firewall_options, index=(_safe_index(firewall_options, TEST_DATA.get('firewall')) if dev else 0), help="Example: Fortinet")

        remote_access_options = [
            "Select Remote Access Strategy...",
            "None / Cloud Only",
            "Legacy VPN (Client-based)",
            "Always-On VPN",
            "VPN with Certificate-based Authentication",
            "Clientless VPN Portal",
            "Zero Trust Network Access (ZTNA) / SASE",
            "SD-WAN with Secure Access Overlay"
        ]
        remote_access = st.selectbox("Remote Access Strategy", remote_access_options, index=(_safe_index(remote_access_options, TEST_DATA.get('remote_access')) if dev else 0), help="Example: Legacy VPN (Client-based)")
        
        saas_backup_options = ["Select SaaS Backup...", "None (Relying on Microsoft/Google)", "Basic Retention Policies Only", "Dedicated Third-Party SaaS Backup"]
        saas_backup = st.selectbox("M365 / SaaS Backup", saas_backup_options, index=(_safe_index(saas_backup_options, TEST_DATA.get('saas_backup')) if dev else 0), help="Example: None (Relying on Microsoft/Google)")
        
    with col3:
        st.subheader("Cloud & Identity")
        identity_options = ["Select Identity Provider...", "Microsoft Entra ID (Azure AD)", "Okta", "On-Prem Active Directory", "None"]
        identity = st.selectbox("Identity Provider", identity_options, index=(_safe_index(identity_options, TEST_DATA.get('identity')) if dev else 0), help="Example: Microsoft Entra ID (Azure AD)")
        m365_license_options = ["None / On-Prem Only", "M365 Business Premium", "Microsoft 365 E5", "Office 365 E3 / M365 E3"]
        m365_licenses = st.multiselect(
            "Microsoft 365 Licensing",
            m365_license_options,
            default=(_coerce_list([TEST_DATA.get('m365_license')], m365_license_options) if dev else []),
            help="Select all that apply. Example: M365 Business Premium"
        )
        m365_license_str = ", ".join(m365_licenses) if m365_licenses else "None / On-Prem Only"
        # Email security: prefer Mimecast or Barracuda; remove Sophos as a recommended option
        email_options = ["Select Email Security...", "Mimecast", "Proofpoint", "Microsoft Defender", "Barracuda", "Egress", "Other"]
        email = st.selectbox("Email Security", email_options, index=(_safe_index(email_options, TEST_DATA.get('email')) if dev else 0), help="Example: Mimecast")
        cloud_env = st.multiselect("Cloud Infrastructure", ["AWS", "Microsoft Azure", "GCP", "Oracle Cloud", "None (Fully On-Prem)"], default=(_coerce_list(TEST_DATA.get('cloud_env', []), ["AWS", "Microsoft Azure", "GCP", "Oracle Cloud", "None (Fully On-Prem)"]) if dev else []), help="Example: AWS")

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
        default=(_coerce_list(TEST_DATA.get('banned_vendors', []), all_vendors) if dev else []),
        help="Select vendors to exclude from all recommendations and LLM-generated content."
    )
    
    st.divider()
    st.subheader("Operations & Validation")
    col_ops1, col_ops2 = st.columns(2)
    with col_ops1:
        in_house_options = ["Select Internal SOC Team...", "No", "Yes (9-to-5)", "Yes (24/7)"]
        in_house_team = st.selectbox("Internal SOC Team", in_house_options, index=(_safe_index(in_house_options, TEST_DATA.get('in_house_team')) if dev else 0), help="Example: No")
        pentest_options = ["Select Penetration Testing Cadence...", "None", "Annual", "Bi-Annual", "Quarterly"]
        pentest_status = st.selectbox("Penetration Testing", pentest_options, index=(_safe_index(pentest_options, TEST_DATA.get('pentest_status')) if dev else 0), help="Example: Annual")
        vuln_options = ["Select Vulnerability Scanning...", "None", "Monthly Authenticated", "Quarterly External", "Continuous"]
        vuln_scanning = st.selectbox("Vuln Scanning", vuln_options, index=(_safe_index(vuln_options, TEST_DATA.get('vuln_scanning')) if dev else 0), help="Example: Monthly Authenticated")
        public_web_apps = st.checkbox("Host Public Web Apps", value=(TEST_DATA['public_web_apps'] if dev else False))
    with col_ops2:
        compliance_options = ["ISO 27001", "Cyber Essentials", "Cyber Essentials Plus", "PCI DSS", "HIPAA", "NIST CSF", "UK DfE (2026) Cyber Security Standards"]
        compliance = st.multiselect(
            "Target Compliance",
            compliance_options,
            default=(_coerce_list(TEST_DATA.get('compliance', []), compliance_options) if dev else []),
            help="Example: ISO 27001, Cyber Essentials"
        )
        physical_locations = st.number_input("Physical Locations", min_value=0, value=(TEST_DATA['physical_locations'] if dev else 0), help="Example: 3")
        advanced_controls = st.multiselect(
            "Advanced Adaptive Controls (Pillar 3)", 
            ["Zero-Trust Architecture (ZTA)", "Network Microsegmentation", "SOAR / Automated Remediation", "User Behaviour Analytics (UBA)", "Automated DR Orchestration", "Deception Tech (Honeypots)"],
            default=(_coerce_list(TEST_DATA.get('advanced_controls', []), ["Zero-Trust Architecture (ZTA)", "Network Microsegmentation", "SOAR / Automated Remediation", "User Behaviour Analytics (UBA)", "Automated DR Orchestration", "Deception Tech (Honeypots)"]) if dev else [])
        )
        proactive_tools_options = [
            "KnowBe4 Security Awareness",
            "Hoxhunt",
            "Cofense PhishMe",
            "Proofpoint Security Awareness",
            "Microsoft Attack Simulation Training",
            "AttackIQ (BAS)",
            "SafeBreach (BAS)",
            "Mandiant Security Validation (BAS)"
        ]
        proactive_tools = st.multiselect(
            "Proactive Security Tools",
            proactive_tools_options,
            default=(_coerce_list(TEST_DATA.get('proactive_tools', []), proactive_tools_options) if dev else []),
            help="Select any training/BAS platforms already in use (e.g., KnowBe4, Hoxhunt)."
        )
        validation_notes = st.text_area("Validation Notes", value=(TEST_DATA['validation_notes'] if dev else ""), placeholder="e.g., Customer requires ISO 27001 alignment by Q4")
        context_notes = st.text_area("Consultant Context (LLM-visible)", value=(TEST_DATA['context_notes'] if dev else ""), placeholder="e.g., Nuances, constraints, or messaging to incorporate across the report")

    st.divider()

# Crown Jewels & Governance Evidence
with st.container():
    # Defaults from TEST_DATA for dev/imported profiles
    _cap_defaults = TEST_DATA.get('critical_asset_profile', DEFAULT_CRITICAL_ASSET_PROFILE) if isinstance(TEST_DATA, dict) else DEFAULT_CRITICAL_ASSET_PROFILE
    _sr_defaults = TEST_DATA.get('service_resilience_profile', DEFAULT_SERVICE_RESILIENCE_PROFILE) if isinstance(TEST_DATA, dict) else DEFAULT_SERVICE_RESILIENCE_PROFILE
    _ip_defaults = TEST_DATA.get('information_protection_profile', DEFAULT_INFORMATION_PROTECTION) if isinstance(TEST_DATA, dict) else DEFAULT_INFORMATION_PROTECTION
    _idg_defaults = TEST_DATA.get('identity_governance_profile', DEFAULT_IDENTITY_GOVERNANCE) if isinstance(TEST_DATA, dict) else DEFAULT_IDENTITY_GOVERNANCE
    _saas_defaults = TEST_DATA.get('saas_governance_profile', DEFAULT_SAAS_GOVERNANCE) if isinstance(TEST_DATA, dict) else DEFAULT_SAAS_GOVERNANCE
    _aa_defaults = TEST_DATA.get('asset_assurance_profile', DEFAULT_ASSET_ASSURANCE) if isinstance(TEST_DATA, dict) else DEFAULT_ASSET_ASSURANCE
    _mon_defaults = TEST_DATA.get('monitoring_assurance_profile', DEFAULT_MONITORING_ASSURANCE) if isinstance(TEST_DATA, dict) else DEFAULT_MONITORING_ASSURANCE
    _sup_defaults = TEST_DATA.get('supplier_assurance_profile', DEFAULT_SUPPLIER_ASSURANCE) if isinstance(TEST_DATA, dict) else DEFAULT_SUPPLIER_ASSURANCE
    _tpa_defaults = TEST_DATA.get('third_party_access_profile', DEFAULT_THIRD_PARTY_ACCESS_PROFILE) if isinstance(TEST_DATA, dict) else DEFAULT_THIRD_PARTY_ACCESS_PROFILE
    _rec_defaults = TEST_DATA.get('recovery_assurance_profile', DEFAULT_RECOVERY_ASSURANCE) if isinstance(TEST_DATA, dict) else DEFAULT_RECOVERY_ASSURANCE
    _ir_defaults = TEST_DATA.get('incident_response_assurance_profile', DEFAULT_IR_ASSURANCE) if isinstance(TEST_DATA, dict) else DEFAULT_IR_ASSURANCE
    _as_defaults = TEST_DATA.get('assurance_status', ASSURANCE_STATUS_DEFAULT) if isinstance(TEST_DATA, dict) else ASSURANCE_STATUS_DEFAULT

    # Critical Asset Profile
    with st.expander("Critical Asset Profile", expanded=False):
        st.subheader("Critical Asset Profile")
        _cap_bs_defaults = [v for v in (_cap_defaults.get('business_services') or []) if v in BUSINESS_SERVICES_OPTIONS]
        _cap_bs_custom_list = [v for v in (_cap_defaults.get('business_services') or []) if v not in BUSINESS_SERVICES_OPTIONS]
        cap_bs = st.multiselect("Business Services", BUSINESS_SERVICES_OPTIONS, default=_cap_bs_defaults)
        cap_bs_custom = st.text_input("Custom Business Services (separate by ';')", value="; ".join(_cap_bs_custom_list))
        cap_bs_final = cap_bs + [s.strip() for s in cap_bs_custom.split(';') if s.strip()]
        cap_sp = st.text_input("Systems/Platforms", value=_cap_defaults.get('systems_platforms', ''))
        _cap_sd_defaults = [v for v in (_cap_defaults.get('sensitive_data_types') or []) if v in SENSITIVE_DATA_OPTIONS]
        _cap_sd_custom_list = [v for v in (_cap_defaults.get('sensitive_data_types') or []) if v not in SENSITIVE_DATA_OPTIONS]
        cap_sd = st.multiselect("Sensitive Data Types", SENSITIVE_DATA_OPTIONS, default=_cap_sd_defaults)
        cap_sd_custom = st.text_input("Custom Sensitive Data Types (separate by ';')", value="; ".join(_cap_sd_custom_list))
        cap_sd_final = cap_sd + [s.strip() for s in cap_sd_custom.split(';') if s.strip()]
        cap_extra = st.text_area("Additional Context", value=_cap_defaults.get('additional_context', ''))
        _cap_dict = {
            "business_services": cap_bs_final,
            "systems_platforms": cap_sp,
            "sensitive_data_types": cap_sd_final,
            "additional_context": cap_extra,
        }

    # Service Resilience Profile
    with st.expander("Service Resilience Profile", expanded=False):
        st.subheader("Service Resilience Profile")
        sr_assess = st.selectbox("Assessment Status", ASSESSMENT_STATUS_OPTIONS, index=(_safe_index(ASSESSMENT_STATUS_OPTIONS, _sr_defaults.get('assessment_status'))))
        sr_crit = st.text_input("Most Critical Service", value=_sr_defaults.get('most_critical_service', ''))
        sr_rto = st.selectbox("Service-specific RTO", RTO_OPTIONS, index=(_safe_index(RTO_OPTIONS, _sr_defaults.get('service_specific_rto'))))
        sr_rpo = st.selectbox("Service-specific RPO", RPO_OPTIONS, index=(_safe_index(RPO_OPTIONS, _sr_defaults.get('service_specific_rpo'))))
        sr_mw = st.selectbox("Manual Workaround", MANUAL_WORKAROUND_OPTIONS, index=(_safe_index(MANUAL_WORKAROUND_OPTIONS, _sr_defaults.get('manual_workaround'))))
        sr_dep = st.selectbox("Dependency Mapping", DEP_MAPPING_OPTIONS, index=(_safe_index(DEP_MAPPING_OPTIONS, _sr_defaults.get('dependency_mapping'))))
        sr_pri = st.selectbox("Recovery Priorities", RECOVERY_PRIORITIES_OPTIONS, index=(_safe_index(RECOVERY_PRIORITIES_OPTIONS, _sr_defaults.get('recovery_priorities'))))
        sr_notes = st.text_area("Notes", value=_sr_defaults.get('notes', ''))
        _sr_dict = {
            "assessment_status": sr_assess,
            "most_critical_service": sr_crit,
            "service_specific_rto": sr_rto,
            "service_specific_rpo": sr_rpo,
            "manual_workaround": sr_mw,
            "dependency_mapping": sr_dep,
            "recovery_priorities": sr_pri,
            "notes": sr_notes,
        }

    # Information Protection
    with st.expander("Information Protection", expanded=False):
        st.subheader("Information Protection")
        ip_cls_opts = ["Sensitivity labels partially deployed", "None", "Unknown", "Other / Custom..."]
        idx_ip_cls, ip_cls_custom_def = _with_custom_prefill(_ip_defaults.get('data_classification_status', 'Unknown'), ip_cls_opts)
        ip_cls_sel = st.selectbox("Data Classification Status", ip_cls_opts, index=idx_ip_cls)
        ip_cls_custom = st.text_input("Custom Classification", value=ip_cls_custom_def if ip_cls_sel == "Other / Custom..." else "")
        ip_cls = _resolve_custom(ip_cls_sel, ip_cls_custom)

        ip_share_opts = ["Restricted and regularly reviewed", "Broadly enabled", "Unknown", "Other / Custom..."]
        idx_ip_share, ip_share_custom_def = _with_custom_prefill(_ip_defaults.get('external_sharing_posture', 'Unknown'), ip_share_opts)
        ip_share_sel = st.selectbox("External Sharing Posture", ip_share_opts, index=idx_ip_share)
        ip_share_custom = st.text_input("Custom External Sharing", value=ip_share_custom_def if ip_share_sel == "Other / Custom..." else "")
        ip_share = _resolve_custom(ip_share_sel, ip_share_custom)

        ip_dlp_opts = ["Deployed for selected sensitive data", "None", "Unknown", "Other / Custom..."]
        idx_ip_dlp, ip_dlp_custom_def = _with_custom_prefill(_ip_defaults.get('dlp_status', 'Unknown'), ip_dlp_opts)
        ip_dlp_sel = st.selectbox("DLP Status", ip_dlp_opts, index=idx_ip_dlp)
        ip_dlp_custom = st.text_input("Custom DLP", value=ip_dlp_custom_def if ip_dlp_sel == "Other / Custom..." else "")
        ip_dlp = _resolve_custom(ip_dlp_sel, ip_dlp_custom)

        ip_ret_opts = ["Retention controls configured", "Unknown", "Other / Custom..."]
        idx_ip_ret, ip_ret_custom_def = _with_custom_prefill(_ip_defaults.get('retention_governance', 'Unknown'), ip_ret_opts)
        ip_ret_sel = st.selectbox("Retention Governance", ip_ret_opts, index=idx_ip_ret)
        ip_ret_custom = st.text_input("Custom Retention Governance", value=ip_ret_custom_def if ip_ret_sel == "Other / Custom..." else "")
        ip_ret = _resolve_custom(ip_ret_sel, ip_ret_custom)

        _ip_dict = {
            "data_classification_status": ip_cls,
            "external_sharing_posture": ip_share,
            "dlp_status": ip_dlp,
            "retention_governance": ip_ret,
        }

    # Identity Governance
    with st.expander("Identity Governance", expanded=False):
        st.subheader("Identity Governance")
        idg_lc = st.text_input("Identity Lifecycle Maturity", value=_idg_defaults.get('identity_lifecycle_maturity', ''))
        idg_leaver = st.text_input("Leaver Deprovisioning", value=_idg_defaults.get('leaver_deprovisioning', ''))
        idg_ar = st.text_input("Access Review Status", value=_idg_defaults.get('access_review_status', ''))
        idg_pam = st.text_input("Privileged Access Model", value=_idg_defaults.get('privileged_access_model', ''))

        idg_pim_opts = ["Just-in-time access for major platforms", "None", "Planned", "Unknown", "Other / Custom..."]
        idx_idg_pim, idg_pim_custom_def = _with_custom_prefill(_idg_defaults.get('pim_pam_status', 'Unknown'), idg_pim_opts)
        idg_pim_sel = st.selectbox("PIM/PAM Status", idg_pim_opts, index=idx_idg_pim)
        idg_pim_custom = st.text_input("Custom PIM/PAM", value=idg_pim_custom_def if idg_pim_sel == "Other / Custom..." else "")
        idg_pim = _resolve_custom(idg_pim_sel, idg_pim_custom)

        idg_bg = st.text_input("Break Glass Governance", value=_idg_defaults.get('break_glass_governance', ''))

        idg_sag_opts = ["Ownership and credential rotation defined", "Informally managed", "Unknown", "Other / Custom..."]
        idx_idg_sag, idg_sag_custom_def = _with_custom_prefill(_idg_defaults.get('service_account_governance', 'Unknown'), idg_sag_opts)
        idg_sag_sel = st.selectbox("Service Account Governance", idg_sag_opts, index=idx_idg_sag)
        idg_sag_custom = st.text_input("Custom Service Account Governance", value=idg_sag_custom_def if idg_sag_sel == "Other / Custom..." else "")
        idg_sag = _resolve_custom(idg_sag_sel, idg_sag_custom)

        idg_shared_opts = ["Restricted and documented", "Widespread", "Unknown", "Other / Custom..."]
        idx_idg_shared, idg_shared_custom_def = _with_custom_prefill(_idg_defaults.get('shared_account_usage', 'Unknown'), idg_shared_opts)
        idg_shared_sel = st.selectbox("Shared Account Usage", idg_shared_opts, index=idx_idg_shared)
        idg_shared_custom = st.text_input("Custom Shared Account Usage", value=idg_shared_custom_def if idg_shared_sel == "Other / Custom..." else "")
        idg_shared = _resolve_custom(idg_shared_sel, idg_shared_custom)

        idg_legacy_opts = ["Restricted for selected dependencies", "Enabled and not reviewed", "Unknown", "Other / Custom..."]
        idx_idg_legacy, idg_legacy_custom_def = _with_custom_prefill(_idg_defaults.get('legacy_authentication_status', 'Unknown'), idg_legacy_opts)
        idg_legacy_sel = st.selectbox("Legacy Authentication Status", idg_legacy_opts, index=idx_idg_legacy)
        idg_legacy_custom = st.text_input("Custom Legacy Authentication Status", value=idg_legacy_custom_def if idg_legacy_sel == "Other / Custom..." else "")
        idg_legacy = _resolve_custom(idg_legacy_sel, idg_legacy_custom)

        idg_notes = st.text_area("Notes", value=_idg_defaults.get('notes', ''), key="idg_notes")
        _idg_dict = {
            "identity_lifecycle_maturity": idg_lc,
            "leaver_deprovisioning": idg_leaver,
            "access_review_status": idg_ar,
            "privileged_access_model": idg_pam,
            "pim_pam_status": idg_pim,
            "break_glass_governance": idg_bg,
            "service_account_governance": idg_sag,
            "shared_account_usage": idg_shared,
            "legacy_authentication_status": idg_legacy,
            "notes": idg_notes,
        }

    # SaaS Governance
    with st.expander("SaaS Governance", expanded=False):
        st.subheader("SaaS Governance")
        saas_inv_opts = ["Register with owners and data classification", "No authoritative inventory", "Unknown", "Other / Custom..."]
        idx_sg_inv, sg_inv_custom_def = _with_custom_prefill(_saas_defaults.get('inventory_status', 'Unknown'), saas_inv_opts)
        sg_inv_sel = st.selectbox("Inventory Status", saas_inv_opts, index=idx_sg_inv)
        sg_inv_custom = st.text_input("Custom Inventory Status", value=sg_inv_custom_def if sg_inv_sel == "Other / Custom..." else "")
        sg_inv = _resolve_custom(sg_inv_sel, sg_inv_custom)

        sg_cp = st.text_input("Critical Platforms", value=_saas_defaults.get('critical_platforms', ''))

        saas_sso_opts = ["Most supported applications", "Limited", "Unknown", "Other / Custom..."]
        idx_sg_sso, sg_sso_custom_def = _with_custom_prefill(_saas_defaults.get('sso_coverage', 'Unknown'), saas_sso_opts)
        sg_sso_sel = st.selectbox("SSO Coverage", saas_sso_opts, index=idx_sg_sso)
        sg_sso_custom = st.text_input("Custom SSO Coverage", value=sg_sso_custom_def if sg_sso_sel == "Other / Custom..." else "")
        sg_sso = _resolve_custom(sg_sso_sel, sg_sso_custom)

        saas_mfa_opts = ["All technically capable platforms", "Unknown", "Other / Custom..."]
        idx_sg_mfa, sg_mfa_custom_def = _with_custom_prefill(_saas_defaults.get('mfa_coverage', 'Unknown'), saas_mfa_opts)
        sg_mfa_sel = st.selectbox("MFA Coverage", saas_mfa_opts, index=idx_sg_mfa)
        sg_mfa_custom = st.text_input("Custom MFA Coverage", value=sg_mfa_custom_def if sg_mfa_sel == "Other / Custom..." else "")
        sg_mfa = _resolve_custom(sg_mfa_sel, sg_mfa_custom)

        sg_off = st.text_input("Offboarding Process", value=_saas_defaults.get('offboarding_process', ''))

        saas_rec_opts = ["Documented for critical platforms", "Unknown", "Other / Custom..."]
        idx_sg_rec, sg_rec_custom_def = _with_custom_prefill(_saas_defaults.get('recovery_responsibility', 'Unknown'), saas_rec_opts)
        sg_rec_sel = st.selectbox("Recovery Responsibility", saas_rec_opts, index=idx_sg_rec)
        sg_rec_custom = st.text_input("Custom Recovery Responsibility", value=sg_rec_custom_def if sg_rec_sel == "Other / Custom..." else "")
        sg_rec = _resolve_custom(sg_rec_sel, sg_rec_custom)

        saas_shadow_opts = ["CASB discovery", "Unknown", "Other / Custom..."]
        idx_sg_shadow, sg_shadow_custom_def = _with_custom_prefill(_saas_defaults.get('shadow_it_visibility', 'Unknown'), saas_shadow_opts)
        sg_shadow_sel = st.selectbox("Shadow IT Visibility", saas_shadow_opts, index=idx_sg_shadow)
        sg_shadow_custom = st.text_input("Custom Shadow IT Visibility", value=sg_shadow_custom_def if sg_shadow_sel == "Other / Custom..." else "")
        sg_shadow = _resolve_custom(sg_shadow_sel, sg_shadow_custom)

        saas_oauth_opts = ["Applications periodically reviewed", "User consent unrestricted or unknown", "Unknown", "Other / Custom..."]
        idx_sg_oauth, sg_oauth_custom_def = _with_custom_prefill(_saas_defaults.get('oauth_app_governance', 'Unknown'), saas_oauth_opts)
        sg_oauth_sel = st.selectbox("OAuth App Governance", saas_oauth_opts, index=idx_sg_oauth)
        sg_oauth_custom = st.text_input("Custom OAuth Governance", value=sg_oauth_custom_def if sg_oauth_sel == "Other / Custom..." else "")
        sg_oauth = _resolve_custom(sg_oauth_sel, sg_oauth_custom)

        sg_notes = st.text_area("Notes", value=_saas_defaults.get('notes', ''), key="saas_notes")
        _saas_dict = {
            "inventory_status": sg_inv,
            "critical_platforms": sg_cp,
            "sso_coverage": sg_sso,
            "mfa_coverage": sg_mfa,
            "offboarding_process": sg_off,
            "recovery_responsibility": sg_rec,
            "shadow_it_visibility": sg_shadow,
            "oauth_app_governance": sg_oauth,
            "notes": sg_notes,
        }

    # Asset Assurance
    with st.expander("Asset Assurance", expanded=False):
        st.subheader("Asset Assurance")
        aa_inv_opts = ["Hardware, software and cloud assets centrally recorded", "Incomplete or unknown", "Unknown", "Other / Custom..."]
        idx_aa_inv, aa_inv_custom_def = _with_custom_prefill(_aa_defaults.get('asset_inventory_maturity', 'Unknown'), aa_inv_opts)
        aa_inv_sel = st.selectbox("Asset Inventory Maturity", aa_inv_opts, index=idx_aa_inv)
        aa_inv_custom = st.text_input("Custom Asset Inventory", value=aa_inv_custom_def if aa_inv_sel == "Other / Custom..." else "")
        aa_inv = _resolve_custom(aa_inv_sel, aa_inv_custom)

        aa_eas = st.text_input("External Attack Surface Visibility", value=_aa_defaults.get('external_attack_surface_visibility', ''))
        aa_vrm_opts = ["Tracker with priorities and dates", "Findings reported but not centrally tracked", "Unknown", "Other / Custom..."]
        idx_aa_vrm, aa_vrm_custom_def = _with_custom_prefill(_aa_defaults.get('vulnerability_remediation_maturity', 'Unknown'), aa_vrm_opts)
        aa_vrm_sel = st.selectbox("Vulnerability Remediation Maturity", aa_vrm_opts, index=idx_aa_vrm)
        aa_vrm_custom = st.text_input("Custom Vulnerability Remediation", value=aa_vrm_custom_def if aa_vrm_sel == "Other / Custom..." else "")
        aa_vrm = _resolve_custom(aa_vrm_sel, aa_vrm_custom)

        aa_cfg = st.text_input("Secure Configuration Baseline", value=_aa_defaults.get('secure_configuration_baseline', ''))
        aa_change = st.text_input("Security Change Assurance", value=_aa_defaults.get('security_change_assurance', ''))
        aa_uts = st.text_input("Unsupported Technology Status", value=_aa_defaults.get('unsupported_technology_status', ''))
        _aa_dict = {
            "asset_inventory_maturity": aa_inv,
            "external_attack_surface_visibility": aa_eas,
            "vulnerability_remediation_maturity": aa_vrm,
            "secure_configuration_baseline": aa_cfg,
            "security_change_assurance": aa_change,
            "unsupported_technology_status": aa_uts,
        }

    # Monitoring Assurance
    with st.expander("Monitoring Assurance", expanded=False):
        st.subheader("Monitoring Assurance")
        mon_cov_opts = ["24/7 alert monitoring", "Business hours only", "Critical alerts outside hours", "Unknown", "Other / Custom..."]
        idx_mon_cov, mon_cov_custom_def = _with_custom_prefill(_mon_defaults.get('monitoring_coverage', 'Unknown'), mon_cov_opts)
        mon_cov_sel = st.selectbox("Monitoring Coverage", mon_cov_opts, index=idx_mon_cov)
        mon_cov_custom = st.text_input("Custom Monitoring Coverage", value=mon_cov_custom_def if mon_cov_sel == "Other / Custom..." else "")
        mon_cov = _resolve_custom(mon_cov_sel, mon_cov_custom)

        mon_logs_options = ["Endpoint", "Identity", "Microsoft 365", "Firewall", "SIEM", "Cloud"]
        _mon_logs_defaults = [v for v in (_mon_defaults.get('log_sources_monitored') or []) if v in mon_logs_options]
        _mon_logs_custom_list = [v for v in (_mon_defaults.get('log_sources_monitored') or []) if v not in mon_logs_options]
        mon_logs = st.multiselect("Log Sources Monitored", options=mon_logs_options, default=_mon_logs_defaults)
        mon_logs_custom = st.text_input("Custom Log Sources Monitored (separate by ';')", value="; ".join(_mon_logs_custom_list))
        mon_logs_final = mon_logs + [s.strip() for s in mon_logs_custom.split(';') if s.strip()]

        mon_ret = st.text_input("Log Retention", value=_mon_defaults.get('log_retention', ''))
        mon_esc = st.text_input("Out-of-hours Escalation", value=_mon_defaults.get('out_of_hours_escalation', ''))

        mon_auth_opts = ["Isolate and remediate", "Investigate and recommend", "Notify only", "Unknown", "Other / Custom..."]
        idx_mon_auth, mon_auth_custom_def = _with_custom_prefill(_mon_defaults.get('response_authority', 'Unknown'), mon_auth_opts)
        mon_auth_sel = st.selectbox("Response Authority", mon_auth_opts, index=idx_mon_auth)
        mon_auth_custom = st.text_input("Custom Response Authority", value=mon_auth_custom_def if mon_auth_sel == "Other / Custom..." else "")
        mon_auth = _resolve_custom(mon_auth_sel, mon_auth_custom)

        mon_test = st.text_input("Detection Testing", value=_mon_defaults.get('detection_testing', ''))
        mon_rep = st.text_input("Security Reporting Cadence", value=_mon_defaults.get('security_reporting_cadence', ''))
        mon_gaps = st.text_input("Known Coverage Gaps", value=_mon_defaults.get('known_coverage_gaps', ''))
        _mon_dict = {
            "monitoring_coverage": mon_cov,
            "log_sources_monitored": mon_logs_final,
            "log_retention": mon_ret,
            "out_of_hours_escalation": mon_esc,
            "response_authority": mon_auth,
            "detection_testing": mon_test,
            "security_reporting_cadence": mon_rep,
            "known_coverage_gaps": mon_gaps,
        }

    # Supplier Assurance & Third-Party Access
    with st.expander("Supplier Assurance & Third-Party Access", expanded=False):
        st.subheader("Supplier Assurance & Third-Party Access")
        sup_maturity_opts = ["Periodic review of critical suppliers", "None", "Unknown", "Other / Custom..."]
        idx_sup_mat, sup_mat_custom_def = _with_custom_prefill(_sup_defaults.get('supplier_assurance_maturity', 'Unknown'), sup_maturity_opts)
        sup_maturity_sel = st.selectbox("Supplier Assurance Maturity", sup_maturity_opts, index=idx_sup_mat)
        sup_maturity_custom = st.text_input("Custom Supplier Assurance Maturity", value=sup_mat_custom_def if sup_maturity_sel == "Other / Custom..." else "")
        sup_maturity = _resolve_custom(sup_maturity_sel, sup_maturity_custom)
        _sup_dict = {"supplier_assurance_maturity": sup_maturity}

        tpa_access_opts = ["Access exists", "Unknown", "Other / Custom..."]
        idx_tpa_acc, tpa_acc_custom_def = _with_custom_prefill(_tpa_defaults.get('access_present', 'Unknown'), tpa_access_opts)
        tpa_access_sel = st.selectbox("Third-Party Access Present", tpa_access_opts, index=idx_tpa_acc)
        tpa_access_custom = st.text_input("Custom Third-Party Access Present", value=tpa_acc_custom_def if tpa_access_sel == "Other / Custom..." else "")
        tpa_access = _resolve_custom(tpa_access_sel, tpa_access_custom)

        tpa_model_opts = ["Named accounts with MFA", "Shared accounts", "Unknown", "Other / Custom..."]
        idx_tpa_model, tpa_model_custom_def = _with_custom_prefill(_tpa_defaults.get('identity_model', 'Unknown'), tpa_model_opts)
        tpa_model_sel = st.selectbox("Identity Model", tpa_model_opts, index=idx_tpa_model)
        tpa_model_custom = st.text_input("Custom Identity Model", value=tpa_model_custom_def if tpa_model_sel == "Other / Custom..." else "")
        tpa_model = _resolve_custom(tpa_model_sel, tpa_model_custom)

        tpa_mfa_opts = ["Universal for supplier access", "Not enforced", "Unknown", "Other / Custom..."]
        idx_tpa_mfa, tpa_mfa_custom_def = _with_custom_prefill(_tpa_defaults.get('mfa_status', 'Unknown'), tpa_mfa_opts)
        tpa_mfa_sel = st.selectbox("MFA Status", tpa_mfa_opts, index=idx_tpa_mfa)
        tpa_mfa_custom = st.text_input("Custom Third-Party MFA", value=tpa_mfa_custom_def if tpa_mfa_sel == "Other / Custom..." else "")
        tpa_mfa = _resolve_custom(tpa_mfa_sel, tpa_mfa_custom)

        tpa_time_opts = ["Yes", "No", "Not applicable"]
        tpa_time = st.selectbox("Time-limited", tpa_time_opts, index=_safe_index(tpa_time_opts, _tpa_defaults.get('time_limited', 'Not applicable')))
        tpa_mon_opts = ["Yes", "No", "Not applicable"]
        tpa_mon = st.selectbox("Monitored", tpa_mon_opts, index=_safe_index(tpa_mon_opts, _tpa_defaults.get('monitored', 'Not applicable')))
        tpa_review_opts = ["Yes", "No", "Not applicable"]
        tpa_review = st.selectbox("Periodically Reviewed", tpa_review_opts, index=_safe_index(tpa_review_opts, _tpa_defaults.get('periodically_reviewed', 'Not applicable')))

        tpa_deps = st.text_input("Critical Supplier Dependencies", value=_tpa_defaults.get('critical_supplier_dependencies', ''))

        tpa_contract_opts = ["Standard requirements for critical suppliers", "None or unknown", "Other / Custom..."]
        idx_tpa_contract, tpa_contract_custom_def = _with_custom_prefill(_tpa_defaults.get('contractual_security_requirements', 'None or unknown'), tpa_contract_opts)
        tpa_contract_sel = st.selectbox("Contractual Security Requirements", tpa_contract_opts, index=idx_tpa_contract)
        tpa_contract_custom = st.text_input("Custom Contractual Requirements", value=tpa_contract_custom_def if tpa_contract_sel == "Other / Custom..." else "")
        tpa_contract = _resolve_custom(tpa_contract_sel, tpa_contract_custom)

        tpa_notify = st.text_input("Incident Notification", value=_tpa_defaults.get('incident_notification', ''))
        tpa_exit = st.text_input("Exit Planning", value=_tpa_defaults.get('exit_planning', ''))
        tpa_conc = st.text_input("Concentration Risk", value=_tpa_defaults.get('concentration_risk', ''))
        tpa_notes = st.text_area("Notes", value=_tpa_defaults.get('notes', ''), key="tpa_notes")
        _tpa_dict = {
            "access_present": tpa_access, "identity_model": tpa_model, "mfa_status": tpa_mfa, "time_limited": tpa_time,
            "monitored": tpa_mon, "periodically_reviewed": tpa_review, "critical_supplier_dependencies": tpa_deps,
            "contractual_security_requirements": tpa_contract, "incident_notification": tpa_notify, "exit_planning": tpa_exit,
            "concentration_risk": tpa_conc, "notes": tpa_notes,
        }

    # Recovery Assurance
    with st.expander("Recovery Assurance", expanded=False):
        st.subheader("Recovery Assurance")
        rec_rt_opts = ["Regular representative restores", "Ad hoc", "Never", "Unknown", "Other / Custom..."]
        idx_rec_rt, rec_rt_custom_def = _with_custom_prefill(_rec_defaults.get('restore_testing', 'Unknown'), rec_rt_opts)
        rec_rt_sel = st.selectbox("Restore Testing", rec_rt_opts, index=idx_rec_rt)
        rec_rt_custom = st.text_input("Custom Restore Testing", value=rec_rt_custom_def if rec_rt_sel == "Other / Custom..." else "")
        rec_rt = _resolve_custom(rec_rt_sel, rec_rt_custom)

        rec_imm_opts = ["Immutable or air-gapped for critical backups", "None", "Unknown", "Other / Custom..."]
        idx_rec_imm, rec_imm_custom_def = _with_custom_prefill(_rec_defaults.get('immutability_status', 'Unknown'), rec_imm_opts)
        rec_imm_sel = st.selectbox("Immutability Status", rec_imm_opts, index=idx_rec_imm)
        rec_imm_custom = st.text_input("Custom Immutability", value=rec_imm_custom_def if rec_imm_sel == "Other / Custom..." else "")
        rec_imm = _resolve_custom(rec_imm_sel, rec_imm_custom)

        rec_sep = st.text_input("Administrative Separation", value=_rec_defaults.get('administrative_separation', ''))
        rec_srv = st.text_input("Service Recovery Testing", value=_rec_defaults.get('service_recovery_testing', ''))
        rec_evd = st.text_input("Evidence Retained", value=_rec_defaults.get('evidence_retained', ''))
        rec_owner = st.text_input("Recovery Ownership", value=_rec_defaults.get('recovery_ownership', ''))
        rec_notes = st.text_area("Notes", value=_rec_defaults.get('notes', ''), key="rec_notes")
        _rec_dict = {
            "restore_testing": rec_rt, "immutability_status": rec_imm, "administrative_separation": rec_sep,
            "service_recovery_testing": rec_srv, "evidence_retained": rec_evd, "recovery_ownership": rec_owner, "notes": rec_notes,
        }

    # Incident Response Assurance
    with st.expander("Incident Response Assurance", expanded=False):
        st.subheader("Incident Response Assurance")
        ir_roles_opts = ["Technical and business roles documented", "Informal", "Unknown", "Other / Custom..."]
        idx_ir_roles, ir_roles_custom_def = _with_custom_prefill(_ir_defaults.get('roles_defined', 'Unknown'), ir_roles_opts)
        ir_roles_sel = st.selectbox("Roles Defined", ir_roles_opts, index=idx_ir_roles)
        ir_roles_custom = st.text_input("Custom Roles Defined", value=ir_roles_custom_def if ir_roles_sel == "Other / Custom..." else "")
        ir_roles = _resolve_custom(ir_roles_sel, ir_roles_custom)

        ir_bauth_opts = ["Documented", "Unknown", "Other / Custom..."]
        idx_ir_bauth, ir_bauth_custom_def = _with_custom_prefill(_ir_defaults.get('business_decision_authority', 'Unknown'), ir_bauth_opts)
        ir_bauth_sel = st.selectbox("Business Decision Authority", ir_bauth_opts, index=idx_ir_bauth)
        ir_bauth_custom = st.text_input("Custom Business Decision Authority", value=ir_bauth_custom_def if ir_bauth_sel == "Other / Custom..." else "")
        ir_bauth = _resolve_custom(ir_bauth_sel, ir_bauth_custom)

        ir_tech_opts = ["Endpoint isolation authorised", "Unknown", "Other / Custom..."]
        idx_ir_tech, ir_tech_custom_def = _with_custom_prefill(_ir_defaults.get('technical_response_authority', 'Unknown'), ir_tech_opts)
        ir_tech_sel = st.selectbox("Technical Response Authority", ir_tech_opts, index=idx_ir_tech)
        ir_tech_custom = st.text_input("Custom Technical Response Authority", value=ir_tech_custom_def if ir_tech_sel == "Other / Custom..." else "")
        ir_tech = _resolve_custom(ir_tech_sel, ir_tech_custom)

        ir_tt_opts = ["Within the past year", "More than one year ago", "Never", "Unknown", "Other / Custom..."]
        idx_ir_tt, ir_tt_custom_def = _with_custom_prefill(_ir_defaults.get('tabletop_status', 'Unknown'), ir_tt_opts)
        ir_tt_sel = st.selectbox("Tabletop Status", ir_tt_opts, index=idx_ir_tt)
        ir_tt_custom = st.text_input("Custom Tabletop Status", value=ir_tt_custom_def if ir_tt_sel == "Other / Custom..." else "")
        ir_tt = _resolve_custom(ir_tt_sel, ir_tt_custom)

        ir_oob = st.text_input("Out-of-band Communications", value=_ir_defaults.get('out_of_band_communications', ''))
        ir_cris = st.text_input("Crisis Communications", value=_ir_defaults.get('crisis_communications', ''))
        ir_reg_opts = ["Decision process and templates prepared", "Included in exercises", "Unknown", "Other / Custom..."]
        idx_ir_reg, ir_reg_custom_def = _with_custom_prefill(_ir_defaults.get('regulatory_notification_readiness', 'Unknown'), ir_reg_opts)
        ir_reg_sel = st.selectbox("Regulatory Notification Readiness", ir_reg_opts, index=idx_ir_reg)
        ir_reg_custom = st.text_input("Custom Regulatory Notification Readiness", value=ir_reg_custom_def if ir_reg_sel == "Other / Custom..." else "")
        ir_reg = _resolve_custom(ir_reg_sel, ir_reg_custom)

        ir_sup = st.text_input("Supplier Coordination", value=_ir_defaults.get('supplier_coordination', ''))
        ir_less = st.text_input("Lessons Learned Process", value=_ir_defaults.get('lessons_learned_process', ''))
        ir_notes = st.text_area("Notes", value=_ir_defaults.get('notes', ''), key="ir_notes")
        _ir_dict = {
            "roles_defined": ir_roles, "business_decision_authority": ir_bauth, "technical_response_authority": ir_tech,
            "tabletop_status": ir_tt, "out_of_band_communications": ir_oob, "crisis_communications": ir_cris,
            "regulatory_notification_readiness": ir_reg, "supplier_coordination": ir_sup, "lessons_learned_process": ir_less, "notes": ir_notes,
        }

    # Assurance Status (map)
    with st.expander("Assurance Status", expanded=False):
        st.subheader("Assurance Status")
        _status_opts = ["Confirmed during consultation", "Reported, evidence not reviewed", "Requires supplier confirmation", "Not applicable", "Unknown"]
        def _status_select(label_key, current):
            return st.selectbox(label_key, _status_opts, index=_safe_index(_status_opts, current or "Unknown"))
        as_default = _status_select("Default Assurance", (_as_defaults or {}).get("default", "Unknown"))
        as_ip = _status_select("Information Protection", (_as_defaults or {}).get("information_protection", ""))
        as_idg = _status_select("Identity Governance", (_as_defaults or {}).get("identity_governance", ""))
        as_saas = _status_select("SaaS Governance", (_as_defaults or {}).get("saas_governance", ""))
        as_mon = _status_select("Monitoring", (_as_defaults or {}).get("monitoring", ""))
        as_sup = _status_select("Supplier Security", (_as_defaults or {}).get("supplier_security", ""))
        as_rec = _status_select("Recovery", (_as_defaults or {}).get("recovery", ""))
        as_ir = _status_select("Incident Response", (_as_defaults or {}).get("incident_response", ""))
        as_ot = _status_select("OT & IoT", (_as_defaults or {}).get("ot_iot", ""))
        as_pf = _status_select("Payment Fraud", (_as_defaults or {}).get("payment_fraud", ""))
        as_app = _status_select("Application Security", (_as_defaults or {}).get("application_security", ""))
        as_int = _status_select("Integration Assurance", (_as_defaults or {}).get("integration_assurance", ""))

        _as_map = {
            "default": as_default,
            "information_protection": as_ip,
            "identity_governance": as_idg,
            "saas_governance": as_saas,
            "monitoring": as_mon,
            "supplier_security": as_sup,
            "recovery": as_rec,
            "incident_response": as_ir,
            "ot_iot": as_ot,
            "payment_fraud": as_pf,
            "application_security": as_app,
            "integration_assurance": as_int,
        }

## --- PARTNERSHIP GOVERNANCE ---
st.markdown("### 🔗 Partnership Governance")
_pt_opts = ["Fully Managed", "Co-Managed"]
partnership_type = st.radio("Partnership Governance Model", _pt_opts, index=(_safe_index(_pt_opts, TEST_DATA.get('partnership_type')) if dev else 0))
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
    index=(_safe_index(managed_status_options, TEST_DATA.get('managed_service_status')) if dev else 0),
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
    mfa_status = st.selectbox("MFA Enforcement", mfa_options, index=(_safe_index(mfa_options, TEST_DATA.get('mfa_status')) if dev else 0), help="Example: Privileged Accounts Only")
    patching_options = ["Select Patch Management...", "Manual / Ad-hoc", "Automated (OS Only)", "Automated (OS & Third-Party)"]
    patching = st.selectbox("Patch Management", patching_options, index=(_safe_index(patching_options, TEST_DATA.get('patching')) if dev else 0), help="Example: Manual / Ad-hoc")
    backup_options = ["Select Backup Strategy...", "No Formal Backups", "On-Premise Only", "Cloud/Offsite (Standard)", "Immutable / Air-Gapped"]
    backups = st.selectbox("Backup Strategy", backup_options, index=(_safe_index(backup_options, TEST_DATA.get('backups')) if dev else 0), help="Example: On-Premise Only")
    
with op_col2:
    insurance_options = ["Select Cyber Insurance Status...", "None", "Exploring Requirements", "Active Policy"]
    insurance = st.selectbox("Cyber Insurance Status", insurance_options, index=(_safe_index(insurance_options, TEST_DATA.get('insurance')) if dev else 0), help="Example: None")
    rto_options = ["Select Downtime Tolerance...", "< 4 Hours (Critical)", "12-24 Hours", "48+ Hours"]
    rto = st.selectbox("Downtime Tolerance", rto_options, index=(_safe_index(rto_options, TEST_DATA.get('rto')) if dev else 0), help="Example: 12-24 Hours")
    ir_readiness_options = ["Select Incident Response (IR) Readiness...", "No Formal Plan", "Documented IR Plan (Untested)", "Tested IR Plan with Active Retainer"]
    ir_readiness = st.selectbox("Incident Response (IR) Readiness", ir_readiness_options, index=(_safe_index(ir_readiness_options, TEST_DATA.get('ir_readiness')) if dev else 0), help="Example: No Formal Plan")
    
    ir_retainer_options = ["Select Elite IR Retainer / DFIR Provider...", "None", "Sophos MDR Plus / Incident Response", "Microsoft DART", "CrowdStrike Falcon Complete IR", "Mandiant / Google IR", "Unit 42 (Palo Alto)", "Kroll Cyber Risk", "Secureworks IR", "Rapid7 IR", "Other"]
    ir_retainer = st.selectbox("Elite IR Retainer / DFIR Provider", ir_retainer_options, index=(_safe_index(ir_retainer_options, TEST_DATA.get('ir_retainer')) if dev else 0), help="Example: None")

st.divider()

st.markdown("### 🤖 AI Usage & Governance")
ai_policy_opts = ["Select AI Usage Policy...", "None", "Informal guidance", "Formalised policy enforced"]
ai_usage_policy = st.selectbox(
    "AI Usage Policy",
    ai_policy_opts,
    index=(_safe_index(ai_policy_opts, TEST_DATA.get('ai_usage_policy', 'None')) if dev else 0),
    help="State of AI acceptable use policy and governance."
)

approved_ai_tools = st.multiselect(
    "Approved Company AI Tools",
    ["Microsoft Copilot", "ChatGPT", "Google Gemini", "Claude", "Custom (in-house)", "None / Unapproved"],
    default=(TEST_DATA.get('approved_ai_tools', []) if dev else []),
    help="Approved AI assistants or models in use."
)

shadow_ai_opts = ["Select Shadow AI Monitoring...", "None", "Planned", "Enabled"]
shadow_ai_monitoring = st.selectbox(
    "Shadow AI Monitoring",
    shadow_ai_opts,
    index=(_safe_index(shadow_ai_opts, TEST_DATA.get('shadow_ai_monitoring', 'None')) if dev else 0),
    help="Discovery and control of unsanctioned AI usage."
)

ai_dlp_controls = st.multiselect(
    "AI Data Loss Controls",
    ["Microsoft Purview DLP", "Defender for Cloud Apps (CASB)", "CASB/SSE (Netskope)", "Proxy controls", "None"],
    default=(TEST_DATA.get('ai_dlp_controls', []) if dev else []),
    help="Controls applied to prompts/responses and AI interactions."
)

st.divider()

## --- SECURITY CULTURE & HUMAN RISK ---
with st.container():
    # Persisted options for import/export compatibility
    _q1_opts = ["Never", "Annually", "Bi-Annually", "Quarterly", "Monthly"]
    _q2_opts = ["None", "Annual Compliance Video", "Annual with simulations", "Continuous with active coaching", "Continuous with nudges/micro-learning"]
    _reporting_opts = ["None", "Informal", "Documented clear routes", "Anonymous hotline", "One-click report (mail client)"]
    _coaching_opts = ["None", "Ad hoc", "Manager-led coaching", "Structured with tracking", "Just-in-time micro-coaching"]
    _role_opts = ["None", "High-risk roles only", "Partial key roles", "Comprehensive role-based"]
    _leadership_opts = ["None", "Ad hoc", "Monthly stand-up", "Quarterly / regular with OKRs", "Board KPIs/OKRs"]
    _policy_ack_opts = ["None", "Annual", "On hire and on-change", "Quarterly or on-change"]
    _q3_opts = ["Most users are Local Admins", "Only IT/Devs are Local Admins", "Zero Trust (No Local Admins/LAPS)"]

    with st.expander("Programme Controls", expanded=True):
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            q1 = st.radio("Phishing Simulations", _q1_opts, index=(_safe_index(_q1_opts, TEST_DATA.get('culture_q1')) if dev else 0))
        with col_c2:
            q2 = st.radio("Security Training Programme", _q2_opts, index=(_safe_index(_q2_opts, TEST_DATA.get('culture_q2')) if dev else 0))
        with col_c3:
            q3 = st.radio("Endpoint Privileges (telemetry)", _q3_opts, index=(_safe_index(_q3_opts, TEST_DATA.get('culture_q3')) if dev else 0))

        col_c4, col_c5, col_c6 = st.columns(3)
        with col_c4:
            reporting_routes = st.radio("Reporting Routes", _reporting_opts, index=(_safe_index(_reporting_opts, TEST_DATA.get('culture_reporting_routes')) if dev else 0))
        with col_c5:
            followup_coaching = st.radio("Follow-up Coaching", _coaching_opts, index=(_safe_index(_coaching_opts, TEST_DATA.get('culture_followup_coaching')) if dev else 0))
        with col_c6:
            role_training = st.radio("Role-based Training Coverage", _role_opts, index=(_safe_index(_role_opts, TEST_DATA.get('culture_role_training')) if dev else 0))

        col_c7, col_c8 = st.columns(2)
        with col_c7:
            leadership = st.radio("Leadership Engagement", _leadership_opts, index=(_safe_index(_leadership_opts, TEST_DATA.get('culture_leadership_engagement')) if dev else 0))
        with col_c8:
            policy_ack = st.radio("Policy Acknowledgement", _policy_ack_opts, index=(_safe_index(_policy_ack_opts, TEST_DATA.get('culture_policy_ack')) if dev else 0))

    with st.expander("Programme Metrics (optional)", expanded=False):
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            phish_fail = st.number_input("Phish Failure Rate (last 90 days, %)", min_value=0, max_value=100, value=int(TEST_DATA.get('culture_phish_fail_pct_90d', 0)) if dev else 0)
        with col_m2:
            report_rate = st.number_input("Report Rate (last 90 days, %)", min_value=0, max_value=100, value=int(TEST_DATA.get('culture_report_rate_pct_90d', 0)) if dev else 0)

    # Culture score (behavioural only; exclude MFA and endpoint admin)
    def _score(map_opts, sel):
        try:
            if map_opts == "q1":
                return {"Never": 0, "Annually": 1, "Bi-Annually": 1, "Quarterly": 2, "Monthly": 2}.get(sel, 0)
            if map_opts == "q2":
                return {"None": 0, "Annual Compliance Video": 1, "Annual with simulations": 1, "Continuous with active coaching": 2, "Continuous with nudges/micro-learning": 2}.get(sel, 0)
            if map_opts == "report":
                return {"None": 0, "Informal": 1, "Documented clear routes": 2, "Anonymous hotline": 2, "One-click report (mail client)": 2}.get(sel, 0)
            if map_opts == "coach":
                return {"None": 0, "Ad hoc": 1, "Manager-led coaching": 1, "Structured with tracking": 2, "Just-in-time micro-coaching": 2}.get(sel, 0)
            if map_opts == "role":
                return {"None": 0, "High-risk roles only": 1, "Partial key roles": 1, "Comprehensive role-based": 2}.get(sel, 0)
            if map_opts == "lead":
                return {"None": 0, "Ad hoc": 1, "Monthly stand-up": 2, "Quarterly / regular with OKRs": 2, "Board KPIs/OKRs": 2}.get(sel, 0)
            if map_opts == "ack":
                return {"None": 0, "Annual": 1, "On hire and on-change": 2, "Quarterly or on-change": 2}.get(sel, 0)
            return 0
        except Exception:
            return 0

    culture_score = 0
    culture_score += _score("q1", q1)
    culture_score += _score("q2", q2)
    culture_score += _score("report", reporting_routes)
    culture_score += _score("coach", followup_coaching)
    culture_score += _score("role", role_training)
    culture_score += _score("lead", leadership)
    culture_score += _score("ack", policy_ack)

    if culture_score <= 5:
        savviness_label = "Pillar 1: Reactive Culture"
    elif culture_score <= 10:
        savviness_label = "Pillar 2: Proactive Culture"
    else:
        savviness_label = "Pillar 3: Adaptive Culture"

    savviness_profiles = {
        "Pillar 1: Reactive Culture": "Currently developing baseline awareness. Build reporting routes, establish structured coaching, and adopt role-based training.",
        "Pillar 2: Proactive Culture": "Strong baseline awareness. Programmes include clear routes, consistent coaching, and role-targeted content.",
        "Pillar 3: Adaptive Culture": "Highly optimised, zero-trust mindset. Users actively report threats; leadership drives OKRs; training is continuous and role-specific."
    }

    st.info(f"**Calculated Score: {culture_score}/14** | Result: {savviness_label} — *{savviness_profiles[savviness_label]}*")
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
    "savviness_label": savviness_label,
    "culture_score": culture_score,
    "culture_q1": q1,
    "culture_q2": q2,
    "culture_q3": q3,
    "endpoints": endpoints, 
    "servers": servers, 
    "remote_access": _norm(remote_access),
    "saas_backup": _norm(saas_backup, "None (Relying on Microsoft/Google)"),
    "ir_readiness": _norm(ir_readiness),
    "operating_systems": ", ".join(operating_systems) if operating_systems else "None", 
    "critical_infra": critical_infra, 
    "mdr_provider": _norm(mdr_provider, "None"), 
    "endpoint": _norm(endpoint), 
    "endpoint_posture": _norm(endpoint_posture),
    "firewall": _norm(firewall), 
    "identity": _norm(identity), 
    "m365_license": _norm(m365_license_str, "None / On-Prem Only"), 
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
    # Security Culture (behavioural fields)
    "culture_q1": q1,
    "culture_q2": q2,
    "culture_q3": q3,  # telemetry only; excluded from culture_score
    "culture_reporting_routes": reporting_routes,
    "culture_followup_coaching": followup_coaching,
    "culture_role_training": role_training,
    "culture_leadership_engagement": leadership,
    "culture_policy_ack": policy_ack,
    "culture_phish_fail_pct_90d": phish_fail,
    "culture_report_rate_pct_90d": report_rate,
    # Operational telemetry
    "mfa_status": _norm(mfa_status),
    "patching": _norm(patching),
    "backups": _norm(backups),
    "insurance": _norm(insurance, "None"),
    "rto": _norm(rto),
    "advanced_controls": ", ".join(advanced_controls) if advanced_controls else "None",
    "proactive_tools": ", ".join(proactive_tools) if proactive_tools else "None",
    "ir_retainer": _norm(ir_retainer, "None"),
    "ai_usage_policy": _norm(ai_usage_policy),
    "approved_ai_tools": ", ".join(approved_ai_tools) if approved_ai_tools else "None",
    "shadow_ai_monitoring": _norm(shadow_ai_monitoring),
    "ai_dlp_controls": ", ".join(ai_dlp_controls) if ai_dlp_controls else "None",
    "banned_vendors": banned_vendors,
    "managed_service_status": _norm(st.session_state.get('managed_service_status', 'None'), "None"),
    "co_managed_units": st.session_state.get('co_managed_units', 0),
    "partnership_type": partnership_type,
    # Structured profiles from UI (JSON-serialisable)
    "critical_asset_profile": _cap_dict,
    "service_resilience_profile": _sr_dict,
    "information_protection_profile": _ip_dict,
    "identity_governance_profile": _idg_dict,
    "saas_governance_profile": _saas_dict,
    "asset_assurance_profile": _aa_dict,
    "monitoring_assurance_profile": _mon_dict,
    "supplier_assurance_profile": _sup_dict,
    "third_party_access_profile": _tpa_dict,
    "recovery_assurance_profile": _rec_dict,
    "incident_response_assurance_profile": _ir_dict,
    "assurance_status": _as_map,
}

import json as _json
_client_hash = _json.dumps(client_inputs, sort_keys=True, default=str)
if st.session_state.get('_client_inputs_hash') != _client_hash:
    st.session_state['client_inputs'] = _sanitise_client_inputs(client_inputs)
    # Attach structured consultation profiles if present in imported TEST_DATA (preserves nested assurance/governance)
    try:
        if isinstance(TEST_DATA, dict):
            for key in [
                "critical_asset_profile",
                "service_resilience_profile",
                "information_protection_profile",
                "identity_governance_profile",
                "saas_governance_profile",
                "asset_assurance_profile",
                "monitoring_assurance_profile",
                "supplier_assurance_profile",
                "third_party_access_profile",
                "recovery_assurance_profile",
                "incident_response_assurance_profile",
                "assurance_status",
            ]:
                if key in TEST_DATA and key not in st.session_state['client_inputs']:
                    st.session_state['client_inputs'][key] = TEST_DATA[key]
        # Ensure defaults exist to avoid None lookups downstream (no open dicts in Pydantic models)
        for key, default in [
            ("critical_asset_profile", DEFAULT_CRITICAL_ASSET_PROFILE),
            ("service_resilience_profile", DEFAULT_SERVICE_RESILIENCE_PROFILE),
            ("information_protection_profile", DEFAULT_INFORMATION_PROTECTION),
            ("identity_governance_profile", DEFAULT_IDENTITY_GOVERNANCE),
            ("saas_governance_profile", DEFAULT_SAAS_GOVERNANCE),
            ("asset_assurance_profile", DEFAULT_ASSET_ASSURANCE),
            ("monitoring_assurance_profile", DEFAULT_MONITORING_ASSURANCE),
            ("supplier_assurance_profile", DEFAULT_SUPPLIER_ASSURANCE),
            ("third_party_access_profile", DEFAULT_THIRD_PARTY_ACCESS_PROFILE),
            ("recovery_assurance_profile", DEFAULT_RECOVERY_ASSURANCE),
            ("incident_response_assurance_profile", DEFAULT_IR_ASSURANCE),
            ("assurance_status", ASSURANCE_STATUS_DEFAULT),
        ]:
            if key not in st.session_state['client_inputs'] or st.session_state['client_inputs'][key] is None:
                st.session_state['client_inputs'][key] = default
    except Exception:
        pass
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
    if st.button("Generate Threat Simulation", type="primary", disabled=(_remaining > 0)):
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

elif st.session_state.get('workflow') == "🎯 Tabletop Exercise & Facilitator":
    # Lightweight keepalive: keep websocket alive during facilitation to avoid idle timeouts
    st.markdown(
        "<script>setInterval(()=>{fetch(window.location.href,{cache:'no-store'}).catch(()=>{})},60000);</script>",
        unsafe_allow_html=True
    )
    st.header("🎯 Tabletop Exercise Builder & Facilitator")

    if "tabletop_plan" not in st.session_state:
        st.session_state["tabletop_plan"] = None
    if "tabletop_notes" not in st.session_state:
        st.session_state["tabletop_notes"] = []
    if "live_scenario_idx" not in st.session_state:
        st.session_state["live_scenario_idx"] = 0
    if "live_inject_idx" not in st.session_state:
        st.session_state["live_inject_idx"] = 0

    tab_design, tab_facilitate, tab_aar = st.tabs([
        "🛠️ 1. Scenario Designer & Editor", 
        "🎙️ 2. Live Facilitation Console", 
        "📋 3. After-Action Review (AAR)"
    ])

    with tab_design:
        st.subheader("Generate & Customise Scenarios")
        st.caption("Scenarios are compiled from the client's actual estate, IR readiness, and operational gaps.")

        col_sc1, col_sc2 = st.columns(2)
        with col_sc1:
            selected_themes = st.multiselect(
                "Select Scenarios to Include:",
                ["Cyber Attack (Ransomware / BEC)", "Unauthorised Access (Social Engineering / Service Desk)", "Cloud / M365 Outage (DR & Business Continuity)"],
                default=["Cyber Attack (Ransomware / BEC)", "Unauthorised Access (Social Engineering / Service Desk)"]
            )
        with col_sc2:
            st.markdown(f"**Target Customer:** `{cached_customer_name}`")
            st.markdown(f"**Key Assets:** `{client_inputs.get('critical_infra', 'Crown Jewels')}`")

        if st.button("Generate Bespoke Tabletop Plan", type="primary"):
            with st.spinner("Compiling scenarios and facilitator guides from estate profile..."):
                client = LLMEngine.get_client()
                deployment = get_config(ConfigKey.AZURE_DEPLOYMENT, "gpt-4o")
                prompt = build_tabletop_plan_prompt(st.session_state['client_inputs'], selected_themes)
                plan = LLMEngine.generate_structured_report(client, deployment, SYSTEM_PERSONA_TABLETOP, prompt, TabletopMasterPlan)
                if plan:
                    st.session_state["tabletop_plan"] = plan.model_dump()
                    st.success("Tabletop scenario compiled. You can now customise below.")
                else:
                    st.error("Generation failed. Check Azure configuration.")

        if st.session_state.get("tabletop_plan"):
            st.divider()
            st.subheader("Bespoke Customisation")
            plan = st.session_state["tabletop_plan"]
            plan["exercise_title"] = st.text_input("Exercise Title", value=plan.get("exercise_title", ""))

            for s_idx, scn in enumerate(plan.get("scenarios", [])):
                with st.expander(f"Scenario {s_idx + 1}: {scn.get('scenario_title')}", expanded=True):
                    scn["scenario_title"] = st.text_input("Title", value=scn.get("scenario_title"), key=f"title_{s_idx}")
                    scn["initial_vector"] = st.text_input("Initial Vector", value=scn.get("initial_vector"), key=f"vec_{s_idx}")
                    
                    for i_idx, inj in enumerate(scn.get("injects", [])):
                        st.markdown(f"**Inject {i_idx + 1}: {inj.get('simulated_timestamp')}**")
                        inj["scenario_narrative"] = st.text_area("Narrative", value=inj.get("scenario_narrative"), key=f"narr_{s_idx}_{i_idx}")
                        inj["expected_mature_response"] = st.text_area("What Good Looks Like", value=inj.get("expected_mature_response"), key=f"resp_{s_idx}_{i_idx}")

            col_lock1, col_lock2 = st.columns(2)
            with col_lock1:
                pptx_data = create_tabletop_pptx(plan)
                st.download_button("📊 Download Presentation Deck (.pptx)", data=pptx_data, file_name=f"{cached_customer_name}_Tabletop_Deck.pptx", mime="application/vnd.openxmlformats-officedocument.presentationml.presentation")
            with col_lock2:
                pdf_data = create_tabletop_facilitator_pdf(plan)
                st.download_button("📑 Download Facilitator Guide (.pdf)", data=pdf_data, file_name=f"{cached_customer_name}_Facilitator_Guide.pdf", mime="application/pdf")

    with tab_facilitate:
        if not st.session_state.get("tabletop_plan"):
            st.info("Please generate or load a tabletop scenario in Tab 1 before facilitating.")
        else:
            plan = st.session_state["tabletop_plan"]
            scenarios = plan.get("scenarios", [])
            s_idx = st.session_state["live_scenario_idx"]
            current_scenario = scenarios[s_idx]
            injects = current_scenario.get("injects", [])
            i_idx = st.session_state["live_inject_idx"]
            current_inject = injects[i_idx]

            st.subheader(f"Scenario {s_idx + 1}: {current_scenario.get('scenario_title')}")
            col_stat1, col_stat2 = st.columns([3, 1])
            with col_stat1:
                st.progress((i_idx + 1) / len(injects), text=f"Inject {i_idx + 1} of {len(injects)}: {current_inject.get('phase_title')}")
            with col_stat2:
                st.caption(f"Clock: **{current_inject.get('simulated_timestamp')}**")

            st.info(f"### Situation Brief:\n{current_inject.get('scenario_narrative')}")

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
            room_decision = st.text_area("What was the client's decision/response?", key=f"rec_dec_{s_idx}_{i_idx}", placeholder="e.g., Client decided not to isolate the endpoint; contacted user on personal phone...")
            facilitator_notes = st.text_input("Facilitator assessment notes (for AAR)", key=f"rec_eval_{s_idx}_{i_idx}", placeholder="e.g., Hesitated for 25 mins on declaring severity...")

            with st.expander("🎲 Need a Dynamic Pivot? (Inject Consequence)", expanded=False):
                st.caption("If the room acted poorly or solved the problem too quickly, trigger an immediate adaptive consequence.")
                if st.button("Generate Immediate Consequence"):
                    with st.spinner("Calculating environmental consequence..."):
                        client = LLMEngine.get_client()
                        deployment = get_config(ConfigKey.AZURE_DEPLOYMENT, "gpt-4o")
                        p_prompt = build_tabletop_pivot_prompt(current_scenario, current_inject, room_decision)
                        pivot = LLMEngine.generate_structured_report(client, deployment, SYSTEM_PERSONA_TABLETOP, p_prompt, TabletopPivotResponse)
                        if pivot:
                            st.warning(f"**CONSEQUENCE:** {pivot.consequence_narrative}")
                            st.markdown("**Urgent Probes:**")
                            for q in pivot.urgent_pivot_questions:
                                st.write(f"- {q}")

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
                    st.session_state["tabletop_notes"].append({
                        "scenario": current_scenario.get("scenario_title"),
                        "phase": current_inject.get("phase_title"),
                        "decision": room_decision,
                        "notes": facilitator_notes
                    })
                    if i_idx < len(injects) - 1:
                        st.session_state["live_inject_idx"] += 1
                    elif s_idx < len(scenarios) - 1:
                        st.session_state["live_scenario_idx"] += 1
                        st.session_state["live_inject_idx"] = 0
                    else:
                        st.success("Exercise completed! Proceed to Tab 3 for the After-Action Report.")
                    st.rerun()

    with tab_aar:
        st.subheader("Post-Exercise Review & Maturity Delta")
        if not st.session_state.get("tabletop_notes"):
            st.info("No exercise notes captured yet. Conduct the live facilitation in Tab 2 to populate findings.")
        else:
            if st.button("Generate After-Action Report (AAR)", type="primary"):
                with st.spinner("Evaluating room performance and synthesising AAR..."):
                    client = LLMEngine.get_client()
                    deployment = get_config(ConfigKey.AZURE_DEPLOYMENT, "gpt-4o")
                    aar_prompt = build_tabletop_aar_prompt(st.session_state["tabletop_plan"], st.session_state["tabletop_notes"], st.session_state["client_inputs"])
                    aar_obj = LLMEngine.generate_structured_report(client, deployment, SYSTEM_PERSONA_TABLETOP, aar_prompt, TabletopAAR)
                    if aar_obj:
                        st.session_state["aar_result"] = aar_obj
                        st.success("After-Action Report generated!")

            if st.session_state.get("aar_result"):
                aar = st.session_state["aar_result"]
                st.markdown(f"### Evaluated Performance: `{aar.overall_maturity_observed}`")
                st.write(aar.executive_summary)

                col_res1, col_res2 = st.columns(2)
                with col_res1:
                    st.markdown("#### ✅ Demonstrated Strengths")
                    for s in aar.key_strengths:
                        st.markdown(f"- {s}")
                with col_res2:
                    st.markdown("#### ⚠️ Identified Critical Gaps")
                    for g in aar.critical_gaps_identified:
                        st.markdown(f"- {g}")

                st.divider()
                st.subheader("🔄 Sync Insights into Client Profile")
                st.caption("Update the client's master profile with these findings to inform future maturity assessments and tabletops.")
                if st.button("Apply Delta to Client Profile"):
                    import datetime
                    today_str = datetime.date.today().isoformat()
                    st.session_state['client_inputs']['incident_response_assurance_profile']['tabletop_status'] = "Within the past year"
                    existing_notes = st.session_state['client_inputs']['incident_response_assurance_profile'].get('notes', '')
                    st.session_state['client_inputs']['incident_response_assurance_profile']['notes'] = (
                        f"{existing_notes}\n[{today_str} Tabletop AAR]: {aar.delta_notes_for_profile}".strip()
                    )
                    st.success(f"Profile updated! The incident_response_assurance_profile now reflects the exercise conducted on {today_str}.")

elif st.session_state['workflow'] == "📈 Cybersecurity Maturity Assessment":
    st.header("Cybersecurity Maturity Assessment")
    # Hint: evidence controls are rendered above as top-level sections
    st.caption("Use the top-level Governance & Assurance Evidence sections above to capture domain evidence before generating.")
if st.session_state.get('workflow') == "📈 Cybersecurity Maturity Assessment" and st.button("Generate Maturity Roadmap", type="primary"):
    if bool(st.session_state.get('staged_enabled', False)):
        st.session_state["_last_generation_ts"] = time.time()
        with st.spinner("Compiling Cybersecurity Maturity Assessment (staged)..."):
            client = LLMEngine.get_client()
            deployment = get_config(ConfigKey.AZURE_DEPLOYMENT, "gpt-4o")
            header_prompt = build_maturity_header_prompt(st.session_state["client_inputs"])
            header_obj = LLMEngine.generate_structured_report(client, deployment, SYSTEM_PERSONA, header_prompt, MaturityHeader)
            if header_obj:
                st.session_state["maturity_obj"] = header_obj
    else:
        st.session_state["_last_generation_ts"] = time.time()
        with st.spinner("Compiling Cybersecurity Maturity Assessment..."):
            client = LLMEngine.get_client()
            deployment = get_config(ConfigKey.AZURE_DEPLOYMENT, "gpt-4o")
            maturity_prompt = build_maturity_prompt(st.session_state["client_inputs"])
            maturity_obj = LLMEngine.generate_structured_report(client, deployment, SYSTEM_PERSONA, maturity_prompt, MaturityReport)
            if maturity_obj:
                st.session_state["maturity_obj"] = maturity_obj
            

    try:
        mr = st.session_state.get('maturity_obj')
        if mr and not getattr(mr, 'success_metrics', None):
            mr.success_metrics = [
                "Reduce mean time to respond (MTTR) through improved monitoring and runbooks",
                "Increase MFA enforcement coverage across all identities",
                "Improve backup immutability and restore assurance through regular testing",
            ]
        if not getattr(mr, 'engagement_cadence', None):
            mr.engagement_cadence = [
                "Monthly governance review",
                "Quarterly roadmap checkpoint",
                "Annual strategic reset with the Board",
            ]
        if not getattr(mr, 'consultant_discovery_guide', None):
            mr.consultant_discovery_guide = [
                "What are the Crown Jewels and their data flows?",
                "What is the acceptable downtime tolerance (RTO)?",
                "Do you carry cyber insurance and what are the conditions?",
                "Where is MFA enforced across identities and services?",
                "How are backups validated and how often?",
            ]
        if not getattr(mr, 'partnership_outline', None):
            mr.partnership_outline = "Planet IT will partner to deliver a co-managed or fully managed engagement focused on measurable outcomes, repeatable governance ceremonies, and continuous improvement."
    except Exception:
        pass

    # Generate maturity-aligned threat scenario via streaming LLM (mirrors Threat Simulator)
    try:
        # Build gap summary from domain assessments for the threat prompt
        gaps_summary = []
        for domain in getattr(mr, 'domain_assessments', []):
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

        pillar = getattr(mr, 'resiliency_matrix_mapping', 'Pillar 1')
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
            mr.threat_scenarios = threat_scenarios
            st.session_state['maturity_threat_scenarios'] = threat_scenarios
            st.session_state['maturity_obj'] = mr
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            f"Threat scenario LLM generation failed; building fallback from maturity data. Error: {e}"
        )
        # Fallback: build a lightweight threat scenario from the maturity report itself
        if mr:
            from prompts import ThreatScenarioItem
            threat_scenarios = [
                ThreatScenarioItem(
                    id="ts-maturity-1",
                    name=f"{mr.resiliency_matrix_mapping} Threat Scenario",
                    incident_type=mr.resiliency_matrix_mapping,
                    narrative=mr.cost_of_inaction,
                )
            ]
            mr.threat_scenarios = threat_scenarios
            st.session_state['maturity_threat_scenarios'] = threat_scenarios
            st.session_state['maturity_obj'] = mr
        # Clear any cached export bytes from previous runs
        for key in ['maturity_docx_bytes']:
            st.session_state.pop(key, None)
        st.success("Cybersecurity Maturity Roadmap Generated Successfully.")
    else:
        st.error("Engine failed to generate the roadmap.")
        
    if st.session_state.get('maturity_obj'):
        st.subheader("📥 Export Deliverables")
        with st.spinner("Preparing Word document..."):
            docx_data = get_maturity_docx_bytes()
        if docx_data:
            st.download_button(
                "📄 Download Cybersecurity Maturity Report (Word)", 
                data=docx_data, 
                file_name=f"{cached_customer_name.replace(' ', '_')}_Cybersecurity_Maturity_Report.docx", 
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"maturity_docx_dl_{st.session_state.get('_client_inputs_hash','')}"
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
        for domain in getattr(maturity, 'domain_assessments', []):
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
        for phase in getattr(maturity, 'phased_roadmap', []):
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