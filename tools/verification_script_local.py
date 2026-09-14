#!/usr/bin/env python3
import json
import sys
import os

from prompts import MaturityReport
from export import create_maturity_docx


def build_minimal_report(profile: dict) -> MaturityReport:
    # Deterministic skeleton ensuring all placeholders are populated
    sav_label = str(profile.get("savviness_label", ""))
    if (
        str(profile.get("mfa_status")) in ["None", "Privileged Accounts Only"]
        or str(profile.get("patching")) == "Manual / Ad-hoc"
        or str(profile.get("backups")) in ["No Formal Backups", "On-Premise Only"]
    ):
        pillar = "Pillar 1"
    else:
        pillar = "Pillar 2" if "Proactive" in sav_label else "Pillar 3" if "Adaptive" in sav_label else "Pillar 2"

    base_domains = [
        "Identity & Access", "Information Protection", "SaaS Governance", "Asset Assurance",
        "Monitoring & Detection", "Supplier Assurance", "Third-Party Access", "Recovery Assurance",
        "Incident Response", "Network & Edge", "Email Security", "Endpoint Security", "Cloud Security",
        "Application Security", "AI Governance"
    ]

    assembled = {
        "executive_summary": (
            f"The organisation operates in {profile.get('industry','Unknown')} with approximately "
            f"{profile.get('users',0)} users. Key crown jewels include {profile.get('critical_infra','Unknown')}."
            " This assessment synthesises governance evidence, operational telemetry, and risk posture to produce a phased roadmap."
        ),
        "executive_summary_actions": [
            "Enforce universal MFA across identities",
            "Implement immutable backup strategy",
            "Automate patch management across OS and third-party software"
        ],
        "executive_summary_action_blocks": [
            {
                "title": "Identity Hardening",
                "actions": [
                    "Deploy Conditional Access enforcing MFA",
                    "Disable legacy authentication",
                    "Implement break-glass governance with periodic review"
                ]
            },
            {
                "title": "Data Resilience",
                "actions": [
                    "Deploy offsite immutable backups for critical workloads",
                    "Run monthly representative restore tests",
                    "Document administrative separation for backup systems"
                ]
            }
        ],
        "resiliency_matrix_mapping": pillar,
        "cost_of_inaction": (
            "Without immediate remediation, the likelihood of business-impacting incidents remains elevated."
            " Ransomware, credential compromise, and configuration drift could lead to prolonged downtime and data loss."
        ),
        "domain_assessments": [
            {
                "domain_name": name,
                "current_maturity_level": pillar,
                "current_state_analysis": f"Baseline analysis for {name}: policies, controls, and telemetry reviewed.",
                "business_impact_narrative": f"Insufficient coverage in {name} may lead to increased exposure and operational risk.",
                "critical_gaps": ["Gap: Missing policies or controls", "Gap: Coverage limited or untested"],
                "remediation_rationale": f"Prioritise {name} hardening to reduce risk and align to roadmap objectives."
            }
            for name in base_domains
        ],
        "phased_roadmap": [
            {
                "phase_title": "Phase 1",
                "primary_objective": "Stabilise hygiene foundations",
                "milestones": ["Enforce universal MFA", "Establish immutable backups", "Automate patching"],
                "business_value_delivered": "Reduced risk of compromise and faster recovery",
                "resource_requirements": "Identity engineer, backup admin, RMM specialist"
            },
            {
                "phase_title": "Phase 2",
                "primary_objective": "Strengthen detection and response",
                "milestones": ["Expand telemetry coverage", "Runbook-driven incident handling", "Periodic tabletop exercises"],
                "business_value_delivered": "Improved MTTR and organisational readiness",
                "resource_requirements": "SOC analyst, IR lead"
            },
            {
                "phase_title": "Phase 3",
                "primary_objective": "Adaptive security and automation",
                "milestones": ["SOAR-driven remediation", "Zero Trust Architecture uplift", "Continuous BAS programme"],
                "business_value_delivered": "Operational efficiency and resilience",
                "resource_requirements": "Automation engineer, security architect"
            }
        ],
        "success_metrics": [
            "Reduce mean time to respond (MTTR) through improved monitoring and runbooks",
            "Increase MFA enforcement coverage across all identities",
            "Improve backup immutability and restore assurance through regular testing",
        ],
        "engagement_cadence": [
            "Monthly governance review",
            "Quarterly roadmap checkpoint",
            "Annual strategic reset with the Board",
        ],
        "consultant_discovery_guide": [
            "What are the Crown Jewels and their data flows?",
            "What is the acceptable downtime tolerance (RTO)?",
            "Where is MFA enforced across identities and services?",
            "How are backups validated and how often?",
        ],
        "partnership_details": (
            "Planet IT will partner to deliver a co-managed or fully managed engagement focused on measurable outcomes,"
            " repeatable governance ceremonies, and continuous improvement."
        ),
        "partnership_links": [],
        "threat_intelligence_context": "Industry threat context summarised: phishing, ransomware, and exploitation of misconfigurations are prevalent.",
        "microsoft_healthchecks_recommendations": "Execute Microsoft Health Checks to identify misconfigurations and apply hardening baselines.",
        "proactive_testing_programme": "Adopt a continuous proactive testing programme including BAS and purple teaming to validate controls.",
        "incident_response_plan_outline": "Establish IR governance, roles, OOB comms, and tested playbooks with periodic exercises.",
        "disaster_recovery_plan_outline": "Define recovery priorities, test restores, and ensure separation and immutability for critical backups."
    }

    # Validate assembled dict against Pydantic model
    try:
        return MaturityReport.model_validate(assembled)
    except Exception as e:
        print("LOCAL SMOKE: validation failed:", e)
        # Attempt minimal recovery by pruning unknown keys or adjusting types if necessary
        return MaturityReport.model_validate(assembled)


def main() -> int:
    # Load sample profile (acts as client_inputs)
    try:
        with open("examples/sample_profile_full.json", "r") as f:
            profile = json.load(f)
    except Exception as e:
        print("LOCAL SMOKE: load profile failed:", e)
        return 1

    # Build deterministic report without network calls
    report = build_minimal_report(profile)
    if not report:
        print("LOCAL SMOKE: report build failed")
        return 1

    # Export DOCX and write to exports/
    try:
        data = create_maturity_docx(profile, report)
        out_dir = "exports"
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "Local_Smoke_Maturity_Report.docx")
        with open(out_path, "wb") as f:
            f.write(data)
        print("LOCAL SMOKE: DOCX bytes:", len(data), "->", out_path)
        return 0
    except Exception as e:
        print("LOCAL SMOKE: export failed:", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())