from __future__ import annotations
"""
Contradiction check (deterministic; conservative baseline).
Detects if any token appears in both strengths and gaps.
"""

def has_strength_gap_contradiction(strengths: list[str] | None, gaps: list[str] | None) -> bool:
    try:
        s = { (x or '').strip().lower() for x in (strengths or []) if (x or '').strip() }
        g = { (x or '').strip().lower() for x in (gaps or []) if (x or '').strip() }
        return bool(s.intersection(g))
    except Exception:
        return False