# prompts.py
import datetime
from pydantic import BaseModel, Field
from typing import List
from data import MATURITY_FRAMEWORK, ASSESSMENT_DOMAINS
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
    domain_name: str = Field(description="The exact name of the security domain (e.g., 'Email Security' or 'Security Awareness').")
    numeric_maturity_score: float = Field(description="The precise maturity score (1.0 to 5.0) as a float.")
    current_maturity_level: str = Field(description="The graded maturity level, e.g., 'Level 2 (Basic)'.")
    current_state_analysis: str = Field(description="Objective summary of the client's current posture in this specific domain based strictly on inputs.")
    risk_exposure_summary: str = Field(description="A deeper explanation of the underlying architectural risks.")
    critical_gaps: List[str] = Field(description="2-3 specific architectural or operational gaps identified.")
    real_world_risk_scenario: str = Field(description="A brief, highly impactful real-world scenario.")
    vendor_agnostic_quick_wins: List[str] = Field(description="2-3 zero-cost, native configuration changes.")
    recommended_solutions: List[DetailedRecommendation] = Field(description="Detailed product/service recommendations specifically mapped to the Planet IT portfolio.")
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
    domain_assessments: List[DomainAssessment] = Field(description="EXACTLY 9 domain assessments, one for each major Planet IT category.")
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
- Use standard British English spelling (e.g., 'optimised', 'behavioural', 'programme', 'neutralise').

GAP ANALYSIS TONE RULE (CRITICAL - PREVENT HALLUCINATIONS):
Do NOT invent specific misconfigurations. If the user states they have a Fortinet Firewall, do not assume it is "configured incorrectly". Instead, focus on architectural limitations. State facts based ONLY on the inputs provided.

MULTI-VENDOR ARCHITECTURE RULES (CRITICAL):
Planet IT is a vendor-agnostic advisor that builds architectures around Sophos, Fortinet, Mimecast, N-able, and Microsoft.
1. THE MDR RULE (STRICT): 
   - If the client has 'None', mandate Sophos MDR. 
   - NEVER recommend Sophos XDR to businesses without a 24/7 internal security team. 
   - If the client uses a third-party MDR (e.g., CrowdStrike, Arctic Wolf, or 'Other Third-Party MDR'), ACKNOWLEDGE their existing security maturity. Do not say they lack MDR. Instead, position the "Planet IT Managed SOC" as a co-managed overlay to tune their existing tool, or suggest a consolidation to Sophos MDR at their next renewal date.
2. FIREWALL/EDGE: Recommend "Fortinet FortiGate" if the client has over 1000 users OR already has Fortinet deployed. Otherwise, recommend "Sophos Firewall".
3. EMAIL SECURITY: Recommend "Mimecast" if the client is in a highly regulated industry (Finance, Healthcare, Education, Legal). Otherwise, recommend Sophos Email.
4. MICROSOFT LICENSING: Recommend upgrading to M365 Business Premium (under 300 users) or M365 E5 (Enterprise) to unlock Entra ID Conditional Access.
5. IDENTITY THREATS: Highlight "Sophos ITDR" to monitor Entra ID/Okta for compromised credentials.
6. VULNERABILITY MANAGEMENT: If vulnerability scanning is rare/never, mandate "Sophos Managed Risk".
7. IT OPERATIONS & BACKUP: If patching is manual, recommend "N-able N-central". If backups are weak, recommend "N-able Cove Data Protection".

ROLE 1: TACTICAL THREAT ANALYST
- Detail how "Sophos MDR" neutralised the threat.

ROLE 2: VIRTUAL CISO / LEAD ARCHITECT
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
    - Section 6 (mdr_case_log): Generate a SOC Case Report.
    """
    return f"Act as ROLE 1.\n{base_prompt}\nOSINT: {osint_data}\n{scenario_rules}"

def build_unified_audit_prompt(client_inputs):
    security_truth = PLANET_IT_PORTFOLIO
    
    discovery_context = f"""
    GRC, RESILIENCE & COMPLIANCE POSTURE:
    - Target Compliance: {client_inputs.get('target_compliance', 'None')}
    - Current Certifications: {client_inputs.get('current_cert', 'None')}
    - Cyber Insurance: {client_inputs.get('insurance_status', 'None')}
    - Vulnerability Scanning & Pen Testing: {client_inputs.get('vuln_scanning', 'Unknown')}
    
    SECURITY CULTURE & HYGIENE:
    - Identity Controls: {client_inputs.get('identity_controls', 'None')}
    - Endpoint Privileges: {client_inputs.get('admin_rights', 'None')}
    - Phishing Test Cadence: {client_inputs.get('phishing_frequency', 'None')}
    
    MODERN ATTACK SURFACE, NETWORK & CLOUD:
    - Workforce Topology: {client_inputs.get('workforce_distribution', 'Unknown')}
    - Workspace Licensing: {client_inputs.get('workspace_license', 'None')}
    - Cloud Infrastructure: {client_inputs.get('cloud_env', 'None')}
    - Cloud Complexity: {client_inputs.get('cloud_complexity', 'Unknown')}
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
    
    rules = f"""
    YOUR KNOWLEDGE BASE (TRUTH ENGINE): {security_truth}
    
    CRITICAL INSTRUCTION FOR DOMAIN ASSESSMENTS:
    You MUST generate exactly 9 `domain_assessments`. You must analyse the client's gaps against ALL 9 of these Planet IT categories:
    1. Managed Detection and Response (SOC)
    2. Endpoint & Server Security
    3. Network & Edge Security (NOTE: Highlight ZTNA if workforce is remote).
    4. Email Security
    5. Identity & Access Management (NOTE: Highlight Sophos ITDR for telemetry and MSFT Licensing for Conditional Access).
    6. Vulnerability & Exposure Management (NOTE: Recommend Sophos Managed Risk if scanning is ad-hoc/never).
    7. Security Awareness & Training
    8. Cloud Security & Posture (NOTE: Highlight Cloud Optix if Cloud Complexity is 'Complex').
    9. IT Operations & Resilience
    
    Act as ROLE 2 and populate the UnifiedEngagementReport JSON schema.
    """
    return base_prompt + rules