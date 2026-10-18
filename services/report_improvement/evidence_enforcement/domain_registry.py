from __future__ import annotations

"""
Central Domain-Evidence Allocation Registry & Assessment Dimension Model (Phase 2.1).

Manages the allocation of canonical evidence records to specific domains,
guaranteeing:
1. Global context is separated from domain-specific controls/gaps.
2. Evidence is mapped only to explicitly related domains.
3. Explicit scoring roles enforce that inventory, asset lists, impact, and compliance targets
   never satisfy control presence or create positive maturity scores.
4. Domain Assessment Dimension Model:
   - Configures required and optional dimensions per domain (governance, control presence, coverage, configuration, operation, monitoring, testing).
   - Domain is eligible for scoring ONLY if its minimum required assessment dimensions are satisfied.
   - Raw counts or a single reported product cannot establish score eligibility or a 3.0 score.
"""

from typing import Dict, List, Optional, Set
from pydantic import BaseModel, Field

from services.report_improvement.evidence_enforcement.canonical_models import (
    AssuranceState,
    EvidenceScope,
    ScoringRole,
    EvidenceRecord,
    EvidenceCoverageResult,
    DomainEvidencePackage,
    DomainScoreEligibilityDecision,
)

# Standard 15 domains recognized in the maturity pipeline
ALL_MATURITY_DOMAINS = [
    ("identity_access", "Identity & Access Management"),
    ("endpoint_security", "Endpoint Security"),
    ("network_edge", "Network & Edge Security"),
    ("cloud_security", "Cloud Security"),
    ("email_security", "Email & Collaboration"),
    ("recovery_assurance", "Backup & Recovery Assurance"),
    ("monitoring_detection", "Monitoring & Threat Detection"),
    ("incident_response", "Incident Response & Preparedness"),
    ("supplier_assurance", "Supply Chain & Third-Party Assurance"),
    ("saas_governance", "SaaS Security & Shadow IT"),
    ("information_protection", "Information Protection & Data Governance"),
    ("application_security", "Application Security & SDLC"),
    ("ai_governance", "AI Governance & Acceptable Use"),
    ("security_testing", "Vulnerability Management & Security Testing"),
    ("asset_assurance", "Asset Management & Assurance"),
]


class DomainDimensionPolicy(BaseModel):
    """Assessment dimensions required to consider a domain score-eligible."""
    domain_key: str
    required_dimensions: List[str] = Field(default_factory=list, min_items=1, max_items=10)
    optional_dimensions: List[str] = Field(default_factory=list, min_items=0, max_items=10)
    min_dimensions_count: int = 2


# Standard assessment dimension policies across domains
# A domain requires at least 2 distinct evidenced dimensions (e.g. control_presence AND (coverage or configuration or operation or monitoring))
DOMAIN_DIMENSION_POLICIES: Dict[str, DomainDimensionPolicy] = {
    d_key: DomainDimensionPolicy(
        domain_key=d_key,
        required_dimensions=["control_presence"],
        optional_dimensions=["coverage", "configuration", "operation", "monitoring", "testing", "governance"],
        min_dimensions_count=2,
    )
    for d_key, _ in ALL_MATURITY_DOMAINS
}
# Incident Response requires governance (formal plan) + testing/operation
DOMAIN_DIMENSION_POLICIES["incident_response"] = DomainDimensionPolicy(
    domain_key="incident_response",
    required_dimensions=["governance"],
    optional_dimensions=["operation", "testing", "monitoring"],
    min_dimensions_count=2,
)
# Monitoring requires monitoring + operation
DOMAIN_DIMENSION_POLICIES["monitoring_detection"] = DomainDimensionPolicy(
    domain_key="monitoring_detection",
    required_dimensions=["monitoring"],
    optional_dimensions=["operation", "testing", "governance"],
    min_dimensions_count=2,
)


class ReuseTrackingRecord(BaseModel):
    """Tracks reuse of an evidence record across multiple domains."""
    evidence_id: str
    assigned_domains: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    reasons: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    is_suspicious_broadcast: bool = False


class DomainAllocationRegistry:
    """Central registry for allocating canonical evidence to domains."""

    def __init__(self):
        self._evidence_pool: Dict[str, EvidenceRecord] = {}
        self._domain_assignments: Dict[str, List[str]] = {k: [] for k, _ in ALL_MATURITY_DOMAINS}
        self._reuse_tracking: Dict[str, ReuseTrackingRecord] = {}

    def register_evidence(self, record: EvidenceRecord) -> None:
        """Register an evidence record in the central pool."""
        self._evidence_pool[record.evidence_id] = record
        self._reuse_tracking[record.evidence_id] = ReuseTrackingRecord(evidence_id=record.evidence_id)

    def allocate_to_domain(self, evidence_id: str, domain_key: str, reason: str) -> None:
        """Explicitly allocate an evidence record to a domain with justification."""
        if evidence_id not in self._evidence_pool:
            raise KeyError(f"Evidence ID {evidence_id} not registered.")
        if domain_key not in self._domain_assignments:
            self._domain_assignments[domain_key] = []

        if evidence_id not in self._domain_assignments[domain_key]:
            self._domain_assignments[domain_key].append(evidence_id)

        # Update reuse tracking
        rt = self._reuse_tracking[evidence_id]
        if domain_key not in rt.assigned_domains:
            rt.assigned_domains.append(domain_key)
            rt.reasons.append(reason)
            # Flag suspicious broadcast if assigned to >4 domains without global context scope
            rec = self._evidence_pool[evidence_id]
            if len(rt.assigned_domains) > 4 and rec.evidence_scope not in (
                EvidenceScope.ORGANISATIONAL_CONTEXT,
                EvidenceScope.CROSS_DOMAIN_CONTEXT,
            ):
                rt.is_suspicious_broadcast = True

    def build_domain_package(self, domain_key: str, domain_name: Optional[str] = None) -> DomainEvidencePackage:
        """Build the isolated DomainEvidencePackage for a domain."""
        name = domain_name or dict(ALL_MATURITY_DOMAINS).get(domain_key, domain_key)
        assigned_ids = self._domain_assignments.get(domain_key, [])

        controls: List[EvidenceRecord] = []
        gaps: List[EvidenceRecord] = []
        unknowns: List[EvidenceRecord] = []
        suppliers: List[EvidenceRecord] = []
        org_context: List[EvidenceRecord] = []
        comp_targets: List[EvidenceRecord] = []
        impacts: List[EvidenceRecord] = []

        evidenced_dimensions: Set[str] = set()

        for eid in assigned_ids:
            rec = self._evidence_pool.get(eid)
            if not rec:
                continue

            # Route by scope, state, and explicit scoring role
            if rec.evidence_scope == EvidenceScope.ORGANISATIONAL_CONTEXT:
                org_context.append(rec)
            elif rec.evidence_scope == EvidenceScope.COMPLIANCE_TARGET or rec.scoring_role == ScoringRole.COMPLIANCE_TARGET_ONLY:
                comp_targets.append(rec)
            elif rec.evidence_scope == EvidenceScope.BUSINESS_IMPACT or rec.scoring_role == ScoringRole.BUSINESS_IMPACT_ONLY:
                impacts.append(rec)
            elif rec.scoring_role == ScoringRole.INVENTORY_ONLY:
                # Inventory records strictly routed to context; never treated as positive controls
                org_context.append(rec)
            elif rec.assurance_state in (AssuranceState.VERIFIED_PRESENT, AssuranceState.REPORTED_PRESENT):
                if rec.scoring_role == ScoringRole.POSITIVE_CONTROL:
                    controls.append(rec)
                    if rec.target_dimension:
                        evidenced_dimensions.add(rec.target_dimension)
                else:
                    org_context.append(rec)
            elif rec.assurance_state in (AssuranceState.REPORTED_ABSENT, AssuranceState.VERIFIED_ABSENT):
                gaps.append(rec)
                if rec.target_dimension:
                    evidenced_dimensions.add(rec.target_dimension)
            elif rec.assurance_state == AssuranceState.REQUIRES_SUPPLIER_CONFIRMATION:
                suppliers.append(rec)
            elif rec.assurance_state in (
                AssuranceState.UNKNOWN,
                AssuranceState.NOT_ESTABLISHED_DURING_CONSULTATION,
                AssuranceState.UNRELIABLE,
            ):
                unknowns.append(rec)

        # Dimension-based score eligibility check:
        # A domain is score-eligible only if its required dimensions are evidenced and
        # the total number of distinct evidenced dimensions meets the configured minimum threshold.
        # In addition, distinct parent sources must be >= 2 for score eligibility.
        policy = DOMAIN_DIMENSION_POLICIES.get(domain_key, DomainDimensionPolicy(domain_key=domain_key))
        has_all_required_dims = all(req in evidenced_dimensions for req in policy.required_dimensions)
        dimension_count_met = len(evidenced_dimensions) >= policy.min_dimensions_count

        substantive_records = controls + gaps
        total_substantive = len(substantive_records)
        contributing_eids: List[str] = [r.evidence_id for r in substantive_records]

        # Parent evidence IDs: use parent_evidence_id if present, else fallback to evidence_id
        contributing_parents: Set[str] = set()
        for r in substantive_records:
            if r.parent_evidence_id:
                contributing_parents.add(r.parent_evidence_id)
            else:
                contributing_parents.add(r.evidence_id)

        contributing_source_types: List[str] = sorted(list({r.source_type for r in substantive_records if r.source_type}))
        distinct_parent_count = len(contributing_parents)

        if substantive_records:
            avg_confidence = round(sum(r.confidence for r in substantive_records) / len(substantive_records), 2)
        else:
            avg_confidence = 0.0

        missing_required_dims = [req for req in policy.required_dimensions if req not in evidenced_dimensions]
        contradicted_dims: List[str] = []

        has_contradiction = any(
            self._evidence_pool[eid].assurance_state == AssuranceState.CONTRADICTED
            for eid in assigned_ids if eid in self._evidence_pool
        )

        decision_reasons: List[str] = []
        score_withheld_reason: Optional[str] = None

        has_sufficient_parent_diversity = distinct_parent_count >= 2

        if has_contradiction:
            cov = EvidenceCoverageResult.CONTRADICTED
            eligible = False
            decision_reasons.append("Evidence contradiction detected in domain assignments.")
            score_withheld_reason = "Contradicted evidence present"
        elif dimension_count_met and has_all_required_dims and has_sufficient_parent_diversity:
            cov = EvidenceCoverageResult.SUFFICIENT
            eligible = True
            decision_reasons.append(
                f"Sufficient evidence across {len(evidenced_dimensions)} dimensions from {distinct_parent_count} distinct parent sources."
            )
        elif dimension_count_met and has_all_required_dims and not has_sufficient_parent_diversity:
            cov = EvidenceCoverageResult.PARTIAL
            eligible = False
            decision_reasons.append(
                f"Evidence derived from only {distinct_parent_count} distinct parent source(s); minimum 2 distinct parent sources required."
            )
            score_withheld_reason = "Insufficient distinct parent evidence sources (minimum 2 required)"
        elif total_substantive >= 1 and (has_all_required_dims or len(evidenced_dimensions) >= 1):
            cov = EvidenceCoverageResult.PARTIAL
            eligible = False
            decision_reasons.append(
                f"Partial evidence ({len(evidenced_dimensions)}/{policy.min_dimensions_count} dimensions, {distinct_parent_count} parent sources)."
            )
            score_withheld_reason = "Partial consultation evidence (below required multi-dimensional threshold)"
        else:
            cov = EvidenceCoverageResult.INSUFFICIENT
            eligible = False
            decision_reasons.append("No substantive control or gap evidence established during consultation.")
            score_withheld_reason = "No substantive domain evidence established"

        # Conditional-domain applicability check:
        # Conditional domains must be backed by affirmative evidence or marked UNDETERMINED with eligible_for_score = False.
        app_status = "APPLICABLE"
        if domain_key in ("application_security", "ai_governance") and total_substantive == 0:
            app_status = "UNDETERMINED"
            eligible = False
            decision_reasons.append(f"Conditional domain {domain_key} applicability undetermined from consultation.")
            score_withheld_reason = "Conditional domain applicability undetermined"

        eligibility_decision = DomainScoreEligibilityDecision(
            domain_key=domain_key,
            eligible_for_score=eligible,
            coverage_result=cov,
            evidenced_dimensions=sorted(list(evidenced_dimensions)),
            missing_required_dimensions=missing_required_dims,
            contradicted_dimensions=contradicted_dims,
            contributing_evidence_ids=contributing_eids,
            contributing_parent_evidence_ids=sorted(list(contributing_parents)),
            distinct_parent_sources_count=distinct_parent_count,
            contributing_source_types=contributing_source_types,
            confidence=avg_confidence,
            decision_reasons=decision_reasons,
            score_withheld_reason=score_withheld_reason,
        )

        # Domain Completeness: An applicable or undetermined domain with 0 controls and 0 gaps
        # cannot have an empty unknowns list (unknowns_count = 0).
        if total_substantive == 0 and len(unknowns) == 0:
            val_rec = EvidenceRecord(
                evidence_id=f"val_{domain_key}_unestablished",
                canonical_topic=f"{domain_key}_baseline",
                assurance_state=AssuranceState.NOT_ESTABLISHED_DURING_CONSULTATION,
                evidence_scope=EvidenceScope.CROSS_DOMAIN_CONTEXT,
                scoring_role=ScoringRole.VALIDATION_ONLY,
                raw_statement=f"No baseline evidence established during consultation for {name}; validation required.",
                normalised_statement=f"No baseline evidence established during consultation for {name}; validation required.",
                source_type="baseline_normalised",
                source_locator=f"assessment_gap:{domain_key}",
                confidence=0.5,
            )
            unknowns.append(val_rec)

        return DomainEvidencePackage(
            domain_key=domain_key,
            domain_display_name=name,
            coverage_result=cov,
            eligible_for_score=eligible,
            applicability_status=app_status,  # type: ignore
            domain_specific_controls=controls,
            domain_specific_gaps=gaps,
            unknowns_and_unvalidated=unknowns,
            supplier_dependencies=suppliers,
            organisational_context=org_context,
            compliance_targets=comp_targets,
            business_impacts=impacts,
            scoring_notes=[],
            eligibility_decision=eligibility_decision,
        )
