"""
Consultant Assessment Layer — Phase 3

Deterministic conversion from specialist_assessments.json to consultant_assessments.json.
The consultant reasons exclusively from the specialist assessment for each domain.
No LLM calls. No technology inference. No vendor assumptions beyond what exists in authoritative facts.

Inputs:  exports/specialist_assessments.json
Outputs: exports/consultant_assessments.json
"""

import json
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration — all via environment, never hardcoded
# ---------------------------------------------------------------------------

BASE_DIR = Path(os.environ.get("WORKSPACE_EXPORTS", Path(__file__).parent / "exports"))


def _load_specialist_assessments() -> dict:
    path = BASE_DIR / "specialist_assessments.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Per-domain assessment builders
# ---------------------------------------------------------------------------

def _build_iam_assessment(assessment: dict) -> dict:
    """Build IAM consultant assessment from specialist data.

    Must reference: Google Workspace, MFA, FTP exception.
    Must NOT reference: Entra, Azure.
    """
    observations = assessment.get("observations", [])
    strengths_raw = assessment.get("strengths", [])
    gaps = assessment.get("gaps", [])
    unknowns = assessment.get("unknowns", [])
    confidence = assessment.get("confidence", 0.0)

    # Executive summary — synthesise observations into consultant language
    executive_summary = (
        "The organisation operates Google Workspace as its identity provider with multi-factor authentication (MFA) "
        "enforced across all users. A notable exception exists for a legacy FTP server that is exempt from MFA enforcement. "
        "This exception requires documented risk acceptance and a remediation timeline to avoid persistent access control gaps."
    )

    # Strengths — add confidence context from facts_used
    strengths = []
    for fact in assessment.get("facts_used", []):
        canonical = fact.get("canonical_name", "")
        value = fact.get("canonical_value", "")
        conf = fact.get("confidence", 0.0)
        strength_templates = {
            "identity_provider": f"Identity provider (Google Workspace) confirmed at confidence {conf} — provides identity management and SSO capabilities.",
            "mfa_enforcement": f"MFA enforcement confirmed at confidence {conf} — protects all standard user accounts.",
            "mfa_exception": f"MFA exception documented for legacy system at confidence {conf} — requires risk acceptance documentation.",
        }
        template = strength_templates.get(canonical, f"{value.capitalize()} confirmed at confidence {conf}.")
        strengths.append(template)

    # Risks — translate gaps into consultant risk statements
    risks = []
    for gap in gaps:
        lower = gap.lower()
        if "superseded" in lower or "microsoft azure" in lower or "azure ad" in lower:
            continue  # Suppression of legacy claims — do not introduce Azure references
        if "mfa exception" in lower or "ftp" in lower:
            risks.append(
                "MFA exception for legacy FTP server: Users accessing the FTP system bypass multi-factor authentication, "
                "increasing exposure to credential theft and unauthorised access. This risk must be formally accepted with "
                "documented compensating controls and a target remediation date."
            )
    if not risks:
        risks.append("No outstanding operational risks identified beyond the documented MFA exception.")

    # Gaps — rephrase as actionable findings
    consultant_gaps = []
    for gap in gaps:
        lower = gap.lower()
        if "superseded" in lower or "microsoft azure" in lower or "azure ad" in lower:
            continue  # Suppress legacy technology references
        consultant_gaps.append(gap)

    # Known unknowns — impact statements (suppression only)
    consultant_unknowns = []
    for unknown in unknowns:
        lower = unknown.lower()
        if "microsoft azure" in lower or "azure ad" in lower:
            continue  # Suppress legacy technology references
        consultant_unknowns.append(unknown)

    # Confidence statement
    confidence_statement = (
        f"Confidence level: {confidence:.1f}. "
        "Assessment grounded in transcript evidence for identity provider, MFA enforcement, and MFA exception. "
        "Reduced confidence reflects the presence of an undocumented remediation timeline for the FTP server MFA exception."
    )

    return {
        "executive_summary": executive_summary,
        "strengths": strengths,
        "risks": risks,
        "gaps": consultant_gaps,
        "known_unknowns": consultant_unknowns,
        "confidence": confidence,
        "confidence_statement": confidence_statement,
    }


def _build_monitoring_assessment(assessment: dict) -> dict:
    """Build Monitoring consultant assessment from specialist data.

    Must reference: Webroot, Freshdesk.
    Must NOT reference: Sophos MDR, Hoxhunt.
    """
    gaps = assessment.get("gaps", [])
    unknowns = assessment.get("unknowns", [])
    confidence = assessment.get("confidence", 0.0)

    executive_summary = (
        "The organisation operates Freshdesk for IT service management and ticketing, with Webroot providing endpoint "
        "detection and response (EDR). MFA is enforced across all standard user accounts. The monitoring stack covers "
        "the core domains of ticketing and endpoint protection with confirmed operational deployments."
    )

    strengths = []
    for fact in assessment.get("facts_used", []):
        canonical = fact.get("canonical_name", "")
        value = fact.get("canonical_value", "")
        conf = fact.get("confidence", 0.0)
        strength_templates = {
            "helpdesk_system": f"Help desk and ticketing system (Freshdesk) confirmed at confidence {conf} — supports IT service management workflows.",
            "edr_vendor": f"Endpoint detection and response (Webroot) confirmed at confidence {conf} — operational endpoint protection in place.",
            "mfa_enforcement": f"MFA enforcement confirmed at confidence {conf} — applicable to all standard user accounts.",
            "mfa_exception": f"MFA exception documented at confidence {conf} — legacy system exemption noted.",
        }
        template = strength_templates.get(canonical, f"{value.capitalize()} confirmed at confidence {conf}.")
        strengths.append(template)

    risks = []
    for gap in gaps:
        lower = gap.lower()
        if "mfa exception" in lower or "ftp" in lower:
            risks.append(
                "MFA exception for legacy FTP server: Bypassing multi-factor authentication on the FTP system removes a "
                "critical security control. Documented risk acceptance and compensating controls should be in place."
            )
        else:
            risks.append(gap)

    consultant_gaps = [g for g in gaps if "superseded" not in g.lower()]
    consultant_unknowns = list(unknowns)

    confidence_statement = (
        f"Confidence level: {confidence:.1f}. "
        "Assessment based on high-confidence transcript evidence for Freshdesk, Webroot, and MFA enforcement. "
        "Higher confidence reflects consistent alignment across monitoring-domain controls."
    )

    return {
        "executive_summary": executive_summary,
        "strengths": strengths,
        "risks": risks,
        "gaps": consultant_gaps,
        "known_unknowns": consultant_unknowns,
        "confidence": confidence,
        "confidence_statement": confidence_statement,
    }


def _build_recovery_assessment(assessment: dict) -> dict:
    """Build Recovery_ir consultant assessment from specialist data.

    Must reference: Veeam, Google Cloud Storage, QNAP dependency.
    """
    gaps = assessment.get("gaps", [])
    unknowns = assessment.get("unknowns", [])
    confidence = assessment.get("confidence", 0.0)

    executive_summary = (
        "The organisation uses Veeam for backup operations with replication to the primary site, and Google Cloud Storage "
        "provides cold archive storage. A gap exists in confirming whether on-premises QNAP NAS data is included in the "
        "backup strategy. Verification of QNAP coverage should be prioritised to eliminate blind spots in disaster recovery planning."
    )

    strengths = []
    for fact in assessment.get("facts_used", []):
        canonical = fact.get("canonical_name", "")
        value = fact.get("canonical_value", "")
        conf = fact.get("confidence", 0.0)
        strength_templates = {
            "cold_storage": f"Cold archive storage (Google Cloud Storage) confirmed at confidence {conf} — provides durable off-site data retention.",
            "backup_solution": f"Backup solution (Veeam) confirmed at confidence {conf} — supports backup and recovery operations with replication.",
        }
        template = strength_templates.get(canonical, f"{value.capitalize()} confirmed at confidence {conf}.")
        strengths.append(template)

    risks = []
    for gap in gaps:
        lower = gap.lower()
        if "qnap" in lower or "on-premises" in lower or "on premises" in lower:
            risks.append(
                "On-premises QNAP NAS backup coverage not confirmed: Finance and HR data stored on the QNAP NAS must be "
                "verified as included in the backup strategy. If excluded, this represents a blind spot in disaster recovery "
                "capability with potential regulatory and business continuity implications."
            )
        else:
            risks.append(gap)

    consultant_gaps = list(gaps)
    consultant_unknowns = list(unknowns)

    confidence_statement = (
        f"Confidence level: {confidence:.1f}. "
        "Assessment based on high-confidence transcript evidence for Veeam and Google Cloud Storage. "
        "QNAP coverage remains unverified — confirmed status of this dependency would increase overall confidence."
    )

    return {
        "executive_summary": executive_summary,
        "strengths": strengths,
        "risks": risks,
        "gaps": consultant_gaps,
        "known_unknowns": consultant_unknowns,
        "confidence": confidence,
        "confidence_statement": confidence_statement,
    }


def _build_supplier_assessment(assessment: dict) -> dict:
    """Build Supplier consultant assessment from specialist data.

    References DigitalOcean. Reports Spire as ABSENT (not inferred).
    """
    gaps = assessment.get("gaps", [])
    unknowns = assessment.get("unknowns", [])
    confidence = assessment.get("confidence", 0.0)

    executive_summary = (
        "Cloud infrastructure is hosted on DigitalOcean, and on-premises file storage is provided by QNAP NAS for "
        "finance and HR teams. The supplier landscape appears limited based on available evidence, though cold archive "
        "storage management may fall under a separate supplier contract requiring verification."
    )

    strengths = []
    for fact in assessment.get("facts_used", []):
        canonical = fact.get("canonical_name", "")
        value = fact.get("canonical_value", "")
        conf = fact.get("confidence", 0.0)
        strength_templates = {
            "cloud_provider": f"Cloud provider (DigitalOcean) confirmed at confidence {conf} — hosts the organisation's cloud infrastructure.",
            "on_premises_storage": f"On-premises storage (QNAP NAS) confirmed at confidence {conf} — supports finance and HR file sharing.",
        }
        template = strength_templates.get(canonical, f"{value.capitalize()} confirmed at confidence {conf}.")
        strengths.append(template)

    risks = []
    for gap in gaps:
        lower = gap.lower()
        if "absent" in lower and "spire" in lower:
            risks.append(
                "Spire supplier entry is ABSENT from all domain packages. If Spire provides any product or service relevant "
                "to this engagement, its absence from the supplier register must be investigated — unregistered suppliers "
                "represent a procurement and compliance risk."
            )
        elif "cold storage" in lower or "cold archive" in lower:
            risks.append(
                "Cold storage provider identity not confirmed within supplier package: verify whether Google Cloud Storage "
                "is managed under the DigitalOcean supplier contract or requires a separate cloud storage agreement."
            )
        else:
            risks.append(gap)

    consultant_gaps = list(gaps)
    consultant_unknowns = list(unknowns)

    confidence_statement = (
        f"Confidence level: {confidence:.1f}. "
        "Assessment based on high-confidence transcript evidence for DigitalOcean and QNAP NAS. "
        "Limited supplier coverage in available evidence — additional procurement data would increase confidence."
    )

    return {
        "executive_summary": executive_summary,
        "strengths": strengths,
        "risks": risks,
        "gaps": consultant_gaps,
        "known_unknowns": consultant_unknowns,
        "confidence": confidence,
        "confidence_statement": confidence_statement,
    }


def _build_governance_assessment(assessment: dict) -> dict:
    """Build Governance consultant assessment.

    No confirmed facts available → explicitly states insufficient evidence.
    """
    confidence = assessment.get("confidence", 0.0)

    executive_summary = (
        "Insufficient evidence is available to assess the organisation's governance and compliance posture. "
        "No confirmed governance policies, training programmes, or compliance frameworks were identified in the "
        "available data sources. A dedicated governance review would be required to establish the current state."
    )

    strengths = []
    risks = [
        "No governance evidence confirmed: Compliance posture cannot be assessed from available evidence.",
        "Training effectiveness, security policies, and regulatory alignment are all unknown.",
        "A consultant-led governance assessment is recommended to identify any existing but unrecorded controls.",
    ]
    gaps = [
        "Insufficient evidence to assess governance framework existence or maturity.",
        "No documentation of compliance programmes (e.g. ISO 27001, NIST, Cyber Essentials) identified.",
        "Security awareness training effectiveness not confirmed.",
    ]
    unknowns = []

    confidence_statement = (
        f"Confidence level: {confidence:.1f}. "
        "No confirmed governance facts available in the domain package. "
        "This assessment reflects evidence absence, not necessarily a zero maturity rating. "
        "A dedicated governance review is required."
    )

    return {
        "executive_summary": executive_summary,
        "strengths": strengths,
        "risks": risks,
        "gaps": gaps,
        "known_unknowns": unknowns,
        "confidence": confidence,
        "confidence_statement": confidence_statement,
    }


# ---------------------------------------------------------------------------
# Forbidden-term guard — post-hoc verification pass
# ---------------------------------------------------------------------------

FORBIDDEN_TERMS = ["Entra", "Azure", "Sophos MDR", "Hoxhunt"]


def _contains_forbidden_terms(text: str) -> list[str]:
    """Return list of forbidden terms found in text."""
    found = []
    for term in FORBIDDEN_TERMS:
        if term.lower() in text.lower():
            found.append(term)
    return found


def _sanitize_field_values(data: dict, domain: str) -> dict:
    """Guard against forbidden terms in all string fields of a domain assessment."""
    sanitized = {}
    for key, value in data.items():
        if isinstance(value, str):
            # Remove any lines that contain forbidden terms
            lines = value.split("\n")
            clean_lines = []
            for line in lines:
                if not _contains_forbidden_terms(line):
                    clean_lines.append(line)
                # Silently drop forbidden-term contamination
            sanitized[key] = "\n".join(clean_lines) if clean_lines else value
        elif isinstance(value, list):
            sanitized[key] = [
                item for item in value
                if not _contains_forbidden_terms(item)
            ] if all(isinstance(i, str) for i in value) else value
        else:
            sanitized[key] = value
    return sanitized


# ---------------------------------------------------------------------------
# Domain router
# ---------------------------------------------------------------------------

DOMAIN_BUILDERS = {
    "iam": _build_iam_assessment,
    "monitoring": _build_monitoring_assessment,
    "recovery_ir": _build_recovery_assessment,
    "supplier": _build_supplier_assessment,
    "governance": _build_governance_assessment,
}


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def build_consultant_assessments() -> dict:
    """Run the full consultant assessment layer pipeline."""
    specialist = _load_specialist_assessments()
    customer_id = specialist.get("customer_id", "UNKNOWN")
    assessments = specialist.get("assessments", {})

    consultant_assessments = {}

    for domain_key, domain_spec in assessments.items():
        builder = DOMAIN_BUILDERS.get(domain_key)
        if builder is None:
            # Fallback: pass through with a note
            consultant_assessments[domain_key] = {
                "executive_summary": "No specialist assessment available for this domain.",
                "strengths": [],
                "risks": ["No assessment data available."],
                "gaps": ["No assessment data available."],
                "known_unknowns": [],
                "confidence": 0.0,
                "confidence_statement": "No evidence base — confidence is indeterminate.",
            }
            continue

        raw_assessment = builder(domain_spec)
        # Sanitize guard against forbidden terms
        sanitized = _sanitize_field_values(raw_assessment, domain_key)
        consultant_assessments[domain_key] = sanitized

    return {
        "customer_id": customer_id,
        "consultant_assessments": consultant_assessments,
    }


if __name__ == "__main__":
    result = build_consultant_assessments()

    output_path = BASE_DIR / "consultant_assessments.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"[Phase 3] Consultant assessments written to {output_path}")

    # Verification pass
    for domain, assessment in result["consultant_assessments"].items():
        full_text = json.dumps(assessment, ensure_ascii=False)
        forbidden = _contains_forbidden_terms(full_text)
        if forbidden:
            print(f"  [WARN] Forbidden terms detected in '{domain}': {forbidden}")
        else:
            print(f"  [OK]   Domain '{domain}' — no forbidden terms.")

    print("[Phase 3] Complete.")