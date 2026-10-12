from __future__ import annotations
from typing import List, Set
from pydantic import BaseModel, Field

class ReportImprovementRules(BaseModel):
    # Toggle-like rules encoded as a set of string flags for simplicity
    enabled: Set[str] = Field(default_factory=set, description="Enabled global rule flags.")
    # Default policy: strict, conservative changes only
    strict_mode: bool = Field(default=True, description="If true, prefer minimal, evidence-backed edits.")
    validate_before_replace: bool = Field(default=True, description="If true, attempt validation before replacing content.")
    prefer_business_impact: bool = Field(default=True, description="Prefer business impact framing over technical detail.")

    @staticmethod
    def default() -> "ReportImprovementRules":
        flags = {
            "NO_UNSUPPORTED_CLAIMS",
            "NO_GENERIC_FINDINGS",
            "NO_GENERIC_RECOMMENDATIONS",
            "NO_GENERIC_EXECUTIVE_LANGUAGE",
            "TRANSCRIPT_EVIDENCE_PRIORITY",
            "VALIDATE_BEFORE_REPLACE",
            "PREFER_BUSINESS_IMPACT",
            "RECOGNISE_EXISTING_CONTROLS",
            "NO_TECHNOLOGY_REPLACEMENT_WITHOUT_JUSTIFICATION",
            "PLANET_ALIGNMENT_WHERE_APPROPRIATE",
            "NO_VENDOR_BIAS",
            "CONSULTATIVE_LANGUAGE",
            "NO_SALES_LANGUAGE",
            "NO_COMPLIANCE_OVERSTATEMENT",
            "NO_MOVIE_PLOT_ATTACK_SCENARIOS",
        }
        return ReportImprovementRules(
            enabled=flags,
            strict_mode=True,
            validate_before_replace=True,
            prefer_business_impact=True,
        )

class ReviewerChange(BaseModel):
    section: str = Field(description="Section identifier.")
    before: str = Field(description="Original text/content (scalar).")
    after: str = Field(description="Improved text/content (scalar).")
    rationale: str = Field(description="Why the change was applied (rules/evidence).")
    rule_refs: List[str] = Field(
        default_factory=list, min_items=0, max_items=10, description="References to applied rules."
    )