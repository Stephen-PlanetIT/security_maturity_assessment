from __future__ import annotations

"""
Canonical Evidence Models for Cybersecurity Maturity Assessment (Phase 2).

Defines the core data structures for evidence classification, assurance states,
evidence scopes, deterministic normalisation, and domain evidence packaging.

Constraints:
- No open dict types (C2)
- All List fields include min_items/max_items (C3)
- British English style (C9)
"""

from enum import Enum
from typing import List, Literal, Optional, Any
from pydantic import BaseModel, Field


class AssuranceState(str, Enum):
    """Authoritative assurance classification for an evidence claim or control."""
    VERIFIED_PRESENT = "VERIFIED_PRESENT"
    REPORTED_PRESENT = "REPORTED_PRESENT"
    REPORTED_ABSENT = "REPORTED_ABSENT"
    VERIFIED_ABSENT = "VERIFIED_ABSENT"
    UNKNOWN = "UNKNOWN"
    NOT_ESTABLISHED_DURING_CONSULTATION = "NOT_ESTABLISHED_DURING_CONSULTATION"
    REQUIRES_SUPPLIER_CONFIRMATION = "REQUIRES_SUPPLIER_CONFIRMATION"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    CONTRADICTED = "CONTRADICTED"
    UNRELIABLE = "UNRELIABLE"


class EvidenceScope(str, Enum):
    """Scope defining how and where evidence may be consumed."""
    ORGANISATIONAL_CONTEXT = "ORGANISATIONAL_CONTEXT"
    CROSS_DOMAIN_CONTEXT = "CROSS_DOMAIN_CONTEXT"
    DOMAIN_SPECIFIC_CONTROL = "DOMAIN_SPECIFIC_CONTROL"
    DOMAIN_SPECIFIC_GAP = "DOMAIN_SPECIFIC_GAP"
    COMPLIANCE_TARGET = "COMPLIANCE_TARGET"
    BUSINESS_IMPACT = "BUSINESS_IMPACT"
    CRITICAL_ASSET = "CRITICAL_ASSET"
    TECHNOLOGY_INVENTORY = "TECHNOLOGY_INVENTORY"
    CONSULTANT_JUDGEMENT = "CONSULTANT_JUDGEMENT"


class ScoringRole(str, Enum):
    """Explicit scoring role determining whether and how evidence can influence maturity."""
    POSITIVE_CONTROL = "POSITIVE_CONTROL"
    NEGATIVE_GAP = "NEGATIVE_GAP"
    COVERAGE_LIMITATION = "COVERAGE_LIMITATION"
    VALIDATION_ONLY = "VALIDATION_ONLY"
    APPLICABILITY_ONLY = "APPLICABILITY_ONLY"
    BUSINESS_IMPACT_ONLY = "BUSINESS_IMPACT_ONLY"
    INVENTORY_ONLY = "INVENTORY_ONLY"
    COMPLIANCE_TARGET_ONLY = "COMPLIANCE_TARGET_ONLY"
    NON_SCORING_CONTEXT = "NON_SCORING_CONTEXT"


class EvidenceRecord(BaseModel):
    """Typed canonical evidence record with explicit assurance state, scope, and scoring role."""
    evidence_id: str = Field(description="Unique stable identifier for the evidence record.")
    canonical_topic: str = Field(description="Canonical topic or control name (e.g. 'mfa_enforcement', 'patch_management').")
    assurance_state: AssuranceState = Field(description="Adjudicated assurance state.")
    evidence_scope: EvidenceScope = Field(description="Classification scope.")
    scoring_role: ScoringRole = Field(
        default=ScoringRole.NON_SCORING_CONTEXT,
        description="Explicit scoring role defining maturity contribution."
    )
    parent_evidence_id: Optional[str] = Field(default=None, description="Parent source ID if derived via compound decomposition.")
    transformation_rule_id: Optional[str] = Field(default=None, description="Rule ID used to decompose or transform this evidence.")
    target_dimension: Optional[str] = Field(default=None, description="Target domain assessment dimension satisfied by this record.")
    raw_statement: str = Field(description="Verbatim or original statement from source.")
    normalised_statement: str = Field(description="Normalised statement in British English.")
    source_type: Literal[
        "consultant_approved",
        "transcript",
        "meeting_summary",
        "customer_profile",
        "environment",
        "supplier_documentation",
        "baseline_normalised",
        "unspecified"
    ] = Field(description="Originating source type.")
    source_locator: Optional[str] = Field(default=None, description="Pointer to source paragraph, line or timestamp.")
    applicable_domains: List[str] = Field(default_factory=list, min_items=0, max_items=50, description="Explicit domains this evidence relates to.")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence rating between 0.0 and 1.0.")
    supplier_owned: bool = Field(default=False, description="Whether this capability is managed/owned by a third-party supplier.")
    supplier_name: Optional[str] = Field(default=None, description="Name of third-party supplier if supplier_owned.")
    notes: Optional[str] = Field(default=None, description="Consultant or normalisation notes.")


class EvidenceCoverageResult(str, Enum):
    """Coverage determination for a specific domain assessment."""
    SUFFICIENT = "SUFFICIENT"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"
    CONTRADICTED = "CONTRADICTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class DomainScoreEligibilityDecision(BaseModel):
    """Authoritative, immutable decision model defining score eligibility for a domain."""
    domain_key: str
    eligible_for_score: bool
    coverage_result: EvidenceCoverageResult
    evidenced_dimensions: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    missing_required_dimensions: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    contradicted_dimensions: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    contributing_evidence_ids: List[str] = Field(default_factory=list, min_items=0, max_items=50)
    contributing_parent_evidence_ids: List[str] = Field(default_factory=list, min_items=0, max_items=50)
    contributing_source_types: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    distinct_parent_sources_count: int = 0
    confidence: float = 1.0
    decision_reasons: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    score_withheld_reason: Optional[str] = None


class DomainEvidencePackage(BaseModel):
    """Complete, segregated evidence package allocated to a single domain."""
    domain_key: str = Field(description="Canonical domain identifier (e.g. 'identity_access').")
    domain_display_name: str = Field(description="Human-readable domain name (e.g. 'Identity & Access Management').")
    coverage_result: EvidenceCoverageResult = Field(description="Calculated coverage status.")
    eligible_for_score: bool = Field(description="Whether the domain has sufficient verified/reported evidence to be scored.")
    eligibility_decision: Optional[DomainScoreEligibilityDecision] = Field(
        default=None,
        description="Authoritative score eligibility decision."
    )
    applicability_status: Literal["APPLICABLE", "CONDITIONALLY_APPLICABLE", "NOT_APPLICABLE", "UNDETERMINED"] = Field(
        default="APPLICABLE",
        description="Domain applicability determination."
    )
    domain_specific_controls: List[EvidenceRecord] = Field(default_factory=list, min_items=0, max_items=100)
    domain_specific_gaps: List[EvidenceRecord] = Field(default_factory=list, min_items=0, max_items=100)
    unknowns_and_unvalidated: List[EvidenceRecord] = Field(default_factory=list, min_items=0, max_items=100)
    supplier_dependencies: List[EvidenceRecord] = Field(default_factory=list, min_items=0, max_items=100)
    organisational_context: List[EvidenceRecord] = Field(default_factory=list, min_items=0, max_items=100)
    compliance_targets: List[EvidenceRecord] = Field(default_factory=list, min_items=0, max_items=50)
    business_impacts: List[EvidenceRecord] = Field(default_factory=list, min_items=0, max_items=50)
    scoring_notes: List[str] = Field(default_factory=list, min_items=0, max_items=20)
