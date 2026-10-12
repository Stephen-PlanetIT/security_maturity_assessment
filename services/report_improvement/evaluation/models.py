from __future__ import annotations

"""
Evaluation harness models (deterministic; no open dicts).

These models provide a typed container for reasoning-quality metrics. They are
safe to import in any context and do not perform IO or model calls.

Constraints:
- No open dicts (C2)
- All List fields include min_items/max_items (C3)
- British English style (C9)
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class MetricScore(BaseModel):
    """
    Generic metric score with bounded ranges for clarity.
    """
    name: str = Field(description="Metric name, e.g., 'control_recognition'")
    value: float = Field(description="Metric value in [0.0, 1.0]")
    min_value: float = Field(default=0.0, description="Minimum expected value range")
    max_value: float = Field(default=1.0, description="Maximum expected value range")
    notes: Optional[str] = Field(default=None, description="Optional notes about the score")


class EvaluationResult(BaseModel):
    """
    Aggregated evaluation results for a single report build. All booleans reflect
    pass/fail of deterministic checks; floats are normalised scores.
    """
    unsupported_claim_count: int = Field(default=0, description="Number of factual assertions lacking evidence IDs")
    control_recognition_score: float = Field(default=0.0, description="Normalised score for recognising existing controls")
    recommendation_traceability_score: float = Field(default=0.0, description="Score indicating mapping of recommendations to gaps/validation requirements")
    customer_specificity_score: float = Field(default=0.0, description="Score representing customer-specific content presence")
    cross_section_consistency_ok: bool = Field(default=True, description="True if cross-section coherence checks passed")
    commercial_proportionality_ok: bool = Field(default=True, description="True if commercial positioning is proportionate")
    executive_readability_ok: bool = Field(default=True, description="True if executive readability heuristics passed")
    evidence_disclosure_ok: bool = Field(default=True, description="True if evidence limitations are disclosed appropriately")
    editing_distance_proxy: float = Field(default=0.0, description="Proxy for human editing distance (lower is better)")

    metric_details: List[MetricScore] = Field(default_factory=list, min_items=0, max_items=200)
    rule_ids: List[str] = Field(default_factory=list, min_items=0, max_items=200)
    notes: List[str] = Field(default_factory=list, min_items=0, max_items=200)