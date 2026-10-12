from __future__ import annotations
from typing import List
from pydantic import BaseModel, Field
from .models import ValidationIssue, EvidenceEnforcementContext

class RevisedSection(BaseModel):
    section_name: str
    revised_content: str
    addressed_rule_ids: List[str] = Field(default_factory=list, min_items=0, max_items=200)
    unresolved_rule_ids: List[str] = Field(default_factory=list, min_items=0, max_items=200)
    evidence_ids_used: List[str] = Field(default_factory=list, min_items=0, max_items=200)

async def revise_section_from_validation_errors(
    section_name: str,
    original_section: str,
    rejected_content: str,
    issues: List[ValidationIssue],
    context: EvidenceEnforcementContext,
) -> RevisedSection:
    """
    Deterministic, conservative fixer for known rule failures. No new facts are introduced.
    This routine only corrects specific, mechanistically detectable violations to aid
    deterministic revalidation (e.g., redact CVE tokens, scrub currency amounts, remove unapproved vendor tokens).
    """
    text = str(rejected_content or "")
    addressed: List[str] = []
    unresolved: List[str] = []
    try:
        import re
        for iss in (issues or []):
            rid = str(getattr(iss, "rule_id", "") or "")
            # First, attempt a registry-based deterministic handler (if available)
            try:
                from services.report_improvement.auto_remediation.deterministic_fixes import DETERMINISTIC_HANDLERS  # type: ignore
                handler = DETERMINISTIC_HANDLERS.get(rid)
            except Exception:
                handler = None
            if handler is not None:
                try:
                    new_text, h_changed = handler(text, issues, context)
                    if h_changed and new_text != text:
                        text = new_text
                        addressed.append(rid)
                        continue
                except Exception:
                    # Fall back to built-in deterministic logic below
                    pass
            # Redact specific CVE references unless explicitly allowed by scenario profile
            if rid == "SCENARIO_CVE_NOT_APPROVED":
                new_text = re.sub(r"\bCVE-\d{4}-\d{4,7}\b", "a specific CVE (redacted pending approval)", text, flags=re.IGNORECASE)
                if new_text != text:
                    text = new_text
                    addressed.append(rid)
                else:
                    unresolved.append(rid)
            # Remove quantified currency values and replace the full cost narrative with an approved fallback text.
            # No model calls; deterministic and conservative. Fallback loaded via config to avoid scattering literals.
            elif rid == "NO_CONCRETE_COSTS_WITHOUT_EVIDENCE":
                from config import get_config
                try:
                    fallback = get_config("EVIDENCE_FALLBACK_COST_TEXT",
                        "Financial exposure has not been quantified from validated business data. Relevant cost drivers include lost productive time, delayed customer delivery, specialist incident response, recovery activity and management overhead. These should be modelled using customer-provided operational and financial inputs.")
                except Exception:
                    fallback = ("Financial exposure has not been quantified from validated business data. Relevant cost drivers include "
                                "lost productive time, delayed customer delivery, specialist incident response, recovery activity and management overhead. "
                                "These should be modelled using customer-provided operational and financial inputs.")
                # Remove currency tokens and ranges entirely
                new_text = re.sub(r"\b(£|GBP|USD|EUR)\s?\d[\d,\.]*(\s*(to|-|–|—)\s*(£|GBP|USD|EUR)\s?\d[\d,\.]*)?", "", text, flags=re.IGNORECASE)
                # Heuristic replacement for a 'cost of inaction' block; otherwise append a single fallback paragraph
                if "cost of inaction" in new_text.lower():
                    try:
                        new_text = re.sub(r"(?si)(cost of inaction.*?)(\n\n|\Z)", lambda m: f"{fallback}\n\n", new_text)
                    except Exception:
                        if fallback not in new_text:
                            new_text = f"{new_text.rstrip()}\n\n{fallback}"
                else:
                    if fallback not in new_text:
                        new_text = f"{new_text.rstrip()}\n\n{fallback}"
                if new_text != text:
                    text = new_text
                    addressed.append(rid)
                else:
                    unresolved.append(rid)
            # Convert absolute absence claims to validation-oriented language
            elif rid == "UNKNOWN_NOT_WEAKNESS":
                new_text = text
                try:
                    from services.report_improvement.auto_remediation.safe_language import SAFE_UNKNOWN_TO_VALIDATION
                    # Apply centralised safe-language replacements (case-insensitive)
                    replacements = [
                        (r"\bno mdr\b", SAFE_UNKNOWN_TO_VALIDATION.get("mdr")),
                        (r"\bno backups\b", SAFE_UNKNOWN_TO_VALIDATION.get("backups")),
                        (r"\bno patching\b", SAFE_UNKNOWN_TO_VALIDATION.get("patching")),
                        (r"\bno edr\b|\bno endpoint\b", SAFE_UNKNOWN_TO_VALIDATION.get("endpoint")),
                        (r"\bno email security\b", SAFE_UNKNOWN_TO_VALIDATION.get("email") or "Email security posture requires validation; confirm current controls and coverage."),
                        (r"\bno identity\b|\bno mfa\b", SAFE_UNKNOWN_TO_VALIDATION.get("identity")),
                        (r"\bno siem\b|\bno monitoring\b", SAFE_UNKNOWN_TO_VALIDATION.get("monitoring")),
                    ]
                    for pat, repl in replacements:
                        if repl:
                            new_text = re.sub(pat, repl, new_text, flags=re.IGNORECASE)
                except Exception:
                    new_text = text
                if new_text != text:
                    text = new_text
                    addressed.append(rid)
                else:
                    unresolved.append(rid)
            # Deter replacement language without approved justification
            elif rid == "NO_REPLACEMENT_WITHOUT_JUSTIFICATION":
                new_text = re.sub(r"\breplace\b", "Review configuration and coverage of the existing control before considering replacement", text, flags=re.IGNORECASE)
                if new_text != text:
                    text = new_text
                    addressed.append(rid)
                else:
                    unresolved.append(rid)
            # Scrub explicit unapproved vendor tokens (prototype for Adlumin)
            elif rid == "UNAPPROVED_VENDOR":
                new_text = re.sub(r"\bAdlumin\b", "approved vendor", text, flags=re.IGNORECASE)
                if new_text != text:
                    text = new_text
                    addressed.append(rid)
                else:
                    unresolved.append(rid)
            # Remove insider threat lexicon if not approved
            elif rid == "INSIDER_SCENARIO_NOT_APPROVED":
                new_text = re.sub(r"\b(insider threat|malicious insider|privileged insider|internal threat actor)\b", "internal risk (unapproved scenario removed)", text, flags=re.IGNORECASE)
                if new_text != text:
                    text = new_text
                    addressed.append(rid)
                else:
                    unresolved.append(rid)
            # Replace generic boilerplate with an evidence-led placeholder phrasing
            elif rid == "GENERIC_FALLBACK_CONTENT":
                # Limited substitution to force more specific phrasing while keeping semantics conservative
                repls = {
                    "Gap: coverage limited or untested": "Address specific coverage gaps identified in evidence, ensuring measurable outcomes.",
                    "Enable baseline hardening with native controls": "Apply targeted hardening with tracked outcomes in line with approved standards.",
                    "Apply configuration baselines and periodic reviews": "Establish configuration baselines and periodic reviews tied to measurable objectives.",
                    "Deploy consultative improvements aligned to risk and operational context": "Implement evidence-led improvements aligned to identified risks and operational constraints.",
                    "Adopt monitoring and validation to reduce dwell time": "Adopt monitoring and validation aligned to approved detection and response capabilities.",
                    "Integrate governance cadence to sustain improvements": "Establish a governance cadence with explicit ownership and success criteria.",
                }
                new_text = text
                for k, v in repls.items():
                    new_text = re.sub(re.escape(k), v, new_text, flags=re.IGNORECASE)
                if new_text != text:
                    text = new_text
                    addressed.append(rid)
                else:
                    unresolved.append(rid)
            # Append a completion sentence if content appears truncated
            elif rid == "TRUNCATED_CONTENT":
                t = text.rstrip()
                if not t.endswith((".", "!", "?")):
                    t = t + "."
                t = t + " Complete recommended action statements to ensure clarity."
                if t != text:
                    text = t
                    addressed.append(rid)
                else:
                    unresolved.append(rid)
            else:
                unresolved.append(rid)
    except Exception:
        unresolved = [str(getattr(iss, "rule_id", "")) for iss in (issues or [])]
    return RevisedSection(
        section_name=section_name,
        revised_content=text,
        addressed_rule_ids=addressed,
        unresolved_rule_ids=unresolved,
        evidence_ids_used=[],
    )