from __future__ import annotations
from typing import Tuple, List, Dict, Any
from section_improvers.shared_rules import ReportImprovementRules, ReviewerChange
from evidence_extraction import AssessmentEvidence, TranscriptInsight

def improve_environment_overview(
    report_dict: Dict[str, Any],
    evidence: AssessmentEvidence,
    adjudication,
    insights: List[TranscriptInsight],
    rules: ReportImprovementRules
) -> Tuple[Dict[str, Any], List[ReviewerChange]]:
    """
    Make the environment section the source of truth if fields exist both in report and evidence.
    Non-destructive: only fills empty scalar fields from evidence; never overwrites non-empty values.
    """
    changes: List[ReviewerChange] = []
    out: Dict[str, Any] = {}

    def _set_if_empty(key: str, value: str, rationale: str):
        try:
            existing = report_dict.get(key)
        except Exception:
            existing = None
        if (existing is None or (isinstance(existing, str) and not existing.strip())) and value:
            out[key] = value
            changes.append(ReviewerChange(
                section="environment",
                before=str(existing)[:180] if existing else "",
                after=str(value)[:180],
                rationale=rationale,
                rule_refs=["TRANSCRIPT_EVIDENCE_PRIORITY"]
            ))

    if evidence.customer_name:
        _set_if_empty("customer_name", evidence.customer_name, "Populate customer_name from transcript evidence.")
    if evidence.industry:
        _set_if_empty("industry", evidence.industry, "Populate industry from transcript evidence.")
    if evidence.crown_jewels:
        try:
            existing = report_dict.get("critical_infra")
        except Exception:
            existing = None
        if (existing is None or (isinstance(existing, str) and not existing.strip())) and len(evidence.crown_jewels) > 0:
            cj_val = "; ".join([str(x) for x in evidence.crown_jewels[:3] if str(x).strip()])
            if cj_val:
                out["critical_infra"] = cj_val
                changes.append(ReviewerChange(
                    section="environment",
                    before=str(existing)[:180] if existing else "",
                    after=cj_val[:180],
                    rationale="Set Crown Jewels (critical_infra) from transcript evidence (top items).",
                    rule_refs=["TRANSCRIPT_EVIDENCE_PRIORITY"]
                ))

    return out, changes