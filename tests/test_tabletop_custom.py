import pytest
from prompts import build_tabletop_plan_prompt

def test_tabletop_prompt_includes_custom_brief():
    client = {
        "customer_name": "TestCo",
        "critical_infra": "ERP",
        # Minimal required keys referenced in prompt builder; defaults cover the rest
    }
    prompt = build_tabletop_plan_prompt(client, ["Ransomware (Double Extortion)"], custom_brief="Custom cloud outage scenario")
    assert "Custom cloud outage scenario" in prompt

def test_tabletop_prompt_default_without_custom_brief():
    client = {
        "customer_name": "TestCo",
        "critical_infra": "ERP",
    }
    prompt = build_tabletop_plan_prompt(client, ["Ransomware (Double Extortion)"])
    # Ensure we did not inject a placeholder for a non-existent brief
    assert "Include exactly one bespoke scenario" not in prompt