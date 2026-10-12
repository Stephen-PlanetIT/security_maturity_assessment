from __future__ import annotations
from typing import Optional
from services.report_improvement.evidence_enforcement.models import (
    ValidationIssue,
    EvidenceEnforcementContext,
)
from .models import RemediationClass


# Default mapping based on available rule_ids in the current validator
# and the specification's default remediation classes.
_RULE_DEFAULTS = {
    # Financials
    "NO_CONCRETE_COSTS_WITHOUT_EVIDENCE": RemediationClass.DETERMINISTIC_FIX,  # Unsupported monetary values
    "UNSUPPORTED_FINANCIAL_FIGURE": RemediationClass.DETERMINISTIC_FIX,
    # Unknown presented as weakness (spec maps UNKNOWN_PRESENTED_AS_WEAKNESS)
    "UNKNOWN_NOT_WEAKNESS": RemediationClass.EVIDENCE_GROUNDED_REWRITE,
    # Replacement recommendation without justification (existing control present)
    "NO_REPLACEMENT_WITHOUT_JUSTIFICATION": RemediationClass.EVIDENCE_GROUNDED_REWRITE,
    # Scenario constraints
    "SCENARIO_CVE_NOT_APPROVED": RemediationClass.SAFE_REMOVAL,  # or evidence-grounded rewrite when applicable
    "SCENARIO_THREAT_ACTOR_NOT_APPROVED": RemediationClass.EVIDENCE_GROUNDED_REWRITE,
    "INSIDER_SCENARIO_NOT_APPROVED": RemediationClass.EVIDENCE_GROUNDED_REWRITE,
    # Vendors
    "UNAPPROVED_VENDOR": RemediationClass.EVIDENCE_GROUNDED_REWRITE,
    # Content quality
    "GENERIC_FALLBACK_CONTENT": RemediationClass.EVIDENCE_GROUNDED_REWRITE,
    "TRUNCATED_CONTENT": RemediationClass.EVIDENCE_GROUNDED_REWRITE,
    # Template/docx placeholders (not yet emitted by validator; reserved)
    "PUBLICATION_PLACEHOLDER": RemediationClass.TEMPLATE_FIX,
    "CONSULTANT_ONLY_CONTENT": RemediationClass.SAFE_REMOVAL,
    "EMPTY_KNOWN_ISSUES_TABLE": RemediationClass.DETERMINISTIC_FIX,
    "DUPLICATE_PARAGRAPH": RemediationClass.DETERMINISTIC_FIX,
    "MARKDOWN_ESCAPE": RemediationClass.DETERMINISTIC_FIX,
    # Score arithmetic (reserved)
    "SCORE_ARITHMETIC_ERROR": RemediationClass.DETERMINISTIC_FIX,
}


def classify_validation_issue(
    issue: ValidationIssue,
    context: EvidenceEnforcementContext,
) -> RemediationClass:
    """
    Classify a deterministic ValidationIssue into a remediation class.

    This function does not alter enforcement decisions; it informs the remediation
    orchestrator which pathway to attempt first (deterministic, safe removal, evidence-grounded rewrite).
    """
    rid = str(getattr(issue, "rule_id", "") or "")
    if not rid:
        return RemediationClass.NOT_REMEDIABLE

    # Direct mapping first
    rc = _RULE_DEFAULTS.get(rid)
    if rc is not None:
        # Minor context-sensitive toggles as safe defaults:
        # - If scenario allows specific CVEs or named actors, downgrade SAFE_REMOVAL to NOT_REMEDIABLE (should not occur).
        if rid == "SCENARIO_CVE_NOT_APPROVED":
            try:
                if getattr(context.scenario_profile, "allow_specific_cves", False):
                    return RemediationClass.NOT_REMEDIABLE
            except Exception:
                pass
        if rid == "SCENARIO_THREAT_ACTOR_NOT_APPROVED":
            try:
                if getattr(context.scenario_profile, "allow_named_threat_actors", False):
                    return RemediationClass.NOT_REMEDIABLE
            except Exception:
                pass
        return rc

    # Fallback heuristic classifications for unforeseen rule_ids
    # - Prefer deterministic fix for purely syntactic/template markers
    text = (issue.offending_text or "").lower()
    if "cve-" in text:
        return RemediationClass.SAFE_REMOVAL
    if any(tok in text for tok in ("£", " usd", " eur")):
        return RemediationClass.DETERMINISTIC_FIX
    if "placeholder" in text or "insert" in text:
        return RemediationClass.TEMPLATE_FIX

    # Default: evidence-grounded rewrite, safe and conservative
    return RemediationClass.EVIDENCE_GROUNDED_REWRITE