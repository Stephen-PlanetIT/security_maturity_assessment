import pytest

from prompts import ProgrammeControls, MaturityReport, MaturityHeader

def test_programme_controls_model_exists():
    assert hasattr(ProgrammeControls, 'phishing_simulations')
    assert hasattr(ProgrammeControls, 'calculated_culture_score')

def test_maturity_report_has_programme_controls_field():
    assert 'programme_controls' in MaturityReport.model_fields

def test_maturity_header_has_programme_controls_field():
    assert 'programme_controls' in MaturityHeader.model_fields