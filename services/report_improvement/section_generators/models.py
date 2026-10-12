from __future__ import annotations

"""
Specialist Section Models (strict, no open dicts)

This module defines shared Pydantic models used by specialist section generators.
Constraints:
- No open dict types (C2)
- All List fields include min_items/max_items (C3)
- British English style in any embedded guidance (C9)
"""

from decimal import Decimal
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

# Reuse existing adjudication and enforcement models (single source of truth)
from services.report_improvement.evidence_adjudicator import (  # type: ignore
    EvidenceClaim,
    KnownUnknown,
    CustomerPriority,
)
from services.report_improvement.evidence_enforcement.models import (  # type: ignore
    ExistingControlRecord,
    ApprovedGapRecord,
    ApprovedEntity,
)
from evidence_extraction import TranscriptInsight  # type: ignore


# Section-independent auxiliary models

class BusinessDependency(BaseModel):
    name: str = Field(description="Canonical dependency name (e.g., 'Order Processing', 'FTP Delivery').")
    process_area: str = Field(description="Process area, e.g., 'Finance', 'Operations', 'Customer Services'.")
    dependency_type: Literal[
        "people",
        "process",
        "technology",
        "supplier",
        "data"
    ] = Field(description="Type of dependency (categorical).")


class ApprovedFramework(BaseModel):
    framework_name: str = Field(description="Canonical framework name (e.g., 'ISO 27001', 'Cyber Essentials').")
    applicability_status: Literal[
        "applicable",
        "target",
        "customer_requested",
        "potentially_relevant"
    ] = Field(description="Declared applicability classification.")
    scope_hint: Optional[str] = Field(default=None, description="Optional scope hint (e.g., 'Head Office + UK Schools').")


class ApprovedProductRecommendation(BaseModel):
    vendor: str = Field(description="Approved vendor/product canonical name.")
    rationale: Optional[str] = Field(default=None, description="Short rationale for inclusion.")
    evidence_ids: List[str] = Field(default_factory=list, min_items=0, max_items=20)


class SectionSummaryKV(BaseModel):
    key: str = Field(description="Section identifier (e.g., 'security_rating').")
    value: str = Field(description="Short summary text for the section.")


class CanonicalEnvironment(BaseModel):
    """
    Canonicalised environment summary built deterministically from adjudicated entities and controls.
    The purpose is to present a typed, bounded view for specialist generators without arbitrary dictionaries.
    """
    customers: List[str] = Field(default_factory=list, min_items=0, max_items=5)
    industries: List[str] = Field(default_factory=list, min_items=0, max_items=5)
    locations: List[str] = Field(default_factory=list, min_items=0, max_items=25)
    technologies: List[str] = Field(default_factory=list, min_items=0, max_items=200)
    systems: List[str] = Field(default_factory=list, min_items=0, max_items=100)
    services: List[str] = Field(default_factory=list, min_items=0, max_items=100)
    platforms: List[str] = Field(default_factory=list, min_items=0, max_items=50)
    products: List[str] = Field(default_factory=list, min_items=0, max_items=200)
    crown_jewels: List[str] = Field(default_factory=list, min_items=0, max_items=50)


class SpecialistSectionInput(BaseModel):
    section_name: str
    customer_name: str

    canonical_environment: CanonicalEnvironment

    supported_claims: List[EvidenceClaim] = Field(default_factory=list, min_items=0, max_items=500)
    partially_supported_claims: List[EvidenceClaim] = Field(default_factory=list, min_items=0, max_items=500)
    existing_controls: List[ExistingControlRecord] = Field(default_factory=list, min_items=0, max_items=500)
    confirmed_gaps: List[ApprovedGapRecord] = Field(default_factory=list, min_items=0, max_items=500)
    known_unknowns: List[KnownUnknown] = Field(default_factory=list, min_items=0, max_items=200)
    contradicted_claims: List[EvidenceClaim] = Field(default_factory=list, min_items=0, max_items=500)

    customer_priorities: List[CustomerPriority] = Field(default_factory=list, min_items=0, max_items=50)
    business_dependencies: List[BusinessDependency] = Field(default_factory=list, min_items=0, max_items=100)
    crown_jewels: List[ApprovedEntity] = Field(default_factory=list, min_items=0, max_items=50)
    relevant_transcript_insights: List[TranscriptInsight] = Field(default_factory=list, min_items=0, max_items=200)

    approved_frameworks: List[ApprovedFramework] = Field(default_factory=list, min_items=0, max_items=20)
    approved_recommendations: List["ApprovedRecommendationRecordLite"] = Field(default_factory=list, min_items=0, max_items=200)
    approved_products: List[ApprovedProductRecommendation] = Field(default_factory=list, min_items=0, max_items=200)

    source_section: Optional[str] = None
    preceding_section_summaries: List[SectionSummaryKV] = Field(default_factory=list, min_items=0, max_items=50)

    evidence_quality: Literal["strong", "mixed", "limited"]
    evidence_limitations: List[str] = Field(default_factory=list, min_items=0, max_items=20)


class GeneratedClaim(BaseModel):
    claim_text: str
    claim_type: Literal[
        "fact",
        "customer_statement",
        "consultant_judgement",
        "planning_assumption",
        "recommendation",
        "validation_requirement"
    ]
    evidence_ids: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    confidence: Literal["high", "medium", "low"]


class SectionGenerationMetadata(BaseModel):
    section_name: str
    generated_claims: List[GeneratedClaim] = Field(default_factory=list, min_items=0, max_items=200)
    existing_controls_recognised: List[str] = Field(default_factory=list, min_items=0, max_items=200)
    confirmed_gaps_used: List[str] = Field(default_factory=list, min_items=0, max_items=200)
    known_unknowns_used: List[str] = Field(default_factory=list, min_items=0, max_items=200)
    recommendations_used: List[str] = Field(default_factory=list, min_items=0, max_items=200)
    evidence_limitations_disclosed: List[str] = Field(default_factory=list, min_items=0, max_items=50)


# Security Rating deterministic scoring models (no open dicts)

class ScoreInputItem(BaseModel):
    name: str = Field(description="Named input as configured by scoring policy (e.g., 'coverage', 'assurance_penalty').")
    value: Decimal = Field(description="Decimal value for the input.")


class DomainScoreInput(BaseModel):
    domain_name: str
    configured_weight: Decimal
    evidence_coverage: Decimal

    confirmed_strength_count: int
    confirmed_gap_count: int
    unvalidated_control_count: int
    unknown_count: int

    approved_score_inputs: List[ScoreInputItem] = Field(default_factory=list, min_items=0, max_items=50)
    supporting_claim_ids: List[str] = Field(default_factory=list, min_items=0, max_items=50)
    scoring_policy_version: str


class DomainScoreResult(BaseModel):
    domain_name: str
    weight: Decimal
    indicative_score: Decimal
    weighted_contribution: Decimal
    maturity_band: str

    rationale: str
    rationale_claim_ids: List[str] = Field(default_factory=list, min_items=0, max_items=50)

    assurance_penalty_applied: Decimal = Decimal("0")
    consultant_review_required: bool = False
    consultant_question: Optional[str] = None


class SecurityRatingOutput(BaseModel):
    overall_score: Decimal
    maturity_band: str
    direction_of_travel: str

    primary_strengths: List[str] = Field(default_factory=list, min_items=0, max_items=10)
    primary_gaps: List[str] = Field(default_factory=list, min_items=0, max_items=10)
    board_takeaway: str

    domain_scores: List[DomainScoreResult] = Field(default_factory=list, min_items=1, max_items=100)
    scoring_limitations: str
    metadata: SectionGenerationMetadata


# Simulated Attack Scenario models

class AttackScenarioOutput(BaseModel):
    disclaimer: str
    scenario_title: str

    initial_access: str
    progression: str
    business_impact: str
    detection_opportunities: str
    containment_considerations: str
    recovery_considerations: str

    relevant_mitre_techniques: List[str] = Field(default_factory=list, min_items=0, max_items=8)

    existing_controls_recognised: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    limitations_and_assumptions: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    recommendations_highlighted: List[str] = Field(default_factory=list, min_items=0, max_items=20)

    mdr_opportunity: Optional[str] = None

    metadata: SectionGenerationMetadata


# Compliance and Framework Alignment models

class FrameworkRequirement(BaseModel):
    framework_name: str
    requirement_area: str
    requirement_summary: str
    applicability_status: Literal[
        "applicable",
        "target",
        "customer_requested",
        "potentially_relevant"
    ]
    evidence_ids: List[str] = Field(default_factory=list, min_items=0, max_items=20)


class FrameworkAlignmentRow(BaseModel):
    framework_name: str
    framework_area: str
    relevant_expectation: str
    current_position: str
    assurance_gap_or_consideration: str
    recommended_focus: str
    evidence_ids: List[str] = Field(default_factory=list, min_items=0, max_items=20)


class ComplianceAlignmentOutput(BaseModel):
    current_position: str
    scope_and_limitations: str
    rows: List[FrameworkAlignmentRow] = Field(default_factory=list, min_items=0, max_items=50)
    priority_actions: List[str] = Field(default_factory=list, min_items=0, max_items=10)
    metadata: SectionGenerationMetadata


# Cost of Inaction models (split qualitative/quantified, gated)

class CostDriver(BaseModel):
    driver_name: str
    description: str
    affected_processes: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    evidence_ids: List[str] = Field(default_factory=list, min_items=0, max_items=20)


class FinancialModelInput(BaseModel):
    name: str
    value: Decimal


class ApprovedFinancialModel(BaseModel):
    model_id: str
    model_version: str
    currency: str

    inputs: List[FinancialModelInput] = Field(default_factory=list, min_items=0, max_items=50)
    calculation_method: str
    output_low: Optional[Decimal] = None
    output_high: Optional[Decimal] = None
    output_central: Optional[Decimal] = None

    approved_by: Optional[str] = None
    approval_status: Literal[
        "approved",
        "draft",
        "not_available"
    ]


class CostOfInactionOutput(BaseModel):
    qualitative_narrative: str
    cost_drivers: List[CostDriver] = Field(default_factory=list, min_items=0, max_items=50)

    quantified_narrative: Optional[str] = None
    financial_model_id: Optional[str] = None

    customer_validation_requirements: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    limitations: str

    metadata: SectionGenerationMetadata


# Domain Assessments

class DomainEvidence(BaseModel):
    domain_name: str

    supported_controls: List[ExistingControlRecord] = Field(default_factory=list, min_items=0, max_items=100)
    confirmed_strengths: List[EvidenceClaim] = Field(default_factory=list, min_items=0, max_items=100)
    confirmed_gaps: List[ApprovedGapRecord] = Field(default_factory=list, min_items=0, max_items=100)
    known_unknowns: List[KnownUnknown] = Field(default_factory=list, min_items=0, max_items=100)
    contradicted_claims: List[EvidenceClaim] = Field(default_factory=list, min_items=0, max_items=100)

    relevant_business_dependencies: List[BusinessDependency] = Field(default_factory=list, min_items=0, max_items=50)
    relevant_crown_jewels: List[ApprovedEntity] = Field(default_factory=list, min_items=0, max_items=50)
    relevant_customer_priorities: List[CustomerPriority] = Field(default_factory=list, min_items=0, max_items=50)
    relevant_transcript_insights: List[TranscriptInsight] = Field(default_factory=list, min_items=0, max_items=100)

    approved_recommendations: List["ApprovedRecommendationRecordLite"] = Field(default_factory=list, min_items=0, max_items=200)
    approved_products: List[ApprovedProductRecommendation] = Field(default_factory=list, min_items=0, max_items=200)

    maturity_score: Optional[DomainScoreResult] = None
    evidence_quality: Literal["strong", "mixed", "limited"]


class DomainAssessmentOutput(BaseModel):
    domain_name: str

    current_maturity: str
    maturity_rationale: str

    technical_analysis: str
    business_impact_and_risk: str

    confirmed_strengths: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    confirmed_gaps: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    validation_requirements: List[str] = Field(default_factory=list, min_items=0, max_items=20)

    zero_cost_quick_wins: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    recommended_solutions: List[str] = Field(default_factory=list, min_items=0, max_items=20)

    strategic_remediation_rationale: str
    partnership_recommendation: str

    metadata: SectionGenerationMetadata


# Cross-section coherence

class CrossSectionNarrativeMap(BaseModel):
    customer_profile_summary: str
    primary_strengths: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    primary_gaps: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    critical_findings: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    approved_recommendations: List[str] = Field(default_factory=list, min_items=0, max_items=50)
    roadmap_priorities: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    approved_frameworks: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    cost_drivers: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    scenario_priorities: List[str] = Field(default_factory=list, min_items=0, max_items=20)


# Exemplar model

class SectionExemplar(BaseModel):
    exemplar_id: str
    section_type: str
    industry_tags: List[str] = Field(default_factory=list, min_items=0, max_items=10)
    technology_tags: List[str] = Field(default_factory=list, min_items=0, max_items=10)
    maturity_tags: List[str] = Field(default_factory=list, min_items=0, max_items=10)

    input_evidence_summary: str
    output_example: str
    quality_annotations: List[str] = Field(default_factory=list, min_items=0, max_items=20)


# Lite record for approved recommendations (avoid circular import from enforcement.models)
class ApprovedRecommendationRecordLite(BaseModel):
    recommendation_id: str
    domain: str
    recommendation_type: Literal[
        "validate",
        "review",
        "optimise",
        "configure",
        "test",
        "document",
        "implement",
        "replace",
        "retire",
        "procure",
        "monitor"
    ]
    target_control: str
    approved_products: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    approved_vendors: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    replacement_justification_required: bool = Field(default=False)
    evidence_references: List[str] = Field(default_factory=list, min_items=0, max_items=50)


# Executive Summary (specialist output)

class ExecutiveSummaryOutput(BaseModel):
    assessment_context: str
    business_overview: str
    security_posture_narrative: str

    key_strengths: List[str] = Field(default_factory=list, min_items=0, max_items=6)
    priority_gaps: List[str] = Field(default_factory=list, min_items=0, max_items=5)
    business_priorities: List[str] = Field(default_factory=list, min_items=0, max_items=5)

    board_level_takeaway: str
    strategic_direction: str

    mdr_positioning: Optional[str] = None

    evidence_limitations: str
    metadata: SectionGenerationMetadata
