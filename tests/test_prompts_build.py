from prompts import build_maturity_prompt, build_maturity_header_prompt

def test_maturity_prompt_includes_evidence_sections():
    inputs = {'customer_name': 'Test', 'industry': 'Tech', 'users': 10}
    text = build_maturity_prompt(inputs)
    assert 'Information Protection & Data Governance' in text
    assert 'Privileged Access & Identity Governance' in text
    assert 'SaaS, Application & Shadow IT Governance' in text

def test_build_maturity_header_prompt_mentions_programme_controls():
    s = build_maturity_header_prompt({'customer_name': 'X', 'industry': 'Y'})
    assert 'programme_controls' in s
