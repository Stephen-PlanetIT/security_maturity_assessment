from data import choose_mdr_recommendation

def test_mdr_decision_respects_banned():
    prefs = {
        'stack_philosophy': 'No preference',
        'response_style': 'No preference',
        'transparency': 'No preference',
        'compliance_tooling': 'No preference',
        'commercials': 'No preference'
    }
    ctx = {'banned_vendors': ['Sophos MDR', 'Adlumin MDR']}
    out = choose_mdr_recommendation(prefs, context=ctx)
    assert out['recommendation'] == 'Tie'

def test_mdr_decision_notes_lack_of_24_7():
    prefs = {
        'stack_philosophy': 'No preference',
        'response_style': 'No preference',
        'transparency': 'No preference',
        'compliance_tooling': 'No preference',
        'commercials': 'No preference'
    }
    ctx = {'monitoring_assurance_profile': {'monitoring_coverage': 'Business hours only'}}
    out = choose_mdr_recommendation(prefs, context=ctx)
    assert any('24/7' in r or '24' in r for r in out['rationale'])
