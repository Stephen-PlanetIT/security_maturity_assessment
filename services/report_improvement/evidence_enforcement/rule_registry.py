from __future__ import annotations
from typing import List
from .models import ApprovedEntity


def canonicalise_entity_name(name: str) -> str:
    """
    Lowercase, trimmed canonical form for entity comparisons.
    """
    try:
        return (name or "").strip().lower()
    except Exception:
        return ""


def alias_match(name: str, entity: ApprovedEntity) -> bool:
    """
    True if name matches the entity's canonical name or any alias (canonical form).
    """
    n = canonicalise_entity_name(name)
    if n == canonicalise_entity_name(entity.canonical_name):
        return True
    try:
        return any(canonicalise_entity_name(a) == n for a in (entity.aliases or []))
    except Exception:
        return False