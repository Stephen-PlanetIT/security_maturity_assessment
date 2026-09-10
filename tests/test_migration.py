from consultation_helpers import migrate_profile

def test_migrate_profile_adds_schema_and_cap():
    legacy = {
        'customer_name': 'LegacyCo',
        'industry': 'Technology',
        'users': 100,
        'critical_infra': 'ERP and CRM'
    }
    out = migrate_profile(legacy)
    assert isinstance(out.get('schema_version'), int)
    cap = out.get('critical_asset_profile', {})
    assert isinstance(cap, dict) and cap.get('systems_platforms') == 'ERP and CRM'
    # Original fields preserved
    assert out.get('critical_infra') == 'ERP and CRM'
