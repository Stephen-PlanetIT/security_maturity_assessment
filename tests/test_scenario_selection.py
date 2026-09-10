from scenario_selection import select_scenario_candidate

def test_supplier_shared_accounts_candidate():
    ctx = {
        'third_party_access_profile': {'identity_model': 'Shared accounts', 'mfa_status': 'Not enforced'},
        'critical_asset_profile': {'business_services': ['Finance and payroll']}
    }
    cand = select_scenario_candidate(ctx)
    assert 'Third' in cand['name'] or 'supplier' in cand['key']
