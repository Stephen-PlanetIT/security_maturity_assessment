"""
consultation_helpers.py — Sanitisation and migration utilities

Responsibilities:
- Recursive sanitisation of nested profile data (dicts/lists/tuples)
- Backward‑compatible profile migration for changed option sets
- Minimal structural defaults for legacy profiles

British English comments and labels are used consistently.
"""
from __future__ import annotations

import copy
import re
from typing import Any, Dict, List

SCHEMA_VERSION = 1

_SANITISE_PATTERNS = [
    (re.compile(r'[--]'), ''),  # control chars
    (re.compile(r'\u200B|\u200C|\u200D|\u200E|\u200F|\u202A|\u202B|\u202C|\u202D|\u202E|\u2060|\u2061|\u2062|\u2063|\u2064|\u2066|\u2067|\u2068|\u2069'), ''),
    (re.compile(r'(?:\r?\n){3,}'), '\n\n'),
]


def _sanitise_str(value: str) -> str:
    s = value if isinstance(value, str) else str(value)
    for pat, repl in _SANITISE_PATTERNS:
        s = pat.sub(repl, s)
    # Preserve intentional newlines; trim only spaces and tabs
    return s.strip(' \t')


def sanitise_nested(obj: Any) -> Any:
    """Recursively sanitise strings within dicts, lists and tuples.
    Non‑string scalars are returned unchanged.
    """
    if obj is None:
        return None
    if isinstance(obj, str):
        return _sanitise_str(obj)
    if isinstance(obj, dict):
        return {k: sanitise_nested(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitise_nested(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(sanitise_nested(v) for v in obj)
    return obj


def get_nested(d: Dict[str, Any], path: List[str], default: Any = None) -> Any:
    cur: Any = d
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key, default)
        if cur is default:
            break
    return cur


_OS_MIGRATION = {
    # Legacy catch‑alls → specific supported options
    "Windows Server": "Windows Server 2019",
    "Windows Server (unspecified)": "Windows Server 2019",
    "Windows Server 2012 / 2012 R2 (EoL)": "Windows Server 2012 / 2012 R2",
}

_IDENTITY_MIGRATION = {
    "Microsoft Entra ID (Azure AD)": "Microsoft Entra ID cloud-only",
    "Hybrid (On-Prem AD + Entra ID)": "Hybrid Active Directory and Microsoft Entra ID",
    "On-Prem Active Directory": "On-premises Active Directory only",
    "None": "Application-local identities / no central identity",
}


def _migrate_operating_systems(profile: Dict[str, Any]) -> None:
    os_val = profile.get("operating_systems")
    if not os_val:
        return
    # Accept list or comma‑separated string
    if isinstance(os_val, str):
        parts = [p.strip() for p in os_val.split(",") if p.strip()]
    elif isinstance(os_val, list):
        parts = [str(p).strip() for p in os_val if str(p).strip()]
    else:
        return
    migrated: List[str] = []
    for p in parts:
        migrated.append(_OS_MIGRATION.get(p, p))
    # De‑duplicate while preserving order
    seen = set()
    dedup = []
    for m in migrated:
        if m not in seen:
            seen.add(m)
            dedup.append(m)
    profile["operating_systems"] = dedup


def _migrate_identity(profile: Dict[str, Any]) -> None:
    ident = profile.get("identity")
    if not ident:
        return
    if isinstance(ident, str):
        profile["identity"] = _IDENTITY_MIGRATION.get(ident, ident)


def _ensure_critical_asset_profile(profile: Dict[str, Any]) -> None:
    """If legacy critical_infra exists and no structured profile, derive a minimal one."""
    if "critical_asset_profile" in profile and isinstance(profile["critical_asset_profile"], dict):
        return
    cap = {
        "business_services": [],
        "systems_platforms": "",
        "sensitive_data_types": [],
        "additional_context": "",
    }
    legacy = profile.get("critical_infra")
    if isinstance(legacy, str) and legacy.strip():
        cap["systems_platforms"] = legacy.strip()
    profile["critical_asset_profile"] = cap


def migrate_profile(profile: Dict[str, Any], source_version: int | None = None) -> Dict[str, Any]:
    """Return a migrated, sanitised copy of an imported profile.

    - Adds schema_version
    - Normalises legacy identity and operating_systems values to supported options
    - Ensures a minimal critical_asset_profile exists based on legacy critical_infra
    - Preserves original keys and values wherever possible
    """
    if not isinstance(profile, dict):
        return profile
    migrated = copy.deepcopy(profile)
    try:
        _migrate_operating_systems(migrated)
    except Exception:
        pass
    try:
        _migrate_identity(migrated)
    except Exception:
        pass
    try:
        _ensure_critical_asset_profile(migrated)
    except Exception:
        pass
    migrated["schema_version"] = SCHEMA_VERSION
    return sanitise_nested(migrated)

# --------- Formatting & Derivations ---------

def format_critical_asset_profile(cap: dict) -> str:
    """Return a compact, British English summary of CAP for prompts/exports."""
    if not isinstance(cap, dict):
        return ""
    bs = cap.get("business_services") or []
    sp = (cap.get("systems_platforms") or "").strip()
    sd = cap.get("sensitive_data_types") or []
    parts = []
    if isinstance(bs, list) and bs:
        parts.append("Business services: " + "; ".join([str(x) for x in bs]))
    if sp:
        parts.append("Systems/platforms: " + sp)
    if isinstance(sd, list) and sd:
        parts.append("Sensitive data: " + "; ".join([str(x) for x in sd]))
    extra = (cap.get("additional_context") or "").strip()
    if extra:
        parts.append(extra)
    return "\n".join(parts)


def derive_critical_infra_from_cap(cap: dict) -> str:
    """Derive a single-line critical_infra summary from CAP without overwriting manual input."""
    if not isinstance(cap, dict):
        return ""
    bs = ", ".join([str(x) for x in (cap.get("business_services") or [])])
    sp = (cap.get("systems_platforms") or "").strip()
    sd = ", ".join([str(x) for x in (cap.get("sensitive_data_types") or [])])
    tokens = []
    if bs:
        tokens.append(bs)
    if sp:
        tokens.append(sp)
    if sd:
        tokens.append(sd)
    return " | ".join(tokens)[:500]


# --------- Additional Formatters (Phase 2) ---------
def _fmt_pair(label: str, value: str) -> str:
    v = (value or "").strip()
    return f"- {label}: {v}" if v else ""

def format_service_resilience_profile(sr: dict) -> str:
    if not isinstance(sr, dict):
        return ""
    lines = [
        _fmt_pair("Assessment status", sr.get("assessment_status", "")),
        _fmt_pair("Most critical service", sr.get("most_critical_service", "")),
        _fmt_pair("Service-specific RTO", sr.get("service_specific_rto", "")),
        _fmt_pair("Service-specific RPO", sr.get("service_specific_rpo", "")),
        _fmt_pair("Manual workaround", sr.get("manual_workaround", "")),
        _fmt_pair("Dependency mapping", sr.get("dependency_mapping", "")),
        _fmt_pair("Recovery priorities", sr.get("recovery_priorities", "")),
    ]
    return "\n".join([l for l in lines if l])

def format_information_protection_profile(ip: dict) -> str:
    if not isinstance(ip, dict):
        return ""
    lines = [
        _fmt_pair("Classification", ip.get("data_classification_status", "")),
        _fmt_pair("External sharing", ip.get("external_sharing_posture", "")),
        _fmt_pair("DLP", ip.get("dlp_status", "")),
        _fmt_pair("Retention", ip.get("retention_governance", "")),
    ]
    return "\n".join([l for l in lines if l])

def format_identity_governance_profile(idg: dict) -> str:
    if not isinstance(idg, dict):
        return ""
    lines = [
        _fmt_pair("Lifecycle", idg.get("identity_lifecycle_maturity", "")),
        _fmt_pair("Leaver deprovisioning", idg.get("leaver_deprovisioning", "")),
        _fmt_pair("Access reviews", idg.get("access_review_status", "")),
        _fmt_pair("Privileged model", idg.get("privileged_access_model", "")),
        _fmt_pair("PIM/PAM", idg.get("pim_pam_status", "")),
        _fmt_pair("Break glass", idg.get("break_glass_governance", "")),
        _fmt_pair("Service accounts", idg.get("service_account_governance", "")),
        _fmt_pair("Shared accounts", idg.get("shared_account_usage", "")),
        _fmt_pair("Legacy authentication", idg.get("legacy_authentication_status", "")),
    ]
    return "\n".join([l for l in lines if l])

def format_saas_governance_profile(sg: dict) -> str:
    if not isinstance(sg, dict):
        return ""
    lines = [
        _fmt_pair("Inventory", sg.get("inventory_status", "")),
        _fmt_pair("Critical platforms", sg.get("critical_platforms", "")),
        _fmt_pair("SSO coverage", sg.get("sso_coverage", "")),
        _fmt_pair("MFA coverage", sg.get("mfa_coverage", "")),
        _fmt_pair("Offboarding", sg.get("offboarding_process", "")),
        _fmt_pair("Recovery responsibility", sg.get("recovery_responsibility", "")),
        _fmt_pair("Shadow IT visibility", sg.get("shadow_it_visibility", "")),
        _fmt_pair("OAuth governance", sg.get("oauth_app_governance", "")),
    ]
    return "\n".join([l for l in lines if l])

def format_asset_assurance_profile(aa: dict) -> str:
    if not isinstance(aa, dict):
        return ""
    lines = [
        _fmt_pair("Asset inventory", aa.get("asset_inventory_maturity", "")),
        _fmt_pair("External attack surface", aa.get("external_attack_surface_visibility", "")),
        _fmt_pair("Vulnerability remediation", aa.get("vulnerability_remediation_maturity", "")),
        _fmt_pair("Secure configuration", aa.get("secure_configuration_baseline", "")),
        _fmt_pair("Security change assurance", aa.get("security_change_assurance", "")),
        _fmt_pair("Unsupported technology", aa.get("unsupported_technology_status", "")),
    ]
    return "\n".join([l for l in lines if l])

def format_monitoring_assurance_profile(mon: dict) -> str:
    if not isinstance(mon, dict):
        return ""
    lines = [
        _fmt_pair("Coverage", mon.get("monitoring_coverage", "")),
        _fmt_pair("Log sources", ", ".join(mon.get("log_sources_monitored", []) or [])),
        _fmt_pair("Retention", mon.get("log_retention", "")),
        _fmt_pair("Out-of-hours escalation", mon.get("out_of_hours_escalation", "")),
        _fmt_pair("Response authority", mon.get("response_authority", "")),
        _fmt_pair("Detection testing", mon.get("detection_testing", "")),
        _fmt_pair("Reporting cadence", mon.get("security_reporting_cadence", "")),
        _fmt_pair("Known gaps", mon.get("known_coverage_gaps", "")),
    ]
    return "\n".join([l for l in lines if l])

def format_supplier_assurance_profile(sa: dict, tp: dict | None = None) -> str:
    if not isinstance(sa, dict):
        sa = {}
    lines = [_fmt_pair("Assurance maturity", sa.get("supplier_assurance_maturity", ""))]
    if isinstance(tp, dict):
        lines.extend([
            _fmt_pair("Third-party access", tp.get("access_present", "")),
            _fmt_pair("Identity model", tp.get("identity_model", "")),
            _fmt_pair("MFA", tp.get("mfa_status", "")),
            _fmt_pair("Time-limited", tp.get("time_limited", "")),
            _fmt_pair("Monitored", tp.get("monitored", "")),
            _fmt_pair("Periodically reviewed", tp.get("periodically_reviewed", "")),
            _fmt_pair("Contractual requirements", tp.get("contractual_security_requirements", "")),
            _fmt_pair("Incident notification", tp.get("incident_notification", "")),
            _fmt_pair("Exit planning", tp.get("exit_planning", "")),
            _fmt_pair("Concentration risk", tp.get("concentration_risk", "")),
        ])
    return "\n".join([l for l in lines if l])

def format_recovery_assurance_profile(rec: dict) -> str:
    if not isinstance(rec, dict):
        return ""
    lines = [
        _fmt_pair("Restore testing", rec.get("restore_testing", "")),
        _fmt_pair("Immutability", rec.get("immutability_status", "")),
        _fmt_pair("Admin separation", rec.get("administrative_separation", "")),
        _fmt_pair("Service recovery", rec.get("service_recovery_testing", "")),
        _fmt_pair("Evidence retained", rec.get("evidence_retained", "")),
        _fmt_pair("Recovery ownership", rec.get("recovery_ownership", "")),
    ]
    return "\n".join([l for l in lines if l])

def format_ir_assurance_profile(ir: dict) -> str:
    if not isinstance(ir, dict):
        return ""
    lines = [
        _fmt_pair("Roles", ir.get("roles_defined", "")),
        _fmt_pair("Business decision authority", ir.get("business_decision_authority", "")),
        _fmt_pair("Technical response authority", ir.get("technical_response_authority", "")),
        _fmt_pair("Tabletop status", ir.get("tabletop_status", "")),
        _fmt_pair("Out-of-band comms", ir.get("out_of_band_communications", "")),
        _fmt_pair("Crisis comms", ir.get("crisis_communications", "")),
        _fmt_pair("Regulatory notification", ir.get("regulatory_notification_readiness", "")),
        _fmt_pair("Supplier coordination", ir.get("supplier_coordination", "")),
        _fmt_pair("Lessons learned", ir.get("lessons_learned_process", "")),
    ]
    return "\n".join([l for l in lines if l])


# --------- Assurance helpers ---------
def assurance_phrase(section: str, status_map: dict) -> str:
    try:
        s = (status_map or {}).get(section) or (status_map or {}).get("default") or ""
    except Exception:
        s = ""
    if s == "Confirmed during consultation":
        return "Confirmed"
    if s == "Reported, evidence not reviewed":
        return "Reported (unverified)"
    if s == "Requires supplier confirmation":
        return "Requires supplier confirmation"
    if s == "Not applicable":
        return "Not applicable"
    if s == "Unknown":
        return "Not established during consultation"
    return s or ""


# --------- Readiness summary ---------
def readiness_summary(client_inputs: dict) -> dict:
    """Return a compact readiness summary highlighting material gaps.
    Outputs keys: unanswered_sections, requires_supplier_confirmation, not_applicable.
    """
    sections = [
        "information_protection", "identity_governance", "saas_governance", "monitoring",
        "supplier_security", "recovery", "incident_response", "ot_iot", "payment_fraud",
        "application_security", "integration_assurance",
    ]
    status = (client_inputs or {}).get("assurance_status", {}) or {}
    unanswered = []
    requires_conf = []
    not_applicable = []
    for s in sections:
        phrase = assurance_phrase(s, status)
        if phrase == "Requires supplier confirmation":
            requires_conf.append(s)
        elif phrase == "Not applicable":
            not_applicable.append(s)
        elif not phrase or phrase == "Not established during consultation":
            unanswered.append(s)
    return {
        "unanswered_sections": unanswered,
        "requires_supplier_confirmation": requires_conf,
        "not_applicable": not_applicable,
    }

# --------- Derived maturity helpers (deterministic, bounded) ---------
# Returns one of: 'Pillar 1', 'Pillar 2', 'Pillar 3', 'Insufficient Evidence', 'Not Applicable'

def _pillar_from_flags(flags: list[str], unknowns: int = 0) -> str:
    # Simple bounded rules: any critical weak flag -> Pillar 1; multiple moderates -> Pillar 2; otherwise Pillar 3
    if any(f == "weak" for f in flags):
        return "Pillar 1"
    if flags.count("moderate") >= 2:
        return "Pillar 2"
    if unknowns >= max(1, len(flags)//2):
        return "Insufficient Evidence"
    return "Pillar 3"

def derive_identity_governance_maturity(idg: dict) -> str:
    if not isinstance(idg, dict):
        return "Insufficient Evidence"
    flags = []
    unknowns = 0
    las = idg.get("legacy_authentication_status") or ""
    if las in ("Enabled and not reviewed",):
        flags.append("weak")
    elif las in ("Unknown", ""):
        unknowns += 1
    pim = idg.get("pim_pam_status") or ""
    if pim in ("None", "Planned"):
        flags.append("weak")
    elif pim in ("Unknown", ""):
        unknowns += 1
    sag = idg.get("service_account_governance") or ""
    if sag in ("Informally managed",):
        flags.append("moderate")
    elif sag in ("Unknown", ""):
        unknowns += 1
    sau = idg.get("shared_account_usage") or ""
    if sau in ("Widespread",):
        flags.append("weak")
    elif sau in ("Unknown", ""):
        unknowns += 1
    return _pillar_from_flags(flags, unknowns)

def derive_data_security_maturity(ip: dict) -> str:
    if not isinstance(ip, dict):
        return "Insufficient Evidence"
    flags = []
    unknowns = 0
    dcls = ip.get("data_classification_status") or ""
    if dcls in ("None",):
        flags.append("moderate")
    elif dcls in ("Unknown", ""):
        unknowns += 1
    dlp = ip.get("dlp_status") or ""
    if dlp in ("None",):
        flags.append("moderate")
    elif dlp in ("Unknown", ""):
        unknowns += 1
    esp = ip.get("external_sharing_posture") or ""
    if esp in ("Broadly enabled",):
        flags.append("moderate")
    elif esp in ("Unknown", ""):
        unknowns += 1
    return _pillar_from_flags(flags, unknowns)

def derive_saas_governance_maturity(sg: dict) -> str:
    if not isinstance(sg, dict):
        return "Insufficient Evidence"
    flags, unknowns = [], 0
    inv = sg.get("inventory_status") or ""
    if inv in ("No authoritative inventory",):
        flags.append("weak")
    elif inv in ("Unknown", ""):
        unknowns += 1
    sso = sg.get("sso_coverage") or ""
    if sso in ("Limited",):
        flags.append("moderate")
    elif sso in ("Unknown", ""):
        unknowns += 1
    oauth = sg.get("oauth_app_governance") or ""
    if oauth in ("User consent unrestricted or unknown",):
        flags.append("moderate")
    elif oauth in ("Unknown", ""):
        unknowns += 1
    return _pillar_from_flags(flags, unknowns)

def derive_asset_assurance_maturity(aa: dict) -> str:
    if not isinstance(aa, dict):
        return "Insufficient Evidence"
    flags, unknowns = [], 0
    aim = aa.get("asset_inventory_maturity") or ""
    if aim in ("Incomplete or unknown",):
        flags.append("weak")
    elif aim in ("Unknown", ""):
        unknowns += 1
    vrm = aa.get("vulnerability_remediation_maturity") or ""
    if vrm in ("Findings reported but not centrally tracked",):
        flags.append("moderate")
    elif vrm in ("Unknown", ""):
        unknowns += 1
    eas = aa.get("external_attack_surface_visibility") or ""
    if eas in ("Unknown",):
        unknowns += 1
    return _pillar_from_flags(flags, unknowns)

def derive_monitoring_maturity(mon: dict) -> str:
    if not isinstance(mon, dict):
        return "Insufficient Evidence"
    flags, unknowns = [], 0
    cov = mon.get("monitoring_coverage") or ""
    if cov in ("Business hours only", "Critical alerts outside hours"):
        flags.append("weak")
    elif cov in ("Unknown", ""):
        unknowns += 1
    ra = mon.get("response_authority") or ""
    if ra in ("Notify only", "Investigate and recommend"):
        flags.append("moderate")
    elif ra in ("Unknown", ""):
        unknowns += 1
    return _pillar_from_flags(flags, unknowns)

def derive_supplier_security_maturity(sa: dict, tp: dict | None = None) -> str:
    flags, unknowns = [], 0
    if isinstance(sa, dict):
        sam = sa.get("supplier_assurance_maturity") or ""
    else:
        sam = ""
    if sam in ("None",):
        flags.append("weak")
    elif sam in ("Unknown", ""):
        unknowns += 1
    if isinstance(tp, dict):
        idm = tp.get("identity_model") or ""
        if idm in ("Shared accounts",):
            flags.append("weak")
        elif idm in ("Unknown", ""):
            unknowns += 1
        smfa = tp.get("mfa_status") or ""
        if smfa in ("Not enforced",):
            flags.append("moderate")
        elif smfa in ("Unknown", ""):
            unknowns += 1
    return _pillar_from_flags(flags, unknowns)

def derive_recovery_assurance_maturity(rec: dict) -> str:
    if not isinstance(rec, dict):
        return "Insufficient Evidence"
    flags, unknowns = [], 0
    rt = rec.get("restore_testing") or ""
    if rt in ("Never", "Ad hoc"):
        flags.append("weak")
    elif rt in ("Unknown", ""):
        unknowns += 1
    im = rec.get("immutability_status") or ""
    if im in ("None",):
        flags.append("moderate")
    elif im in ("Unknown", ""):
        unknowns += 1
    return _pillar_from_flags(flags, unknowns)

def derive_incident_response_maturity(ir: dict) -> str:
    if not isinstance(ir, dict):
        return "Insufficient Evidence"
    flags, unknowns = [], 0
    roles = ir.get("roles_defined") or ""
    if roles in ("Informal",):
        flags.append("moderate")
    elif roles in ("Unknown", ""):
        unknowns += 1
    tt = ir.get("tabletop_status") or ""
    if tt in ("Never", "More than one year ago"):
        flags.append("weak")
    elif tt in ("Unknown", ""):
        unknowns += 1
    return _pillar_from_flags(flags, unknowns)

# --------- Recommendation helper (capability-led, evidence-aware) ---------
def add_recommendation(
    recs: List[str],
    capability: str,
    trigger: str,
    evidence_status: str,
    current_control: str | None = None,
    validation_action: str | None = None,
    remediation_action: str | None = None,
    vendor_options: List[str] | None = None,
) -> None:
    """Append a capability-led recommendation string respecting evidence status.

    Rules:
    - Unknown → recommend assessment/validation (do not suggest procurement).
    - Existing control → recommend configuration review/testing/governance.
    - Confirmed missing → proportionate remediation.
    - Mature → acknowledge maintenance only.
    - Vendor options are listed last and optional; external vendor filtering happens upstream.
    """
    parts: List[str] = []
    parts.append(f"Capability: {capability}")
    if trigger:
        parts.append(f"Trigger: {trigger}")
    if evidence_status:
        parts.append(f"Status: {evidence_status}")
    if current_control:
        parts.append(f"Current: {current_control}")
    # Prefer validation for Unknown / Reported
    if evidence_status in ("Not established during consultation", "Reported (unverified)", "Requires supplier confirmation"):
        if validation_action:
            parts.append(f"Validation: {validation_action}")
    # Remediation where appropriate
    if remediation_action and evidence_status not in ("Not applicable",):
        parts.append(f"Remediation: {remediation_action}")
    if vendor_options:
        parts.append("Options: " + ", ".join(vendor_options))
    # Compose and deduplicate simple duplicates
    msg = " — ".join(parts)
    if msg not in recs:
        recs.append(msg)
