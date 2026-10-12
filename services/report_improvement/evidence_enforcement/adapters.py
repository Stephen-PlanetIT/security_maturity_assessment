from __future__ import annotations
from typing import Optional
from .models import FinancialEvidenceProfile, ApprovedScenarioProfile
try:
    # Type-only imports; runtime present in project
    from services.report_improvement.evidence_adjudicator import CostAssumptionProfile, ApprovedAttackInputs  # type: ignore
except Exception:  # pragma: no cover
    CostAssumptionProfile = object  # type: ignore
    ApprovedAttackInputs = object  # type: ignore


def adapt_cost_profile(source: Optional["CostAssumptionProfile"]) -> FinancialEvidenceProfile:
    """
    Adapt adjudication CostAssumptionProfile to enforcement FinancialEvidenceProfile.
    Fail-closed defaults: quantified_financial_output_allowed=False, planning_assumptions_only=True.
    No values/ranges are approved by default.
    """
    try:
        if source is None:
            return FinancialEvidenceProfile()
        return FinancialEvidenceProfile(
            quantified_financial_output_allowed=False,
            approved_currency="GBP",
            approved_values=[],
            approved_ranges=[],
            approved_calculation_ids=[],
            available_inputs={},
            planning_assumptions_only=True,
        )
    except Exception:
        # Fail closed
        return FinancialEvidenceProfile()


def adapt_scenario_profile(source: Optional["ApprovedAttackInputs"]) -> ApprovedScenarioProfile:
    """
    Adapt adjudication ApprovedAttackInputs to enforcement ApprovedScenarioProfile.
    Fail-closed defaults: allow_* flags are False; approved lists empty except for explicit copies.
    """
    try:
        if source is None:
            return ApprovedScenarioProfile()
        # Pull explicit allowed references only; keep allow_* strict
        confirmed_tech = list(getattr(source, "confirmed_technologies", []) or [])
        confirmed_cj = list(getattr(source, "confirmed_crown_jewels", []) or [])
        return ApprovedScenarioProfile(
            approved_initial_access_routes=[],
            approved_technologies=confirmed_tech,
            approved_systems=[],
            approved_crown_jewels=confirmed_cj,
            approved_control_gaps=[],
            approved_mitre_techniques=[],
            allow_specific_cves=False,
            approved_cves=[],
            allow_named_threat_actors=False,
            approved_threat_actors=[],
            allow_named_attack_tools=False,
            approved_attack_tools=[],
            allow_insider_threat=False,
            allow_nation_state_scenario=False,
            approved_detection_capabilities=[],
            approved_response_capabilities=[],
        )
    except Exception:
        # Fail closed
        return ApprovedScenarioProfile()