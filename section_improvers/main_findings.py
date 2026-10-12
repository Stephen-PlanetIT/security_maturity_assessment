from __future__ import annotations
from typing import Tuple, List, Optional, Any
from section_improvers.shared_rules import ReportImprovementRules, ReviewerChange
from evidence_extraction import AssessmentEvidence, TranscriptInsight

def improve_main_findings(
    raw: Optional[Any],
    evidence: AssessmentEvidence,
    adjudication,
    insights: List[TranscriptInsight],
    rules: ReportImprovementRules
) -> Tuple[Any, List[ReviewerChange]]:
    """
    Non-destructive improvement:
    - If main findings is a string block and lacks explicit Business/Compliance impact, append concise evidence-led context.
    - Facts only; do not invent recommendations or scores. Never overwrite existing text.
    - If findings is a list/dict of unknown shape, preserve unchanged to avoid schema risk.
    """
    changes: List[ReviewerChange] = []
    if raw is None:
        return raw, changes

    # Only handle the simple string case safely; preserve other structures
    if isinstance(raw, str):
        before = raw
        text = before.strip()
        if not text:
            return raw, changes

        lower = text.lower()
        needs_biz = "business impact" not in lower
        needs_comp = "compliance impact" not in lower

        appended_lines: List[str] = []

        # Business Impact line from evidence (crown jewels, downtime tolerance, priorities)
        if needs_biz:
            try:
                cj = ""
                try:
                    cj_list = [str(x).strip() for x in (getattr(evidence, "crown_jewels", []) or []) if str(x).strip()]
                    if cj_list:
                        cj = cj_list[0]
                except Exception:
                    cj = ""
                rto = ""
                try:
                    rto_list = [str(x).strip() for x in (getattr(evidence, "downtime_requirements", []) or []) if str(x).strip()]
                    if rto_list:
                        rto = rto_list[0]
                except Exception:
                    rto = ""
                prios = []
                try:
                    prios = [str(x).strip() for x in (getattr(evidence, "business_priorities", []) or []) if str(x).strip()]
                except Exception:
                    prios = []
                parts = []
                if cj:
                    parts.append(f"threatens access to '{cj}'")
                if rto:
                    parts.append(f"with downtime tolerance of {rto}")
                if prios:
                    parts.append(f"and impacts priorities such as {', '.join(prios[:2])}")
                if parts:
                    appended_lines.append(f"Business Impact: The current weaknesses {', '.join(parts)}.")
            except Exception:
                pass

        # Compliance Impact line from evidence (obligations)
        if needs_comp:
            try:
                obls = [str(x).strip() for x in (getattr(evidence, "compliance_requirements", []) or []) if str(x).strip()]
                if obls:
                    appended_lines.append(f"Compliance Impact: Misalignment with stated obligations may arise (e.g., {', '.join(obls[:2])}).")
            except Exception:
                pass

        if appended_lines:
            after = before + ("\n\n" if not before.endswith("\n") else "\n") + " ".join(appended_lines)
            changes.append(
                ReviewerChange(
                    section="main_findings",
                    before=before[:280],
                    after=after[:280],
                    rationale="Appended concise Business/Compliance impact lines using transcript evidence.",
                    rule_refs=["PREFER_BUSINESS_IMPACT", "NO_GENERIC_FINDINGS", "TRANSCRIPT_EVIDENCE_PRIORITY"],
                )
            )
            return after, changes

        return raw, changes

    # Non-string shapes: preserve unchanged to avoid schema risk
    return raw, changes
