from __future__ import annotations
"""
Customer specificity metric (deterministic; conservative baseline).
Detects presence of concrete business dependencies/services references.
"""

def compute_customer_specificity_score(text_blocks: list[str] | None) -> float:
    try:
        if not text_blocks:
            return 0.0
        tokens = 0
        hits = 0
        for t in text_blocks:
            s = (t or "").strip()
            if not s:
                continue
            tokens += 1
            # Conservative: look for common business nouns and proper noun tokens
            if any(k in s.lower() for k in ("service", "customer", "production", "delivery", "finance", "warehouse", "clinic", "store")):
                hits += 1
        if tokens == 0:
            return 0.0
        return max(0.0, min(1.0, hits / tokens))
    except Exception:
        return 0.0