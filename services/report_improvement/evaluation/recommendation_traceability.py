from __future__ import annotations
"""
Recommendation traceability metric (deterministic; conservative baseline).
Returns 0.0 by default until richer signals are surfaced.
"""

def compute_recommendation_traceability_score(recommendations: list[str] | None, gaps: list[str] | None) -> float:
    try:
        if not recommendations or not gaps:
            return 0.0
        rec = [r.strip().lower() for r in recommendations if r and r.strip()]
        gps = [g.strip().lower() for g in gaps if g and g.strip()]
        if not rec or not gps:
            return 0.0
        matched = 0
        for r in rec:
            if any(r in g for g in gps):
                matched += 1
        return max(0.0, min(1.0, matched / max(1, len(rec))))
    except Exception:
        return 0.0