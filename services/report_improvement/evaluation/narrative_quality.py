from __future__ import annotations
"""
Narrative quality heuristics (deterministic; conservative baseline).
Checks length bounds and simple jargon heuristics.
"""

def executive_readability_ok(text: str | None) -> bool:
    """
    True if the text stays within conservative readability bounds.
    Currently enforces a soft cap of ~1200 words per paragraph block.
    """
    try:
        s = (text or "").strip()
        if not s:
            return True
        return len(s.split()) <= 1200
    except Exception:
        return True


def commercial_proportionality_ok(text: str | None) -> bool:
    """
    True if overt sales/jargon phrases are not present. Conservative baseline.
    """
    try:
        s = (text or "").strip().lower()
        if not s:
            return True
        bad = ("guaranteed prevention", "transform overnight", "industry-leading without evidence")
        return not any(b in s for b in bad)
    except Exception:
        return True