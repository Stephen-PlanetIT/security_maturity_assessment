"""
consultation_schema.py — Option constants and defaults for consultation inputs (Phase 1)
"""
from __future__ import annotations

# Critical Asset Profile
BUSINESS_SERVICES_OPTIONS = [
    "Finance and payroll",
    "ERP or line-of-business platform",
    "CRM",
    "Microsoft 365 collaboration",
    "Customer or supplier portal",
    "Payment or EPOS",
    "Operational technology",
    "MIS or student records",
    "HR systems",
    "Production or distribution",
    "Customer-facing services",
    "Other",
]

SENSITIVE_DATA_OPTIONS = [
    "Personal data",
    "Special-category personal data",
    "Financial data",
    "Payment-card data",
    "Student or safeguarding data",
    "Customer or supplier confidential data",
    "Intellectual property",
    "Operationally sensitive data",
    "Credentials or secrets",
    "None identified",
    "Unknown",
]

DEFAULT_CRITICAL_ASSET_PROFILE = {
    "business_services": [],
    "systems_platforms": "",
    "sensitive_data_types": [],
    "additional_context": "",
}

# Service Resilience Profile
ASSESSMENT_STATUS_OPTIONS = [
    "Not assessed",
    "Informally understood",
    "Documented for selected services",
    "Documented for critical services",
    "Documented, owned and regularly reviewed",
]

RTO_OPTIONS = [
    "Near-continuous availability",
    "Less than 4 hours",
    "4 to 12 hours",
    "12 to 24 hours",
    "24 to 48 hours",
    "More than 48 hours",
    "Varies by service",
    "Unknown",
]

RPO_OPTIONS = [
    "Near zero",
    "Less than 1 hour",
    "Less than 4 hours",
    "Same working day",
    "24 hours",
    "More than 24 hours",
    "Varies by service",
    "Unknown",
]

MANUAL_WORKAROUND_OPTIONS = [
    "None identified",
    "Informal",
    "Documented for selected services",
    "Documented for critical services",
    "Documented and exercised",
    "Unknown",
]

DEP_MAPPING_OPTIONS = [
    "Not documented",
    "Partially understood",
    "Documented for selected critical services",
    "Documented across critical services",
    "Documented and regularly validated",
    "Unknown",
]

RECOVERY_PRIORITIES_OPTIONS = [
    "Not documented",
    "System list only",
    "Prioritised critical systems",
    "Business services mapped to technical dependencies",
    "Priorities approved by business owners",
    "Priorities validated through exercises",
    "Unknown",
]

DEFAULT_SERVICE_RESILIENCE_PROFILE = {
    "assessment_status": "",
    "most_critical_service": "",
    "service_specific_rto": "",
    "service_specific_rpo": "",
    "manual_workaround": "",
    "dependency_mapping": "",
    "recovery_priorities": "",
    "notes": "",
}

# -------- Additional Consultation Groups (Phase 2 scaffolding) --------

# Information Protection & Data Governance
DEFAULT_INFORMATION_PROTECTION = {
    "data_classification_status": "",
    "external_sharing_posture": "",
    "dlp_status": "",
    "retention_governance": "",
}

# Identity Governance & Privileged Access
DEFAULT_IDENTITY_GOVERNANCE = {
    "identity_lifecycle_maturity": "",
    "leaver_deprovisioning": "",
    "access_review_status": "",
    "privileged_access_model": "",
    "pim_pam_status": "",
    "break_glass_governance": "",
    "service_account_governance": "",
    "shared_account_usage": "",
    "legacy_authentication_status": "",
    "notes": "",
}

# SaaS, Application & Shadow IT Governance
DEFAULT_SAAS_GOVERNANCE = {
    "inventory_status": "",
    "critical_platforms": "",
    "sso_coverage": "",
    "mfa_coverage": "",
    "offboarding_process": "",
    "recovery_responsibility": "",
    "shadow_it_visibility": "",
    "oauth_app_governance": "",
    "notes": "",
}

# Asset, Configuration & Exposure Assurance
DEFAULT_ASSET_ASSURANCE = {
    "asset_inventory_maturity": "",
    "external_attack_surface_visibility": "",
    "vulnerability_remediation_maturity": "",
    "secure_configuration_baseline": "",
    "security_change_assurance": "",
    "unsupported_technology_status": "",
}

# Monitoring, Telemetry & Response Coverage
DEFAULT_MONITORING_ASSURANCE = {
    "monitoring_coverage": "",
    "log_sources_monitored": [],
    "log_retention": "",
    "out_of_hours_escalation": "",
    "response_authority": "",
    "detection_testing": "",
    "security_reporting_cadence": "",
    "known_coverage_gaps": "",
}

# Supplier & Third-Party Security
DEFAULT_SUPPLIER_ASSURANCE = {
    "supplier_assurance_maturity": "",
}

DEFAULT_THIRD_PARTY_ACCESS_PROFILE = {
    "access_present": "",
    "identity_model": "",
    "mfa_status": "",
    "time_limited": "",
    "monitored": "",
    "periodically_reviewed": "",
    "critical_supplier_dependencies": "",
    "contractual_security_requirements": "",
    "incident_notification": "",
    "exit_planning": "",
    "concentration_risk": "",
    "notes": "",
}

# Recovery Assurance
DEFAULT_RECOVERY_ASSURANCE = {
    "restore_testing": "",
    "immutability_status": "",
    "administrative_separation": "",
    "service_recovery_testing": "",
    "evidence_retained": "",
    "recovery_ownership": "",
    "notes": "",
}

# Incident Response Assurance
DEFAULT_IR_ASSURANCE = {
    "roles_defined": "",
    "business_decision_authority": "",
    "technical_response_authority": "",
    "tabletop_status": "",
    "out_of_band_communications": "",
    "crisis_communications": "",
    "regulatory_notification_readiness": "",
    "supplier_coordination": "",
    "lessons_learned_process": "",
    "notes": "",
}

# Assurance status registry (global + per-section)
ASSURANCE_STATUS_DEFAULT = {
    "default": "Unknown",
    "information_protection": "",
    "identity_governance": "",
    "saas_governance": "",
    "monitoring": "",
    "supplier_security": "",
    "recovery": "",
    "incident_response": "",
    "ot_iot": "",
    "payment_fraud": "",
    "application_security": "",
    "integration_assurance": "",
}

# --- Conditional module defaults ---
DEFAULT_OT_SECURITY_PROFILE = {
    "asset_inventory": "",
    "network_separation": "",
    "vendor_access": "",
    "patch_governance": "",
    "monitoring": "",
    "recovery_planning": "",
    "notes": "",
}

DEFAULT_PAYMENT_FRAUD_PROFILE = {
    "payment_processes_present": "",
    "change_verification": "",
    "dual_authorisation": "",
    "finance_mailbox_protection": "",
    "fraud_response_process": "",
    "notes": "",
}

DEFAULT_APPLICATION_SECURITY_PROFILE = {
    "secure_development_lifecycle": "",
    "code_repository_security": "",
    "secrets_management": "",
    "dependency_scanning": "",
    "application_security_testing": "",
    "api_inventory": "",
    "notes": "",
}

DEFAULT_INTEGRATION_ASSURANCE_PROFILE = {
    "security_due_diligence": "",
    "new_site_security_baseline": "",
    "pre_connection_assurance": "",
    "identity_integration": "",
    "supplier_review": "",
    "integration_tracking": "",
    "notes": "",
}
