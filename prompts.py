# prompts.py
import datetime
from pydantic import BaseModel, Field
from typing import List
from data import MATURITY_FRAMEWORK, ASSESSMENT_DOMAINS, RECOMMENDED_SOLUTION_MAP
from catalog import PLANET_IT_PORTFOLIO

# --- THREAT SIMULATOR SCHEMAS ---
class TimelineEvent(BaseModel):
    timestamp: str = Field(description="The timestamp of the event, e.g., '02:00 UTC'")
    event_description: str = Field(description="A detailed description of the attack progression.")

class ScenarioReport(BaseModel):
    narrative: str = Field(description="Sections 1-4: The full threat narrative and MDR response formatted in Markdown.")
    timeline: List[TimelineEvent] = Field(description="Section 5: The chronological attack timeline.")
    mdr_case_log: str = Field(description="A mocked-up, highly technical Planet IT SOC Case Report.")

# --- PLATFORM REPORT SCHEMAS (UNIFIED) ---
class DetailedRecommendation(BaseModel):
    solution_name: str = Field(description="Name of the recommended solution (e.g., Planet IT Managed SOC).")
    description: str = Field(description="A clear summary of what this solution is and how it works.")
    business_value: str = Field(description="Why/how this specific solution helps the business mitigate risk.")
    strategic_rationale: str = Field(description="Deep context on exactly why this specific tool or service was chosen.")

class DomainAssessment(BaseModel):
    domain_name: str = Field(description="The exact name of the security domain.")
    numeric_maturity_score: float = Field(description="The precise maturity score (1.0 to 5.0) as a float.")
    current_maturity_level: str = Field(description="The graded maturity level, e.g., 'Level 2 (Basic)'.")
    current_state_analysis: str = Field(description="Objective summary of the client's current posture.")
    risk_exposure_summary: str = Field(description="A deeper explanation of the underlying risks.")
    critical_gaps: List[str] = Field(description="2-3 specific architectural or operational gaps identified.")
    real_world_risk_scenario: str = Field(description="A brief, highly impactful real-world scenario.")
    vendor_agnostic_quick_wins: List[str] = Field(description="2-3 zero-cost, native configuration changes.")
    recommended_solutions: List[DetailedRecommendation] = Field(description="Detailed product/service recommendations.")
    budgetary_estimate: str = Field(description="Rough cost estimate: 'Low (£)', 'Medium (££)', or 'High (£££)'.")

class HighLevelPhase(BaseModel):
    phase: str = Field(description="e.g., Phase 1: Foundation & Visibility (Months 1-3)")
    summary: str = Field(description="High level summary of the objectives and expected outcomes.")

class FinancialAnalysis(BaseModel):
    peer_benchmark_statement: str = Field(description="A comparative statement benchmarking their maturity against industry peers.")
    estimated_financial_exposure: str = Field(description="A FAIR-lite estimate of the financial cost of a breach.")
    immediate_budgetary_ask: str = Field(description="A rough estimate of the immediate budget required.")

class ExecutiveProse(BaseModel):
    current_setup_summary: str = Field(description="A plain English prose summary of their current technology and security setup.")
    current_strengths: List[str] = Field(description="2-3 key strengths or good investments in their current posture.")
    current_weaknesses: List[str] = Field(description="2-3 primary weaknesses or critical flaws in their current posture.")
    license_security_analysis: str = Field(description="Brief analysis of current native cloud licenses.")

class InfrastructureStack(BaseModel):
    microsoft_licensing_and_identity: str = Field(description="Specific Microsoft licensing upgrade paths (e.g., moving to M365 Business Premium or E5) and Entra ID Conditional Access strategies.")
    email_security_strategy: str = Field(description="Clear recommendation between Mimecast or Sophos Email based on the client's industry/compliance needs.")
    firewall_and_edge_strategy: str = Field(description="Clear recommendation between Fortinet (Enterprise/Complex) or Sophos Firewall (SME/Consolidated).")

class ITOperationsAnalysis(BaseModel):
    patching_and_asset_management: str = Field(description="An objective analysis of their patching. Recommend Planet IT Co-Managed IT / N-central if patching is manual.")
    data_resilience_and_backup: str = Field(description="An objective analysis of their server/M365 backup strategy. Recommend N-able Cove if backups are weak.")
    co_managed_opportunities: str = Field(description="A summary of how Planet IT can augment their internal IT team.")

class PDFExecutiveSummary(BaseModel):
    top_3_business_risks: List[str] = Field(description="The 3 most critical business risks identified, written in plain English for the CEO.")
    financial_analysis: FinancialAnalysis = Field(description="Financial quantification and peer benchmarking.")
    executive_prose: ExecutiveProse = Field(description="Prose summary of setup, strengths, weaknesses, and license capabilities.")
    infrastructure_stack: InfrastructureStack = Field(description="Dedicated breakdown of Microsoft Licensing, Email, and Firewall strategies.")
    it_operations_analysis: ITOperationsAnalysis = Field(description="Deep dive into IT operations, patching, backups, and N-able Co-Managed opportunities.")
    cost_of_inaction: str = Field(description="A stark, objective statement on the financial and operational risks of doing nothing.")
    compliance_alignment: str = Field(description="Explanation of how this roadmap accelerates the client toward target compliance.")
    domain_assessments: List[DomainAssessment] = Field(description="Detailed gap analysis for each of the 8 security domains.")
    high_level_roadmap: List[HighLevelPhase] = Field(description="A brief strategic 3-phase roadmap for the executive.")
    success_metrics: List[str] = Field(description="3-4 measurable 12-month KPIs.")

class TechnicalPhase(BaseModel):
    phase_name: str = Field(description="e.g., 'Phase 1: Foundation & Visibility (Months 0-3)'.")
    engineering_tasks: List[str] = Field(description="3-4 specific engineering or deployment tasks for this phase.")
    sophos_products_deployed: List[str] = Field(description="The specific solutions rolled out in this phase.")

class QuickWin(BaseModel):
    task: str = Field(description="A specific technical task.")
    effort_vs_impact: str = Field(description="Categorisation (e.g., 'Low Effort / High Impact').")

class PPTXTechnicalRoadmap(BaseModel):
    operational_reality_statement: str = Field(description="An empathetic but firm statement acknowledging their current FTEs and budget.")
    high_impact_quick_wins: List[QuickWin] = Field(description="A list of 3-5 tasks they can execute immediately.")
    architecture_current_state: str = Field(description="Deep technical analysis of their current stack.")
    target_operating_model: str = Field(description="The technical blueprint of where they need to be (The Planet IT Managed Ecosystem).")
    implementation_phases: List[TechnicalPhase] = Field(description="Step-by-step engineering tasks to deploy the recommended solutions.")

class UnifiedEngagementReport(BaseModel):
    executive_pdf_content: PDFExecutiveSummary = Field(description="The business and risk-focused content for the PDF Executive Summary.")
    technical_pptx_content: PPTXTechnicalRoadmap = Field(description="The deep engineering and deployment content for the PowerPoint deck.")

# --- MASTER PERSONA ---
SYSTEM_PERSONA = """
You are a Dual-Role Cybersecurity Expert from Planet IT: A Principal Threat Intelligence Analyst (tactical) and an Enterprise Virtual CISO (strategic).

GENERAL RULES & STRICT GUARDRAILS:
- IDENTITY: You represent Planet IT. All advisory, consulting, and SOC services must be attributed to Planet IT.
- Tone MUST be strictly objective, consultative, formal, and highly technical.
- Use standard British English spelling.

MULTI-VENDOR ARCHITECTURE RULES (CRITICAL):
Planet IT is a vendor-agnostic advisor that builds architectures around Sophos, Fortinet, Mimecast, N-able, and Microsoft.
1. XDR vs MDR RULE (STRICT): NEVER recommend Sophos XDR to small businesses without a 24/7 dedicated security team. XDR requires humans looking at logs at 3 AM. You MUST default to "Sophos MDR / Planet IT Managed SOC" for 95% of businesses.
2. FIREWALL/EDGE: Recommend "Fortinet FortiGate" if the client has over 1000 users OR already has Fortinet deployed. Otherwise, recommend "Sophos Firewall".
3. EMAIL SECURITY: Recommend "Mimecast" if the client is in a highly regulated industry (Finance, Healthcare, Education). Otherwise, recommend Sophos Email.
4. MICROSOFT LICENSING: Provide direct licensing upgrade paths. Recommend moving to M365 Business Premium (under 300 users) or M365 E5 (Enterprise) to unlock native security features like Entra ID P1/P2 Conditional Access.
5. IT OPERATIONS & BACKUP: If patching is manual/failing, recommend "N-able N-central". If backups are weak, recommend "N-able Cove Data Protection".

ROLE 1: TACTICAL THREAT ANALYST
- Detail how the "Planet IT Managed SOC" neutralised the threat.

ROLE 2: VIRTUAL CISO / LEAD ARCHITECT
- BIFURCATED REPORTING: Ensure the PDF speaks to the CEO (financials, risk, operations) and the PPTX speaks to the IT Director (execution, quick wins).
- OPERATIONAL REALITY RULE: If the client has 0 or 1 Security FTEs, heavily push Planet IT Managed Services (SOC & Co-Managed IT) over complex tool deployments.
"""

def build_scenario_prompt(client_inputs, osint_data, attack_vector, custom_scenario=""):
    safe_scenario = f"<user_override>{custom_scenario[:500]}</user_override>" if custom_scenario else attack_vector
    current_time = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    base_prompt = f"ENGAGEMENT DETAILS: Customer: {client_inputs.get('customer_name', 'Client')} | Industry: {client_inputs.get('industry', 'N/A')} | Users: {client_inputs.get('users', 500)}"
    scenario_rules = f"""SCENARIO REQUIREMENTS:
    - Section 1: Initial Access Vector: {safe_scenario}.
    - Section 2: Progression.
    - Section 3: MDR Response (ONLY authorised actions).
    - Section 4: Recommendations.
    - Section 5: Timeline.
    - Section 6 (mdr_case_log): Generate a SOC Case Report. Format: Case ID: [Random #-######], Date: {current_time}.
    """
    return f"Act as ROLE 1.\n{base_prompt}\nOSINT: {osint_data}\n{scenario_rules}"

def build_unified_audit_prompt(client_inputs):
    security_truth = PLANET_IT_PORTFOLIO
    
    discovery_context = f"""
    GRC, RESILIENCE & COMPLIANCE POSTURE:
    - Target Compliance: {client_inputs.get('target_compliance', 'None')}
    - Current Certifications: {client_inputs.get('current_cert', 'None')}
    - Cyber Insurance: {client_inputs.get('insurance_status', 'None')}
    
    SECURITY CULTURE & HYGIENE:
    - Identity Controls: {client_inputs.get('identity_controls', 'None')}
    - Endpoint Privileges: {client_inputs.get('admin_rights', 'None')}
    - Phishing Test Cadence: {client_inputs.get('phishing_frequency', 'None')}
    
    MODERN ATTACK SURFACE & LICENSING:
    - Workspace Licensing: {client_inputs.get('workspace_license', 'None')}
    - Cloud Infrastructure: {client_inputs.get('cloud_env', 'None')}
    - SaaS Sprawl: {client_inputs.get('saas_sprawl', 'None')}
    
    FINANCIAL & RESOURCING CONTEXT:
    - Est. Annual Revenue: {client_inputs.get('revenue_band', 'Unknown')}
    - Est. Downtime Cost/Hr: {client_inputs.get('downtime_cost', 'Unknown')}
    - Dedicated IT/Security FTEs: {client_inputs.get('security_ftes', '0')}
    - IT Budget Trend: {client_inputs.get('budget_trend', 'Unknown')}
    
    IT OPERATIONS & BACKUP CONTEXT:
    - Patching Strategy: {client_inputs.get('patching_strategy', 'Unknown')}
    - Asset Visibility: {client_inputs.get('asset_visibility', 'Unknown')}
    - M365 Backup Status: {client_inputs.get('m365_backup', 'Unknown')}
    - Server Backup Strategy: {client_inputs.get('server_backup', 'Unknown')}
    """
    base_prompt = f"ENGAGEMENT DETAILS: Customer: {client_inputs.get('customer_name', 'Client')}\nCLIENT ENVIRONMENT: Industry: {client_inputs.get('industry', 'N/A')} | Users: {client_inputs.get('users', 500)}\n{discovery_context}\nTECH STACK: MDR: {client_inputs.get('mdr_provider', 'None')}, Endpoint: {client_inputs.get('endpoint', 'None')}, Firewall: {client_inputs.get('firewall', 'None')}"
    rules = f"YOUR KNOWLEDGE BASE (TRUTH ENGINE): {security_truth}\nFRAMEWORK: {MATURITY_FRAMEWORK}\nDOMAINS: {ASSESSMENT_DOMAINS}\nAct as ROLE 2 and populate the UnifiedEngagementReport JSON schema."
    return base_prompt + rules