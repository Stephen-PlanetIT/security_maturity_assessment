from consultation_helpers import (
    derive_identity_governance_maturity,
    derive_data_security_maturity,
    derive_saas_governance_maturity,
    derive_asset_assurance_maturity,
    derive_monitoring_maturity,
    derive_supplier_security_maturity,
    derive_recovery_assurance_maturity,
    derive_incident_response_maturity,
)

def test_identity_governance_maturity_pillar1_for_weak():
    idg = {'legacy_authentication_status': 'Enabled and not reviewed', 'pim_pam_status': 'None'}
    assert derive_identity_governance_maturity(idg).startswith('Pillar 1')

def test_monitoring_unknown_yields_reasonable_category():
    mon = {'monitoring_coverage': 'Unknown', 'response_authority': 'Unknown'}
    res = derive_monitoring_maturity(mon)
    assert res in ('Insufficient Evidence', 'Pillar 2', 'Pillar 3')

def test_recovery_weak_gives_pillar1():
    rec = {'restore_testing': 'Never', 'immutability_status': 'None'}
    assert derive_recovery_assurance_maturity(rec).startswith('Pillar 1')
