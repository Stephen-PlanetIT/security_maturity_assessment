from __future__ import annotations
import re


def normalise_text(s: str) -> str:
    """
    Lightweight normalisation for deterministic comparison:
    - Trim whitespace
    - Collapse internal whitespace to single spaces
    - Preserve case by default (callers may .lower() as needed)
    """
    try:
        s = (s or "").strip()
        s = re.sub(r"\s+", " ", s)
        return s
    except Exception:
        return (s or "").strip()