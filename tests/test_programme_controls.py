import pytest

from prompts import ProgrammeControls, MaturityReport, MaturityHeader, build_maturity_header_prompt


def test_programme_controls_model_exists():
    # Ensure the ProgrammeControls model declares key fields (Pydantic v2 uses model_fields introspection)
    fields = set(getattr(ProgrammeControls, "model_fields", {}).keys())
    required = {
        "phishing_simulations",
        "security_training_programme",
        "endpoint_privileges",
        "reporting_routes",
        "followup_coaching",
        "role_based_training",
        "leadership_engagement",
        "policy_acknowledgement",
        "phish_failure_rate_90d",
        "report_rate_90d",
        "calculated_culture_score",
        "culture_tier",
    }
    assert required.issubset(fields)


def test_maturity_report_has_programme_controls_field():
    # Verify MaturityReport exposes programme_controls field
    assert "programme_controls" in MaturityReport.model_fields


def test_maturity_header_has_programme_controls_field():
    # Verify MaturityHeader exposes programme_controls field
    assert "programme_controls" in MaturityHeader.model_fields


def test_header_prompt_mentions_programme_controls():
    # Ensure header prompt instructs the model to include programme_controls
    s = build_maturity_header_prompt({"customer_name": "X", "industry": "Y"})
    assert "programme_controls" in s