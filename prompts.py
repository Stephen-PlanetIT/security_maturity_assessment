# prompts.py
import os
import datetime
import random
from pydantic import BaseModel, Field
from typing import List
from data import MATURITY_FRAMEWORK, ASSESSMENT_DOMAINS, RECOMMENDED_SOLUTION_MAP, DEFAULT_VCISO_CONTEXT

SYSTEM_PERSONA = "You are a Principal Cybersecurity Architect and Senior Threat Intelligence Analyst."

# ==========================================
# PYDANTIC MODELS: Maturity Report
# ==========================================
class MaturityReport(BaseModel):
    client_name: str = Field(description="The name of the client organization.")
    report_date: datetime.datetime = Field(default=datetime.datetime.now(), description="The date the report was generated.")
    maturity_level_overall: str = Field(description="An aggregated maturity level across all domains (e.g., 'Pillar 2').")
    domain_assessments: List[DomainAssessment] = Field(description="List of individual domain assessments.")

# ==========================================
# PYDANTIC MODELS: THREAT SIMULATOR
# ==========================================
class TimelineEvent(BaseModel):
    timestamp: str = Field(description="The timestamp of the event, e.g., '02:00 UTC'")
    event_description: str = Field(description="A detailed description of the attack progression or MDR intervention.")

class ScenarioReport(BaseModel):
    executive_summary: str = Field(description="A concise executive summary of the breach scenario and its implications.")
    unmitigated_narrative: str = Field(description="The detailed narrative of what would happen without Sophos MDR intervention. This should include the initial access, attacker progression, and eventual compromise.")
    unmitigated_timeline: List[TimelineEvent] = Field(
        description="The chronological timeline of events without Sophos MDR intervention. Must contain exactly 5 events.",
        min_items=5,
        max_items=5
    )
    mitigated_timeline: List[TimelineEvent] = Field(
        description="The chronological timeline of events with Sophos MDR intervention. Must contain exactly 5 events.",
        min_items=5,
        max_items=5
    )

# ==========================================
# PYDANTIC MODELS: VCISO ASSESSMENT
# ==========================================

class DomainAssessment(BaseModel):
    domain_name: str = Field(description="The exact name of the security domain.")
    current_maturity_level: str = Field(description="Must be exactly one of: 'Pillar 1: Reactive Cybersecurity', 'Pillar 2: Proactive Cybersecurity', or 'Pillar 3: Adaptive Cybersecurity'.")
    current_state_analysis: str = Field(
        description="A comprehensive analysis of the current posture. You must write a minimum of two detailed paragraphs. Bullet points are strictly prohibited."
    )
    business_impact_narrative: str = Field(
        description="Explain exactly what these gaps mean to the business (Probability x Impact). Write in full, descriptive sentences. Do not use lists."
    )
    critical_gaps: List[str] = Field(description="2-3 specific architectural or operational gaps identified.")
    vendor_agnostic_quick_wins: List[str] = Field(description="2-3 zero-cost, native configuration changes.")
    recommended_solutions: List[str] = Field(description="Specific product recommendations pulled strictly from the RECOMMENDED_SOLUTION_MAP.")
    remediation_rationale: str = Field(
        description="The strategic, architectural justification. Explain the behaviour of the attack path and why this specific tool severs it. Must be a detailed, multi-paragraph narrative."
    )
    shared_responsibility: str = Field(description="The accountability split. Clarify exactly what Planet IT will deploy or manage versus what the Client is responsible for (e.g., HR policy enforcement, user adherence).")

class RoadmapPhase(BaseModel):
    phase_title: str = Field(description="Must be strictly named: 'Phase 1: Foundational Hygiene', 'Phase 2: Active Managed Defence', or 'Phase 3: Adaptive Governance & Resilience'.")    
    timeline: str = Field(description="e.g., '0-3 Months', '3-9 Months', '10-18+ Months'.")
    primary_objective: str = Field(description="The overarching strategic goal for this phase (e.g., 'Stabilisation and Perimeter Hardening').")
    key_deliverables: List[str] = Field(description="3-4 specific tactical deliverables for this phase.")
    estimated_effort: str = Field(description="Categorise the effort required (e.g., 'Low Effort / High Impact', 'Moderate Effort / Operational Shift', 'High Effort / Transformational').")
    milestones: List[str] = Field(description="Strategic deployment milestones combining the recommended solutions. Include the operational 'Why' for each milestone.")
    resource_requirements: str = Field(description="Who needs to execute this phase (e.g., 'Planet IT SOC, Internal IT Team, External Pen-Testers').")
    business_value_delivered: str = Field(description="A concise statement on what tangible risk reduction or operational improvement the board achieves by completing this phase.")

class RadarChartData(BaseModel):
    iam: int = Field(description="Score 1, 2, or 3. STRICT RULE: Must be exactly 1 if MFA Enforcement is 'None' or 'Privileged Accounts Only'.")
    endpoint: int = Field(description="Score 1, 2, or 3. STRICT RULE: Must be exactly 1 if Patch Management is 'Manual / Ad-hoc' or Endpoint Capability is 'Legacy AV Only'.")
    network: int = Field(description="Score 1, 2, or 3. STRICT RULE: Must be exactly 1 if Remote Access is 'Legacy VPN' or 'None'.")
    email: int = Field(description="Score 1, 2, or 3.")
    cloud: int = Field(description="Score 1, 2, or 3. STRICT RULE: Must be exactly 1 if SaaS Backup is 'None'.")
    secops: int = Field(description="Score 1, 2, or 3.")

def build_mdr_case_prompt(context: DEFAULT_VCISO_CONTEXT) -> str:
    prompt = (
        f"Given the following context:\n"
        f"- Current Maturity Level: {context.current_maturity_level}\n"
        f"- Business Impact Narrative: {context.business_impact_narrative}\n"
        f"- Critical Gaps: {', '.join(context.critical_gaps)}\n"
        f"Generate a detailed MDR case log that includes:\n"
        f"- A brief overview of the incident.\n"
        f"- The timeline of detection and response actions taken by Sophos MDR."
    )
    return prompt

def build_vciso_prompt(context: DEFAULT_VCISO_CONTEXT) -> str:
    prompt = (
        f"Given the following context:\n"
        f"- Current Maturity Level: {context.current_maturity_level}\n"
        f"- Business Impact Narrative: {context.business_impact_narrative}\n"
        f"- Critical Gaps: {', '.join(context.critical_gaps)}\n"
        f"Generate a comprehensive vCISO report that includes:\n"
        f"- An executive summary of the current security posture and its implications.\n"
        f"- A detailed analysis of each security domain."
    )
    return prompt

def build_scenario_prompt(context: DEFAULT_VCISO_CONTEXT) -> str:
    prompt = (
        f"Given the following context:\n"
        f"- Current Maturity Level: {context.current_maturity_level}\n"
        f"- Business Impact Narrative: {context.business_impact_narrative}\n"
        f"- Critical Gaps: {', '.join(context.critical_gaps)}\n"
        f"- Recommended Solutions: {', '.join(context.recommended_solutions)}\n"
        f"Generate a detailed security scenario report that includes:\n"
        f"- An executive summary of the breach scenario and its implications.\n"
        f"- The narrative of what would happen without Sophos MDR intervention, including initial access, attacker progression, and eventual compromise.\n"
        f"- A timeline of events without Sophos MDR intervention (exactly 5 events).\n"
        f"- A timeline of events with Sophos MDR intervention (exactly 5 events).\n"
    )
    return prompt