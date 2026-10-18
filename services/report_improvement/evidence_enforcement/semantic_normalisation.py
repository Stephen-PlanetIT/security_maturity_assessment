from __future__ import annotations

"""
Field-Aware Semantic Normalisation and Compound Evidence Decomposition (Phase 2.1).

Replaces naive string-level boolean matching with strict, field-aware canonical interpretation.
Guarantees:
1. Field key context dictates expected value types, absence tokens, unknown tokens, and decomposition.
2. Compound phrases (e.g. 'Privileged Accounts Only', 'Automated (OS Only)', 'None (Relying on provider)')
   are decomposed into distinct positive controls, coverage limitations, dependencies, and validation requirements.
3. Explicit scoring roles prevent inventory, asset lists, impact statements, and compliance targets
   from masquerading as positive maturity controls.
4. Customer-agnostic: No hard-coded customer names, fixture strings, or sector branches.
"""

from typing import Dict, List, Optional, Tuple, Any
import hashlib
from pydantic import BaseModel, Field

from services.report_improvement.evidence_enforcement.canonical_models import (
    AssuranceState,
    EvidenceScope,
    ScoringRole,
    EvidenceRecord,
)

# Standard tokens across all fields
GENERIC_ABSENCE_TOKENS = {
    "none", "no", "not in place", "no formal plan", "none / cloud only",
    "unmanaged", "nil", "disabled", "absent", "false", "0", "zero",
}

GENERIC_UNKNOWN_TOKENS = {
    "unknown", "unspecified", "not sure", "tbd", "to be determined",
    "pending", "unclear", "investigating", "blank", "", "null",
}

GENERIC_NOT_APPLICABLE_TOKENS = {
    "n/a", "na", "not applicable", "not relevant", "none required",
}


class DecomposedEvidenceItem(BaseModel):
    """A single atomic proposition derived from a field's raw value."""
    topic_suffix: str
    raw_statement: str
    normalised_statement: str
    assurance_state: AssuranceState
    evidence_scope: EvidenceScope
    scoring_role: ScoringRole
    target_dimension: str
    applicable_domains: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    transformation_rule_id: str
    confidence: float = 0.85


def interpret_field_value(
    field_key: str,
    raw_val: Any,
    source_locator: str,
    parent_evidence_id: str,
) -> List[EvidenceRecord]:
    """
    Applies field-aware semantic interpretation and decomposition to produce
    one or more typed EvidenceRecords.
    """
    raw_val_str = "" if raw_val is None else str(raw_val).strip()
    val_lower = raw_val_str.lower()

    derived_items: List[DecomposedEvidenceItem] = []

    # 1. Identity & MFA Enforcement
    if field_key == "mfa_status":
        if val_lower in GENERIC_UNKNOWN_TOKENS:
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="mfa_status_unknown",
                raw_statement=raw_val_str or "Unknown",
                normalised_statement="Multi-factor authentication enforcement posture is unestablished; validation required.",
                assurance_state=AssuranceState.UNKNOWN,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_GAP,
                scoring_role=ScoringRole.VALIDATION_ONLY,
                target_dimension="control_presence",
                applicable_domains=["identity_access"],
                transformation_rule_id="RULE_MFA_UNKNOWN",
                confidence=0.5,
            ))
        elif "privileged" in val_lower and ("only" in val_lower or "subset" in val_lower or "admin" in val_lower):
            # Present: Privileged accounts enforced
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="mfa_privileged_present",
                raw_statement=raw_val_str,
                normalised_statement="Multi-factor authentication is enforced across administrative and privileged accounts.",
                assurance_state=AssuranceState.REPORTED_PRESENT,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_CONTROL,
                scoring_role=ScoringRole.POSITIVE_CONTROL,
                target_dimension="control_presence",
                applicable_domains=["identity_access"],
                transformation_rule_id="RULE_MFA_PRIVILEGED_PRESENT",
                confidence=0.80,
            ))
            # Limitation: General staff / standard user coverage gap
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="mfa_general_coverage_gap",
                raw_statement=raw_val_str,
                normalised_statement="Multi-factor authentication is not enforced across general staff and non-privileged accounts.",
                assurance_state=AssuranceState.REPORTED_ABSENT,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_GAP,
                scoring_role=ScoringRole.COVERAGE_LIMITATION,
                target_dimension="coverage",
                applicable_domains=["identity_access"],
                transformation_rule_id="RULE_MFA_GENERAL_ABSENT",
                confidence=0.80,
            ))
        elif any(t in val_lower for t in ["all", "enforced across staff", "universal", "all users"]):
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="mfa_universal_present",
                raw_statement=raw_val_str,
                normalised_statement="Multi-factor authentication is universally enforced across all user and administrative accounts.",
                assurance_state=AssuranceState.REPORTED_PRESENT,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_CONTROL,
                scoring_role=ScoringRole.POSITIVE_CONTROL,
                target_dimension="control_presence",
                applicable_domains=["identity_access"],
                transformation_rule_id="RULE_MFA_UNIVERSAL_PRESENT",
                confidence=0.85,
            ))
        elif any(tok in val_lower for tok in GENERIC_ABSENCE_TOKENS):
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="mfa_absent",
                raw_statement=raw_val_str,
                normalised_statement="Multi-factor authentication is absent or not enforced.",
                assurance_state=AssuranceState.REPORTED_ABSENT,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_GAP,
                scoring_role=ScoringRole.NEGATIVE_GAP,
                target_dimension="control_presence",
                applicable_domains=["identity_access"],
                transformation_rule_id="RULE_MFA_ABSENT",
                confidence=0.85,
            ))
        else:
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="mfa_reported",
                raw_statement=raw_val_str,
                normalised_statement=f"MFA deployment: {raw_val_str}",
                assurance_state=AssuranceState.REPORTED_PRESENT,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_CONTROL,
                scoring_role=ScoringRole.POSITIVE_CONTROL,
                target_dimension="control_presence",
                applicable_domains=["identity_access"],
                transformation_rule_id="RULE_MFA_GENERIC_REPORTED",
                confidence=0.75,
            ))

    # 2. Patch Management & Vulnerability Management
    elif field_key == "patching":
        if val_lower in GENERIC_UNKNOWN_TOKENS:
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="patching_unknown",
                raw_statement=raw_val_str or "Unknown",
                normalised_statement="Patch management cadence and coverage are unestablished; validation required.",
                assurance_state=AssuranceState.UNKNOWN,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_GAP,
                scoring_role=ScoringRole.VALIDATION_ONLY,
                target_dimension="operation",
                applicable_domains=["security_testing"],
                transformation_rule_id="RULE_PATCHING_UNKNOWN",
                confidence=0.5,
            ))
        elif "os only" in val_lower or "os-only" in val_lower:
            # Control: OS patching automated
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="patching_os_automated",
                raw_statement=raw_val_str,
                normalised_statement="Operating system patching is automated across workstations and servers.",
                assurance_state=AssuranceState.REPORTED_PRESENT,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_CONTROL,
                scoring_role=ScoringRole.POSITIVE_CONTROL,
                target_dimension="control_presence",
                applicable_domains=["security_testing"],
                transformation_rule_id="RULE_PATCHING_OS_PRESENT",
                confidence=0.80,
            ))
            # Limitation: Third-party and firmware patching unmanaged
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="patching_third_party_gap",
                raw_statement=raw_val_str,
                normalised_statement="Third-party application, hypervisor, and network device patching coverage is not established.",
                assurance_state=AssuranceState.REPORTED_ABSENT,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_GAP,
                scoring_role=ScoringRole.COVERAGE_LIMITATION,
                target_dimension="coverage",
                applicable_domains=["security_testing"],
                transformation_rule_id="RULE_PATCHING_THIRDPARTY_GAP",
                confidence=0.80,
            ))
        elif any(tok in val_lower for tok in GENERIC_ABSENCE_TOKENS):
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="patching_absent",
                raw_statement=raw_val_str,
                normalised_statement="No automated or systematic patch management process is maintained.",
                assurance_state=AssuranceState.REPORTED_ABSENT,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_GAP,
                scoring_role=ScoringRole.NEGATIVE_GAP,
                target_dimension="control_presence",
                applicable_domains=["security_testing"],
                transformation_rule_id="RULE_PATCHING_ABSENT",
                confidence=0.85,
            ))
        else:
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="patching_present",
                raw_statement=raw_val_str,
                normalised_statement=f"Patch management process: {raw_val_str}",
                assurance_state=AssuranceState.REPORTED_PRESENT,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_CONTROL,
                scoring_role=ScoringRole.POSITIVE_CONTROL,
                target_dimension="control_presence",
                applicable_domains=["security_testing"],
                transformation_rule_id="RULE_PATCHING_GENERIC",
                confidence=0.75,
            ))

    # 3. SaaS Backups
    elif field_key == "saas_backup":
        if any(tok in val_lower for tok in ["none", "relying on", "no independent", "not in place"]):
            # Absence of independent SaaS backup
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="saas_backup_absent",
                raw_statement=raw_val_str,
                normalised_statement="Independent third-party SaaS backup is absent; organisation relies solely on provider native retention.",
                assurance_state=AssuranceState.REPORTED_ABSENT,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_GAP,
                scoring_role=ScoringRole.NEGATIVE_GAP,
                target_dimension="control_presence",
                applicable_domains=["recovery_assurance", "saas_governance"],
                transformation_rule_id="RULE_SAAS_BACKUP_ABSENT",
                confidence=0.90,
            ))
            # Validation requirement on provider retention limits
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="saas_retention_validation",
                raw_statement=raw_val_str,
                normalised_statement="Provider recycle-bin retention policies and contractual recovery SLAs require formal validation.",
                assurance_state=AssuranceState.UNKNOWN,
                evidence_scope=EvidenceScope.CROSS_DOMAIN_CONTEXT,
                scoring_role=ScoringRole.VALIDATION_ONLY,
                target_dimension="testing",
                applicable_domains=["recovery_assurance"],
                transformation_rule_id="RULE_SAAS_RETENTION_VALIDATION",
                confidence=0.75,
            ))
        elif val_lower in GENERIC_UNKNOWN_TOKENS:
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="saas_backup_unknown",
                raw_statement=raw_val_str or "Unknown",
                normalised_statement="SaaS data backup architecture is unconfirmed; validation required.",
                assurance_state=AssuranceState.UNKNOWN,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_GAP,
                scoring_role=ScoringRole.VALIDATION_ONLY,
                target_dimension="control_presence",
                applicable_domains=["recovery_assurance", "saas_governance"],
                transformation_rule_id="RULE_SAAS_BACKUP_UNKNOWN",
                confidence=0.5,
            ))
        else:
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="saas_backup_present",
                raw_statement=raw_val_str,
                normalised_statement=f"Dedicated SaaS backup deployed: {raw_val_str}",
                assurance_state=AssuranceState.REPORTED_PRESENT,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_CONTROL,
                scoring_role=ScoringRole.POSITIVE_CONTROL,
                target_dimension="control_presence",
                applicable_domains=["recovery_assurance", "saas_governance"],
                transformation_rule_id="RULE_SAAS_BACKUP_PRESENT",
                confidence=0.85,
            ))

    # 4. Incident Response Readiness
    elif field_key == "ir_readiness":
        if any(tok in val_lower for tok in ["no formal plan", "informal", "none", "not in place", "no plan"]):
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="ir_plan_absent",
                raw_statement=raw_val_str,
                normalised_statement="No formal incident response plan, playbooks, or retained response partner are established.",
                assurance_state=AssuranceState.REPORTED_ABSENT,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_GAP,
                scoring_role=ScoringRole.NEGATIVE_GAP,
                target_dimension="governance",
                applicable_domains=["incident_response"],
                transformation_rule_id="RULE_IR_PLAN_ABSENT",
                confidence=0.90,
            ))
        elif val_lower in GENERIC_UNKNOWN_TOKENS:
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="ir_plan_unknown",
                raw_statement=raw_val_str or "Unknown",
                normalised_statement="Incident response preparedness and escalation pathways are unconfirmed; validation required.",
                assurance_state=AssuranceState.UNKNOWN,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_GAP,
                scoring_role=ScoringRole.VALIDATION_ONLY,
                target_dimension="governance",
                applicable_domains=["incident_response"],
                transformation_rule_id="RULE_IR_PLAN_UNKNOWN",
                confidence=0.5,
            ))
        else:
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="ir_plan_present",
                raw_statement=raw_val_str,
                normalised_statement=f"Documented incident response plan: {raw_val_str}",
                assurance_state=AssuranceState.REPORTED_PRESENT,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_CONTROL,
                scoring_role=ScoringRole.POSITIVE_CONTROL,
                target_dimension="governance",
                applicable_domains=["incident_response"],
                transformation_rule_id="RULE_IR_PLAN_PRESENT",
                confidence=0.80,
            ))

    # 5. Core Backups
    elif field_key == "backups":
        if val_lower in GENERIC_UNKNOWN_TOKENS:
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="backups_unknown",
                raw_statement=raw_val_str or "Unknown",
                normalised_statement="Backup immutability, offline segregation, and restore testing are unconfirmed; validation required.",
                assurance_state=AssuranceState.UNKNOWN,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_GAP,
                scoring_role=ScoringRole.VALIDATION_ONLY,
                target_dimension="control_presence",
                applicable_domains=["recovery_assurance"],
                transformation_rule_id="RULE_BACKUP_UNKNOWN",
                confidence=0.5,
            ))
        elif any(tok in val_lower for tok in GENERIC_ABSENCE_TOKENS):
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="backups_absent",
                raw_statement=raw_val_str,
                normalised_statement="No system backups are reported in place.",
                assurance_state=AssuranceState.REPORTED_ABSENT,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_GAP,
                scoring_role=ScoringRole.NEGATIVE_GAP,
                target_dimension="control_presence",
                applicable_domains=["recovery_assurance"],
                transformation_rule_id="RULE_BACKUP_ABSENT",
                confidence=0.90,
            ))
        else:
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="backups_reported",
                raw_statement=raw_val_str,
                normalised_statement=f"Backup solution: {raw_val_str}",
                assurance_state=AssuranceState.REPORTED_PRESENT,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_CONTROL,
                scoring_role=ScoringRole.POSITIVE_CONTROL,
                target_dimension="control_presence",
                applicable_domains=["recovery_assurance"],
                transformation_rule_id="RULE_BACKUP_PRESENT",
                confidence=0.75,
            ))

    # 6. MDR Provider
    elif field_key == "mdr_provider":
        if any(tok in val_lower for tok in GENERIC_ABSENCE_TOKENS) or val_lower == "none":
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="mdr_absent",
                raw_statement=raw_val_str,
                normalised_statement="No 24/7 Managed Detection and Response (MDR) service is deployed.",
                assurance_state=AssuranceState.REPORTED_ABSENT,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_GAP,
                scoring_role=ScoringRole.NEGATIVE_GAP,
                target_dimension="monitoring",
                applicable_domains=["monitoring_detection"],
                transformation_rule_id="RULE_MDR_ABSENT",
                confidence=0.90,
            ))
        elif val_lower in GENERIC_UNKNOWN_TOKENS:
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="mdr_unknown",
                raw_statement=raw_val_str or "Unknown",
                normalised_statement="Security monitoring and alert triaging arrangements are unestablished; validation required.",
                assurance_state=AssuranceState.UNKNOWN,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_GAP,
                scoring_role=ScoringRole.VALIDATION_ONLY,
                target_dimension="monitoring",
                applicable_domains=["monitoring_detection"],
                transformation_rule_id="RULE_MDR_UNKNOWN",
                confidence=0.5,
            ))
        else:
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="mdr_present",
                raw_statement=raw_val_str,
                normalised_statement=f"Managed Detection & Response provider in place: {raw_val_str}",
                assurance_state=AssuranceState.REPORTED_PRESENT,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_CONTROL,
                scoring_role=ScoringRole.POSITIVE_CONTROL,
                target_dimension="monitoring",
                applicable_domains=["monitoring_detection"],
                transformation_rule_id="RULE_MDR_PRESENT",
                confidence=0.85,
            ))

    # 7. Endpoint Protection
    elif field_key == "endpoint":
        if any(tok in val_lower for tok in GENERIC_ABSENCE_TOKENS):
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="endpoint_absent",
                raw_statement=raw_val_str,
                normalised_statement="No centralised endpoint protection platform is reported deployed.",
                assurance_state=AssuranceState.REPORTED_ABSENT,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_GAP,
                scoring_role=ScoringRole.NEGATIVE_GAP,
                target_dimension="control_presence",
                applicable_domains=["endpoint_security"],
                transformation_rule_id="RULE_ENDPOINT_ABSENT",
                confidence=0.90,
            ))
        elif val_lower in GENERIC_UNKNOWN_TOKENS:
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="endpoint_unknown",
                raw_statement=raw_val_str or "Unknown",
                normalised_statement="Endpoint protection deployment status is unconfirmed; validation required.",
                assurance_state=AssuranceState.UNKNOWN,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_GAP,
                scoring_role=ScoringRole.VALIDATION_ONLY,
                target_dimension="control_presence",
                applicable_domains=["endpoint_security"],
                transformation_rule_id="RULE_ENDPOINT_UNKNOWN",
                confidence=0.5,
            ))
        else:
            # Single product name satisfies control presence, but NOT coverage or configuration
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="endpoint_product_present",
                raw_statement=raw_val_str,
                normalised_statement=f"Endpoint protection software reported deployed: {raw_val_str}",
                assurance_state=AssuranceState.REPORTED_PRESENT,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_CONTROL,
                scoring_role=ScoringRole.POSITIVE_CONTROL,
                target_dimension="control_presence",
                applicable_domains=["endpoint_security"],
                transformation_rule_id="RULE_ENDPOINT_PRODUCT_PRESENT",
                confidence=0.80,
            ))

    # 8. Firewall & Perimeter
    elif field_key == "firewall":
        if val_lower in ["other", "unspecified", "legacy"] or val_lower in GENERIC_UNKNOWN_TOKENS:
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="firewall_unspecified",
                raw_statement=raw_val_str,
                normalised_statement="Perimeter firewall model, UTM inspection capabilities, and rule review cadence are unverified; validation required.",
                assurance_state=AssuranceState.UNKNOWN,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_GAP,
                scoring_role=ScoringRole.VALIDATION_ONLY,
                target_dimension="configuration",
                applicable_domains=["network_edge"],
                transformation_rule_id="RULE_FIREWALL_UNSPECIFIED",
                confidence=0.5,
            ))
        elif any(tok in val_lower for tok in GENERIC_ABSENCE_TOKENS):
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="firewall_absent",
                raw_statement=raw_val_str,
                normalised_statement="No dedicated perimeter firewall is reported.",
                assurance_state=AssuranceState.REPORTED_ABSENT,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_GAP,
                scoring_role=ScoringRole.NEGATIVE_GAP,
                target_dimension="control_presence",
                applicable_domains=["network_edge"],
                transformation_rule_id="RULE_FIREWALL_ABSENT",
                confidence=0.90,
            ))
        else:
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="firewall_present",
                raw_statement=raw_val_str,
                normalised_statement=f"Perimeter firewall appliance: {raw_val_str}",
                assurance_state=AssuranceState.REPORTED_PRESENT,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_CONTROL,
                scoring_role=ScoringRole.POSITIVE_CONTROL,
                target_dimension="control_presence",
                applicable_domains=["network_edge"],
                transformation_rule_id="RULE_FIREWALL_PRESENT",
                confidence=0.80,
            ))

    # 9. Remote Access
    elif field_key == "remote_access":
        if "cloud only" in val_lower or "cloud-only" in val_lower or "none / cloud only" in val_lower:
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="remote_access_cloud_only",
                raw_statement=raw_val_str,
                normalised_statement="Remote access is cloud-only with no traditional inbound VPN access maintained.",
                assurance_state=AssuranceState.REPORTED_PRESENT,
                evidence_scope=EvidenceScope.TECHNOLOGY_INVENTORY,
                scoring_role=ScoringRole.INVENTORY_ONLY,
                target_dimension="configuration",
                applicable_domains=["network_edge"],
                transformation_rule_id="RULE_REMOTE_ACCESS_INVENTORY",
                confidence=0.85,
            ))
        elif val_lower in GENERIC_UNKNOWN_TOKENS:
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="remote_access_unknown",
                raw_statement=raw_val_str or "Unknown",
                normalised_statement="Remote access mechanisms and ingress security controls are unconfirmed; validation required.",
                assurance_state=AssuranceState.UNKNOWN,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_GAP,
                scoring_role=ScoringRole.VALIDATION_ONLY,
                target_dimension="control_presence",
                applicable_domains=["network_edge"],
                transformation_rule_id="RULE_REMOTE_ACCESS_UNKNOWN",
                confidence=0.5,
            ))
        else:
            derived_items.append(DecomposedEvidenceItem(
                topic_suffix="remote_access_present",
                raw_statement=raw_val_str,
                normalised_statement=f"Remote access solution: {raw_val_str}",
                assurance_state=AssuranceState.REPORTED_PRESENT,
                evidence_scope=EvidenceScope.DOMAIN_SPECIFIC_CONTROL,
                scoring_role=ScoringRole.POSITIVE_CONTROL,
                target_dimension="control_presence",
                applicable_domains=["network_edge"],
                transformation_rule_id="RULE_REMOTE_ACCESS_PRESENT",
                confidence=0.75,
            ))

    # 10. Typed Numeric Quantities (users, endpoints, servers)
    # Never pass numeric counts through string absence token matching!
    elif field_key in ("users", "endpoints", "servers", "user_count", "endpoint_count", "server_count"):
        try:
            num_val = float(str(raw_val).replace(",", "").strip())
            is_zero = (num_val == 0)
            if is_zero:
                norm_stmt = f"Explicit zero quantity reported for {field_key}."
                state = AssuranceState.REPORTED_ABSENT
            else:
                norm_stmt = f"Organisational metric ({field_key}): {int(num_val) if num_val.is_integer() else num_val}"
                state = AssuranceState.REPORTED_PRESENT
        except (ValueError, TypeError):
            is_zero = False
            norm_stmt = f"Organisational metric ({field_key}): unestablished or invalid format"
            state = AssuranceState.UNKNOWN

        derived_items.append(DecomposedEvidenceItem(
            topic_suffix=f"{field_key}_quantitative",
            raw_statement=raw_val_str,
            normalised_statement=norm_stmt,
            assurance_state=state,
            evidence_scope=EvidenceScope.ORGANISATIONAL_CONTEXT,
            scoring_role=ScoringRole.NON_SCORING_CONTEXT,
            target_dimension="",
            applicable_domains=[],
            transformation_rule_id="RULE_TYPED_NUMERIC_QUANTITY",
            confidence=0.95 if state in (AssuranceState.REPORTED_PRESENT, AssuranceState.REPORTED_ABSENT) else 0.50,
        ))

    # 11. Technology Inventory Fields (OS, Cloud, M365)
    elif field_key in ("operating_systems", "cloud_env", "m365_license"):
        derived_items.append(DecomposedEvidenceItem(
            topic_suffix=f"{field_key}_inventory",
            raw_statement=raw_val_str,
            normalised_statement=f"Technology platform inventory ({field_key}): {raw_val_str}",
            assurance_state=AssuranceState.REPORTED_PRESENT,
            evidence_scope=EvidenceScope.TECHNOLOGY_INVENTORY,
            scoring_role=ScoringRole.INVENTORY_ONLY,
            target_dimension="inventory",
            applicable_domains=["cloud_security" if field_key == "cloud_env" else "endpoint_security"],
            transformation_rule_id="RULE_TECH_INVENTORY_ONLY",
            confidence=0.85,
        ))

    # 12. Cyber Insurance
    elif field_key == "insurance":
        is_active = any(tok in val_lower for tok in ["active", "yes", "in place"])
        derived_items.append(DecomposedEvidenceItem(
            topic_suffix="cyber_insurance_context",
            raw_statement=raw_val_str,
            normalised_statement=f"Cyber insurance policy status: {raw_val_str}",
            assurance_state=AssuranceState.REPORTED_PRESENT if is_active else AssuranceState.REPORTED_ABSENT,
            evidence_scope=EvidenceScope.ORGANISATIONAL_CONTEXT,
            scoring_role=ScoringRole.NON_SCORING_CONTEXT,
            target_dimension="governance",
            applicable_domains=["supplier_assurance"],
            transformation_rule_id="RULE_INSURANCE_CONTEXT",
            confidence=0.85,
        ))

    # 13. Recovery Time Objective (Business Impact)
    elif field_key == "rto":
        derived_items.append(DecomposedEvidenceItem(
            topic_suffix="rto_impact",
            raw_statement=raw_val_str,
            normalised_statement=f"Target recovery time objective: {raw_val_str}",
            assurance_state=AssuranceState.REPORTED_PRESENT,
            evidence_scope=EvidenceScope.BUSINESS_IMPACT,
            scoring_role=ScoringRole.BUSINESS_IMPACT_ONLY,
            target_dimension="governance",
            applicable_domains=["recovery_assurance"],
            transformation_rule_id="RULE_RTO_IMPACT_ONLY",
            confidence=0.90,
        ))

    # 14. Culture & Savviness
    elif field_key in ("savviness_label", "culture_score", "culture_q1", "culture_q2", "culture_q3"):
        derived_items.append(DecomposedEvidenceItem(
            topic_suffix=f"{field_key}_context",
            raw_statement=raw_val_str,
            normalised_statement=f"Organisational culture and savviness ({field_key}): {raw_val_str}",
            assurance_state=AssuranceState.REPORTED_PRESENT,
            evidence_scope=EvidenceScope.ORGANISATIONAL_CONTEXT,
            scoring_role=ScoringRole.NON_SCORING_CONTEXT,
            target_dimension="governance",
            applicable_domains=[],
            transformation_rule_id="RULE_CULTURE_CONTEXT",
            confidence=0.85,
        ))

    # 15. Fallback generic handling - SAFE: Never creates control_presence or scoring evidence!
    else:
        state = AssuranceState.UNKNOWN if val_lower in GENERIC_UNKNOWN_TOKENS else (
            AssuranceState.REPORTED_ABSENT if any(tok in val_lower for tok in GENERIC_ABSENCE_TOKENS) else AssuranceState.REPORTED_PRESENT
        )
        derived_items.append(DecomposedEvidenceItem(
            topic_suffix=f"{field_key}_generic",
            raw_statement=raw_val_str or "(blank)",
            normalised_statement=raw_val_str or "Unspecified during consultation",
            assurance_state=state,
            evidence_scope=EvidenceScope.CROSS_DOMAIN_CONTEXT,
            scoring_role=ScoringRole.NON_SCORING_CONTEXT,
            target_dimension="",  # Safe: no target dimension
            applicable_domains=[],
            transformation_rule_id="RULE_GENERIC_FALLBACK",
            confidence=0.50,
        ))

    # Convert derived items to EvidenceRecords
    results: List[EvidenceRecord] = []
    for idx, item in enumerate(derived_items):
        item_eid = f"{parent_evidence_id}_{item.topic_suffix}_{idx}"
        results.append(EvidenceRecord(
            evidence_id=item_eid,
            canonical_topic=item.topic_suffix,
            assurance_state=item.assurance_state,
            evidence_scope=item.evidence_scope,
            scoring_role=item.scoring_role,
            parent_evidence_id=parent_evidence_id,
            transformation_rule_id=item.transformation_rule_id,
            target_dimension=item.target_dimension,
            raw_statement=item.raw_statement,
            normalised_statement=item.normalised_statement,
            source_type="customer_profile",
            source_locator=source_locator,
            applicable_domains=item.applicable_domains,
            confidence=item.confidence,
        ))

    return results
