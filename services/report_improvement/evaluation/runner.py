from __future__ import annotations

"""
Evaluation harness runner (deterministic; non-blocking by default).

This module computes a conservative EvaluationResult from already generated
report content and adjudicated evidence context. It is designed to be safe:
- No model calls
- No IO
- No transcript logging
- Returns defaults when inputs are insufficient

Future expansions will compute richer metrics; for now we return a baseline
result suitable for logging and dashboards.
"""

from typing import Any, Dict

from services.report_improvement.evaluation.models import EvaluationResult  # type: ignore


def run_evaluation(final_report: Dict[str, Any], adjudication: Any, ctx: Any) -> EvaluationResult:
    """
    Compute a conservative EvaluationResult. Adds baseline control recognition using a
    deterministic cross-section map; remains non-blocking and logs aggregates only.
    """
    try:
        # Build a cross-section map to extract strengths deterministically
        try:
            from services.report_improvement.section_generators.cross_section_context import build_cross_section_map_from_report  # type: ignore
            cs = build_cross_section_map_from_report(final_report or {})
            exec_strengths = list(getattr(cs, "primary_strengths", []) or [])
            # SR strengths may be represented in the same list depending on builder; safe to reuse
            sr_strengths = list(getattr(cs, "primary_strengths", []) or [])
            da_strengths: list[list[str]] = []  # placeholder until structured DA strengths are surfaced
        except Exception:
            exec_strengths, sr_strengths, da_strengths = [], [], []

        # Control recognition baseline
        try:
            from services.report_improvement.evaluation.control_recognition import compute_control_recognition_score  # type: ignore
            ctrl_score = float(compute_control_recognition_score(exec_strengths, sr_strengths, da_strengths))
        except Exception:
            ctrl_score = 0.0

        ev = EvaluationResult(
            unsupported_claim_count=0,
            control_recognition_score=ctrl_score,
            recommendation_traceability_score=0.0,
            customer_specificity_score=0.0,
            cross_section_consistency_ok=True,
            commercial_proportionality_ok=True,
            executive_readability_ok=True,
            evidence_disclosure_ok=True,
            editing_distance_proxy=0.0,
            metric_details=[],
            rule_ids=[],
            notes=[],
        )
        return ev
    except Exception:
        # Defensive default
        return EvaluationResult()
