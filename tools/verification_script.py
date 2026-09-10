"""End‑to‑end verification for the Maturity export pipeline.

- Validates Pydantic schema constraints (10 domains, presence of 'ai' in RadarChartData)
- Generates a DOCX via export.create_maturity_docx using a minimal but valid MaturityReport
- Confirms non‑zero byte output and prints concise pass/fail results
"""

import io
import os
import sys
# Ensure project root is on sys.path when executed as tools/verification_script.py
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from prompts import (
    MaturityReport, DomainAssessment, RoadmapPhase, RadarChartData, ExecutiveSummaryActionBlock
)
from export import create_maturity_docx

# 1) Schema assertions via model_json_schema (Pydantic v2‑friendly)
schema = MaturityReport.model_json_schema()
radar_entry = schema.get('properties', {}).get('radar_chart_data', {})
radar_props = radar_entry.get('properties', {})
# Pydantic v2 nests sub-models via $ref in $defs; resolve if needed
if not radar_props:
    ref = radar_entry.get('$ref')
    if isinstance(ref, str) and ref.startswith('#/$defs/'):
        def_name = ref.split('/')[-1]
        radar_def = (schema.get('$defs', {}) or {}).get(def_name, {})
        radar_props = radar_def.get('properties', {})
if 'ai' not in radar_props:
    raise SystemExit("SCHEMA_FAIL: RadarChartData is missing 'ai' property (ref-resolved)")

domains_schema = schema.get('properties', {}).get('domain_assessments', {})
min_items = domains_schema.get('minItems')
max_items = domains_schema.get('maxItems')
if min_items != 15 or max_items != 19:
    raise SystemExit("SCHEMA_FAIL: domain_assessments must have minItems=15 and maxItems=19")

# 2) Build a minimal, valid report instance (British English text) with 15 standard domains
sample_domains = []
for i in range(15):
    sample_domains.append(DomainAssessment(
        domain_name=f"Test Domain {i+1}",
        current_maturity_level="Pillar 2: Proactive Cybersecurity",
        current_state_analysis="This is a short, flowing paragraph describing the current state in British English. The analysis avoids bullet points and summarises posture.",
        business_impact_narrative="A concise narrative outlining business impact tied to RTO and regulatory exposure. This avoids formulas and hyperlinks and uses flowing prose.",
        critical_gaps=["Gap A", "Gap B"],
        vendor_agnostic_quick_wins=["Enable native logging", "Tighten conditional access"],
        recommended_solutions=[
            "Deploy managed detection to reduce time to neutralisation.",
            "Implement immutable backups to reduce data‑loss impact.",
            "Harden identity policies to reduce credential misuse."
        ],
        remediation_rationale="Multi‑paragraph rationale compressed for test purposes. It explains why the recommended capability severs the attack path in operational terms.",
        shared_responsibility="Planet IT configures and monitors; the Client enforces HR policy and user adherence.",
        gap_remediation_steps=["Step 1", "Step 2", "Step 3"]
    ))

phases = [
    RoadmapPhase(
        phase_title="Phase 1: Foundational Hygiene",
        timeline="0-3 Months",
        primary_objective="Stabilisation and baseline hardening",
        key_deliverables=["MFA enforcement", "Automated patching", "Immutable backups"],
        estimated_effort="Low Effort / High Impact",
        milestones=["Deploy MFA", "Roll out RMM", "Configure backups"],
        resource_requirements="Planet IT SOC, Internal IT Team",
        business_value_delivered="Rapid risk reduction across identity, endpoint, and recovery."
    ),
    RoadmapPhase(
        phase_title="Phase 2: Active Managed Defence",
        timeline="3-9 Months",
        primary_objective="Human‑led threat hunting and response",
        key_deliverables=["MDR onboarding", "Exposure management", "Phishing simulations"],
        estimated_effort="Moderate Effort / Operational Shift",
        milestones=["MDR live", "External EASM", "Training programme"],
        resource_requirements="Planet IT SOC, Client stakeholders",
        business_value_delivered="Reduced dwell time and measurable operational resilience."
    ),
    RoadmapPhase(
        phase_title="Phase 3: Adaptive Governance & Resilience",
        timeline="10-18+ Months",
        primary_objective="Automation and adaptive controls",
        key_deliverables=["SOAR automation", "Zero‑Trust expansion", "Automated DR"],
        estimated_effort="High Effort / Transformational",
        milestones=["SOAR playbooks", "ZTA policies", "DR orchestration"],
        resource_requirements="Planet IT SOC, Internal IT Team",
        business_value_delivered="Sustained resilience and reduced recovery time."
    ),
]

report = MaturityReport(
    executive_summary="Multi‑paragraph executive summary in British English explaining context, risk, and roadmap.",
    executive_summary_actions=[
        "Missing universal MFA — Enforce Conditional Access",
        "Manual patching — Implement automated RMM",
        "On‑premise only backups — Adopt immutable offsite backups",
    ],
    executive_summary_action_blocks=[
        ExecutiveSummaryActionBlock(
            heading="Universal MFA not enforced",
            finding="Paragraph summarising current gap in British English.",
            risk="Risk tied to the Crown Jewels and RTO.",
            remediation_actions=["Enforce MFA", "Condition access policies", "Review exceptions", "Phase roll‑out"]
        ),
        ExecutiveSummaryActionBlock(
            heading="Manual patching across servers",
            finding="Paragraph summarising current gap in British English.",
            risk="Risk tied to exploitable CVEs.",
            remediation_actions=["Deploy RMM", "Automate third‑party updates", "Monitor success", "Report compliance"]
        ),
        ExecutiveSummaryActionBlock(
            heading="Backups not immutable",
            finding="Paragraph summarising current gap in British English.",
            risk="Risk tied to ransomware and recovery uncertainty.",
            remediation_actions=["Adopt immutable backups", "Test restores", "Protect credentials", "Document runbooks"]
        ),
    ],
    radar_chart_data=RadarChartData(
        iam=2,
        privileged_access=2,
        endpoint=2,
        network=2,
        email=2,
        cloud=2,
        saas=2,
        data_security=2,
        secops=2,
        testing=2,
        supplier=2,
        resilience=2,
        culture=2,
        grc=2,
        ai=2,
    ),
    resiliency_matrix_mapping="Pillar 2: Proactive Cybersecurity",
    cost_of_inaction="Multi‑paragraph narrative on the operational and financial consequences of inaction.",
    monetary_cost_of_inaction=None,
    partnership_details="",
    compliance_alignment=None,
    microsoft_healthchecks_recommendations="",
    domain_assessments=sample_domains,
    phased_roadmap=phases,
    success_metrics=["Reduce MTTR", "Increase MFA coverage", "Improve backup immutability"],
    engagement_cadence=["Monthly governance", "Quarterly roadmap review", "Annual strategic reset"],
    consultant_discovery_guide=["What are the Crown Jewels?", "What is the RTO?", "Do you have cyber insurance?", "Where is MFA enforced?", "How are backups tested?"],
)

# 3) Run export pipeline
client_inputs = {
    "customer_name": "TestCorp",
    "consultant_name": "TestConsultant",
    "industry": "Technology",
    "users": 250,
    "endpoints": 300,
    "servers": 50,
    "operating_systems": "Windows, Linux",
    "cloud_env": "Azure",
    "in_house_team": "No",
    "compliance": "ISO 27001",
    "critical_infra": "ERP",
    "mdr_provider": "Sophos MDR",
    "endpoint": "Sophos",
    "endpoint_posture": "EDR Deployed (Endpoint Detection & Response)",
    "firewall": "Sophos",
    "identity": "Microsoft Entra ID (Azure AD)",
    "email": "Mimecast",
    "m365_license": "M365 Business Premium",
    "savviness": "Pillar 2: Proactive Culture",
    "pentest_status": "Annual",
    "vuln_scanning": "Monthly Authenticated",
    "remote_access": "VPN with Conditional Access",
    "saas_backup": "Dedicated Third-Party SaaS Backup",
    "ir_readiness": "Documented IR Plan (Untested)",
    "mfa_status": "Universal / Conditional Access",
    "patching": "Automated (OS & Third-Party)",
    "backups": "Immutable / Air-Gapped",
    "insurance": "Active Policy",
    "rto": "12-24 Hours",
    "advanced_controls": "ZTA, SOAR",
}

try:
    doc_bytes = create_maturity_docx(client_inputs, report)
    assert isinstance(doc_bytes, (bytes, bytearray)) and len(doc_bytes) > 10000
    print("DOCX_RENDER_OK: length=", len(doc_bytes))
except Exception as e:
    raise SystemExit("DOCX_RENDER_FAIL: " + str(e))

print("VERIFICATION_COMPLETE")