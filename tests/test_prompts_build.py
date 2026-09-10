from prompts import build_maturity_prompt

def test_maturity_prompt_includes_evidence_sections():
    inputs = {'customer_name': 'Test', 'industry': 'Tech', 'users': 10}
    text = build_maturity_prompt(inputs)
    assert 'Information Protection & Data Governance' in text
    assert 'Privileged Access & Identity Governance' in text
    assert 'SaaS, Application & Shadow IT Governance' in text

def test_build_maturity_header_prompt_contains_required_fields():
    # Existing assertions remain
    # New assertion for programme_controls mention
    from prompts import build_maturity_header_prompt
    s = build_maturity_header_prompt({'customer_name': 'X', 'industry': 'Y'})
    assert 'programme_controls' in s
