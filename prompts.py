from __future__ import annotations
# prompts.py
import os
import datetime
import random
from pydantic import BaseModel, Field
from typing import List, Optional
from data import MATURITY_FRAMEWORK, ASSESSMENT_DOMAINS, RECOMMENDED_SOLUTION_MAP, DEFAULT_MATURITY_CONTEXT, FULLY_MANAGED_URL, CO_MANAGED_URL, COMPACT_VENDOR_WHITELIST_TEXT, DFE_2026_STANDARD_NAME, DFE_2026_CONTROLS
from consultation_helpers import (
    format_critical_asset_profile,
    format_service_resilience_profile,
    format_information_protection_profile,
    format_identity_governance_profile,
    format_saas_governance_profile,
    format_asset_assurance_profile,
    format_monitoring_assurance_profile,
    format_supplier_assurance_profile,
    format_recovery_assurance_profile,
    format_ir_assurance_profile,
    assurance_phrase,
)

# ==========================================
# PYDANTIC MODELS: THREAT SIMULATOR
# ==========================================
class TimelineEvent(BaseModel):
    timestamp: str = Field(description="The timestamp of the event, e.g., '02:00 UTC'")
    event_description: str = Field(description="A detailed description of the attack progression or MDR intervention.")

class ThreatEvent(BaseModel):
    event_id: str = Field(description="Unique identifier for the threat event.")
    name: str = Field(description="Name of the threat event.")
    description: str = Field(description="Description of the event.")
    severity: int = Field(ge=1, le=3, description="Severity rating mapped to Pillar scoring: 1-3.")

class ThreatScenarioOutline(BaseModel):
    title: str = Field(description="Title of the threat scenario outline.")
    executive_summary: str = Field(description="Executive summary describing the scenario at a high level.")
    timeline: List[str] = Field(description="Structured timeline steps for the threat scenario.", min_items=4, max_items=8)
    threat_events: List[ThreatEvent] = Field(description="Threat events composing the outline.", min_items=1)
    impact: Optional[str] = Field(default=None, description="Concise narrative of impact aligned to pillar scoring.")
    mitigations: Optional[List[str]] = Field(default=None, description="Mitigations for the threat scenario outline.", min_items=0, max_items=6)

class PillarScore(BaseModel):
    pillar_1: int = Field(ge=1, le=3, description="Pillar 1 score (Reactive).")
    pillar_2: int = Field(ge=1, le=3, description="Pillar 2 score (Proactive).")
    pillar_3: int = Field(ge=1, le=3, description="Pillar 3 score (Adaptive).")

class ThreatScenarioEnvelope(BaseModel):
    customer_id: str = Field(description="Client identifier for the engagement.")
    maturity_level: str = Field(description="Current maturity level, e.g., Pillar 1/2/3.")
    outline: ThreatScenarioOutline = Field(description="Threat scenario outline payload to be rendered into templates.")
    threat_payload: Optional[ThreatScenarioOutline] = Field(
        default=None,
        description="Extended threat scenario payload for internal rendering and potential future extension."
    )
class ThreatTimelines(BaseModel):
    without_sophos: List[TimelineEvent] = Field(
        description="The FULL unmitigated attack timeline showing what would occur WITHOUT Sophos MDR. Must span from initial access through to objective completion (exfiltration, encryption, or final objective). Do NOT include any MDR detection or intervention events.",
        min_items=5,
        max_items=12
    )
    with_sophos: List[TimelineEvent] = Field(
        description="The attack timeline WITH Sophos MDR interception. First event at start_time, last event at end_time (38-min MTTR). Must show detection, isolation, and neutralisation by Sophos MDR before objective completion.",
        min_items=5,
        max_items=12
    )

class ScenarioReport(BaseModel):
    narrative: str = Field(
        description="Threat narrative formatted in Markdown with the following sections: "
        "Section 1: Threat Actor & Initial Access (hyperlink MITRE T-codes and CVEs). "
        "Section 2: Attacker Progression (hypothetical modality; for Sections 1–4 rely ONLY on the client's current stack; no MDR assumptions). "
        "Section 3: Data Exfiltration (hypothetical path for staging and exfiltration without MDR, using the current stack). "
        "Section 4: Full Impact Delivery (hypothetical path to encryption/destruction or final objective without MDR, using the current stack). "
        "Alternative Viewpoint (MDR Vendor Interception): Apply the selected MDR vendor and explain how it would likely detect anomalies and neutralise before objective completion. "
        "Recommended Solutions (Post‑Scenario): Summarise the defence strategy in a consultative, third‑person tone; draw from the authorised solution map; do not use first‑ or second‑person."
    )
    timeline: List[TimelineEvent] = Field(
        description="Section 5: The chronological attack timeline showing the WITH-Sophos MDR version. First event at start_time, last event at end_time (38-min MTTR).",
        min_items=5,
        max_items=12,
    )
    timelines: ThreatTimelines = Field(
        description="Dual timelines: one showing the unmitigated attack path (without_sophos) and one showing the MDR-protected path (with_sophos)."
    )

# =============================================================
# PYDANTIC MODELS: CYBERSECURITY MATURITY ASSESSMENT
# =============================================================
class DomainAssessment(BaseModel):
    domain_name: str = Field(description="The exact name of the security domain.")
    current_maturity_level: str = Field(description="Must be exactly one of: 'Pillar 1: Reactive Cybersecurity', 'Pillar 2: Proactive Cybersecurity', or 'Pillar 3: Adaptive Cybersecurity'.")
    current_state_analysis: str = Field(
        description="A comprehensive analysis of the current posture. You must write a minimum of two detailed paragraphs. Bullet points are strictly prohibited."
    )
    business_impact_narrative: str = Field(
        description="A board-ready business impact statement written in flowing, descriptive paragraphs. Convey the probability and severity of exploitation in natural language—do NOT display formula notation (e.g. 'Probability x Impact = Risk Score'), raw numerical scores, or clickable Markdown hyperlinks. You may reference relevant MITRE technique codes as inline plain text (e.g., 'T1189') where they add technical precision, but do NOT wrap them in Markdown link syntax. Tie the consequences directly to the client's Crown Jewels, Downtime Tolerance (RTO), Cyber Insurance status, and regulatory exposure. Write in full, descriptive sentences. Bullet points are strictly prohibited."
    )
    critical_gaps: List[str] = Field(description="2-3 specific architectural or operational gaps identified.", min_items=2, max_items=3)
    vendor_agnostic_quick_wins: List[str] = Field(description="2-3 zero-cost, native configuration changes.", min_items=2, max_items=3)
    recommended_solutions: List[str] = Field(description="Consultative recommendations written as flowing British English paragraphs. Provide 3–4 concise, narrative items that explain the operational need and capability rationale first, then (optionally) conclude with 'Product Example: <vendor>' drawn from the authorised solution map. Avoid rigid 'Risk | Need | Capability' patterns.", min_items=3, max_items=4)
    remediation_rationale: str = Field(
        description="The strategic, architectural justification. Explain the behaviour of the attack path and why this specific tool severs it. Must be a detailed, multi-paragraph narrative."
    )
    shared_responsibility: str = Field(description="The accountability split. Clarify exactly what Planet IT will deploy or manage versus what the Client is responsible for (e.g., HR policy enforcement, user adherence).")
    gap_remediation_steps: Optional[List[str]] = Field(
        description="Remediation steps to fill the gaps in this domain. Typically 3–5 concrete actions.",
        default=None,
        min_items=3,
        max_items=5
    )
    weighted_contribution_percent: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Per-domain weighted contribution (0–100) used by the maturity gauge: round(MATURITY_WEIGHTS[domain_key] * (radar score/3) * 100). STRICT: honour 3‑point cap and Capability Mismatch guardrails."
    )

class RoadmapPhase(BaseModel):
    phase_title: str = Field(description="Must be strictly named: Phase 1: Foundational Hygiene, Phase 2: Active Managed Defence, Phase 3: Adaptive Governance & Resilience.")    
    timeline: str = Field(description="e.g., '0-3 Months', '3-9 Months', '10-18+ Months'.")
    primary_objective: str = Field(description="The overarching objective of this phase.")
    key_deliverables: List[str] = Field(description="3-4 deliverables for this phase.", min_items=3, max_items=4)
    estimated_effort: str = Field(description="Categorise the effort required for this phase.")
    milestones: List[str] = Field(description="Milestones for this phase.", min_items=3, max_items=5)
    resource_requirements: str = Field(description="Who executes this phase.")
    business_value_delivered: str = Field(description="What business value is delivered by completing this phase.")

class DomainAssessmentsBatch(BaseModel):
    domain_assessments: List[DomainAssessment] = Field(description="Batch of domain assessments.", min_items=5, max_items=19)

def build_maturity_header_prompt(client_inputs) -> str:
    """Build a compact header prompt for MaturityHeader generation.
    The prompt requests a structured header payload tailored for staged maturity output.
    This version enforces full population of Roadmap phases and governance fields to reduce missing data in downstream rendering.
    """
    customer = client_inputs.get('customer_name', 'the client')
    industry = client_inputs.get('industry', 'their industry')
    return (
        f"Generate a MaturityHeader payload for {customer} in {industry}. "
        + "Provide the following fields in a structured, JSON-like payload: "
        + "executive_summary; executive_summary_actions (3 items); executive_summary_action_blocks (3 blocks); "
        + "radar_chart_data; resiliency_matrix_mapping; programme_controls; phased_roadmap (exactly 3 phases; each phase must include: phase_title, timeline, primary_objective, key_deliverables (3–4 items), estimated_effort, milestones (3–5 items), resource_requirements, business_value_delivered); "
        + "microsoft_healthchecks_recommendations; compliance_alignment; proactive_testing_programme; incident_response_plan_outline; disaster_recovery_plan_outline; "
        + "optional: success_metrics; engagement_cadence; consultant_discovery_guide; (for each optional list, include min_items/max_items constraints in the returned payload as part of the JSON)."
        + " Use British English. Output should be parse-friendly by Pydantic models."
    )

def build_domain_batch_prompt(client_inputs, domains_subset) -> str:
    """Build a compact domain batch prompt for DomainAssessmentsBatch generation.
    Instruct the model to return a DomainAssessmentsBatch payload containing domain_assessments
    for the provided domain names. Keep language concise and UK English.
    """
    domain_list = ", ".join(domains_subset) if domains_subset else ""
    customer = client_inputs.get('customer_name', 'the client')
    return (
        f"Generate a DomainAssessmentsBatch payload for {customer} covering domains: {domain_list}. "
        + "Output a JSON-like payload with a top-level key 'domain_assessments' containing an array of domain objects. "
        + "Each domain object must conform to DomainAssessment schema (domain_name, current_maturity_level, etc.). "
        + "Keep text concise and in British English."
    )


class RadarChartData(BaseModel):
    # Identity
    iam: int = Field(description="Score 1, 2, or 3. STRICT RULE: Must be exactly 1 if MFA Enforcement is 'None' or 'Privileged Accounts Only'.")
    privileged_access: int = Field(description="Score 1, 2, or 3. Consider administrator account separation, PIM/PAM, service-account governance, and access reviews.")
    # Endpoint & Network
    endpoint: int = Field(description="Score 1, 2, or 3. STRICT RULE: Must be exactly 1 if Patch Management is 'Manual / Ad-hoc' or Endpoint Capability is 'Legacy AV Only'.")
    network: int = Field(description="Score 1, 2, or 3. STRICT RULE: Must be exactly 1 if Remote Access is 'Legacy VPN' or 'None'.")
    # Messaging & Cloud
    email: int = Field(description="Score 1, 2, or 3.")
    cloud: int = Field(description="Score 1, 2, or 3. STRICT RULE: Must be exactly 1 if SaaS Backup is 'None'.")
    # SaaS & Data
    saas: int = Field(description="Score 1, 2, or 3. Consider application inventory, SSO/MFA coverage, offboarding, OAuth consent governance, and shadow IT control.")
    data_security: int = Field(description="Score 1, 2, or 3. Consider classification/labels, retention, external sharing posture, and DLP governance.")
    # Operations & Assurance
    secops: int = Field(description="Score 1, 2, or 3. STRICT RULE: Must be exactly 1 if Incident Response Readiness is 'No Formal Plan'.")
    testing: int = Field(description="Score 1, 2, or 3. STRICT RULE: Must be exactly 1 if Penetration Testing cadence is 'None' or Vulnerability Scanning is 'None'.")
    supplier: int = Field(description="Score 1, 2, or 3. Consider supplier assurance maturity, third-party access model, and contractual security requirements.")
    resilience: int = Field(description="Score 1, 2, or 3. Consider restore testing, immutability, administrative separation, and service recovery exercises.")
    culture: int = Field(description="Score 1, 2, or 3. Consider reporting routes, follow-up/coaching, role-based training; do not include MFA or endpoint admin in this score.")
    grc: int = Field(description="Score 1, 2, or 3. STRICT RULE: Must be exactly 1 if Incident Response Readiness is 'No Formal Plan' or 'Untested'.")
    ai: int = Field(description="Score 1, 2, or 3. STRICT RULE: Must be exactly 1 if there is no AI usage policy, no monitoring for company AI/shadow AI, or evidence of uncontrolled AI use in context.")

class MonetaryCostGBP(BaseModel):
    amount_gbp: float = Field(description="GBP amount, must be non-negative.")
    source: Optional[str] = Field(default=None, description="Source of the cost estimate (e.g., industry baselines).")
    rationale: Optional[str] = Field(default=None, description="Rationale for the cost estimate and any key assumptions.")

class GapRemediationPlan(BaseModel):
    gap_description: str = Field(description="Description of the identified remediation gap.")
    recommended_actions: List[str] = Field(description="Action steps to remediate the gap.", min_items=2, max_items=6)
    owner: Optional[str] = Field(default=None, description="Owner responsible for remediation.")
    due_by: Optional[str] = Field(default=None, description="Due date ISO format (YYYY-MM-DD).")

class ComplianceSection(BaseModel):
    standard: str = Field(description="Compliance standard or control set (e.g., ISO 27001, NIST CSF).")
    critical_gaps: List[str] = Field(
        description="List of critical gaps within this standard.",
        min_items=2,
        max_items=6,
    )
    fill_plan: List[GapRemediationPlan] = Field(
        description="Remediation plan items for the gaps.",
        min_items=2,
        max_items=6,
    )

class ThreatScenarioItem(BaseModel):
    """A threat scenario linked to a maturity assessment, auto-generated from gaps."""
    id: str = Field(description="Unique identifier for the threat scenario, e.g. 'ts-maturity-1'.")
    name: str = Field(description="Display name for the threat scenario.")
    incident_type: str = Field(description="Pillar mapping for this scenario, e.g. 'Pillar 1: Reactive Cybersecurity'.")
    narrative: str = Field(description="Full Markdown narrative describing the threat scenario.")

class ExecutiveSummaryActionBlock(BaseModel):
    heading: str = Field(description="Short headline for the recommendation, e.g., 'Legacy endpoint protection with no EDR capability'. British English.")
    finding: str = Field(description="1–2 paragraphs describing the current gap/finding in British English. Bullet points are prohibited.")
    risk: str = Field(description="Concise board-level risk statement tied to Crown Jewels, RTO, and insurance/regulatory context. Bullet points are prohibited.")
    remediation_actions: List[str] = Field(description="Concrete remediation steps. Provide 4–8 actions.", min_items=4, max_items=8)

class ProgrammeControls(BaseModel):
    phishing_simulations: str = Field(description="Phishing simulation cadence, e.g., 'Monthly', 'Quarterly', 'Annually', or 'Never'.")
    security_training_programme: str = Field(description="Security awareness training programme description.")
    endpoint_privileges: str = Field(description="Endpoint privilege telemetry status, e.g., 'Zero Trust (No Local Admins/LAPS)'.")
    reporting_routes: str = Field(description="Reporting routes status, e.g., 'One-click report (mail client)'.")
    followup_coaching: str = Field(description="Follow-up coaching approach.")
    role_based_training: str = Field(description="Role-based training coverage.")
    leadership_engagement: str = Field(description="Leadership engagement cadence.")
    policy_acknowledgement: str = Field(description="Policy acknowledgement cadence.")
    phish_failure_rate_90d: Optional[int] = Field(default=None, ge=0, le=100, description="Phish failure rate over the last 90 days (percent).")
    report_rate_90d: Optional[int] = Field(default=None, ge=0, le=100, description="Report rate over the last 90 days (percent).")
    calculated_culture_score: Optional[int] = Field(default=None, ge=0, le=14, description="Calculated culture score (0–14) from behavioural measures.")
    culture_tier: Optional[str] = Field(default=None, description="Culture tier label, e.g., 'Pillar 1: Reactive Culture', 'Pillar 2: Proactive Culture', or 'Pillar 3: Adaptive Culture'.")

class MaturityHeader(BaseModel):
    executive_summary: str = Field(description="A concise executive summary for the three-phased maturity roadmap.")
    executive_summary_actions: List[str] = Field(description="Exactly three 'Finding — Action' items.", min_items=3, max_items=3)
    executive_summary_action_blocks: List[ExecutiveSummaryActionBlock] = Field(description="Three structured recommendation blocks carrying Heading, Finding, Risk, and Remediation actions.", min_items=3, max_items=3)
    radar_chart_data: RadarChartData = Field(description="Radar scores for the three pillars.")
    resiliency_matrix_mapping: str = Field(description="Explicit mapping of radar scores to Pillars 1-3.")
    phased_roadmap: List[RoadmapPhase] = Field(description="Three sequential roadmap phases.", min_items=3, max_items=3)
    threat_scenarios: Optional[List["ThreatScenarioItem"]] = Field(
        default=None,
        description="Auto-generated threat scenarios populated via maturity-gap analysis. Set after initial report generation.",
        min_items=1,
        max_items=3
    )
    cost_of_inaction: Optional[str] = Field(default=None, description="A brief cost-of-inaction narrative to accompany the maturity header.")
    # Optional fields (keep optional to preserve compatibility)
    success_metrics: Optional[List[str]] = Field(default=None, description="3-4 measurable KPIs.", min_items=3, max_items=4)
    engagement_cadence: Optional[List[str]] = Field(default=None, description="Schedule of advisory meetings.", min_items=3, max_items=6)
    consultant_discovery_guide: Optional[List[str]] = Field(default=None, description="Provocative questions for the discovery phase.", min_items=5, max_items=10)
    microsoft_healthchecks_recommendations: Optional[str] = Field(default=None, description="Recommendations for Microsoft healthchecks and hardening when Microsoft tools are used.")
    compliance_alignment: Optional[List[ComplianceSection]] = Field(default=None, description="Structured alignment of compliance standards and identified gaps with remediation plans.", min_items=1, max_items=3)
    proactive_testing_programme: Optional[str] = Field(default=None, description="Narrative for proactive security testing.")
    incident_response_plan_outline: Optional[str] = Field(default=None, description="Incident Response plan outline.")
    disaster_recovery_plan_outline: Optional[str] = Field(default=None, description="Disaster Recovery plan outline.")
    programme_controls: Optional[ProgrammeControls] = Field(default=None, description="Structured programme controls reflecting behavioural measures and telemetry from the consultation (security culture).")

class MaturityReport(BaseModel):
    executive_summary: str = Field(description="A detailed, multi-paragraph C-level executive summary of the business risk and overall posture. You MUST include context on the threat landscape for their specific industry, the financial and reputational impact of a breach to their specific Crown Jewels, and a high-level strategic roadmap summary. Write this specifically for a CISO, IT Director, or Board of Directors audience. Minimum 3 paragraphs.")
    executive_summary_actions: List[str] = Field(description="Exactly three 'Finding — Action' bullet points that summarise the top findings and the specific remediation action required. Provide precisely three items; each item must be a single concise sentence formatted as 'Finding — Action' in British English, vendor-agnostic, and directly tied to the executive summary.", min_items=3, max_items=3)
    executive_summary_action_blocks: List[ExecutiveSummaryActionBlock] = Field(description="Three structured recommendation blocks carrying Heading, Finding, Risk, and Remediation actions.", min_items=3, max_items=3)
    radar_chart_data: RadarChartData = Field(description="Scores of 1, 2, or 3 mapping directly to the Resiliency Matrix pillars.")
    resiliency_matrix_mapping: str = Field(description="Explicitly map the customer within the Cyber Resiliency Matrix: Pillar 1, Pillar 2, or Pillar 3.")
    cost_of_inaction: Optional[str] = Field(default=None, description="A detailed, multi-paragraph narrative explaining the severe operational, financial, and reputational consequences if this strategic roadmap is ignored. You must explicitly tie this to their stated Downtime Tolerance (RTO), their Cyber Insurance status, and potential regulatory fines or loss of client trust. Make the business case for investment undeniable. Minimum 2 paragraphs. Bullet points are strictly prohibited.")
    monetary_cost_of_inaction: Optional[MonetaryCostGBP] = Field(default=None, description="Monetary cost estimate for inaction (GBP). Grounded in credible baselines; see MonetaryCostGBP for details.")
    # Governance fields (deduplicated and aligned with PLAN requirements)
    partnership_details: Optional[str] = Field(default=None, description="Optional governance narrative or details for partnership engagement.")
    partnership_links: Optional[List[str]] = Field(default=None, description="Optional list of governance resource URLs or documents.", min_items=1, max_items=5)
    threat_intelligence_context: Optional[str] = Field(default=None, description="Threat intelligence context relevant to the governance narrative.")
    cost_of_inaction_summary: Optional[str] = Field(default=None, description="Short GBP cost-of-inaction narrative derived from MonetaryCostGBP or explicit input.")
    compliance_alignment: Optional[List[ComplianceSection]] = Field(default=None, description="Structured alignment of compliance standards and identified gaps with remediation plans.", min_items=1, max_items=3)
    partnership_outline: Optional[str] = Field(
        default=None,
        description="Dedicated section describing co-managed or fully managed partnership arrangements and responsibilities between Planet IT and the client."
    )
    microsoft_healthchecks_recommendations: Optional[str] = Field(default=None, description="Recommendations for Microsoft healthchecks and hardening when Microsoft tools are used.")
    
    # Proactive testing, IR and DR programme outlines
    proactive_testing_programme: Optional[str] = Field(default=None, description="A comprehensive, narrative programme for proactive security validation: penetration testing cadence (external, internal, web app/API), continuous exposure management, breach-and-attack simulation/ATT&CK emulation, and phishing exercises. Reference CREST/NCSC CHECK where appropriate. Minimum 2 paragraphs. Bullet points are strictly prohibited.")
    incident_response_plan_outline: Optional[str] = Field(default=None, description="A narrative outline of the Incident Response Plan: roles/RACI, communications tree, top playbooks mapped to likely incidents, integration with any IR retainer, and a quarterly tabletop testing schedule. Minimum 2 paragraphs. Bullet points are strictly prohibited.")
    disaster_recovery_plan_outline: Optional[str] = Field(default=None, description="A narrative outline of the Disaster Recovery Plan: RTO/RPO mapping for critical systems, backup immutability/air-gapping, failover/runbook procedures, and DR test cadence. Must reference the provided RTO where available. Minimum 2 paragraphs. Bullet points are strictly prohibited.")
    
    # --- DOMAIN LENGTH (UPDATED) ---
    domain_assessments: List[DomainAssessment] = Field(
        description="Generate assessments for the 15 standard domains and include conditional domains when applicable based on evidence. This array must contain at least 15 items (standard domains) and may include up to 19 items including conditional domains.",
        min_items=15,
        max_items=19
    )
    
    # --- LOCKED ROADMAP LENGTH ---
    phased_roadmap: List[RoadmapPhase] = Field(
        description="You MUST generate exactly 3 sequential roadmap objects tracking Phases 1, 2, and 3. This array must contain exactly 3 items.",
        min_items=3,
        max_items=3
    )
    
    success_metrics: Optional[List[str]] = Field(default=None, description="3-4 measurable KPIs.", min_items=3, max_items=4)
    engagement_cadence: Optional[List[str]] = Field(default=None, description="Schedule of advisory meetings.", min_items=3, max_items=6)
    consultant_discovery_guide: Optional[List[str]] = Field(default=None, description="Provocative questions for the discovery phase.", min_items=5, max_items=10)
    threat_scenarios: Optional[List[ThreatScenarioItem]] = Field(
        default=None,
        description="Auto-generated threat scenarios populated via maturity-gap analysis. Set after initial report generation.",
        min_items=1,
        max_items=3
    )
    programme_controls: Optional[ProgrammeControls] = Field(default=None, description="Structured programme controls reflecting behavioural measures and telemetry from the consultation (security culture).")

# ==========================================
# CONTEXT INJECTION & MASTER PERSONA
# ==========================================
context_injection = DEFAULT_MATURITY_CONTEXT

SYSTEM_PERSONA = f''' 

- Evaluate clients against the Planet IT Cyber Resiliency Matrix. Map them strictly to Pillar 1 (Reactive), Pillar 2 (Proactive), or Pillar 3 (Adaptive).
- CONTEXTUAL REASONING REQUIREMENT: You must explicitly tie technical gaps in the domains to the customer's Crown Jewels, Industry, and submitted Operational Telemetry (e.g., RTO, Insurance requirements). Explain the operational and financial impact of a failure.
- ROADMAP USABILITY: Structure the roadmap as a long-tail business transformation plan stretching into advanced Adaptive capabilities. Define clear objectives, required resources, and the tangible business value delivered at the end of each phase.
- Analyse the provided penetration testing frequency and vulnerability scanning posture. Recommend continuous exposure management if lacking.
- Lead with Vendor-Agnostic Quick Wins tailored to their specific environment.
- Strongly articulate the "Cost of Inaction".

### SOPHOS AI-NATIVE CYBER DEFENSE SYSTEM (JULY 2026+)
Sophos has launched the industry's first AI-Native Cyber Defense System, a unified architecture where endpoint, network, email, cloud, identity, SIEM, threat intelligence, and MDR operate as one system within Sophos Central. Key capabilities include: agentic AI-led continuous threat hunting; SOAR automation playbooks with expanded two-way third-party response actions; vendor-agnostic email monitoring (EMS) included with both Sophos MDR and Sophos MDR Plus; thousands of additional detectors from the Secureworks Counter Threat Unit; and an optional Next-Gen SIEM add-on for compliance data retention (1, 3, 5, 7, or 10 years). When recommending Sophos MDR or Sophos MDR Plus, always reference these capabilities as the current-state offering.

### MICROSOFT DEFENDER EXPERTS & DART AWARENESS
If the client uses Microsoft Defender Experts for XDR (managed threat hunting) or holds a Microsoft DART retainer, recognise this as a Pillar 2 SecOps capability. However, the Capability Mismatch rule still applies absolutely: if automated patching, universal MFA, or immutable backups are missing, these Microsoft investments are crippled by poor operational hygiene and domain scores remain capped at Pillar 1. When Defender Experts is present, recommend Sophos MDR (powered by the AI-Native Cyber Defense System) for cross-vendor telemetry integration (firewalls, OT, third-party SaaS) and 24/7 human-led response. When DART is active, acknowledge the IR capability but stress that DART is reactive—operational 24/7 monitoring (via Sophos MDR) is still needed for sub-hour MTTR.

### IR RETAINER AWARENESS (VENDOR-AGNOSTIC)
If the client holds an active IR retainer with any provider (Microsoft DART, CrowdStrike, Mandiant, Unit 42, Kroll, Secureworks, Rapid7), acknowledge this as evidence of Pillar 2 incident response maturity in the SecOps domain. However, IR retainers are reactive by nature—proactive 24/7 MDR coverage is still essential for real-time threat neutralisation. If the client has both an IR retainer AND Sophos MDR Plus, note that MDR Plus includes full IR, making a separate retainer redundant unless required by cyber insurance policy mandates.

### VENDOR BAN CONSTRAINT
If the client has explicitly banned specific vendors, you MUST NOT recommend, mention, or suggest those vendors in any section of the report. Suggest functionally equivalent alternatives from other providers instead. If all viable vendors in a category are banned, state that a solution is required and Planet IT can advise on suitable alternatives.

### CONSULTATIVE VERBOSITY & FORMATTING
You are writing for a C-level and technical director audience. Terse, high-level summaries are unacceptable. 
* You must provide deep, narrative-driven reasoning for every assessment.
* Explain the 'why' behind every 'what'. 
* Bullet points and numbered lists are strictly prohibited within narrative fields (such as analysis, rationale, and summaries). You must write flowing, comprehensive paragraphs.
* Use UK English spellings (e.g., analyse, behaviour, programme).

 BACKGROUND KNOWLEDGE BASE:
 {context_injection}
'''

# ==========================================
# PROMPT BUILDERS
# ==========================================
def build_scenario_prompt(client_inputs, osint_data, attack_vector, custom_scenario=""):
    now = datetime.datetime.now(datetime.timezone.utc)
    start_time = (now - datetime.timedelta(minutes=38)).strftime("%H:%M UTC")
    end_time = now.strftime("%H:%M UTC")

    base_prompt = f"ENGAGEMENT DETAILS: Customer: {client_inputs['customer_name']} | Consultant: {client_inputs.get('consultant_name', 'Advisor')}\nCLIENT ENVIRONMENT: Industry: {client_inputs['industry']} | Users: {client_inputs.get('users', '500')} | Endpoints: {client_inputs.get('endpoints', '600')} | Servers: {client_inputs.get('servers', '50')} | Critical Asset: {client_inputs['critical_infra']} | Security Culture Tier: {client_inputs.get('savviness', 'Unknown')} | Stack: MDR/SOC: {client_inputs.get('mdr_provider', 'None')}, Endpoint: {client_inputs['endpoint']}, Email: {client_inputs['email']}, Firewall: {client_inputs['firewall']}, Identity: {client_inputs['identity']}"
    mdr_label = str(client_inputs.get('mdr_provider', '') or 'Sophos MDR')
    
    scenario_rules = f"""SCENARIO REQUIREMENTS:
    - Meta: Use cautious, hypothetical phrasing throughout ("could", "may", "would likely") unless citing concrete telemetry. Avoid absolute security claims (e.g., "prevent(s)", "ensure(s)", "guarantee(s)"); prefer "reduces likelihood" or "reduces exposure".
    - Section 1: Threat Actor & Initial Access — Initial Access: "{attack_vector if not custom_scenario else custom_scenario}" (hyperlink MITRE T-codes and CVEs).
    - Section 2: Attacker Progression — Hypothetical attempted movement toward {client_inputs['critical_infra']}. For Sections 1–4, rely ONLY on the client's current stack; do NOT assume any MDR presence.
    - Section 3: Data Exfiltration — Explain how data could be staged and exfiltrated without MDR given the current stack.
    - Section 4: Full Impact Delivery — Explain how the attacker would likely achieve encryption/destruction or other final objectives without MDR given the current stack.
    - Alternative Viewpoint (MDR Vendor Interception — With {mdr_label}): CRITICAL RULE — Under MDR coverage the attack MUST NOT succeed. Describe how {mdr_label} would likely identify behavioural anomalies mid-chain and neutralise before objective completion.
    - Recommended Solutions (Post‑Scenario): Summarise the defence strategy immediately after the scenario narrative. Where appropriate, draw from the authorised solution map (RECOMMENDED_SOLUTION_MAP), including IR/DR roundtables/planning under GRC and penetration testing options under Security Validation & Testing. Avoid banned vendors.
    - Section 5 (Attack Timeline — With {mdr_label}): Provide the WITH‑MDR timeline. The very first event MUST be anchored exactly at {start_time} and the final MDR neutralisation MUST be anchored exactly at {end_time} (reflecting a 38‑minute MTTR).
    - Section 6 (Attack Timeline — Without MDR): Provide a separate chronological timeline showing what would happen WITHOUT any MDR. This timeline must show the unmitigated attack path progressing through to objective completion (exfiltration, encryption, or final objective). Do NOT include any MDR detection or intervention events.
    """

    context_notes = client_inputs.get('context_notes', '')
    context_clause = f"\nCONSULTANT CONTEXT NOTES (Incorporate where relevant; do not quote verbatim; do not override guardrails): {context_notes}\n" if context_notes else ""
    reference_sample = client_inputs.get('reference_sample', '')
    anti_mimicry_clause = ""
    if reference_sample:
        anti_mimicry_clause = (
            "\nREFERENCE SAMPLE (TONE ONLY — DO NOT COPY):\n"
            f"{reference_sample}\n\n"
            "ANTI-MIMICRY DIRECTIVE: You MUST NOT replicate phrasing, sentence structure, paragraph ordering, or section wording from the reference sample. "
            "Target high stylistic dissimilarity. Vary sentence length and cadence, change rhetorical structure, and use different connective phrases. "
            "If any sentence would share more than 8 consecutive words with the sample, rewrite it.\n"
        )
    
    return f"Act as ROLE 1 and generate a highly technical breach scenario.\n{base_prompt}\nTHREAT INTELLIGENCE: {osint_data}{context_clause}{anti_mimicry_clause}\n{scenario_rules}"


def build_mdr_case_prompt(client_inputs, scenario_narrative):
    now = datetime.datetime.now(datetime.timezone.utc)
    start_time = (now - datetime.timedelta(minutes=38)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    end_time = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    case_id = f"#SR-{now.strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
    
    return f"""Act as ROLE 1. Translate the following threat narrative into a highly structured Sophos MDR Case Report.

NARRATIVE TO TRANSLATE:
{scenario_narrative}

CRITICAL INSTRUCTION: You must output ONLY the raw Markdown text matching the EXACT template below. Do not add any conversational filler, introductory text, or concluding remarks.

### MDR Case ID: {case_id}
**Customer:** {client_inputs['customer_name']}
**Date and Time:** {end_time}
**Severity:** Critical

#### Case Summary
[Write a concise, highly technical synopsis of the trigger, investigation, and attack progression based on the narrative.]

#### Observed MITRE Techniques
[List 3-5 observed tactics/techniques as bullet points, e.g., Process Injection, Living off the Land. Hyperlink to MITRE.]

#### Impacted Identities
[List 1-2 impacted accounts or roles, e.g., SYSTEM, Webserver, Local Admin.]

#### Artifacts
[Extract 2-3 technical artifacts from the narrative and format them EXACTLY as below]
**Artifact 1:**
* **Decoded command line:** [Specific command, script, or executable]
* **Command path:** [Specific file path, e.g., C:\\Windows\\System32\\cmd.exe]
* **Sophos PID:** [Generate a realistic formatted Sophos PID, e.g., 6012:134151631315154554]
* **Purpose:** [Brief explanation of what this artifact did in the attack]

#### Active Users
[List the active user context during execution, e.g., SYSTEM, ITAdmin.]

#### Timeline
[Provide a detailed, chronological timeline of the attack progression. You MUST use EXACT timestamps. The very first event MUST occur at {start_time} and the final neutralisation event MUST occur at {end_time}.]

#### 🛡️ Response Actions
[List 2-3 bullet points of ONLY authorised MDR actions taken by Sophos to neutralise the threat.]

#### ⚙️ Recommendations
[List 3-4 vendor-agnostic hardening steps.]
"""


def build_maturity_prompt(client_inputs):
    banned = client_inputs.get('banned_vendors', [])
    ban_clause = ""
    if banned:
        ban_list = ", ".join(banned)
        ban_clause = f"""
### VENDOR BAN CONSTRAINT (STRICT COMPLIANCE REQUIRED)
The client has explicitly banned the following vendors: [{ban_list}].
You MUST NOT recommend, mention, or suggest any of these banned vendors in any section of the report, including domain assessments, recommended solutions, phased roadmap, or any other field. Suggest functionally equivalent alternatives from other providers instead. If all viable vendors in a category are banned, state that a solution is required and Planet IT can advise on suitable alternatives.
"""
    base_prompt = f"""ENGAGEMENT DETAILS: Customer: {client_inputs['customer_name']} | Consultant: {client_inputs.get('consultant_name', 'Advisor')}
    CLIENT ENVIRONMENT: Industry: {client_inputs['industry']} | Users: {client_inputs.get('users', '500')} | Endpoints: {client_inputs.get('endpoints', '600')} | Servers: {client_inputs.get('servers', '50')} | Critical Asset: {client_inputs.get('critical_infra', 'Unknown')} | Security Culture Tier: {client_inputs.get('savviness', 'Unknown')} | Compliance Targets: {client_inputs.get('compliance', [])}

    STACK: MDR/SOC: {client_inputs.get('mdr_provider', 'None')} | Endpoint Vendor: {client_inputs.get('endpoint', 'Unknown')} | Endpoint Capability: {client_inputs.get('endpoint_posture', 'Unknown')} | Email: {client_inputs.get('email', 'Unknown')} | Firewall: {client_inputs.get('firewall', 'Unknown')} | Identity: {client_inputs.get('identity', 'Unknown')}
    NETWORK & DATA: Remote Access: {client_inputs.get('remote_access', 'Unknown')} | SaaS Backup (M365): {client_inputs.get('saas_backup', 'Unknown')}
    ADAPTIVE CONTROLS DEPLOYED: {client_inputs.get('advanced_controls', 'None')}
    PROACTIVE SECURITY TOOLS IN USE: {client_inputs.get('proactive_tools', 'None')}

    OPERATIONAL TELEMETRY & RISK FACTORS:
    - MFA Enforcement: {client_inputs.get('mfa_status', 'Unknown')}
    - Patch Management: {client_inputs.get('patching', 'Unknown')}
    - Infrastructure Backups: {client_inputs.get('backups', 'Unknown')}
    - Incident Response Readiness: {client_inputs.get('ir_readiness', 'Unknown')}
    - Elite IR Retainer: {client_inputs.get('ir_retainer', 'None')}
    - Cyber Insurance Status: {client_inputs.get('insurance', 'Unknown')}
    - Downtime Tolerance (RTO): {client_inputs.get('rto', 'Unknown')}
    - AI Usage Policy: {client_inputs.get('ai_usage_policy', 'Unknown')}
    - Approved Company AI Tools: {client_inputs.get('approved_ai_tools', 'None')}
    - Shadow AI Monitoring: {client_inputs.get('shadow_ai_monitoring', 'Unknown')}
    - AI Data Loss Controls: {client_inputs.get('ai_dlp_controls', 'None')}

    VALIDATION & TESTING CONTEXT: Pentest Frequency: {client_inputs.get('pentest_status', 'Unknown')} | Vuln Scanning: {client_inputs.get('vuln_scanning', 'Unknown')} | Notes: {client_inputs.get('validation_notes', 'None')}

    PARTNERSHIP STATUS & ENTITLEMENTS: Current Managed Service Status: {client_inputs.get('managed_service_status','None')} | Partnership Preference: {client_inputs.get('partnership_type','Unknown')} | Co-Managed Service Units (if any): {client_inputs.get('co_managed_units', 0)}
    """

    # Consultation Evidence Summaries (structured inputs)
    cap_summary = format_critical_asset_profile(client_inputs.get('critical_asset_profile', {}) or {})
    sr_summary = format_service_resilience_profile(client_inputs.get('service_resilience_profile', {}) or {})
    ip_profile = client_inputs.get('information_protection_profile') or client_inputs.get('information_protection') or {}
    idg_profile = client_inputs.get('identity_governance_profile') or client_inputs.get('identity_governance') or {}
    saas_profile = client_inputs.get('saas_governance_profile') or client_inputs.get('saas_governance') or {}
    asset_profile = client_inputs.get('asset_assurance_profile') or client_inputs.get('asset_assurance') or {}
    mon_profile = client_inputs.get('monitoring_assurance_profile') or client_inputs.get('monitoring') or {}
    supp_profile = client_inputs.get('supplier_assurance_profile') or client_inputs.get('supplier_security') or {}
    tpa_profile = client_inputs.get('third_party_access_profile') or {}
    rec_profile = client_inputs.get('recovery_assurance_profile') or client_inputs.get('recovery') or {}
    ir_profile = client_inputs.get('incident_response_assurance_profile') or client_inputs.get('incident_response') or {}

    evidence_block = """
### CONSULTATION EVIDENCE SUMMARIES (REFERENCE ONLY)
- Business Services & Sensitive Data (CAP):
{cap}

- Business Service Resilience:
{sr}

- Information Protection & Data Governance:
{ip}

- Privileged Access & Identity Governance:
{idg}

- SaaS, Application & Shadow IT Governance:
{saas}

- Asset, Configuration & Exposure Assurance:
{asset}

- Monitoring, Telemetry & Response Coverage:
{mon}

- Supplier & Third‑Party Security:
{supplier}

- Recovery Assurance:
{rec}

- Incident Response Assurance:
{ir}

STRICT: Use this evidence across domains without repeating identical prose; assign a primary owner per topic and cross‑reference impacts elsewhere.
""".format(
        cap=cap_summary or "(No structured CAP provided)",
        sr=sr_summary or "(No service resilience evidence provided)",
        ip=format_information_protection_profile(ip_profile) or "(Not established during consultation)",
        idg=format_identity_governance_profile(idg_profile) or "(Not established during consultation)",
        saas=format_saas_governance_profile(saas_profile) or "(Not established during consultation)",
        asset=format_asset_assurance_profile(asset_profile) or "(Not established during consultation)",
        mon=format_monitoring_assurance_profile(mon_profile) or "(Not established during consultation)",
        supplier=format_supplier_assurance_profile(supp_profile, tpa_profile) or "(Not established during consultation)",
        rec=format_recovery_assurance_profile(rec_profile) or "(Not established during consultation)",
        ir=format_ir_assurance_profile(ir_profile) or "(Not established during consultation)",
    )

    # Evidence & Assurance Status instructions
    as_status = client_inputs.get('assurance_status', {}) or {}
    as_default = assurance_phrase('default', as_status)
    assurance_clause = f"""
### EVIDENCE & ASSURANCE STATUS (STRICT)
- Default assurance: {as_default or 'Not established during consultation'}
- Use proportionate wording:
  - Confirmed during consultation → "The organisation has implemented..."
  - Reported, evidence not reviewed → "The organisation advised that..." / "The current understanding is..."
  - Requires supplier confirmation → "The reported position should be confirmed with the relevant provider."
  - Unknown → "The consultation did not establish whether..." / "A focused validation exercise would clarify..."
  - Not applicable → Treat as neutral; do not score as weak.
- Clarify authority distinction (STRICT): Monitoring response authority describes what the SOC/MDR may do under runbooks; incident technical response authority describes the organisation’s internally approved incident powers. Do not conflate these.
- Avoid repeating assurance phrasing in every paragraph; use it sparingly where it changes confidence.
"""
    
    rules = f"""
FRAMEWORK & DOMAINS (REFERENCE ONLY):
- Apply the Planet IT Cyber Resiliency framework and assess all domains listed in ASSESSMENT_DOMAINS.
- Do NOT echo full framework or domain definitions in your output.

AUTHORIZED PRODUCT MAPPING (REFERENCE ONLY):
- Use RECOMMENDED_SOLUTION_MAP by reference; do NOT restate the full mapping verbatim.

### THE PLANET IT CYBER RESILIENCY MATRIX (THE THREE PILLARS)
You must assess the client's current maturity and map them strictly against these three pillars:

**Pillar 1: Reactive Cybersecurity**
* **Theme:** Foundational Hygiene & Baseline Control.
* **Scope:** Anti-Virus, Firewalls, Email Gateways, MFA, Basic Backup & Recovery, Log Collection, Vulnerability Assessment, and Cyber Essentials.
* **Rule:** If a client lacks basic patching (e.g., Manual/Ad-Hoc), universally enforced MFA, or viable backups, they are stuck in Pillar 1. If they have advanced tools like MDR but lack these foundations, explicitly call out a "Capability Mismatch" where advanced tools are crippled by poor operational hygiene.

**Pillar 2: Proactive Cybersecurity**
* **Theme:** Active Managed Defence & Human Risk.
* **Scope:** Managed Detection & Response (MDR), EDR/XDR, Penetration Testing, Security Awareness Training, Digital Forensics & Incident Response (DFIR), SIEM, Threat Intelligence, SASE, and ISO 27001 alignment.
* **Rule:** This pillar transitions the client from passive tools to active hunting and validated defence.

**Pillar 3: Adaptive Cybersecurity**
* **Theme:** Adaptive Governance, Automation, and Resilience.
* **Scope:** Zero-Trust Architecture (ZTA), Microsegmentation, User & Behaviour Analytics (UBA), Security Orchestration Automation & Response (SOAR), Automated Disaster Recovery, Honeypots & Canarys, Continuous IoC Scanning, and Proactive Threat Hunting.
* **Rule:** The "long tail" of the roadmap must stretch into these advanced controls to demonstrate long-term business value and enterprise resilience.

### STRATEGIC ROADMAP GENERATION (THE LONG TAIL)
Ensure the 'phased_roadmap' pushes the customer through a transformational journey. You MUST use these exact phase names to maintain continuity:
* **Phase 1: Foundational Hygiene (0-3 Months)** -> Focuses on eliminating Pillar 1 (Reactive) gaps.
* **Phase 2: Active Managed Defence (3-9 Months)** -> Focuses on deploying Pillar 2 (Proactive) controls like MDR and Phish Training.
* **Phase 3: Adaptive Governance & Resilience (10-18+ Months)** -> Focuses on the long tail of Pillar 3 (Adaptive) capabilities, integrating ZTA, UBA, SOAR, and Automated DR into the client's environment.

### RISK SCORING ENGINE
When you assess business impact in the domain analysis, you MUST internally calculate a risk score using Probability (1-3) x Impact (1-3) = Risk Score (1-9). However, you must never display the raw formula or arithmetic in the business_impact_narrative. Instead, weave the severity into natural, board-level prose (e.g., "The combination of high likelihood and critical operational impact makes this gap a top-priority remediation candidate"). Factor the client's submitted RTO, Cyber Insurance Status, and Operational Telemetry directly into the impact reasoning.

### RESPONSIBILITY MATRIX
Planet IT believes in shared accountability. In your 'shared_responsibility' field, explicitly state the responsibility split. 
* **Planet IT is responsible for:** Guiding best practice, configuring the stack, 24/7 monitoring, and providing policy frameworks.
* **The Client is responsible for:** Data ownership, internal staff adherence to policies, and signing Risk Waivers if they refuse critical roadmap items.

CRITICAL REQUIREMENT: You MUST explicitly assess ALL {len(ASSESSMENT_DOMAINS)} domains (families) listed above. Do not omit, group, or skip any of them.

### PARTNERSHIP GOVERNANCE & THREAT INTELLIGENCE CONTEXT
You MUST populate the following optional fields with substantive, consultative content:
- **partnership_details:** A dedicated section describing co-managed or fully managed partnership arrangements. Reference the official partnership URLs: Fully Managed ({FULLY_MANAGED_URL}) and Co-Managed ({CO_MANAGED_URL}). Explain what Planet IT delivers under each model, the shared responsibility matrix, and SLAs. Minimum 2 paragraphs. Bullet points are strictly prohibited.
- **partnership_links:** A list of 2-3 official Planet IT governance or partnership resource URLs. Use the two official URLs above plus one additional Planet IT resource URL.
- **threat_intelligence_context:** A threat intelligence contextualisation specific to the client's industry and Crown Jewels. Summarise the current threat actor landscape, relevant APT groups, and how the client's assets are targeted. Minimum 1 paragraph. Bullet points are strictly prohibited.

### EXISTING MANAGED SERVICE STATUS (STRICT HANDLING)
If the 'Current Managed Service Status' indicates 'Planet IT Fully Managed (Active)', assume general alignment to the Planet stack is likely; verify actual deployment and configuration before asserting alignment. Do not inflate any radar scores or bypass guardrails. Focus recommended solutions on optimisation, health checks, and advanced adoption rather than duplicative procurement. If 'Planet IT Co-Managed (Active)' and 'Co-Managed Service Units' > 0, explicitly flag which Phase 1/2 tasks can be executed under existing service units; treat them as entitlements (not guarantees) and confirm with the account team. If an 'Other MSP' is active, acknowledge the existing partnership and avoid redundant managed‑support recommendations; propose an optional migration path to Planet IT only if it provides clear value in context.

### PROACTIVE TESTING, IR AND DR PROGRAMMES
You MUST also populate the following optional narrative fields with concrete, execution-ready guidance tailored to the client's environment:
- **proactive_testing_programme:** Define a 12–18 month security validation programme with a penetration testing cadence (e.g., external quarterly, internal bi-annual, web app/API aligned to release cycles), continuous exposure management recommendations, breach-and-attack simulation/ATT&CK emulation, and phishing campaigns. Include scoping prerequisites and evidence management approach. Minimum 2 paragraphs. Bullet points are strictly prohibited.
- **incident_response_plan_outline:** Summarise the IR plan with roles/RACI, communications tree, incident playbooks mapped to the client's top threats, integration with any IR retainer (e.g., Sophos MDR Plus, Microsoft DART), and a quarterly tabletop/testing schedule. Minimum 2 paragraphs. Bullet points are strictly prohibited.
- **disaster_recovery_plan_outline:** Summarise DR strategy with system-level RTO/RPO mapping for the Crown Jewels, immutable/air-gapped backups, failover runbooks, and DR exercise cadence. Tie explicitly to the submitted RTO. Minimum 2 paragraphs. Bullet points are strictly prohibited.

Act as ROLE 2 and populate the required JSON schema to deliver a comprehensive Cybersecurity Maturity Assessment. Ensure all Vendor-Agnostic Quick Wins are tailored to mitigate the risks highlighted in the client's Security Culture Tier and align with their listed Compliance Targets."""
    
    # Inject MDR decision hint ahead of rules, if present
    mdr_pref = client_inputs.get('mdr_decision', 'None')
    mdr_hint = ""
    if not mdr_pref or mdr_pref in ('None', 'Tie'):
        try:
            ep = str(client_inputs.get('endpoint', '')).lower()
            comp = str(client_inputs.get('compliance', [])).lower()
        except Exception:
            ep = ''
            comp = ''
        if 'sophos' in ep:
            mdr_pref = 'Sophos MDR'
        elif 'pci' in comp or 'hipaa' in comp:
            mdr_pref = 'Adlumin MDR'
        else:
            mdr_pref = ''
    if mdr_pref:
        mdr_hint = f"""
    ### MDR DECISION ENGINE HINT
    Preferred MDR Provider: {mdr_pref}.
    Apply this preference when selecting recommended_solutions for the 'Security Operations & Response (SecOps)' domain. If the preferred vendor is banned, fall back to an allowable alternative from the AUTHORIZED PRODUCT MAPPING. Maintain the Capability Mismatch penalties and all guardrails exactly as specified.
    """
    context_clause = ""
    cn = client_inputs.get('context_notes', '')
    if cn:
        context_clause = f"""
### CONSULTANT CONTEXT NOTES (STRICTLY NON-OVERRIDING)
Use these notes to tailor narratives and recommendations where appropriate. Do not violate guardrails or inflate scores. Do not copy verbatim; synthesise them into relevant sections.
{cn}
"""
    anti_mimicry_clause = ""
    reference_sample = client_inputs.get('reference_sample', '')
    if reference_sample:
        anti_mimicry_clause = f"""
### REFERENCE SAMPLE (TONE ONLY — DO NOT COPY)
{reference_sample}

### ANTI-MIMICRY DIRECTIVE
You MUST NOT replicate the reference sample's phrasing, sentence structure, paragraph ordering, or section wording. Target high stylistic dissimilarity. Vary sentence length, use alternative connective phrases, and restructure paragraphs while preserving required schema and guardrails. If any sentence would share more than 8 consecutive words with the sample, rewrite it.
"""

    whitelist_clause = f"""
    ### ALLOWED VENDORS BY DOMAIN (STRICT)
    {COMPACT_VENDOR_WHITELIST_TEXT}

    Selection rules:
    - Prefer Sophos across domains where functionally appropriate.
    - In IAM and Email, prefer Microsoft 365 native controls (Entra/Intune) when licence supports.
    - SecOps: Sophos MDR by default; Sophos MDR Plus where full IR is required; Adlumin when SIEM transparency/compliance reporting is a primary driver or Sophos is banned/unsuitable.
    - Network & Cloud Perimeter: Sophos Firewall by default; Fortinet for >1000 users or explicit SD‑WAN/ASIC requirements.
    - Use up to three vendor candidates per domain and respect the ban list absolutely.
    Strict: Recommend only from this allow‑list; keep selections concise and justified in context.
    """

    # DfE 2026 compliance clause (only when explicitly targeted)
    comp_targets = str(client_inputs.get('compliance', '')).lower()
    industry = str(client_inputs.get('industry', 'Other'))
    want_dfe = any(x in comp_targets for x in [
        "dfe", "department for education", "uk dfe (2026)", "education standards (2026)"])
    dfe_clause = ""
    if want_dfe:
        # Map telemetry to deterministic gaps so the LLM cannot inflate compliance
        mfa = str(client_inputs.get('mfa_status', 'Unknown'))
        patching = str(client_inputs.get('patching', 'Unknown'))
        backups = str(client_inputs.get('backups', 'Unknown'))
        ir = str(client_inputs.get('ir_readiness', 'Unknown'))
        remote = str(client_inputs.get('remote_access', 'Unknown'))
        endpoint_cap = str(client_inputs.get('endpoint_posture', 'Unknown'))
        email_sec = str(client_inputs.get('email', 'Unknown'))
        culture = str(client_inputs.get('savviness', ''))

        hard_rules = []
        if mfa in ["None", "Privileged Accounts Only"]:
            hard_rules.append("- If MFA is not universal, include a explicit gap for 'DFE-01 Account Security and MFA'.")
        if patching == "Manual / Ad-hoc":
            hard_rules.append("- If Patch Management is Manual/Ad‑hoc, include a explicit gap for 'DFE-02 Patch and Vulnerability Management'.")
        if backups in ["No Formal Backups", "On-Premise Only"]:
            hard_rules.append("- If backups are 'No Formal' or 'On‑Premise Only', include a explicit gap for 'DFE-03 Backups and Recovery'.")
        if ir in ["No Formal Plan", "Documented IR Plan (Untested)"]:
            hard_rules.append("- If IR readiness is 'No Formal Plan' or 'Untested', include a explicit gap for 'DFE-04 Incident Response Plan and Testing'.")
        if remote in ["Legacy VPN (Client-based)", "None / Cloud Only"]:
            hard_rules.append("- If Remote Access is legacy/none, include a explicit gap for 'DFE-06 Network Perimeter and Remote Access'.")
        if endpoint_cap == "Legacy AV Only (Signatures/Heuristics)":
            hard_rules.append("- If Endpoint capability is legacy AV only, include a explicit gap for 'DFE-07 Endpoint Protection and EDR/XDR'.")
        if 'Pillar 1' in culture:
            hard_rules.append("- If Security Culture is Pillar 1, include a explicit gap for 'DFE-09 Security Awareness and Behaviour'.")
        if industry == "Education":
            hard_rules.append("- If industry is Education, you MUST include an explicit assessment of 'DFE-11 Safeguarding: Filtering and Monitoring'. If web filtering/monitoring capability is not evidenced from inputs, treat it as a critical gap and propose a remediation plan.")

        catalogue_lines = "\n".join([f"- {c['id']}: {c['name']}" for c in DFE_2026_CONTROLS])
        rules_lines = "\n".join(hard_rules) if hard_rules else "- Apply control mapping pragmatically based on telemetry; do not infer compliance without explicit evidence."
        dfe_clause = f"""
### UK Department for Education (2026) Compliance Alignment (STRICT)
Standard: {DFE_2026_STANDARD_NAME}

Controls Catalogue:
{catalogue_lines}

Output Requirements:
- You MUST add a ComplianceSection entry for this standard in 'compliance_alignment'.
- Set 'standard' exactly to: {DFE_2026_STANDARD_NAME}
- Populate 'critical_gaps' with 2–6 specific gaps mapped to the above control IDs where telemetry indicates non‑compliance.
- Populate 'fill_plan' with 2–6 GapRemediationPlan items that describe concrete actions, owners, and due dates where appropriate.

Deterministic Mapping Rules:
{rules_lines}
"""
    
    # Explicit instruction for Executive Summary Actions (headline‑style 'Finding — Action')
    actions_instruction = """
### EXECUTIVE SUMMARY STRUCTURE (REQUIRED)
In the executive_summary, avoid generic sector commentary. Address the client specifically and cover:
- Current Position
- Business Context
- Operational Dependency
- Primary Risks
- Priority Improvements
- Strategic Outlook

### EXECUTIVE SUMMARY ACTIONS (REQUIRED)
Populate 'executive_summary_actions' with exactly three items. Use concise headline‑style phrasing formatted as 'Finding — Action'. Write in British English, keep vendor‑agnostic, and ensure each action directly remediates the highest risks summarised in the executive_summary. Avoid additional punctuation beyond the em dash.

### EXECUTIVE SUMMARY ACTIONS — STRUCTURED (REQUIRED)
Populate 'executive_summary_action_blocks' with exactly three objects. For each object:
- heading: Short headline, British English (max ~12 words).
- finding: 1–2 short paragraphs (target ≤ 150 words total); no bullet points; consultative tone.
- risk: A concise statement (target ≤ 80 words) contextualised to Crown Jewels, RTO, insurance/regulators; no bullet points.
- remediation_actions: 4–8 concrete steps, each ≤ 24 words. Respect ban list; remain vendor‑agnostic where appropriate.

Do NOT restate full framework, domain lists, or product mappings in any field; reference them without echoing definitions.
"""

    conditional_domains_note = """
### CONDITIONAL DOMAINS (STRICT)
Only generate conditional domains when applicable evidence is present. If a module is Not applicable, exclude it or clearly indicate N/A; do not score it as weak.
"""

    radar_hint_clause = """
    ### RADAR EVIDENCE HINTS (STRICT)
    Use the structured consultation evidence to inform RadarChartData logically:
    - saas: Reflect SaaS governance evidence (inventory status, SSO/MFA coverage, offboarding process, OAuth governance, shadow IT visibility).
    - data_security: Reflect Information Protection evidence (classification/labels, external sharing posture, DLP, retention governance).
    - supplier: Reflect Supplier Assurance and Third‑Party Access evidence (assurance maturity, identity model, supplier MFA, review cadence).
    - resilience: Reflect Recovery Assurance evidence (restore testing cadence, immutability, administrative separation, recovery exercises).
    - secops: Reflect Monitoring Assurance evidence (coverage, response authority, detection testing), not identity hygiene.
    - grc: Reflect IR readiness and governance evidence; maintain penalties where IR is absent or untested.
    - ai: Reflect AI governance evidence (policy, shadow AI monitoring, DLP/CASB coverage).
    STRICT: Honour the 3‑point cap and Capability Mismatch exactly; do not inflate scores without explicit supporting evidence.
    """

    return base_prompt + "\n\n" + evidence_block + "\n\n" + radar_hint_clause + "\n\n" + assurance_clause + "\n\n" + ban_clause + "\n\n" + whitelist_clause + (("\n" + dfe_clause + "\n") if dfe_clause else "") + (mdr_hint + "\n" if mdr_hint else "") + context_clause + anti_mimicry_clause + rules + "\n\n" + conditional_domains_note + "\n\n" + """
    ### DOMAIN WRITING PROFILES (REQUIRED)
    Use domain-specific personas to vary vocabulary, sentence structure, and emphasis so that each domain reads as if authored by a different specialist:
    - Identity & Access Management (IAM): persona: Identity Security Consultant; focus on authentication, privileged access, identity threats.
    - Network Security: persona: Network Security Architect; focus on segmentation, traffic controls, and service resilience.
    - Security Operations & Response (SecOps): persona: SOC Consultant; focus on detection engineering, triage discipline, and MTTR.
    - Security Validation & Testing: persona: Security Assurance Consultant; focus on evidence, scoping, and test cadence.
    - Governance, Risk & Compliance (GRC): persona: Governance Advisor; focus on policy, oversight, and regulatory exposure.
    - AI Governance & Security: persona: AI Risk & Security Lead; focus on AI acceptable use, shadow AI discovery, model/data risk, and monitoring.
    Strictly avoid repeated connective phrases across domains. Vary sentence length and cadence.
    """ + "\n\n" + actions_instruction + "\n\n" + """
    ### PROGRAMME CONTROLS (REQUIRED)
    Populate 'programme_controls' with the following keys: phishing_simulations; security_training_programme; endpoint_privileges; reporting_routes; followup_coaching; role_based_training; leadership_engagement; policy_acknowledgement; phish_failure_rate_90d (0–100); report_rate_90d (0–100); calculated_culture_score (0–14); culture_tier. Use British English and ensure values align with the provided consultation telemetry and culture score guardrails.
    """


def build_mc_interpretation_prompt(client_inputs, mc: dict) -> str:
    """Build a short ROLE 2 prompt that produces a consultative, customer‑focused interpretation of Monte Carlo stats.
    The LLM must:
    - Use British English and probabilistic language; avoid guarantees.
    - Explain AAL, P50/P90/P95, and CVaR95 in plain language without formulas.
    - Tie implications to the client’s Crown Jewels, RTO, insurance/regulatory context.
    - Provide 1–2 cohesive paragraphs (no bullet points).
    """
    customer = client_inputs.get('customer_name', 'the client')
    industry = client_inputs.get('industry', 'their industry')
    crown = client_inputs.get('critical_infra', 'critical systems')
    rto = client_inputs.get('rto', 'Unknown')
    insurance = client_inputs.get('insurance', 'Unknown')
    br = f"{float(mc.get('breach_probability_pct', 0.0)):.1f}%"
    aal = f"£{float(mc.get('aal_gbp', 0.0)):,.0f}"
    p50 = f"£{float(mc.get('p50_gbp', 0.0)):,.0f}"
    p90 = f"£{float(mc.get('p90_gbp', 0.0)):,.0f}"
    p95 = f"£{float(mc.get('p95_gbp', 0.0)):,.0f}"
    cvar = f"£{float(mc.get('cvar95_gbp', 0.0)):,.0f}"
    return (
        "Act as ROLE 2 (Virtual CISO). Write a concise, consultative interpretation of the Monte Carlo risk results.\n\n"
        f"CONTEXT — CLIENT: {customer} ({industry}) | Crown Jewels: {crown} | RTO: {rto} | Insurance: {insurance}\n"
        f"CONTEXT — MONTE CARLO: Breach probability: {br} | AAL: {aal} | P50: {p50} | P90: {p90} | P95: {p95} | CVaR95: {cvar}\n\n"
        "REQUIREMENTS:\n"
        "- Use British English.\n"
        "- Avoid formulas and guarantees; use probabilistic, risk‑based language.\n"
        "- Provide 1–2 paragraphs (no bullet points) that explain what these figures mean in business terms, tie them to downtime tolerance and the client’s assets, and outline the consequence of inaction.\n"
        "- Do not invent numbers; only interpret the figures provided.\n"
    )

# Forward-ref resolution for models to ensure safe cross-references
ThreatScenarioItem.update_forward_refs()
MaturityHeader.update_forward_refs()


