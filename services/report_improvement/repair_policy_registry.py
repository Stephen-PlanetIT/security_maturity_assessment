from __future__ import annotations

"""
Maturity Assessment Repair Policy Registry.

Declarative ownership map defining permitted repair actions, scopes, and budget
for known quality defects across the maturity reporting pipeline.
"""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class FailureCategory(str, Enum):
    SCHEMA_STRUCTURE = "SCHEMA_STRUCTURE"
    EVIDENCE_LINEAGE = "EVIDENCE_LINEAGE"
    FACTUAL_ACCURACY = "FACTUAL_ACCURACY"
    CONTROL_RECOGNITION = "CONTROL_RECOGNITION"
    SCORING_CONSISTENCY = "SCORING_CONSISTENCY"
    NARRATIVE_QUALITY = "NARRATIVE_QUALITY"
    CROSS_SECTION_COHERENCE = "CROSS_SECTION_COHERENCE"
    RECOMMENDATION_TRACEABILITY = "RECOMMENDATION_TRACEABILITY"
    THREAT_SCENARIO_GROUNDING = "THREAT_SCENARIO_GROUNDING"
    COMPLIANCE_ALIGNMENT = "COMPLIANCE_ALIGNMENT"
    COST_GROUNDING = "COST_GROUNDING"
    TEMPLATE_BINDING = "TEMPLATE_BINDING"
    DIAGNOSTIC_ISOLATION = "DIAGNOSTIC_ISOLATION"
    DOCX_RENDER = "DOCX_RENDER"
    DELIVERY_METADATA = "DELIVERY_METADATA"


class RepairAction(str, Enum):
    DETERMINISTIC_NORMALISATION = "DETERMINISTIC_NORMALISATION"
    DETERMINISTIC_BINDING_REPAIR = "DETERMINISTIC_BINDING_REPAIR"
    DETERMINISTIC_SANITISATION = "DETERMINISTIC_SANITISATION"
    RESTORE_LAST_VALIDATED_VALUE = "RESTORE_LAST_VALIDATED_VALUE"
    REGENERATE_OWNING_SECTION = "REGENERATE_OWNING_SECTION"
    REGENERATE_SECTION_AND_DEPENDENCIES = "REGENERATE_SECTION_AND_DEPENDENCIES"
    REBUILD_STRUCTURED_SECTION = "REBUILD_STRUCTURED_SECTION"
    POST_RENDER_DOCX_REPAIR = "POST_RENDER_DOCX_REPAIR"
    CONSULTANT_EXCEPTION_REQUIRED = "CONSULTANT_EXCEPTION_REQUIRED"
    DELIVERY_COMPLETION_REQUIRED = "DELIVERY_COMPLETION_REQUIRED"
    NO_SAFE_AUTOMATED_REPAIR = "NO_SAFE_AUTOMATED_REPAIR"


class EscalationState(str, Enum):
    FINAL_READY = "FINAL_READY"
    CUSTOMER_REVIEW_DRAFT = "CUSTOMER_REVIEW_DRAFT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class NoProgressBehaviour(str, Enum):
    STOP_AND_RETAIN_LAST_VALID = "STOP_AND_RETAIN_LAST_VALID"
    ESCALATE_TO_CONSULTANT = "ESCALATE_TO_CONSULTANT"
    ALLOW_CUSTOMER_REVIEW_DRAFT = "ALLOW_CUSTOMER_REVIEW_DRAFT"


class RepairPolicyRule(BaseModel):
    rule_id: str = Field(description="Unique rule ID matching validator or coherence rules")
    failure_category: FailureCategory
    owning_component: str = Field(description="Module responsible for generation or enforcement")
    affected_section: str = Field(description="Primary affected report section")
    dependent_sections: List[str] = Field(default_factory=list, description="Sections consuming output from affected section")
    permitted_repair_action: RepairAction
    deterministic_or_model_based: str = Field(description="'deterministic' | 'model_based' | 'hybrid' | 'human_only'")
    evidence_required: bool = Field(default=True)
    safe_to_auto_repair: bool = Field(default=True)
    maximum_attempts: int = Field(default=2)
    no_progress_behaviour: NoProgressBehaviour = Field(default=NoProgressBehaviour.STOP_AND_RETAIN_LAST_VALID)
    escalation_state: EscalationState = Field(default=EscalationState.REVIEW_REQUIRED)


# Global Declarative Repair Policy Registry
REPAIR_POLICY_REGISTRY: Dict[str, RepairPolicyRule] = {
    # 1. STRUCTURED_OUTPUT_INVALID
    "STRUCTURED_OUTPUT_INVALID": RepairPolicyRule(
        rule_id="STRUCTURED_OUTPUT_INVALID",
        failure_category=FailureCategory.SCHEMA_STRUCTURE,
        owning_component="services.report_improvement.section_generators",
        affected_section="specialist_sections",
        dependent_sections=["template_projection", "export"],
        permitted_repair_action=RepairAction.REBUILD_STRUCTURED_SECTION,
        deterministic_or_model_based="deterministic",
        evidence_required=False,
        safe_to_auto_repair=True,
        maximum_attempts=1,
        no_progress_behaviour=NoProgressBehaviour.STOP_AND_RETAIN_LAST_VALID,
        escalation_state=EscalationState.REVIEW_REQUIRED,
    ),

    # 2. EVIDENCE_LINEAGE_MISSING
    "EVIDENCE_LINEAGE_MISSING": RepairPolicyRule(
        rule_id="EVIDENCE_LINEAGE_MISSING",
        failure_category=FailureCategory.EVIDENCE_LINEAGE,
        owning_component="services.report_improvement.evidence_enforcement.domain_registry",
        affected_section="domain_assessments",
        dependent_sections=["executive_summary", "security_rating", "phased_roadmap"],
        permitted_repair_action=RepairAction.REBUILD_STRUCTURED_SECTION,
        deterministic_or_model_based="deterministic",
        evidence_required=True,
        safe_to_auto_repair=True,
        maximum_attempts=1,
        no_progress_behaviour=NoProgressBehaviour.ESCALATE_TO_CONSULTANT,
        escalation_state=EscalationState.REVIEW_REQUIRED,
    ),

    # 3. UNSUPPORTED_FACT
    "UNSUPPORTED_FACT": RepairPolicyRule(
        rule_id="UNSUPPORTED_FACT",
        failure_category=FailureCategory.FACTUAL_ACCURACY,
        owning_component="services.report_improvement.auto_remediation.evidence_rewriter",
        affected_section="executive_summary",
        dependent_sections=["main_findings", "phased_roadmap"],
        permitted_repair_action=RepairAction.REGENERATE_OWNING_SECTION,
        deterministic_or_model_based="model_based",
        evidence_required=True,
        safe_to_auto_repair=True,
        maximum_attempts=2,
        no_progress_behaviour=NoProgressBehaviour.STOP_AND_RETAIN_LAST_VALID,
        escalation_state=EscalationState.REVIEW_REQUIRED,
    ),

    # 4. UNKNOWN_CONVERTED_TO_ABSENCE
    "UNKNOWN_CONVERTED_TO_ABSENCE": RepairPolicyRule(
        rule_id="UNKNOWN_CONVERTED_TO_ABSENCE",
        failure_category=FailureCategory.FACTUAL_ACCURACY,
        owning_component="services.report_improvement.evidence_enforcement.validator",
        affected_section="domain_assessments",
        dependent_sections=["executive_summary", "phased_roadmap"],
        permitted_repair_action=RepairAction.DETERMINISTIC_NORMALISATION,
        deterministic_or_model_based="deterministic",
        evidence_required=True,
        safe_to_auto_repair=True,
        maximum_attempts=2,
        no_progress_behaviour=NoProgressBehaviour.STOP_AND_RETAIN_LAST_VALID,
        escalation_state=EscalationState.REVIEW_REQUIRED,
    ),

    # 5. EXISTING_CONTROL_NOT_RECOGNISED
    "EXISTING_CONTROL_NOT_RECOGNISED": RepairPolicyRule(
        rule_id="EXISTING_CONTROL_NOT_RECOGNISED",
        failure_category=FailureCategory.CONTROL_RECOGNITION,
        owning_component="services.report_improvement.evidence_enforcement.domain_registry",
        affected_section="domain_assessments",
        dependent_sections=["executive_summary", "security_rating"],
        permitted_repair_action=RepairAction.DETERMINISTIC_NORMALISATION,
        deterministic_or_model_based="deterministic",
        evidence_required=True,
        safe_to_auto_repair=True,
        maximum_attempts=2,
        no_progress_behaviour=NoProgressBehaviour.STOP_AND_RETAIN_LAST_VALID,
        escalation_state=EscalationState.REVIEW_REQUIRED,
    ),

    # 6. SCORE_INCONSISTENCY
    "SCORE_INCONSISTENCY": RepairPolicyRule(
        rule_id="SCORE_INCONSISTENCY",
        failure_category=FailureCategory.SCORING_CONSISTENCY,
        owning_component="services.report_improvement.section_generators.security_rating",
        affected_section="security_rating",
        dependent_sections=["executive_summary"],
        permitted_repair_action=RepairAction.DETERMINISTIC_NORMALISATION,
        deterministic_or_model_based="deterministic",
        evidence_required=True,
        safe_to_auto_repair=True,
        maximum_attempts=2,
        no_progress_behaviour=NoProgressBehaviour.STOP_AND_RETAIN_LAST_VALID,
        escalation_state=EscalationState.REVIEW_REQUIRED,
    ),

    # 7. SCORE_PRESENT_WHEN_WITHHELD
    "SCORE_PRESENT_WHEN_WITHHELD": RepairPolicyRule(
        rule_id="SCORE_PRESENT_WHEN_WITHHELD",
        failure_category=FailureCategory.SCORING_CONSISTENCY,
        owning_component="services.report_improvement.canonical_score",
        affected_section="security_rating",
        dependent_sections=["template_projection", "export"],
        permitted_repair_action=RepairAction.DETERMINISTIC_BINDING_REPAIR,
        deterministic_or_model_based="deterministic",
        evidence_required=True,
        safe_to_auto_repair=True,
        maximum_attempts=2,
        no_progress_behaviour=NoProgressBehaviour.STOP_AND_RETAIN_LAST_VALID,
        escalation_state=EscalationState.REVIEW_REQUIRED,
    ),

    # 8. DOMAIN_CONTENT_GENERIC
    "DOMAIN_CONTENT_GENERIC": RepairPolicyRule(
        rule_id="DOMAIN_CONTENT_GENERIC",
        failure_category=FailureCategory.NARRATIVE_QUALITY,
        owning_component="services.report_improvement.section_generators.domain_assessments",
        affected_section="domain_assessments",
        dependent_sections=["executive_summary", "phased_roadmap"],
        permitted_repair_action=RepairAction.REGENERATE_OWNING_SECTION,
        deterministic_or_model_based="model_based",
        evidence_required=True,
        safe_to_auto_repair=True,
        maximum_attempts=2,
        no_progress_behaviour=NoProgressBehaviour.STOP_AND_RETAIN_LAST_VALID,
        escalation_state=EscalationState.REVIEW_REQUIRED,
    ),

    # 9. DOMAIN_CONTENT_DUPLICATED
    "DOMAIN_CONTENT_DUPLICATED": RepairPolicyRule(
        rule_id="DOMAIN_CONTENT_DUPLICATED",
        failure_category=FailureCategory.NARRATIVE_QUALITY,
        owning_component="services.report_improvement.auto_remediation.deterministic_fixes",
        affected_section="domain_assessments",
        dependent_sections=[],
        permitted_repair_action=RepairAction.DETERMINISTIC_NORMALISATION,
        deterministic_or_model_based="deterministic",
        evidence_required=False,
        safe_to_auto_repair=True,
        maximum_attempts=2,
        no_progress_behaviour=NoProgressBehaviour.STOP_AND_RETAIN_LAST_VALID,
        escalation_state=EscalationState.REVIEW_REQUIRED,
    ),

    # 10. CROSS_SECTION_CONTRADICTION
    "CROSS_SECTION_CONTRADICTION": RepairPolicyRule(
        rule_id="CROSS_SECTION_CONTRADICTION",
        failure_category=FailureCategory.CROSS_SECTION_COHERENCE,
        owning_component="services.report_improvement.section_generators.quality_checks",
        affected_section="cross_section_narrative",
        dependent_sections=["executive_summary", "threat_scenarios", "phased_roadmap"],
        permitted_repair_action=RepairAction.REGENERATE_SECTION_AND_DEPENDENCIES,
        deterministic_or_model_based="hybrid",
        evidence_required=True,
        safe_to_auto_repair=True,
        maximum_attempts=1,
        no_progress_behaviour=NoProgressBehaviour.ESCALATE_TO_CONSULTANT,
        escalation_state=EscalationState.REVIEW_REQUIRED,
    ),

    # 11. RECOMMENDATION_UNGROUNDED
    "RECOMMENDATION_UNGROUNDED": RepairPolicyRule(
        rule_id="RECOMMENDATION_UNGROUNDED",
        failure_category=FailureCategory.RECOMMENDATION_TRACEABILITY,
        owning_component="services.report_improvement.section_generators.domain_assessments",
        affected_section="domain_assessments",
        dependent_sections=["phased_roadmap"],
        permitted_repair_action=RepairAction.REGENERATE_OWNING_SECTION,
        deterministic_or_model_based="model_based",
        evidence_required=True,
        safe_to_auto_repair=True,
        maximum_attempts=2,
        no_progress_behaviour=NoProgressBehaviour.STOP_AND_RETAIN_LAST_VALID,
        escalation_state=EscalationState.REVIEW_REQUIRED,
    ),

    # 12. EXISTING_CONTROL_RECOMMENDED_AS_NEW
    "EXISTING_CONTROL_RECOMMENDED_AS_NEW": RepairPolicyRule(
        rule_id="EXISTING_CONTROL_RECOMMENDED_AS_NEW",
        failure_category=FailureCategory.CONTROL_RECOGNITION,
        owning_component="services.report_improvement.evidence_enforcement.validator",
        affected_section="phased_roadmap",
        dependent_sections=["domain_assessments"],
        permitted_repair_action=RepairAction.DETERMINISTIC_NORMALISATION,
        deterministic_or_model_based="deterministic",
        evidence_required=True,
        safe_to_auto_repair=True,
        maximum_attempts=2,
        no_progress_behaviour=NoProgressBehaviour.STOP_AND_RETAIN_LAST_VALID,
        escalation_state=EscalationState.REVIEW_REQUIRED,
    ),

    # 13. ROADMAP_DEPENDENCY_INVALID
    "ROADMAP_DEPENDENCY_INVALID": RepairPolicyRule(
        rule_id="ROADMAP_DEPENDENCY_INVALID",
        failure_category=FailureCategory.CROSS_SECTION_COHERENCE,
        owning_component="services.report_improvement.section_generators.cross_section_context",
        affected_section="phased_roadmap",
        dependent_sections=["executive_summary"],
        permitted_repair_action=RepairAction.REGENERATE_OWNING_SECTION,
        deterministic_or_model_based="model_based",
        evidence_required=True,
        safe_to_auto_repair=True,
        maximum_attempts=2,
        no_progress_behaviour=NoProgressBehaviour.ESCALATE_TO_CONSULTANT,
        escalation_state=EscalationState.REVIEW_REQUIRED,
    ),

    # 14. THREAT_SCENARIO_UNSUPPORTED
    "THREAT_SCENARIO_UNSUPPORTED": RepairPolicyRule(
        rule_id="THREAT_SCENARIO_UNSUPPORTED",
        failure_category=FailureCategory.THREAT_SCENARIO_GROUNDING,
        owning_component="services.report_improvement.section_generators.attack_scenario",
        affected_section="threat_scenarios",
        dependent_sections=["executive_summary"],
        permitted_repair_action=RepairAction.REGENERATE_OWNING_SECTION,
        deterministic_or_model_based="model_based",
        evidence_required=True,
        safe_to_auto_repair=True,
        maximum_attempts=2,
        no_progress_behaviour=NoProgressBehaviour.STOP_AND_RETAIN_LAST_VALID,
        escalation_state=EscalationState.REVIEW_REQUIRED,
    ),

    # 15. THREAT_SCENARIO_UNSUPPORTED_CVE
    "THREAT_SCENARIO_UNSUPPORTED_CVE": RepairPolicyRule(
        rule_id="THREAT_SCENARIO_UNSUPPORTED_CVE",
        failure_category=FailureCategory.THREAT_SCENARIO_GROUNDING,
        owning_component="services.report_improvement.section_generators.attack_scenario",
        affected_section="threat_scenarios",
        dependent_sections=["executive_summary"],
        permitted_repair_action=RepairAction.REBUILD_STRUCTURED_SECTION,
        deterministic_or_model_based="deterministic",
        evidence_required=True,
        safe_to_auto_repair=True,
        maximum_attempts=1,
        no_progress_behaviour=NoProgressBehaviour.STOP_AND_RETAIN_LAST_VALID,
        escalation_state=EscalationState.REVIEW_REQUIRED,
    ),

    # 16. COMPLIANCE_TARGET_DROPPED
    "COMPLIANCE_TARGET_DROPPED": RepairPolicyRule(
        rule_id="COMPLIANCE_TARGET_DROPPED",
        failure_category=FailureCategory.COMPLIANCE_ALIGNMENT,
        owning_component="services.report_improvement.section_generators.compliance_alignment",
        affected_section="compliance_alignment",
        dependent_sections=["executive_summary"],
        permitted_repair_action=RepairAction.REGENERATE_OWNING_SECTION,
        deterministic_or_model_based="model_based",
        evidence_required=True,
        safe_to_auto_repair=True,
        maximum_attempts=2,
        no_progress_behaviour=NoProgressBehaviour.STOP_AND_RETAIN_LAST_VALID,
        escalation_state=EscalationState.REVIEW_REQUIRED,
    ),

    # 17. COST_NARRATIVE_UNGROUNDED
    "COST_NARRATIVE_UNGROUNDED": RepairPolicyRule(
        rule_id="COST_NARRATIVE_UNGROUNDED",
        failure_category=FailureCategory.COST_GROUNDING,
        owning_component="services.report_improvement.auto_remediation.deterministic_fixes",
        affected_section="cost_of_inaction",
        dependent_sections=["executive_summary"],
        permitted_repair_action=RepairAction.DETERMINISTIC_NORMALISATION,
        deterministic_or_model_based="deterministic",
        evidence_required=False,
        safe_to_auto_repair=True,
        maximum_attempts=2,
        no_progress_behaviour=NoProgressBehaviour.STOP_AND_RETAIN_LAST_VALID,
        escalation_state=EscalationState.REVIEW_REQUIRED,
    ),

    # 18. TEMPLATE_BINDING_INVALID
    "TEMPLATE_BINDING_INVALID": RepairPolicyRule(
        rule_id="TEMPLATE_BINDING_INVALID",
        failure_category=FailureCategory.TEMPLATE_BINDING,
        owning_component="services.report_improvement.template_projection",
        affected_section="template_projection",
        dependent_sections=["export"],
        permitted_repair_action=RepairAction.DETERMINISTIC_BINDING_REPAIR,
        deterministic_or_model_based="deterministic",
        evidence_required=False,
        safe_to_auto_repair=True,
        maximum_attempts=2,
        no_progress_behaviour=NoProgressBehaviour.STOP_AND_RETAIN_LAST_VALID,
        escalation_state=EscalationState.REVIEW_REQUIRED,
    ),

    # 19. INTERNAL_DIAGNOSTIC_LEAK
    "INTERNAL_DIAGNOSTIC_LEAK": RepairPolicyRule(
        rule_id="INTERNAL_DIAGNOSTIC_LEAK",
        failure_category=FailureCategory.DIAGNOSTIC_ISOLATION,
        owning_component="services.report_improvement.authority_map",
        affected_section="export",
        dependent_sections=[],
        permitted_repair_action=RepairAction.DETERMINISTIC_SANITISATION,
        deterministic_or_model_based="deterministic",
        evidence_required=False,
        safe_to_auto_repair=True,
        maximum_attempts=2,
        no_progress_behaviour=NoProgressBehaviour.STOP_AND_RETAIN_LAST_VALID,
        escalation_state=EscalationState.REVIEW_REQUIRED,
    ),

    # 20. DOCX_RENDER_DEFECT
    "DOCX_RENDER_DEFECT": RepairPolicyRule(
        rule_id="DOCX_RENDER_DEFECT",
        failure_category=FailureCategory.DOCX_RENDER,
        owning_component="services.report_improvement.evidence_enforcement.docx_publication_validator",
        affected_section="customer_docx",
        dependent_sections=[],
        permitted_repair_action=RepairAction.POST_RENDER_DOCX_REPAIR,
        deterministic_or_model_based="deterministic",
        evidence_required=False,
        safe_to_auto_repair=True,
        maximum_attempts=1,
        no_progress_behaviour=NoProgressBehaviour.STOP_AND_RETAIN_LAST_VALID,
        escalation_state=EscalationState.REVIEW_REQUIRED,
    ),

    # 21. CONTENT_AFTER_BACK_COVER
    "CONTENT_AFTER_BACK_COVER": RepairPolicyRule(
        rule_id="CONTENT_AFTER_BACK_COVER",
        failure_category=FailureCategory.DOCX_RENDER,
        owning_component="services.report_improvement.evidence_enforcement.docx_publication_validator",
        affected_section="customer_docx",
        dependent_sections=[],
        permitted_repair_action=RepairAction.POST_RENDER_DOCX_REPAIR,
        deterministic_or_model_based="deterministic",
        evidence_required=False,
        safe_to_auto_repair=True,
        maximum_attempts=1,
        no_progress_behaviour=NoProgressBehaviour.STOP_AND_RETAIN_LAST_VALID,
        escalation_state=EscalationState.REVIEW_REQUIRED,
    ),

    # 22. DELIVERY_METADATA_INCOMPLETE
    "DELIVERY_METADATA_INCOMPLETE": RepairPolicyRule(
        rule_id="DELIVERY_METADATA_INCOMPLETE",
        failure_category=FailureCategory.DELIVERY_METADATA,
        owning_component="services.report_improvement.evidence_enforcement.docx_publication_validator",
        affected_section="customer_docx",
        dependent_sections=[],
        permitted_repair_action=RepairAction.DELIVERY_COMPLETION_REQUIRED,
        deterministic_or_model_based="deterministic",
        evidence_required=False,
        safe_to_auto_repair=False,
        maximum_attempts=0,
        no_progress_behaviour=NoProgressBehaviour.ALLOW_CUSTOMER_REVIEW_DRAFT,
        escalation_state=EscalationState.CUSTOMER_REVIEW_DRAFT,
    ),

    # 23. CONTRADICTORY_CUSTOMER_EVIDENCE
    "CONTRADICTORY_CUSTOMER_EVIDENCE": RepairPolicyRule(
        rule_id="CONTRADICTORY_CUSTOMER_EVIDENCE",
        failure_category=FailureCategory.FACTUAL_ACCURACY,
        owning_component="services.report_improvement.evidence_adjudicator",
        affected_section="domain_assessments",
        dependent_sections=["executive_summary", "security_rating"],
        permitted_repair_action=RepairAction.CONSULTANT_EXCEPTION_REQUIRED,
        deterministic_or_model_based="human_only",
        evidence_required=True,
        safe_to_auto_repair=False,
        maximum_attempts=0,
        no_progress_behaviour=NoProgressBehaviour.ESCALATE_TO_CONSULTANT,
        escalation_state=EscalationState.REVIEW_REQUIRED,
    ),

    # 24. CONDITIONAL_DOMAIN_UNRESOLVED
    "CONDITIONAL_DOMAIN_UNRESOLVED": RepairPolicyRule(
        rule_id="CONDITIONAL_DOMAIN_UNRESOLVED",
        failure_category=FailureCategory.EVIDENCE_LINEAGE,
        owning_component="services.report_improvement.evidence_enforcement.domain_registry",
        affected_section="domain_assessments",
        dependent_sections=["security_rating"],
        permitted_repair_action=RepairAction.CONSULTANT_EXCEPTION_REQUIRED,
        deterministic_or_model_based="human_only",
        evidence_required=True,
        safe_to_auto_repair=False,
        maximum_attempts=0,
        no_progress_behaviour=NoProgressBehaviour.ESCALATE_TO_CONSULTANT,
        escalation_state=EscalationState.REVIEW_REQUIRED,
    ),
}


def get_repair_policy(rule_id: str) -> Optional[RepairPolicyRule]:
    """Retrieves the declarative repair policy rule by rule_id or returns None."""
    return REPAIR_POLICY_REGISTRY.get(rule_id)


def export_repair_policy_registry_as_dict() -> Dict[str, Any]:
    """Exports all registered repair policies as a JSON-serialisable dictionary."""
    return {k: v.model_dump() for k, v in REPAIR_POLICY_REGISTRY.items()}
