from types import SimpleNamespace
from aar_renderer import build_aar_context, validate_aar_context, SUPPORTED_KEYS, sanitize_text

def test_red_flags_and_lists_are_clean():
    aar = SimpleNamespace(
        customer_name="Client",
        exercise_title="Exercise",
        executive_summary="Summary.",
        overall_maturity_observed="Pillar 2: Proactive",
        capability_assessments=[{"capability":"Incident Response","maturity":"Pillar 2"}],
        scenarios=[{
            "title":"Initial Anomaly",
            "summary":"Suspicious login",
            "objectives":["Validate login"],
            "capabilities_exercised":["Incident Response"],
            "expected_outcomes":["Rapid containment"],
            "outcome_summary":"Contained quickly",
            "injects":[{"simulated_time":"09:15","information_presented":"Unusual sign-in","intended_capability":"Incident Response","response_observed":"Locked","decision_owner":"IR Lead","outcome":"Contained"}]
        }],
        key_strengths=[{"summary":"Rapid containment","evidence_source":"observed","confidence":"High"}],
        critical_gaps_identified=[{"summary":"Delayed logs","rationale":"May delay decisions","evidence_source":"stated","confidence":"Medium"}],
        improvement_actions=[{"priority":"High","recommendation":"Improve logs","accountable_owner":"IR Lead","closure_evidence":"Policy updated"}],
        red_flags=[{"issue":"Out-of-hours escalation unclear","proposed_resolution":"Define and test independent alerting channel.","owner":"Client / Planet IT","discovered_scenario":"Session-wide"}],
        facilitator_observations="",
        exercise_limitations=[],
        approved_distribution=[],
        profile_changes=[],
    )
    ctx = build_aar_context({}, [{"scenario":"Scenario 1","phase":"Detect","decision":"Lock","notes":"Prompt action","simulated_timestamp":"09:15"}], aar, {"min_aar":True})
    ok, defects = validate_aar_context(ctx, SUPPORTED_KEYS, strict=True)
    assert ok, defects
    # Check core lists
    assert isinstance(ctx.get("strengths_render"), list)
    assert isinstance(ctx.get("gaps_render"), list)
    assert isinstance(ctx.get("actions_render"), list)
    # Red flags present and have required fields
    rfl = ctx.get("red_flags")
    assert isinstance(rfl, list) and len(rfl) == 1
    rf = rfl[0]
    for key in ("issue_id","discovered_scenario","issue","proposed_resolution","owner"):
        assert sanitize_text(rf.get(key, "")) != ""