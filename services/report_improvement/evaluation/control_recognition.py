from __future__ import annotations

"""
Control recognition metric (deterministic; conservative baseline).

This module provides a placeholder implementation that can be safely invoked
without external context. It does not perform IO or model calls and returns a
conservative default until richer metrics are implemented.

Function:
- compute_control_recognition_score(...) -> float in [0.0, 1.0]
"""

from typing import List


def compute_control_recognition_score(
    exec_strengths: List[str] | None,
    sr_strengths: List[str] | None,
    da_strengths_by_domain: List[List[str]] | None,
) -> float:
    """
    A conservative baseline that estimates recognition consistency across sections:
    - If no inputs provided, return 0.0 (avoid false positives).
    - Score is the average fraction of recognised strengths across provided lists.
    - Inputs are normalised to lower-case tokens for approximate matching.
    """
    try:
        def _norm(xs: List[str] | None) -> List[str]:
            return [str(x).strip().lower() for x in (xs or []) if str(x).strip()]

        es = set(_norm(exec_strengths))
        sr = set(_norm(sr_strengths))
        doms = [set(_norm(s)) for s in (da_strengths_by_domain or []) if s]

        # If nothing to compare, return 0.0
        if not es and not sr and not doms:
            return 0.0

        parts = []
        if es and sr:
            inter = es.intersection(sr)
            parts.append(len(inter) / max(1, len(es)))
        if es and doms:
            # Measure recognition across domains (mean of per-domain overlaps)
            fracs = []
            for ds in doms:
                inter = es.intersection(ds)
                fracs.append(len(inter) / max(1, len(es)))
            if fracs:
                parts.append(sum(fracs) / len(fracs))
        if sr and doms:
            fracs = []
            for ds in doms:
                inter = sr.intersection(ds)
                fracs.append(len(inter) / max(1, len(sr)))
            if fracs:
                parts.append(sum(fracs) / len(fracs))

        if not parts:
            return 0.0
        # Clamp to [0.0, 1.0]
        val = sum(parts) / len(parts)
        return max(0.0, min(1.0, float(val)))
    except Exception:
        return 0.0