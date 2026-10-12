SAFE_UNKNOWN_TO_VALIDATION = {
    "patching": "The assessment did not conclusively establish the current patch-management operating model. Confirm update deployment, exception handling and compliance reporting before deciding whether additional tooling is required.",
    "mfa": "Validate MFA coverage across privileged, service and externally accessible accounts, and document any approved exceptions.",
    "endpoint": "Review endpoint coverage, telemetry quality and operational integration before deciding whether optimisation or platform change is justified.",
    "mdr": "The assessment did not establish whether the monitoring model provides managed 24/7 detection and response coverage. Confirm scope, telemetry sources, escalation arrangements and containment authority.",
    "backups": "Validate representative restore testing, administrative separation and recovery sequencing across the existing estate.",
    "ai_policy": "Branded has established an initial AI-governance baseline. Further assurance should focus on policy adoption, approved-tool coverage, sensitive-data handling and visibility of unmanaged AI use.",
    "email": "Email security posture requires validation; confirm current controls and coverage.",
    "identity": "Identity posture requires validation; confirm MFA coverage and exception handling.",
    "monitoring": "Monitoring posture requires validation; confirm scope, telemetry sources, escalation arrangements and containment authority.",
}

# Model‑guidance safe rewrite patterns (evidence‑grounded rewrite only; not used by deterministic handlers)
SAFE_PATTERNS = [
    {"rule": "UNKNOWN_TO_VALIDATION", "input_hint": "unknown MDR", "output": SAFE_UNKNOWN_TO_VALIDATION["mdr"]},
    {"rule": "EXISTING_MFA", "input_hint": "enforce universal MFA", "output": SAFE_UNKNOWN_TO_VALIDATION["mfa"]},
    {"rule": "EXISTING_ENDPOINT", "input_hint": "deploy endpoint protection", "output": "Review endpoint protection coverage, telemetry quality and operational integration before deciding whether optimisation or platform change is justified."},
    {"rule": "UNKNOWN_BACKUP", "input_hint": "implement backups", "output": SAFE_UNKNOWN_TO_VALIDATION["backups"]},
    {"rule": "UNSUPPORTED_CVE", "input_hint": "named CVE", "output": "A plausible initial-access route could involve misuse of an externally accessible service, although the assessment did not identify a specific exploitable vulnerability."},
    {"rule": "UNAPPROVED_VENDOR", "input_hint": "named product", "output": "Assess capability requirements against telemetry coverage, response authority, operating hours and existing endpoint investment."},
    {"rule": "AI_CONTRADICTION", "input_hint": "no AI usage policy", "output": SAFE_UNKNOWN_TO_VALIDATION["ai_policy"]},
    {"rule": "INSIDER_UNAPPROVED", "input_hint": "insider threat", "output": "The scenario should begin with an evidence-supported identity, email, supplier or externally accessible service risk once confirmed."},
    {"rule": "EMAIL_UNKNOWN", "input_hint": "no email security", "output": SAFE_UNKNOWN_TO_VALIDATION["email"]},
    {"rule": "IDENTITY_UNKNOWN", "input_hint": "no identity/MFA", "output": SAFE_UNKNOWN_TO_VALIDATION["identity"]},
]

REPLACEMENT_LANGUAGE = {
    "no_replacement_without_justification": "Review configuration and coverage of the existing control before considering replacement.",
}

def rewrite_existing_mfa_to_validation(src: str, evidence_present: bool) -> str:
    """
    Safe helper: when MFA is already present/recorded, convert prescriptive 'enforce MFA'
    language to validation‑oriented wording. No model use; conservative.
    """
    try:
        s = str(src or "")
        if not s:
            return s
        if evidence_present and ("mfa" in s.lower()):
            return SAFE_UNKNOWN_TO_VALIDATION["mfa"]
        return s
    except Exception:
        return src

def rewrite_unsupported_cve(section: str, approved_external_service_evidence: bool) -> str:
    """
    Safe helper for unsupported CVE claims. If an externally accessible service is an approved,
    evidence‑supported risk, replace the named CVE with a generic, validation‑oriented route.
    Otherwise remove the CVE claim entirely and fall back to a limited‑assurance statement.
    """
    try:
        s = str(section or "")
        low = s.lower()
        if "cve-" in low or "cve_" in low or "cve " in low:
            if approved_external_service_evidence:
                return "A plausible initial-access route could involve misuse of an externally accessible service, although the assessment did not identify a specific exploitable vulnerability."
            # No approved route: avoid inventing detail
            return "The assessment did not establish a specific initial-access route."
        return s
    except Exception:
        return section
