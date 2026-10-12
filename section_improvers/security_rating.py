from __future__ import annotations
from typing import Tuple, List, Optional, Dict, Any
from section_improvers.shared_rules import ReportImprovementRules, ReviewerChange
from evidence_extraction import AssessmentEvidence, TranscriptInsight

def improve_security_rating(
    rating_obj: Optional[Dict[str, Any]],
    evidence: AssessmentEvidence,
    adjudication,
    insights: List[TranscriptInsight],
    rules: ReportImprovementRules
) -> Tuple[Dict[str, Any], List[ReviewerChange]]:
    """
    Non-destructive improvement of Security Rating snapshot lists:
    - If snapshot.primary_strengths or snapshot.primary_gaps are empty or clearly generic placeholders,
      append evidence-driven items from confirmed_strengths / confirmed_gaps, capped to preserve brevity.
    - Never overwrite existing items; only append unique, non-empty items.

    Note: Deterministic scoring (including Capability Mismatch penalties where MDR is present but foundational hygiene
    is missing/unvalidated) is enforced by the validator/scoring layer. This improver must not bypass or weaken that logic.
    """
    changes: List[ReviewerChange] = []
    if rating_obj is None:
        return {}, changes

    try:
        snapshot = rating_obj.get("snapshot") if isinstance(rating_obj, dict) else None
        if not isinstance(snapshot, dict):
            return rating_obj, changes

        strengths = snapshot.get("primary_strengths")
        gaps = snapshot.get("primary_gaps")

        # Generic placeholder detection (lightweight)
        def _is_generic_list(lst):
            try:
                if not isinstance(lst, list) or len(lst) == 0:
                    return True
                s = " ".join([str(x).lower() for x in lst])
                tokens = ("good cyber hygiene", "best practice", "industry standard", "defence in depth")
                return any(t in s for t in tokens)
            except Exception:
                return False

        # Build candidate lists from adjudication (facts only; do NOT treat unknowns as gaps)
        try:
            controls = getattr(adjudication, "existing_controls", []) or []
            ev_strengths = [str(getattr(c, "control_name", "")).strip() for c in controls if str(getattr(c, "control_name", "")).strip()]
        except Exception:
            ev_strengths = []

        try:
            unsup = getattr(adjudication, "unsupported_claims", []) or []
            contrad = getattr(adjudication, "contradicted_claims", []) or []
            # Strictly avoid unknowns/unvalidated as gaps
            ev_gaps = []
            for cl in list(unsup)[:6] + list(contrad)[:6]:
                txt = str(getattr(cl, "claim_text", "")).strip()
                if txt:
                    ev_gaps.append(txt)
        except Exception:
            ev_gaps = []

        # Append strengths
        appended = False
        if (not isinstance(strengths, list) or _is_generic_list(strengths)) and ev_strengths:
            new_list = []
            if isinstance(strengths, list):
                new_list.extend([s for s in strengths if str(s).strip()])
            # Cap to at most 4 total
            for item in ev_strengths:
                if item not in new_list:
                    new_list.append(item)
                if len(new_list) >= 4:
                    break
            snapshot["primary_strengths"] = new_list
            appended = True

        # Append gaps
        appended_g = False
        if (not isinstance(gaps, list) or _is_generic_list(gaps)) and ev_gaps:
            new_list_g = []
            if isinstance(gaps, list):
                new_list_g.extend([g for g in gaps if str(g).strip()])
            for item in ev_gaps:
                if item not in new_list_g:
                    new_list_g.append(item)
                if len(new_list_g) >= 6:
                    break
            snapshot["primary_gaps"] = new_list_g
            appended_g = True

        if appended or appended_g:
            before = {"strengths": strengths or [], "gaps": gaps or []}
            after = {"strengths": snapshot.get("primary_strengths", []), "gaps": snapshot.get("primary_gaps", [])}
            changes.append(
                ReviewerChange(
                    section="security_rating",
                    before=str(before)[:280],
                    after=str(after)[:280],
                    rationale="Aligned security snapshot lists with evidence-confirmed strengths and gaps (non-destructive append).",
                    rule_refs=["NO_GENERIC_FINDINGS", "TRANSCRIPT_EVIDENCE_PRIORITY"],
                )
            )
    except Exception:
        # Fail closed: leave rating unchanged on any parsing error
        return rating_obj, changes

    return rating_obj, changes
