import streamlit as st
import time
import json
from core import LLMEngine
from prompts import (
    TabletopMasterPlan,
    build_tabletop_plan_prompt,
    SYSTEM_PERSONA_TABLETOP,
)
from export import create_tabletop_pptx, create_tabletop_facilitator_pdf
from config import get_config, ConfigKey
from catalog import PLANET_IT_PORTFOLIO
from ui_shared_sections import render_governance_assurance_sections, render_ai_usage_and_governance, render_security_culture_sections

def _safe_index(options, value):
    """Return index of value in options; 0 if missing or invalid."""
    try:
        return options.index(value) if value in options else 0
    except Exception:
        return 0

def _coerce_list(value, options):
    """Coerce values into a valid list constrained to options."""
    try:
        if isinstance(value, list):
            return [v for v in value if v in options]
        if isinstance(value, str):
            parts = [p.strip() for p in value.split(",") if p.strip()]
            return [p for p in parts if p in options]
    except Exception:
        pass
    return []

st.set_page_config(page_title="Tabletop Designer", layout="wide")

# Auth-aware guard: if login is enabled and user not signed-in, route to app.py sign-in
from config import get_config
def _is_auth_enabled():
    try:
        return str(get_config("AUTH_ENABLED", "false")).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        return False
if _is_auth_enabled() and not st.session_state.get("_auth_user"):
    st.warning("Sign in required to access the Tabletop Designer.")
    st.page_link("app.py", label="🔐 Go to Sign In")
    st.stop()

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

st.header("🛠️ Tabletop Exercise Designer & Editor")

with st.expander("Customer Estate & Engagement Profile (Quick Capture)", expanded=False):
    qc_name = st.text_input("Customer Name", value=st.session_state.get("client_inputs", {}).get("customer_name", ""))
    qc_industry = st.text_input("Industry", value=st.session_state.get("client_inputs", {}).get("industry", ""))
    qc_users = st.number_input("Headcount", min_value=0, value=int(st.session_state.get("client_inputs", {}).get("users", 0)))
    qc_crown = st.text_input("Crown Jewels", value=st.session_state.get("client_inputs", {}).get("critical_infra", ""))
    if st.button("Apply Quick Profile"):
        st.session_state.setdefault("client_inputs", {})
        st.session_state["client_inputs"].update({
            "customer_name": qc_name.strip(),
            "industry": (qc_industry or "").strip() or "Unknown",
            "users": qc_users,
            "critical_infra": (qc_crown or "").strip(),
        })
        st.success("Quick profile applied to Tabletop context.")

# Guard: require client profile
client_inputs = st.session_state.get("client_inputs") or {}
cached_customer_name = client_inputs.get("customer_name", "Client")
key_assets = client_inputs.get("critical_infra", "Crown Jewels")

with st.expander("Customer Estate & Engagement Profile (Advanced)", expanded=False):
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("Organisational Profile")
        customer_name = st.text_input("Customer Name", value=client_inputs.get("customer_name", ""), key="adv_customer_name")
        consultant_name = st.text_input("Consultant Name", value=client_inputs.get("consultant_name", ""))
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
        industry = st.selectbox("Industry", industry_options, index=_safe_index(industry_options, client_inputs.get("industry")))
        users = st.number_input("Headcount", min_value=0, value=int(client_inputs.get("users", 0)), key="adv_users")
        critical_infra = st.text_input("Crown Jewels", value=client_inputs.get("critical_infra", ""), key="adv_critical_infra")

    with col2:
        st.subheader("Technology Stack")
        endpoints = st.number_input("Number of Endpoints", min_value=0, value=int(client_inputs.get("endpoints", 0)))
        servers = st.number_input("Number of Servers", min_value=0, value=int(client_inputs.get("servers", 0)))
        _os_options = ["Windows 10", "Windows 11", "Windows Server", "macOS", "Linux", "ChromeOS"]
        operating_systems = st.multiselect("Operating Systems in Use", _os_options, default=_coerce_list(client_inputs.get("operating_systems", []), _os_options))

        mdr_options = ["Select MDR / SOC Provider...", "None", "Sophos MDR", "Sophos MDR Plus", "Microsoft Defender Experts", "CrowdStrike Falcon Complete", "Arctic Wolf", "Expel", "Red Canary", "Local Partner SOC", "Other"]
        mdr_provider = st.selectbox("Current MDR / SOC Provider", mdr_options, index=_safe_index(mdr_options, client_inputs.get("mdr_provider")))

        endpoint_options = ["Select Endpoint Vendor...", "Sophos", "Microsoft Defender", "CrowdStrike", "SentinelOne", "Trend Micro", "Symantec", "N-able", "Other"]
        endpoint = st.selectbox("Endpoint Security Vendor", endpoint_options, index=_safe_index(endpoint_options, client_inputs.get("endpoint")))

        endpoint_posture_options = ["Select Endpoint Capability...", "Legacy AV Only (Signatures/Heuristics)", "Next-Gen AV (NGAV / Deep Learning)", "EDR Deployed (Endpoint Detection & Response)", "XDR Deployed (Cross-Domain Telemetry)", "Full ZTNA / Device Control Enforced"]
        endpoint_posture = st.selectbox("Endpoint Capability (Licensing)", endpoint_posture_options, index=_safe_index(endpoint_posture_options, client_inputs.get("endpoint_posture")))

        firewall_options = ["Select Firewall Vendor...", "Fortinet", "Palo Alto", "Cisco", "Sophos", "Check Point", "SonicWall", "Other"]
        firewall = st.selectbox("Firewall Vendor", firewall_options, index=_safe_index(firewall_options, client_inputs.get("firewall")))

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
        remote_access = st.selectbox("Remote Access Strategy", remote_access_options, index=_safe_index(remote_access_options, client_inputs.get("remote_access")))

        saas_backup_options = ["Select SaaS Backup...", "None (Relying on Microsoft/Google)", "Basic Retention Policies Only", "Dedicated Third-Party SaaS Backup"]
        saas_backup = st.selectbox("M365 / SaaS Backup", saas_backup_options, index=_safe_index(saas_backup_options, client_inputs.get("saas_backup")))

    with col3:
        st.subheader("Cloud & Identity")
        identity_options = ["Select Identity Provider...", "Microsoft Entra ID (Azure AD)", "Okta", "On-Prem Active Directory", "None"]
        identity = st.selectbox("Identity Provider", identity_options, index=_safe_index(identity_options, client_inputs.get("identity")))

        m365_license_options = ["None / On-Prem Only", "M365 Business Premium", "Microsoft 365 E5", "Office 365 E3 / M365 E3"]
        m365_licenses = st.multiselect("Microsoft 365 Licensing", m365_license_options, default=_coerce_list([client_inputs.get("m365_license")] if client_inputs.get("m365_license") else [], m365_license_options))
        m365_license_str = ", ".join(m365_licenses) if m365_licenses else "None / On-Prem Only"

        email_options = ["Select Email Security...", "Mimecast", "Proofpoint", "Microsoft Defender", "Barracuda", "Egress", "Other"]
        email = st.selectbox("Email Security", email_options, index=_safe_index(email_options, client_inputs.get("email")))

        cloud_env_options = ["AWS", "Microsoft Azure", "GCP", "Oracle Cloud", "None (Fully On-Prem)"]
        cloud_env = st.multiselect("Cloud Infrastructure", cloud_env_options, default=_coerce_list(client_inputs.get("cloud_env", []), cloud_env_options))

    st.divider()

    st.markdown("### 🚫 Ban Vendors from Recommendations")
    st.caption("Select any vendors your customer has explicitly ruled out. They will not appear in any generated recommendations or reports.")
    all_vendors = sorted(set(item["vendor"] for category in PLANET_IT_PORTFOLIO.values() for item in category))
    banned_vendors = st.multiselect("Excluded Vendors", options=all_vendors, default=_coerce_list(client_inputs.get("banned_vendors", []), all_vendors))

    st.divider()
    st.subheader("Operations & Validation")
    col_ops1, col_ops2 = st.columns(2)
    with col_ops1:
        in_house_options = ["Select Internal SOC Team...", "No", "Yes (9-to-5)", "Yes (24/7)"]
        in_house_team = st.selectbox("Internal SOC Team", in_house_options, index=_safe_index(in_house_options, client_inputs.get("in_house_team")))
        pentest_options = ["Select Penetration Testing Cadence...", "None", "Annual", "Bi-Annual", "Quarterly"]
        pentest_status = st.selectbox("Penetration Testing", pentest_options, index=_safe_index(pentest_options, client_inputs.get("pentest_status")))
        vuln_options = ["Select Vulnerability Scanning...", "None", "Monthly Authenticated", "Quarterly External", "Continuous"]
        vuln_scanning = st.selectbox("Vuln Scanning", vuln_options, index=_safe_index(vuln_options, client_inputs.get("vuln_scanning")))
        public_web_apps = st.checkbox("Host Public Web Apps", value=bool(client_inputs.get("public_web_apps", False)))
    with col_ops2:
        compliance_options = ["ISO 27001", "Cyber Essentials", "Cyber Essentials Plus", "PCI DSS", "HIPAA", "NIST CSF", "UK DfE (2026) Cyber Security Standards"]
        compliance = st.multiselect("Target Compliance", compliance_options, default=_coerce_list(client_inputs.get("compliance", []), compliance_options))
        physical_locations = st.number_input("Physical Locations", min_value=0, value=int(client_inputs.get("physical_locations", 0)))
        advanced_controls = st.multiselect(
            "Advanced Adaptive Controls (Pillar 3)",
            ["Zero-Trust Architecture (ZTA)", "Network Microsegmentation", "SOAR / Automated Remediation", "User Behaviour Analytics (UBA)", "Automated DR Orchestration", "Deception Tech (Honeypots)"],
            default=_coerce_list(client_inputs.get("advanced_controls", []), ["Zero-Trust Architecture (ZTA)", "Network Microsegmentation", "SOAR / Automated Remediation", "User Behaviour Analytics (UBA)", "Automated DR Orchestration", "Deception Tech (Honeypots)"])
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
        proactive_tools = st.multiselect("Proactive Security Tools", proactive_tools_options, default=_coerce_list(client_inputs.get("proactive_tools", []), proactive_tools_options))
        validation_notes = st.text_area("Validation Notes", value=client_inputs.get("validation_notes", ""))
        context_notes = st.text_area("Consultant Context (LLM-visible)", value=client_inputs.get("context_notes", ""))

    st.divider()
    col_apply1, col_apply2 = st.columns([1, 1])
    with col_apply1:
        ir_readiness_options = ["Unknown", "No Formal Plan", "Plan Drafted", "Plan Approved", "Plan Tested (Tabletop in past year)"]
        ir_readiness = st.selectbox("Incident Response Readiness", ir_readiness_options, index=_safe_index(ir_readiness_options, client_inputs.get("ir_readiness")))
        ir_retainer_options = ["None", "Microsoft DART", "Sophos MDR Plus / Incident Response", "Other"]
        ir_retainer = st.selectbox("Active IR Retainer", ir_retainer_options, index=_safe_index(ir_retainer_options, client_inputs.get("ir_retainer")))

    with col_apply2:
        managed_service_options = ["None (No managed service in place)", "Planet IT Fully Managed (Active)", "Planet IT Co-Managed (Active)", "Other MSP (Active)"]
        managed_service_status = st.selectbox("Managed Service Status", managed_service_options, index=_safe_index(managed_service_options, client_inputs.get("managed_service_status")))
        co_managed_units = st.number_input("Co-Managed Service Units", min_value=0, value=int(client_inputs.get("co_managed_units", 0)))
        partnership_type_options = ["Fully Managed", "Co-Managed", "Project-Based", "Advisory Only"]
        partnership_type = st.selectbox("Partnership Preference", partnership_type_options, index=_safe_index(partnership_type_options, client_inputs.get("partnership_type")))

    st.divider()
    st.subheader("Operational Telemetry (Hygiene)")
    col_tel1, col_tel2, col_tel3 = st.columns(3)
    with col_tel1:
        mfa_options = ["Unknown", "None", "Privileged Accounts Only", "Universal / Conditional Access"]
        mfa_status = st.selectbox("MFA Enforcement", mfa_options, index=_safe_index(mfa_options, client_inputs.get("mfa_status")))
    with col_tel2:
        patching_options = ["Unknown", "Manual / Ad-hoc", "Automated (OS Only)", "Automated (OS + Apps)"]
        patching = st.selectbox("Patch Management", patching_options, index=_safe_index(patching_options, client_inputs.get("patching")))
    with col_tel3:
        backup_options = ["Unknown", "No Formal Backups", "On-Premise Only", "Cloud/Offsite (Standard)", "Cloud/Offsite (Immutable/Air-gapped)"]
        backups = st.selectbox("Infrastructure Backups", backup_options, index=_safe_index(backup_options, client_inputs.get("backups")))

    if st.button("Apply Advanced Profile", type="primary"):
        st.session_state.setdefault("client_inputs", {})
        st.session_state["client_inputs"].update({
            "customer_name": (customer_name or "").strip(),
            "consultant_name": (consultant_name or "").strip(),
            "industry": industry,
            "users": int(users),
            "critical_infra": (critical_infra or "").strip(),
            "endpoints": int(endpoints),
            "servers": int(servers),
            "operating_systems": operating_systems,
            "mdr_provider": mdr_provider,
            "endpoint": endpoint,
            "endpoint_posture": endpoint_posture,
            "firewall": firewall,
            "remote_access": remote_access,
            "saas_backup": saas_backup,
            "identity": identity,
            "m365_license": m365_license_str,
            "email": email,
            "cloud_env": cloud_env,
            "banned_vendors": banned_vendors,
            "in_house_team": in_house_team,
            "pentest_status": pentest_status,
            "vuln_scanning": vuln_scanning,
            "public_web_apps": bool(public_web_apps),
            "compliance": compliance,
            "physical_locations": int(physical_locations),
            "advanced_controls": advanced_controls,
            "proactive_tools": proactive_tools,
            "validation_notes": (validation_notes or "").strip(),
            "context_notes": (context_notes or "").strip(),
            "ir_readiness": ir_readiness,
            "ir_retainer": ir_retainer,
            "managed_service_status": managed_service_status,
            "co_managed_units": int(co_managed_units),
            "partnership_type": partnership_type,
            "mfa_status": mfa_status,
            "patching": patching,
            "backups": backups,
        })
        st.success("Advanced profile applied to Tabletop context.")

# Extended inputs parity with Maturity (shared)
ai_dict = render_ai_usage_and_governance()
sav_dict = render_security_culture_sections()
cap_dict, sr_dict, ip_dict, idg_dict, saas_dict, aa_dict, mon_dict, sup_dict, tpa_dict, rec_dict, ir_dict, as_map = render_governance_assurance_sections()
st.session_state.setdefault("client_inputs", {})
# Merge Security Culture (behaviours)
st.session_state["client_inputs"].update({
    "savviness": sav_dict.get("savviness"),
    "savviness_label": sav_dict.get("savviness_label"),
    "culture_score": sav_dict.get("culture_score"),
    "culture_q1": sav_dict.get("culture_q1"),
    "culture_q2": sav_dict.get("culture_q2"),
    "culture_q3": sav_dict.get("culture_q3"),
    "culture_reporting_routes": sav_dict.get("culture_reporting_routes"),
    "culture_followup_coaching": sav_dict.get("culture_followup_coaching"),
    "culture_role_training": sav_dict.get("culture_role_training"),
    "culture_leadership_engagement": sav_dict.get("culture_leadership_engagement"),
    "culture_policy_ack": sav_dict.get("culture_policy_ack"),
    "culture_phish_fail_pct_90d": sav_dict.get("culture_phish_fail_pct_90d"),
    "culture_report_rate_pct_90d": sav_dict.get("culture_report_rate_pct_90d"),
})
# Merge AI Governance
st.session_state["client_inputs"].update(ai_dict)
# Merge Governance & Assurance evidence maps
st.session_state["client_inputs"].update({
    "critical_asset_profile": cap_dict,
    "service_resilience_profile": sr_dict,
    "information_protection_profile": ip_dict,
    "identity_governance_profile": idg_dict,
    "saas_governance_profile": saas_dict,
    "asset_assurance_profile": aa_dict,
    "monitoring_assurance_profile": mon_dict,
    "supplier_assurance_profile": sup_dict,
    "third_party_access_profile": tpa_dict,
    "recovery_assurance_profile": rec_dict,
    "incident_response_assurance_profile": ir_dict,
    "assurance_status": as_map,
})
col_sc1, col_sc2 = st.columns(2)
with col_sc1:
    selected_themes = st.multiselect(
        "Select Scenarios to Include:",
        [
            "Cyber Attack (Ransomware / BEC)",
            "Unauthorised Access (Social Engineering / Service Desk)",
            "Cloud / M365 Outage (DR & Business Continuity)",
        ],
        default=[
            "Cyber Attack (Ransomware / BEC)",
            "Unauthorised Access (Social Engineering / Service Desk)",
        ],
    )
with col_sc2:
    st.markdown(f"**Target Customer:** `{cached_customer_name}`")
    st.markdown(f"**Key Assets:** `{key_assets}`")

if st.button("Generate Bespoke Tabletop Plan", type="primary"):
    with st.spinner("Compiling scenarios and facilitator guides from estate profile..."):
        client = LLMEngine.get_client()
        deployment = get_config(ConfigKey.AZURE_DEPLOYMENT, "gpt-4o")
        prompt = build_tabletop_plan_prompt(client_inputs, selected_themes)
        plan = LLMEngine.generate_structured_report(
            client, deployment, SYSTEM_PERSONA_TABLETOP, prompt, TabletopMasterPlan
        )
        if plan:
            st.session_state["tabletop_plan"] = plan.model_dump()
            st.success("Tabletop scenario compiled. You can now customise below.")
            # Navigate to Live Facilitation (full-page) after generation
            st.page_link("pages/04_Live_Facilitation.py", label="Go to Live Facilitation ➡️")
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
                inj["scenario_narrative"] = st.text_area(
                    "Narrative", value=inj.get("scenario_narrative"), key=f"narr_{s_idx}_{i_idx}"
                )
                inj["expected_mature_response"] = st.text_area(
                    "What Good Looks Like", value=inj.get("expected_mature_response"), key=f"resp_{s_idx}_{i_idx}"
                )

    col_json1, col_json2 = st.columns(2)
    with col_json1:
        st.download_button(
            "🧩 Export Tabletop Plan (.json)",
            data=(json.dumps(plan, ensure_ascii=False, indent=2)).encode("utf-8"),
            file_name=f"{cached_customer_name}_Tabletop_Plan.json",
            mime="application/json",
        )
    with col_json2:
        uploaded_plan = st.file_uploader("Import Tabletop Plan (.json)", type=["json"])
        if uploaded_plan is not None:
            try:
                imported = json.loads(uploaded_plan.getvalue().decode("utf-8"))
                validated = TabletopMasterPlan.model_validate(imported)
                st.session_state["tabletop_plan"] = validated.model_dump()
                st.success("Tabletop plan imported and applied to the editor.")
            except Exception as e:
                st.error(f"Invalid plan JSON: {e}")

    st.divider()
    col_lock1, col_lock2 = st.columns(2)
    with col_lock1:
        pptx_data = create_tabletop_pptx(plan)
        st.download_button(
            "📊 Download Presentation Deck (.pptx)",
            data=pptx_data,
            file_name=f"{cached_customer_name}_Tabletop_Deck.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
    with col_lock2:
        pdf_data = create_tabletop_facilitator_pdf(plan)
        st.download_button(
            "📑 Download Facilitator Guide (.pdf)",
            data=pdf_data,
            file_name=f"{cached_customer_name}_Facilitator_Guide.pdf",
            mime="application/pdf",
        )
