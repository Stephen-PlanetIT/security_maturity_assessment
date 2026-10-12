from __future__ import annotations
from typing import List, Dict, Any

from services.report_improvement.section_generators.models import (
    ExecutiveSummaryOutput,
    AttackScenarioOutput,
    ComplianceAlignmentOutput,
    FrameworkAlignmentRow,
    DomainAssessmentOutput,
    SecurityRatingOutput,
)


def _bullet(lines: List[str]) -> str:
    out: List[str] = []
    for s in (lines or []):
        t = str(s or "").strip()
        if t:
            out.append(f"- {t}")
    return "\n".join(out)


def to_text_executive_summary(es: ExecutiveSummaryOutput) -> str:
    """
    Deterministic projection for DOCX binding under the Executive Summary section.
    Preserves specialist content ordering and renders list fields as real bullets.
    """
    parts: List[str] = []
    parts.append(str(getattr(es, "assessment_context", "") or "").strip())
    parts.append(str(getattr(es, "business_overview", "") or "").strip())
    parts.append(str(getattr(es, "security_posture_narrative", "") or "").strip())
    ks = list(getattr(es, "key_strengths", []) or [])
    if ks:
        parts.append("Key strengths:\n" + _bullet(ks))
    pg = list(getattr(es, "priority_gaps", []) or [])
    if pg:
        parts.append("Priority gaps:\n" + _bullet(pg))
    bp = list(getattr(es, "business_priorities", []) or [])
    if bp:
        parts.append("Business priorities:\n" + _bullet(bp))
    blt = str(getattr(es, "board_level_takeaway", "") or "").strip()
    if blt:
        parts.append("Board takeaway: " + blt)
    sd = str(getattr(es, "strategic_direction", "") or "").strip()
    if sd:
        parts.append("Strategic direction: " + sd)
    mdrp = getattr(es, "mdr_positioning", None)
    if mdrp:
        parts.append("MDR positioning: " + str(mdrp))
    evl = str(getattr(es, "evidence_limitations", "") or "").strip()
    if evl:
        parts.append("Evidence limitations: " + evl)
    return "\n\n".join([p for p in parts if p]).strip()


def to_text_attack_scenario(ao: AttackScenarioOutput) -> str:
    """
    Deterministic projection for Simulated Attack Scenario section.
    Avoid object repr; emit only concrete string fields in the correct order.
    """
    fields = [
        "disclaimer",
        "scenario_title",
        "initial_access",
        "progression",
        "business_impact",
        "detection_opportunities",
        "containment_considerations",
        "recovery_considerations",
    ]
    parts: List[str] = []
    for f in fields:
        try:
            v = getattr(ao, f, "") or ""
        except Exception:
            v = ""
        t = str(v).strip()
        if t:
            parts.append(t)
    return "\n\n".join(parts)


def _row_to_dict(r: FrameworkAlignmentRow) -> Dict[str, str]:
    return {
        "standard": str(getattr(r, "framework_name", "") or ""),
        "area": str(getattr(r, "framework_area", "") or ""),
        "expectation": str(getattr(r, "relevant_expectation", "") or ""),
        "current_position": str(getattr(r, "current_position", "") or ""),
        "gap": str(getattr(r, "assurance_gap_or_consideration", "") or ""),
        "fill_plan": str(getattr(r, "recommended_focus", "") or ""),
    }


def to_render_compliance(ca: ComplianceAlignmentOutput) -> Dict[str, Any]:
    """
    Structured context for compliance table loops.
    Keys:
      - current_position: str
      - scope_and_limitations: str
      - priority_actions: List[str]
      - rows: List[{standard, area, expectation, current_position, gap, fill_plan}]
    """
    rows = []
    for r in (getattr(ca, "rows", []) or []):
        try:
            rows.append(_row_to_dict(r))
        except Exception:
            continue
    return {
        "current_position": str(getattr(ca, "current_position", "") or ""),
        "scope_and_limitations": str(getattr(ca, "scope_and_limitations", "") or ""),
        "priority_actions": list(getattr(ca, "priority_actions", []) or []),
        "rows": rows,
    }


def to_render_domain_assessments(items: List[DomainAssessmentOutput]) -> List[Dict[str, Any]]:
    """
    Structured per-domain context aligned to DOCX tables. List item keys:
      - domain_name
      - current_maturity
      - maturity_rationale
      - technical_analysis
      - business_impact_and_risk
      - confirmed_strengths (List[str])
      - confirmed_gaps (List[str])
      - validation_requirements (List[str])
      - zero_cost_quick_wins (List[str])
      - recommended_solutions (List[str])
      - strategic_remediation_rationale
      - partnership_recommendation
    """
    out: List[Dict[str, Any]] = []
    for d in (items or []):
        try:
            out.append(
                {
                    "domain_name": str(getattr(d, "domain_name", "") or ""),
                    "current_maturity": str(getattr(d, "current_maturity", "") or ""),
                    "maturity_rationale": str(getattr(d, "maturity_rationale", "") or ""),
                    "technical_analysis": str(getattr(d, "technical_analysis", "") or ""),
                    "business_impact_and_risk": str(getattr(d, "business_impact_and_risk", "") or ""),
                    "confirmed_strengths": list(getattr(d, "confirmed_strengths", []) or []),
                    "confirmed_gaps": list(getattr(d, "confirmed_gaps", []) or []),
                    "validation_requirements": list(getattr(d, "validation_requirements", []) or []),
                    "zero_cost_quick_wins": list(getattr(d, "zero_cost_quick_wins", []) or []),
                    "recommended_solutions": list(getattr(d, "recommended_solutions", []) or []),
                    "strategic_remediation_rationale": str(getattr(d, "strategic_remediation_rationale", "") or ""),
                    "partnership_recommendation": str(getattr(d, "partnership_recommendation", "") or ""),
                }
            )
        except Exception:
            continue
    return out


def assert_security_rating_consistency(sro: SecurityRatingOutput) -> None:
    """
    Assert that sum of weighted_contribution across domain_scores ~= overall_score within a small tolerance.
    Raise ValueError on mismatch. Used to enforce single-source invariants during export.
    """
    try:
        overall = float(getattr(sro, "overall_score", 0))
    except Exception:
        overall = 0.0
    total = 0.0
    try:
        for ds in (getattr(sro, "domain_scores", []) or []):
            try:
                total += float(getattr(ds, "weighted_contribution", 0))
            except Exception:
                continue
    except Exception:
        total = 0.0
    if abs(total - overall) > 1.01:  # allow small rounding drift
        raise ValueError(
            f"Inconsistent Security Rating: sum(weighted_contribution)={total:.2f} vs overall_score={overall:.2f}"
        )