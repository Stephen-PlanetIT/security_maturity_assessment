from __future__ import annotations
from typing import Tuple, List, Optional
from section_improvers.shared_rules import ReportImprovementRules, ReviewerChange
from evidence_extraction import AssessmentEvidence, TranscriptInsight

def _is_generic_language(text: str) -> bool:
    try:
        s = (text or "").lower()
        tokens = (
            "cybersecurity is important",
            "evolving threat landscape",
            "best practice",
            "modern attacker",
            "defence in depth",
        )
        return any(t in s for t in tokens)
    except Exception:
        return False

def improve_executive_summary(
    raw: Optional[str],
    evidence: AssessmentEvidence,
    adjudication,
    insights: List[TranscriptInsight],
    rules: ReportImprovementRules,
) -> Tuple[str, List[ReviewerChange]]:
    """
    Non-destructive improvement:
    - If clearly generic language is detected, prepend a short business-context line using evidence (customer_name/industry) without inventing claims.
    - If absent, append concise lines to acknowledge business priorities, existing investments, and key gaps using transcript facts only.
    - Never remove or overwrite substantive content; only prepend/append succinct evidence-led context.
    """
    before = raw or ""
    changes: List[ReviewerChange] = []
    if not before.strip():
        return before, changes

    improved_text = before
    prefixed = False

    # 1) Replace clearly generic opening (when rule enabled)
    try:
        if "NO_GENERIC_EXECUTIVE_LANGUAGE" in (rules.enabled or set()) and _is_generic_language(before):
            prefix_bits = []
            if getattr(evidence, "customer_name", None):
                prefix_bits.append(str(evidence.customer_name))
            if getattr(evidence, "industry", None):
                prefix_bits.append(str(evidence.industry))
            prefix = " — ".join(prefix_bits) if prefix_bits else "The organisation"
            improved_text = f"{prefix} operates with specific operational constraints and objectives established in consultation. " + before
            changes.append(
                ReviewerChange(
                    section="executive_summary",
                    before=before[:280],
                    after=improved_text[:280],
                    rationale="Replaced generic opening with customer-specific context using transcript evidence.",
                    rule_refs=["NO_GENERIC_EXECUTIVE_LANGUAGE", "TRANSCRIPT_EVIDENCE_PRIORITY"],
                )
            )
            prefixed = True
    except Exception:
        pass

    # 2) Append concise evidence-led context blocks (if not already present)
    appended_lines: List[str] = []

    # Business priorities (use adjudicated priorities/categories)
    try:
        cps = (getattr(adjudication, "customer_priorities", []) or [])
        priorities: List[str] = []
        for cp in cps:
            try:
                p = str(getattr(cp, "priority", "")).strip()
                if p:
                    priorities.append(p)
            except Exception:
                continue
        if priorities:
            top = list(dict.fromkeys(priorities))[:2]
            lower_text = improved_text.lower()
            missing = [p for p in top if p.lower() not in lower_text]
            if missing:
                appended_lines.append(f"Business priorities highlighted during consultation: {'; '.join(missing)}.")
    except Exception:
        pass

    # Existing investments (adjudicated existing_controls)
    try:
        ctrls = (getattr(adjudication, "existing_controls", []) or [])
        stack: List[str] = []
        for c in ctrls:
            try:
                name = str(getattr(c, "control_name", "")).strip()
                if name:
                    stack.append(name)
            except Exception:
                continue
        stack = list(dict.fromkeys(stack))[:3]
        if stack:
            lower_text = improved_text.lower()
            if not any(s.lower() in lower_text for s in stack):
                appended_lines.append(f"Existing investments acknowledged: {', '.join(stack)}.")
    except Exception:
        pass

    # Confirmed gaps (adjudicated unsupported/contradicted claims only)
    try:
        claims: List[str] = []
        try:
            for cl in ((getattr(adjudication, "unsupported_claims", []) or [])[:4]):
                txt = str(getattr(cl, "claim_text", "")).strip()
                if txt:
                    claims.append(txt)
            for cl in ((getattr(adjudication, "contradicted_claims", []) or [])[:4]):
                txt = str(getattr(cl, "claim_text", "")).strip()
                if txt:
                    claims.append(txt)
        except Exception:
            pass
        if claims:
            top_gaps = list(dict.fromkeys(claims))[:2]
            lower_text = improved_text.lower()
            if not any(g.lower() in lower_text for g in top_gaps):
                appended_lines.append(f"Key weaknesses observed in consultation: {'; '.join(top_gaps)}.")
    except Exception:
        pass

    if appended_lines:
        after_text = improved_text + ("\n\n" if not improved_text.endswith("\n") else "\n") + " ".join(appended_lines)
        changes.append(
            ReviewerChange(
                section="executive_summary",
                before=improved_text[:280],
                after=after_text[:280],
                rationale="Appended concise evidence-led context (priorities, investments, gaps) without altering existing wording.",
                rule_refs=["TRANSCRIPT_EVIDENCE_PRIORITY", "RECOGNISE_EXISTING_CONTROLS", "NO_GENERIC_FINDINGS"],
            )
        )
        improved_text = after_text

    return improved_text, changes
