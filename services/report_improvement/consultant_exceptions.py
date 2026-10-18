from __future__ import annotations

"""
Consultant Exception Generator and Sidecar Exporter.

Constructs structured, actionable consultant exceptions when automated repair
is not safe or permissible (contradictions, conditional domain applicability,
commercial decisions, high-impact recommendations).

Provides explicit distinction between:
- blocks_internal_workflow (false for almost all issues, allowing pipeline continuation);
- blocks_final_delivery (true for material contradictions, unresolved applicability, etc.).
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ConsultantExceptionCategory(str, Enum):
    EVIDENCE_CONTRADICTION = "EVIDENCE_CONTRADICTION"
    APPLICABILITY_DECISION = "APPLICABILITY_DECISION"
    BORDERLINE_INTERPRETATION = "BORDERLINE_INTERPRETATION"
    COMMERCIAL_DECISION = "COMMERCIAL_DECISION"
    HIGH_IMPACT_RECOMMENDATION = "HIGH_IMPACT_RECOMMENDATION"
    DELIVERY_APPROVAL = "DELIVERY_APPROVAL"


class ContradictionSourceResolution(BaseModel):
    selected_source: Optional[str] = None
    superseded_source: Optional[str] = None
    precedence_rule: Optional[str] = None
    rationale: Optional[str] = None
    affected_outputs: List[str] = Field(default_factory=list)


class ConsultantException(BaseModel):
    exception_id: str = Field(description="Unique exception tracking ID (e.g. EXC-001)")
    affected_section: str = Field(description="Section where the exception occurred")
    exception_category: ConsultantExceptionCategory
    rule_id: str = Field(description="Governing repair policy rule ID")
    evidence_summary: str = Field(description="Summary of ingested facts and observations")
    conflicting_or_missing_information: str = Field(description="Precise statement of conflict or deficiency")
    current_proposed_wording: str = Field(description="Current report text or ruling under exception")
    available_resolution_options: List[str] = Field(default_factory=list, min_items=1, max_items=10)
    recommended_option: Optional[str] = Field(default=None, description="Recommended course of action if safe")
    business_consequence: str = Field(description="Business or advisory impact if unresolved")
    dependent_sections: List[str] = Field(default_factory=list, description="Other report sections impacted")
    client_or_supplier_confirmation_required: bool = Field(default=False)
    blocks_internal_workflow: bool = Field(default=False, description="Whether this exception stops internal pipeline execution")
    blocks_final_delivery: bool = Field(default=True, description="Whether this exception blocks FINAL_READY publication")
    precedence_resolution: Optional[ContradictionSourceResolution] = None


class ConsultantExceptionReport(BaseModel):
    exceptions: List[ConsultantException] = Field(default_factory=list, min_items=0, max_items=100)
    total_exceptions: int = Field(default=0)
    requires_client_confirmation: bool = Field(default=False)
    has_blocking_delivery_exceptions: bool = Field(default=False)
    has_blocking_workflow_exceptions: bool = Field(default=False)


def build_consultant_exception(
    exception_id: str,
    affected_section: str,
    category: ConsultantExceptionCategory,
    rule_id: str,
    evidence_summary: str,
    conflicting_info: str,
    current_wording: str,
    options: List[str],
    recommended: Optional[str] = None,
    business_consequence: str = "",
    dependent_sections: Optional[List[str]] = None,
    client_confirmation_required: bool = False,
    blocks_internal_workflow: bool = False,
    blocks_final_delivery: bool = True,
    precedence_resolution: Optional[ContradictionSourceResolution] = None,
) -> ConsultantException:
    # Contradictions requiring human confirmation must not pick an ungrounded recommended option
    rec = recommended
    if category == ConsultantExceptionCategory.EVIDENCE_CONTRADICTION and client_confirmation_required and not precedence_resolution:
        rec = "Consultant, client, or supplier confirmation required before selecting interpretation."

    return ConsultantException(
        exception_id=exception_id,
        affected_section=affected_section,
        exception_category=category,
        rule_id=rule_id,
        evidence_summary=evidence_summary,
        conflicting_or_missing_information=conflicting_info,
        current_proposed_wording=current_wording,
        available_resolution_options=options,
        recommended_option=rec,
        business_consequence=business_consequence or "Consultant review required prior to client publication.",
        dependent_sections=dependent_sections or [],
        client_or_supplier_confirmation_required=client_confirmation_required,
        blocks_internal_workflow=blocks_internal_workflow,
        blocks_final_delivery=blocks_final_delivery,
        precedence_resolution=precedence_resolution,
    )


def export_consultant_exceptions_summary(exceptions: List[ConsultantException]) -> Dict[str, Any]:
    """Generates structured report summary dictionary for consultant exceptions."""
    report = ConsultantExceptionReport(
        exceptions=exceptions,
        total_exceptions=len(exceptions),
        requires_client_confirmation=any(e.client_or_supplier_confirmation_required for e in exceptions),
        has_blocking_delivery_exceptions=any(e.blocks_final_delivery for e in exceptions),
        has_blocking_workflow_exceptions=any(e.blocks_internal_workflow for e in exceptions),
    )
    return report.model_dump()
