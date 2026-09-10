from prompts import build_maturity_prompt

def test_maturity_prompt_includes_evidence_sections():
    inputs = {'customer_name': 'Test', 'industry': 'Tech', 'users': 10}
    text = build_maturity_prompt(inputs)
    assert 'Information Protection & Data Governance' in text
    assert 'Privileged Access & Identity Governance' in text
    assert 'SaaS, Application & Shadow IT Governance' in text
