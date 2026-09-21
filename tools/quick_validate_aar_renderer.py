import os
from types import SimpleNamespace
from aar_renderer import build_aar_context, validate_aar_context, SUPPORTED_KEYS, _detect_template_schema_version

def main():
    # 1) Verify template schema marker
    p = os.path.join(os.getcwd(), 'planet_it_tabletop_report_template.docx')
    schema = _detect_template_schema_version(p) or 'missing'
    print('TEMPLATE_SCHEMA_VERSION=', schema)

    # 2) Build and validate a minimal context including red_flags without using docxtpl
    aar = SimpleNamespace(
        customer_name='Client',
        exercise_title='Exercise',
        exercise_id='TTX-TEST-001',
        exercise_date='2026-09-17',
        start_time='09:00',
        end_time='12:00',
        exercise_location='Virtual',
        delivery_mode='Remote',
        audience_profile='Blended',
        report_status='Draft',
        report_version='1.0',
        information_classification='Confidential',
        executive_summary='Summary.',
        overall_maturity_observed='Pillar 2: Proactive',
        maturity_rationale='Proactive behaviours observed; telemetry access can improve.',
        capability_assessments=[{'capability': 'Incident Response', 'maturity': 'Pillar 2'}],
        scenarios=[{
            'title': 'Initial Anomaly',
            'summary': 'Suspicious login',
            'objectives': ['Validate login'],
            'capabilities_exercised': ['Incident Response'],
            'expected_outcomes': ['Rapid containment'],
            'outcome_summary': 'Contained quickly',
            'injects': [{
                'simulated_time': '09:15',
                'information_presented': 'Unusual sign-in',
                'intended_capability': 'Incident Response',
                'response_observed': 'Locked',
                'decision_owner': 'IR Lead',
                'outcome': 'Contained'
            }]
        }],
        key_strengths=[{'summary': 'Rapid containment', 'evidence_source': 'observed', 'confidence': 'High'}],
        critical_gaps_identified=[{'summary': 'Delayed logs', 'rationale': 'May delay decisions', 'evidence_source': 'stated', 'confidence': 'Medium'}],
        improvement_actions=[{'priority': 'High', 'recommendation': 'Improve logs', 'accountable_owner': 'IR Lead', 'closure_evidence': 'Policy updated'}],
        red_flags=[{'issue': 'Out-of-hours escalation unclear', 'proposed_resolution': 'Define and test independent alerting channel.', 'owner': 'Client / Planet IT', 'discovered_scenario': 'Session-wide'}],
        facilitator_observations='',
        exercise_limitations=[],
        approved_distribution=[],
        profile_changes=[],
    )
    session_notes = [{
        'scenario': 'Scenario 1',
        'phase': 'Detect',
        'decision': 'Lock',
        'notes': 'Prompt action',
        'simulated_timestamp': '09:15'
    }]

    ctx = build_aar_context({}, session_notes, aar, {'min_aar': True})
    ok, defects = validate_aar_context(ctx, SUPPORTED_KEYS, strict=True)

    print('CONTEXT_VALID=', ok)
    print('DEFECTS=', defects)
    print('FIELDS_SAMPLE=', sorted([k for k in ctx.keys() if k in SUPPORTED_KEYS])[:10], '...')
    print('RED_FLAGS_COUNT=', len(ctx.get('red_flags') or []))
    if ctx.get('red_flags'):
        print('RED_FLAG_SAMPLE=', ctx['red_flags'][0])
    print('STRENGTHS_COUNT=', len(ctx.get('strengths_render') or []))
    print('GAPS_COUNT=', len(ctx.get('gaps_render') or []))
    print('ACTIONS_COUNT=', len(ctx.get('actions_render') or []))

if __name__ == "__main__":
    main()