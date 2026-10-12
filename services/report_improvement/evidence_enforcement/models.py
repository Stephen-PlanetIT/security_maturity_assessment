from __future__ import annotations
from enum import Enum
from typing import Any, Literal, Tuple, Dict, List
from pydantic import BaseModel, Field


class ValidationStatus(str, Enum):
    PASS = "pass"
    WARNING = "warning"
    BLOCK = "block"
    HUMAN_REVIEW = "human_review"


class ValidationSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EvidenceReference(BaseModel):
    evidence_id: str = Field(description="Stable identifier for the evidence item.")
    source_type: Literal[
        "transcript",
        "summary",
        "assessment",
        "environment",
        "customer_document",
        "approved_catalogue",
        "approved_calculation"
    ]
    source_locator: str | None = Field(default=None, description="Optional pointer (e.g. line index, paragraph id).")
    excerpt: str | None = Field(default=None, description="Optional short excerpt for human review.")


class ApprovedEntity(BaseModel):
    canonical_name: str = Field(description="Normalised, canonical entity name.")
    entity_type: Literal[
        "customer",
        "technology",
        "product",
        "vendor",
        "supplier",
        "platform",
        "system",
        "service",
        "location",
        "framework",
        "crown_jewel",
        "data_type",
        "business_process"
    ]
    aliases: List[str] = Field(default_factory=list, min_items=0, max_items=50)
    evidence_references: List[EvidenceReference] = Field(default_factory=list, min_items=0, max_items=50)


class ExistingControlRecord(BaseModel):
    control_id: str = Field(description="Stable ID for the control record.")
    canonical_name: str = Field(description="Canonical control name (e.g., 'Sophos MDR').")
    category: str = Field(description="Control category (e.g., 'monitoring', 'backup').")
    implementation_status: Literal[
        "implemented",
        "partially_implemented",
        "planned",
        "unvalidated",
        "unknown",
        "not_present"
    ]
    effectiveness_status: Literal[
        "effective",
        "partially_effective",
        "unvalidated",
        "unknown",
        "ineffective"
    ]
    products: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    evidence_references: List[EvidenceReference] = Field(default_factory=list, min_items=0, max_items=50)


class ApprovedGapRecord(BaseModel):
    gap_id: str = Field(description="Stable ID for the approved gap.")
    domain: str = Field(description="Domain area for the gap (e.g., 'backup', 'identity').")
    statement: str = Field(description="Approved gap statement (verbatim or normalised).")
    status: Literal[
        "confirmed",
        "partially_supported",
        "unvalidated",
        "unknown",
        "contradicted"
    ]
    permitted_language: List[str] = Field(default_factory=list, min_items=0, max_items=50)
    prohibited_language: List[str] = Field(default_factory=list, min_items=0, max_items=50)
    evidence_references: List[EvidenceReference] = Field(default_factory=list, min_items=0, max_items=50)


class ApprovedRecommendationRecord(BaseModel):
    recommendation_id: str = Field(description="Stable ID for the recommendation.")
    domain: str = Field(description="Domain area this recommendation targets.")
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
    target_control: str = Field(description="The control or capability the recommendation applies to.")
    approved_products: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    approved_vendors: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    replacement_justification_required: bool = Field(default=False, description="If true, 'replace' requires explicit justification.")
    evidence_references: List[EvidenceReference] = Field(default_factory=list, min_items=0, max_items=50)


class FinancialEvidenceProfile(BaseModel):
    quantified_financial_output_allowed: bool = Field(default=False, description="Permit specific financial outputs.")
    approved_currency: str = Field(default="GBP", description="Default allowed currency (use ISO code or symbol).")
    approved_values: List[float] = Field(default_factory=list, min_items=0, max_items=50)
    approved_ranges: List[Tuple[float, float]] = Field(default_factory=list, min_items=0, max_items=20)
    approved_calculation_ids: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    available_inputs: Dict[str, float] = Field(default_factory=dict)
    planning_assumptions_only: bool = Field(default=True, description="If true, block quantified costs.")


class ApprovedScenarioProfile(BaseModel):
    approved_initial_access_routes: List[str] = Field(default_factory=list, min_items=0, max_items=50)
    approved_technologies: List[str] = Field(default_factory=list, min_items=0, max_items=100)
    approved_systems: List[str] = Field(default_factory=list, min_items=0, max_items=100)
    approved_crown_jewels: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    approved_control_gaps: List[str] = Field(default_factory=list, min_items=0, max_items=50)
    approved_mitre_techniques: List[str] = Field(default_factory=list, min_items=0, max_items=100)

    allow_specific_cves: bool = Field(default=False)
    approved_cves: List[str] = Field(default_factory=list, min_items=0, max_items=50)

    allow_named_threat_actors: bool = Field(default=False)
    approved_threat_actors: List[str] = Field(default_factory=list, min_items=0, max_items=50)

    allow_named_attack_tools: bool = Field(default=False)
    approved_attack_tools: List[str] = Field(default_factory=list, min_items=0, max_items=50)

    allow_insider_threat: bool = Field(default=False)
    allow_nation_state_scenario: bool = Field(default=False)

    approved_detection_capabilities: List[str] = Field(default_factory=list, min_items=0, max_items=50)
    approved_response_capabilities: List[str] = Field(default_factory=list, min_items=0, max_items=50)


class MaturityScoreRecord(BaseModel):
    domain: str = Field(description="Domain name.")
    weight: float = Field(description="Weight as a 0-1 fraction.")
    score: float = Field(description="Score e.g., 1-3 mapped/normalised as needed.")
    weighted_contribution: float = Field(description="Computed contribution.")
    rationale_claim_ids: List[str] = Field(default_factory=list, min_items=0, max_items=20)


class ValidationIssue(BaseModel):
    rule_id: str
    status: ValidationStatus
    severity: ValidationSeverity
    section_name: str
    paragraph_index: int | None = None
    table_index: int | None = None
    cell_reference: str | None = None

    offending_text: str
    explanation: str

    related_evidence_ids: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    related_control_ids: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    related_gap_ids: List[str] = Field(default_factory=list, min_items=0, max_items=20)

    required_action: Literal[
        "none",
        "rewrite",
        "remove",
        "replace_with_validation_language",
        "retain_original",
        "request_human_review",
        "prevent_publication"
    ]
    suggested_safe_wording: str | None = None


class SectionValidationResult(BaseModel):
    section_name: str
    status: ValidationStatus
    issues: List[ValidationIssue] = Field(default_factory=list, min_items=0, max_items=200)
    passed_rule_ids: List[str] = Field(default_factory=list, min_items=0, max_items=200)
    retry_permitted: bool = True
    retry_count: int = 0
    maximum_retries: int = 2
    human_review_required: bool = False
    automatic_publication_allowed: bool = False
    used_original_content: bool = False

    @property
    def has_blocking_errors(self) -> bool:
        return any(
            issue.status in {
                ValidationStatus.BLOCK,
                ValidationStatus.HUMAN_REVIEW
            }
            for issue in self.issues
        )


class ReportValidationResult(BaseModel):
    status: ValidationStatus
    section_results: List[SectionValidationResult]
    cross_section_issues: List[ValidationIssue] = Field(default_factory=list, min_items=0, max_items=200)
    publication_issues: List[ValidationIssue] = Field(default_factory=list, min_items=0, max_items=200)
    automatic_publication_allowed: bool = False
    human_review_required: bool = True


class EvidenceEnforcementContext(BaseModel):
    approved_entities: List[ApprovedEntity] = Field(default_factory=list, min_items=0, max_items=2000)
    existing_controls: List[ExistingControlRecord] = Field(default_factory=list, min_items=0, max_items=500)
    approved_gaps: List[ApprovedGapRecord] = Field(default_factory=list, min_items=0, max_items=500)
    approved_recommendations: List[ApprovedRecommendationRecord] = Field(default_factory=list, min_items=0, max_items=500)
    financial_profile: FinancialEvidenceProfile = Field(default_factory=FinancialEvidenceProfile)
    scenario_profile: ApprovedScenarioProfile = Field(default_factory=ApprovedScenarioProfile)