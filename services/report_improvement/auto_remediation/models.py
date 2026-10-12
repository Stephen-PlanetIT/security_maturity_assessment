from __future__ import annotations
from enum import Enum
from typing import List, Literal
from pydantic import BaseModel, Field
from services.report_improvement.evidence_enforcement.models import (
    SectionValidationResult,
    ReportValidationResult,
)


class RemediationClass(str, Enum):
    DETERMINISTIC_FIX = "deterministic_fix"
    EVIDENCE_GROUNDED_REWRITE = "evidence_grounded_rewrite"
    SAFE_REMOVAL = "safe_removal"
    TEMPLATE_FIX = "template_fix"
    CONSULTANT_DECISION = "consultant_decision"
    NOT_REMEDIABLE = "not_remediable"


class RemediationDisposition(str, Enum):
    REMEDIATED = "remediated"
    PARTIALLY_REMEDIATED = "partially_remediated"
    ESCALATED = "escalated"
    FAILED = "failed"


class RemediationAction(BaseModel):
    action_id: str
    rule_id: str
    section_name: str
    remediation_class: RemediationClass

    offending_text: str
    replacement_text: str | None = None

    evidence_ids: List[str] = Field(default_factory=list, min_items=0, max_items=50)
    control_ids: List[str] = Field(default_factory=list, min_items=0, max_items=50)
    approved_entity_ids: List[str] = Field(default_factory=list, min_items=0, max_items=50)

    deterministic_handler: str | None = None
    requires_model_rewrite: bool = False
    requires_consultant_decision: bool = False

    explanation: str
    confidence: Literal["high", "medium", "low"]


class RemediationPlan(BaseModel):
    section_name: str
    actions: List[RemediationAction] = Field(default_factory=list, min_items=0, max_items=200)
    automatic_actions: List[str] = Field(default_factory=list, min_items=0, max_items=200)
    consultant_decisions: List[str] = Field(default_factory=list, min_items=0, max_items=200)
    original_content_hash: str


class RemediationResult(BaseModel):
    section_name: str
    original_content: str
    remediated_content: str

    actions_attempted: List[RemediationAction] = Field(default_factory=list, min_items=0, max_items=200)
    disposition: RemediationDisposition

    resolved_rule_ids: List[str] = Field(default_factory=list, min_items=0, max_items=200)
    unresolved_rule_ids: List[str] = Field(default_factory=list, min_items=0, max_items=200)

    evidence_ids_used: List[str] = Field(default_factory=list, min_items=0, max_items=200)

    original_content_hash: str
    remediated_content_hash: str

    validation_before: SectionValidationResult
    validation_after: SectionValidationResult | None = None

    consultant_review_required: bool = False
    consultant_questions: List[str] = Field(default_factory=list, min_items=0, max_items=50)


class ReportRemediationResult(BaseModel):
    section_results: List[RemediationResult] = Field(default_factory=list, min_items=0, max_items=200)
    resolved_issue_count: int
    unresolved_issue_count: int
    final_validation: ReportValidationResult
    automatic_publication_allowed: bool
    human_review_required: bool


class EGRevisedSection(BaseModel):
    section_name: str
    revised_content: str
    addressed_rule_ids: List[str] = Field(default_factory=list, min_items=0, max_items=200)
    unresolved_rule_ids: List[str] = Field(default_factory=list, min_items=0, max_items=200)
    evidence_ids_used: List[str] = Field(default_factory=list, min_items=0, max_items=200)
    named_entities_used: List[str] = Field(default_factory=list, min_items=0, max_items=200)
    recommendations_used: List[str] = Field(default_factory=list, min_items=0, max_items=200)


class RevisedDomainAssessment(BaseModel):
    domain_name: str
    current_maturity: str
    maturity_rationale: str
    technical_analysis: str
    business_impact_and_risk: str
    confirmed_strengths: List[str] = Field(default_factory=list, min_items=0, max_items=50)
    confirmed_gaps: List[str] = Field(default_factory=list, min_items=0, max_items=50)
    validation_requirements: List[str] = Field(default_factory=list, min_items=0, max_items=50)
    zero_cost_quick_wins: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    recommended_solutions: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    strategic_rationale: str
    partnership_recommendation: str
    evidence_ids_used: List[str] = Field(default_factory=list, min_items=0, max_items=100)
