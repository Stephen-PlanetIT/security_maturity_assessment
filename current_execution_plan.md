Objective: Add programme controls to the maturity generator’s structured JSON by introducing a typed ProgrammeControls model, wiring it into MaturityReport and MaturityHeader, and updating prompts to instruct population. Include tests to verify field presence and prompt instruction.

Action [1]:

    FILE: prompts.py

    SEARCH:
class MaturityHeader(BaseModel):

    REPLACE:
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

    VERIFICATION: python -c "from prompts import ProgrammeControls; print('OK' if hasattr(ProgrammeControls, 'phishing_simulations') else 'FAIL')"

Action [2]:

    FILE: prompts.py

    SEARCH:
        disaster_recovery_plan_outline: Optional[str] = Field(default=None, description="Disaster Recovery plan outline.")

    REPLACE:
        disaster_recovery_plan_outline: Optional[str] = Field(default=None, description="Disaster Recovery plan outline.")
        programme_controls: Optional[ProgrammeControls] = Field(default=None, description="Structured programme controls reflecting behavioural measures and telemetry from the consultation (security culture).")

    VERIFICATION: python -c "from prompts import MaturityHeader; print('OK' if 'programme_controls' in MaturityHeader.model_fields else 'FAIL')"

Action [3]:

    FILE: prompts.py

    SEARCH:
        threat_scenarios: Optional[List[ThreatScenarioItem]] = Field(
        default=None,
        description="Auto-generated threat scenarios populated via maturity-gap analysis. Set after initial report generation.",
        min_items=1,
        max_items=3
    )

    REPLACE:
        threat_scenarios: Optional[List[ThreatScenarioItem]] = Field(
        default=None,
        description="Auto-generated threat scenarios populated via maturity-gap analysis. Set after initial report generation.",
        min_items=1,
        max_items=3
    )
        programme_controls: Optional[ProgrammeControls] = Field(default=None, description="Structured programme controls reflecting behavioural measures and telemetry from the consultation (security culture).")

    VERIFICATION: python -c "from prompts import MaturityReport; print('OK' if 'programme_controls' in MaturityReport.model_fields else 'FAIL')"

Action [4]:

    FILE: prompts.py

    SEARCH:
        + "radar_chart_data; resiliency_matrix_mapping; phased_roadmap (exactly 3 phases; each phase must include: phase_title, timeline, primary_objective, key_deliverables (3–4 items), estimated_effort, milestones (3–5 items), resource_requirements, business_value_delivered); "

    REPLACE:
        + "radar_chart_data; resiliency_matrix_mapping; programme_controls; phased_roadmap (exactly 3 phases; each phase must include: phase_title, timeline, primary_objective, key_deliverables (3–4 items), estimated_effort, milestones (3–5 items), resource_requirements, business_value_delivered); "

    VERIFICATION: python -c "from prompts import build_maturity_header_prompt; s=build_maturity_header_prompt({'customer_name':'X','industry':'Y'}); print('OK' if 'programme_controls' in s else 'FAIL')"

Action [5]:

    FILE: prompts.py

    SEARCH:
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
        """ + "\n\n" + actions_instruction

    REPLACE:
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
        Populate 'programme_controls' with: phishing_simulations; security_training_programme; endpoint_privileges; reporting_routes; followup_coaching; role_based_training; leadership_engagement; policy_acknowledgement; phish_failure_rate_90d (0–100); report_rate_90d (0–100); calculated_culture_score (0–14); culture_tier. Use British English and ensure values align with the provided consultation telemetry and culture score guardrails.
        """

    VERIFICATION: python -c "from prompts import build_maturity_prompt; s=build_maturity_prompt({'customer_name':'X','industry':'Y'}); print('OK' if 'PROGRAMME CONTROLS (REQUIRED)' in s else 'FAIL')"

Action [6]:

    FILE: tests/test_programme_controls.py

    SEARCH:

    REPLACE:
import pytest

from prompts import ProgrammeControls, MaturityReport, MaturityHeader

def test_programme_controls_model_exists():
    assert hasattr(ProgrammeControls, 'phishing_simulations')
    assert hasattr(ProgrammeControls, 'calculated_culture_score')

def test_maturity_report_has_programme_controls_field():
    assert 'programme_controls' in MaturityReport.model_fields

def test_maturity_header_has_programme_controls_field():
    assert 'programme_controls' in MaturityHeader.model_fields

    VERIFICATION: pytest -q tests/test_programme_controls.py

Action [7]:

    FILE: tests/test_prompts_build.py

    SEARCH:
    assert 'SaaS, Application & Shadow IT Governance' in text

    REPLACE:
    assert 'SaaS, Application & Shadow IT Governance' in text

def test_build_maturity_header_prompt_contains_required_fields():
    # Existing assertions remain
    # New assertion for programme_controls mention
    from prompts import build_maturity_header_prompt
    s = build_maturity_header_prompt({'customer_name': 'X', 'industry': 'Y'})
    assert 'programme_controls' in s

    VERIFICATION: pytest -q tests/test_prompts_build.py