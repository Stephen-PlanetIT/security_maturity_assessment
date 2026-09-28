Objective: Add an evidence-led “Concerns vs Risks Alignment” analysis to the self-reported known issues section, comparing the customer’s top three concerns to the consultation’s top three risks, assessing proportionality, and outlining remediation, without altering scoring, Capability Mismatch penalties, or the radar cap.

Action [1]:

    FILE: prompts.py

    SEARCH: 
class CriticalIssueRAGItem(BaseModel):
     severity_label: str = Field(description="One of: 'RED', 'AMBER', 'GREEN'.")
     severity_pct: int = Field(ge=10, le=60, description="Canonical buckets: RED 40, AMBER 35, GREEN 25. Use the nearest canonical value.")
     issue_title: str = Field(description="Short headline for the issue.")
     business_exposure: str = Field(description="1–2 concise paragraphs in British English explaining the business exposure. Bullet points are prohibited.")
     priority_action: str = Field(description="One clear priority action sentence.")

class ComplianceSection(BaseModel):

    REPLACE: 
class CriticalIssueRAGItem(BaseModel):
     severity_label: str = Field(description="One of: 'RED', 'AMBER', 'GREEN'.")
     severity_pct: int = Field(ge=10, le=60, description="Canonical buckets: RED 40, AMBER 35, GREEN 25. Use the nearest canonical value.")
     issue_title: str = Field(description="Short headline for the issue.")
     business_exposure: str = Field(description="1–2 concise paragraphs in British English explaining the business exposure. Bullet points are prohibited.")
     priority_action: str = Field(description="One clear priority action sentence.")

class ConcernAlignmentItem(BaseModel):
     concern_text: str = Field(description="Customer-stated concern text under consideration.")
     aligned_to_top_risk: str = Field(description="Alignment verdict: 'Aligned' or 'Misaligned'.")
     proportionality: str = Field(description="One of: 'Proportionate', 'Overstated', 'Understated'.")
     top_risk_reference: Optional[str] = Field(default=None, description="Reference to the most relevant actual top risk or domain/gap.")
     resolution_outline: List[str] = Field(description="2–5 concise remediation steps addressing the concern proportionately.", min_items=2, max_items=5)

class ConcernAlignmentReport(BaseModel):
     customer_top_three_concerns: List[str] = Field(description="The customer's top three concerns as captured (verbatim).", min_items=1, max_items=3)
     actual_top_three_risks: List[str] = Field(description="Actual top three risks derived from the consultation (evidence-led).", min_items=1, max_items=3)
     alignment_items: List[ConcernAlignmentItem] = Field(description="Alignment and proportionality verdicts for each concern.", min_items=1, max_items=3)
     overall_summary: str = Field(description="Short narrative summarising alignment and any notable mismatches; British English.")

class ComplianceSection(BaseModel):

    VERIFICATION: python -c "from prompts import ConcernAlignmentItem, ConcernAlignmentReport; print('OK')"


Action [2]:

    FILE: prompts.py

    SEARCH:
    programme_controls: Optional[ProgrammeControls] = Field(default=None, description="Structured programme controls reflecting behavioural measures and telemetry from the consultation (security culture).")
    known_issues_assessment: Optional[List[KnownIssueAssessmentItem]] = Field(default=None, description="Assessment of customer-stated known issues with Planet IT adjudication and remediation guidance.", min_items=1, max_items=10)
    critical_issues_rag: Optional[List[CriticalIssueRAGItem]] = Field(default=None, description="RAG summary entries derived from critical gaps for executive communication. Non-scoring.", min_items=1, max_items=5)

    REPLACE:
    programme_controls: Optional[ProgrammeControls] = Field(default=None, description="Structured programme controls reflecting behavioural measures and telemetry from the consultation (security culture).")
    concerns_vs_risks_alignment: Optional[ConcernAlignmentReport] = Field(default=None, description="Non-scoring alignment analysis between customer's top three concerns and the consultation's actual top three risks, including proportionality verdicts and resolution outline.")
    known_issues_assessment: Optional[List[KnownIssueAssessmentItem]] = Field(default=None, description="Assessment of customer-stated known issues with Planet IT adjudication and remediation guidance.", min_items=1, max_items=10)
    critical_issues_rag: Optional[List[CriticalIssueRAGItem]] = Field(default=None, description="RAG summary entries derived from critical gaps for executive communication. Non-scoring.", min_items=1, max_items=5)

    VERIFICATION: python -c "from prompts import MaturityHeader; assert 'concerns_vs_risks_alignment' in MaturityHeader.model_json_schema().get('properties', {}); print('OK')"


Action [3]:

    FILE: prompts.py

    SEARCH:
    programme_controls: Optional[ProgrammeControls] = Field(default=None, description="Structured programme controls reflecting behavioural measures and telemetry from the consultation (security culture).")
    known_issues_assessment: Optional[List[KnownIssueAssessmentItem]] = Field(default=None, description="Assessment of customer-stated known issues with Planet IT adjudication and remediation guidance.", min_items=1, max_items=10)
    critical_issues_rag: Optional[List[CriticalIssueRAGItem]] = Field(default=None, description="RAG summary entries derived from critical gaps for executive communication. Non-scoring.", min_items=1, max_items=5)

    REPLACE:
    programme_controls: Optional[ProgrammeControls] = Field(default=None, description="Structured programme controls reflecting behavioural measures and telemetry from the consultation (security culture).")
    concerns_vs_risks_alignment: Optional[ConcernAlignmentReport] = Field(default=None, description="Non-scoring alignment analysis between customer's top three concerns and the consultation's actual top three risks, including proportionality verdicts and resolution outline.")
    known_issues_assessment: Optional[List[KnownIssueAssessmentItem]] = Field(default=None, description="Assessment of customer-stated known issues with Planet IT adjudication and remediation guidance.", min_items=1, max_items=10)
    critical_issues_rag: Optional[List[CriticalIssueRAGItem]] = Field(default=None, description="RAG summary entries derived from critical gaps for executive communication. Non-scoring.", min_items=1, max_items=5)

    VERIFICATION: python -c "from prompts import MaturityReport; assert 'concerns_vs_risks_alignment' in MaturityReport.model_json_schema().get('properties', {}); print('OK')"


Action [4]:

    FILE: prompts.py

    SEARCH:
    known_issues_clause = f"""
 ### KNOWN ISSUES (CUSTOMER-STATED — DO NOT AFFECT SCORING)
 Known issues provided in their own words (verbatim):
 {known_issues_text or "- (None provided)"}
 
 OUTPUT REQUIREMENTS:
 - Populate 'known_issues_assessment' with 1–10 items. For each:
   • issue_text
   • our_ruling: One of 'Agree', 'Partially Agree', 'Disagree'
   • rationale: 1–2 paragraphs; British English; no bullet points
   • suggested_remediations: 2–6 actions
   • aligned_solutions: 1–3 consultative solution suggestions (respect ban list; draw from authorised solution map)
 STRICT: This adjudication MUST NOT influence radar scores or pillar mapping.
 """

    REPLACE:
    known_issues_clause = f"""
 ### KNOWN ISSUES (CUSTOMER-STATED — DO NOT AFFECT SCORING)
 Known issues provided in their own words (verbatim):
 {known_issues_text or "- (None provided)"}
 
 OUTPUT REQUIREMENTS:
 - Populate 'known_issues_assessment' with 1–10 items. For each:
   • issue_text
   • our_ruling: One of 'Agree', 'Partially Agree', 'Disagree'
   • rationale: 1–2 paragraphs; British English; no bullet points
   • suggested_remediations: 2–6 actions
   • aligned_solutions: 1–3 consultative solution suggestions (respect ban list; draw from authorised solution map)
 STRICT: This adjudication MUST NOT influence radar scores or pillar mapping.

 ### CONCERNS VS RISKS ALIGNMENT (NON-SCORING)
 OUTPUT REQUIREMENTS:
 - Populate 'concerns_vs_risks_alignment' with:
   • customer_top_three_concerns: top three from known issues (verbatim)
   • actual_top_three_risks: evidence-led top three risks derived from the consultation. If 'security_rating.snapshot.primary_gaps' exists, use the top three entries. Otherwise rank domains by exposure_index = MATURITY_WEIGHTS[domain_key] × (4 - radar_chart_data[domain_key]); select the top three domains and take the most material 'critical_gaps' from the corresponding 'domain_assessments'.
   • alignment_items: For each concern, provide:
     – aligned_to_top_risk: 'Aligned'|'Misaligned'
     – proportionality: 'Proportionate'|'Overstated'|'Understated'
     – top_risk_reference: a short reference to the nearest actual top risk/domain
     – resolution_outline: 2–5 concise remediation steps
   • overall_summary: 1 short paragraph summarising where concerns are well aligned or not.
 STRICT:
 - This analysis is advisory only and MUST NOT influence radar scores, pillar mapping, or maturity rating.
 - Preserve Capability Mismatch penalties exactly where applicable.
 """

    VERIFICATION: python -c "from prompts import build_maturity_prompt; s=build_maturity_prompt({'customer_name':'X','industry':'Y'}); assert 'CONCERNS VS RISKS ALIGNMENT' in s; print('OK')"