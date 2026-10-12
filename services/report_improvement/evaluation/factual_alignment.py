from __future__ import annotations

"""
Factual alignment metric (deterministic; conservative baseline).

This module provides a placeholder implementation that can be safely invoked
without external context. It does not perform IO or model calls and returns a
conservative default until richer metrics are implemented.

Function:
- compute_unsupported_claim_count(...) -> int
"""

from typing import List
from services.report_improvement.section_generators.models import GeneratedClaim  # type: ignore


def compute_unsupported_claim_count(claims: List[GeneratedClaim] | None) -> int:
    """
    Count claims lacking any evidence_ids. Conservative baseline:
    - A claim with an empty or missing evidence_ids list is considered unsupported.
    - Returns 0 if claims list is None (avoid false positives).
    """
    if not claims:
        return 0
    unsupported = 0
    for c in claims:
        try:
            if not c.evidence_ids or len(c.evidence_ids) == 0:
                unsupported += 1
        except Exception:
            # Defensive: do not raise metrics exceptions
            continue
    return unsupported