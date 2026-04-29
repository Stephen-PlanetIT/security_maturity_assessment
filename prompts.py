# prompts.py
import datetime
from pydantic import BaseModel, Field
from typing import List
from data import MATURITY_FRAMEWORK, ASSESSMENT_DOMAINS, RECOMMENDED_SOLUTION_MAP

# ==========================================
# PYDANTIC MODELS: THREAT SIMULATOR
# ==========================================
class TimelineEvent(BaseModel):
    timestamp: str = Field(description="The timestamp of the event, e.g., '02:00 UTC'")
    event_description: str = Field(description="A detailed description of the attack progression.")

class ScenarioReport(BaseModel):
    narrative: str = Field(description="Sections 1-4: The full threat narrative and MDR response formatted in Markdown.")
    timeline: List[TimelineEvent] = Field(description="Section 5: The chronological attack timeline.")

# ==========================================
# PYDANTIC MODELS: VCISO ASSESSMENT
# ==========================================
class DomainAssessment(BaseModel):
    domain_name: str = Field(description="The exact name of the security domain.")
    numeric_maturity_score: float = Field(description="The precise maturity score (1.0 to 5.0) as a float.")
    current_maturity_level: str = Field(description="The graded maturity level, e.g., 'Level 2 (Basic)'.")
    current_state_analysis: str = Field(description="Objective summary of the client's current posture.")
    critical_gaps: List[str] = Field(description="2-3 specific architectural or operational gaps identified.")
    vendor_agnostic_quick_wins: List[str] = Field(description="2-3 zero-cost, native configuration changes.")
    recommended_solutions: List[str] = Field(description="Specific product recommendations pulled strictly from the AUTHORISED PRODUCT MAPPING.")
    budgetary_estimate: str = Field(description="Rough cost estimate: 'Low (£)', 'Medium (££)', or 'High (£££)'.")

class RoadmapPhase(BaseModel):
    phase_name: str = Field(description="The phase timeline, e.g., 'Phase 1: Quick Wins (0-3 Months)'.")
    milestones: List[str] = Field(description="Strategic deployment milestones combining the recommended solutions.")

class MaturityReport(BaseModel):
    executive_summary: str = Field(description="A C-level executive summary of the business risk.")
    cost_of_inaction: str = Field(description="A stark, objective statement on the financial and operational risks.")
    compliance_alignment: str = Field(description="A dedicated paragraph explaining exactly how this specific roadmap accelerates the client toward their selected Target Compliance Frameworks (e.g., NIS2, ISO27001, PCI:DSS).")
    domain_assessments: List[DomainAssessment] = Field(description="Detailed gap analysis for each of the 8 security domains.")
    phased_roadmap: List[RoadmapPhase] = Field(description="A 3-phase strategic roadmap.")
    success_metrics: List[str] = Field(description="3-4 measurable 12-month KPIs.")
    engagement_cadence: List[str] = Field(description="A schedule of ongoing advisory meetings.")
    consultant_discovery_guide: List[str] = Field(description="3 provocative, insightful questions for the consultant to ask.")

# ==========================================
# MASTER PERSONA
# ==========================================
SYSTEM_PERSONA = """
You are a Dual-Role Cybersecurity Expert: A Principal Threat Intelligence Analyst (tactical) and an Enterprise Virtual CISO (strategic).

GENERAL RULES & STRICT GUARDRAILS:
- Tone MUST be strictly objective, consultative, formal, and highly technical.
- Use standard British English spelling (e.g., 'optimised', 'behavioural', 'programme', 'neutralise').
- PROTECT THE SOPHOS BRAND: Never imply a Sophos product failed. Attribute breaches to extreme human error or third-party vulnerabilities.
- HYPERLINKING REQUIREMENT: Always hyperlink MITRE T-codes, CVEs, and products.

ROLE 1: TACTICAL THREAT ANALYST
- Detail how Sophos MDR neutralised the threat using ONLY authorised response actions (Isolate, Terminate, Block).

ROLE 2: VIRTUAL CISO
- Evaluate clients against the 1-5 Maturity Framework across the 8 domains.
- If the user specifies Target Compliance Frameworks (e.g., NIS2, ISO27001), you MUST explicitly map the Quick Wins, Recommendations, and Success Metrics to the requirements of those specific frameworks.
- RULE ON EXISTING TOOLS: If the client already possesses a recommended tool, DO NOT recommend purchasing it. Recommend "Optimising existing configurations".
- Pitch Sophos MDR consolidation heavily if they use a competitor.
"""

def build_scenario_prompt(client_inputs, osint_data, attack_vector, custom_scenario=""):
    base_prompt = f"ENGAGEMENT DETAILS: Customer: {client_inputs['customer_name']}\nCLIENT ENVIRONMENT: Industry: {client_inputs['industry']} | Users: {client_inputs['users']} | Critical Asset: {client_inputs['critical_infra']}\nTECH STACK: Endpoint: {client_inputs['endpoint']}, Firewall: {client_inputs['firewall']}, Identity: {client_inputs['identity']}, Cloud: {client_inputs['cloud_env']}"
    scenario_rules = f"SCENARIO REQUIREMENTS:\n- Section 1: Vector: '{attack_vector if not custom_scenario else custom_scenario}'.\n- Section 2: Progression toward {client_inputs['critical_infra']}.\n- Section 3: MDR Response (ONLY authorised actions).\n- Section 4: Recommendations.\n- Section 5: Timeline."
    return f"Act as ROLE 1.\n{base_prompt}\nOSINT: {osint_data}\n{scenario_rules}"

def build_mdr_case_prompt(client_inputs, scenario_narrative):
    current_time = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"Act as ROLE 1. Summarise into a mock Sophos MDR Case report.\nCUSTOMER: {client_inputs['customer_name']}\nNARRATIVE: {scenario_narrative}\nFormat: Case ID: [Random #-######]\nCustomer: {client_inputs['customer_name']}\nDate and Time: {current_time}\n//Analysis: [Synopsis.]\n//Response Actions: [ONLY Authorised Actions.]\n//Recommendations: [Hardening steps.]\n//Technical details: [Indicators.]\n//References: [MITRE/CVE links.]"

def build_vciso_prompt(client_inputs):
    discovery_context = f"""
    GRC, RESILIENCE & COMPLIANCE POSTURE:
    - Target Compliance/Frameworks: {client_inputs.get('target_compliance')}
    - Current Certifications: {client_inputs.get('current_cert')}
    - IR Plan Review Status: {client_inputs.get('ir_plan_review')}
    - MFA Enforcement: {client_inputs.get('mfa_status')}
    - Phishing Test Cadence: {client_inputs.get('phishing_frequency')}
    - Training Maturity: {client_inputs.get('training_maturity')}
    - Local Admin Rights: {client_inputs.get('admin_rights')}
    - Backup Strategy: {client_inputs.get('backup_strategy')}
    - Tabletop Testing: {client_inputs.get('last_tabletop')}
    - Asset Visibility: {client_inputs.get('asset_visibility')}
    - Data Classification: {client_inputs.get('data_classification')}
    - Third-Party Risk: {client_inputs.get('tprm_status')}
    - IR Retainer: {client_inputs.get('ir_retainer')}
    - Cyber Insurance: {client_inputs.get('insurance_status')}
    """
    
    base_prompt = f"ENGAGEMENT DETAILS: Customer: {client_inputs['customer_name']}\nCLIENT ENVIRONMENT: Industry: {client_inputs['industry']} | Users: {client_inputs['users']}\nCalculated Savviness: {client_inputs['savviness']}\n{discovery_context}\nTECH STACK: MDR: {client_inputs['mdr_provider']}, Endpoint: {client_inputs['endpoint']}, Firewall: {client_inputs['firewall']}, Identity: {client_inputs['identity']}, Cloud: {client_inputs['cloud_env']}, M365: {client_inputs['m365_license']}"
    
    rules = f"FRAMEWORK: {MATURITY_FRAMEWORK}\nDOMAINS: {ASSESSMENT_DOMAINS}\nMAP: {RECOMMENDED_SOLUTION_MAP}\nAct as ROLE 2 and populate the required JSON schema."
    return base_prompt + rules