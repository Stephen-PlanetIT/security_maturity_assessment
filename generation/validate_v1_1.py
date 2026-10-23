#!/usr/bin/env python3
"""
Lightweight validator for GenerationContract v1.1 inject map.
- Validates presence of required fields per inject
- Validates root_cause_reveal structure
- Validates non-empty next_inject_trigger and previous_inject_id
- Produces a concise summary of results
"""
import json
import sys

REQUIRED_FIELDS = [
    "inject_id","slide_reference","scenario_id",
    "known_facts_before","new_confirmed_facts","remaining_unknowns",
    "business_impact_introduction_point","stakeholder_pressure_introduction_point",
    "decisions_required","next_inject_trigger","previous_inject_id","root_cause_reveal"
]

ROOT_CAUSE_FIELDS = ["hidden_context","facilitator_visible_context","wrap_up_reveal_point"]

def load_map(path: str):
    with open(path, "r") as f:
        return json.load(f)

def validate_inject(item: dict, idx: int):
    issues = []
    for k in REQUIRED_FIELDS:
        if k not in item:
            issues.append(f"Missing field: {k}")
    rc = item.get("root_cause_reveal")
    if isinstance(rc, dict):
        for f in ROOT_CAUSE_FIELDS:
            if f not in rc:
                issues.append(f"root_cause_reveal missing: {f}")
    else:
        issues.append("root_cause_reveal not a dict")

    # progression check
    if not item.get("next_inject_trigger"):
        issues.append("next_inject_trigger is empty")
    if not item.get("previous_inject_id"):
        issues.append("previous_inject_id is empty")

    return issues

def main():
    path = "generation/per_inject_state_map_complete_v1.1.json"
    try:
        data = load_map(path)
    except Exception as e:
        print(f"ERROR: failed to load JSON: {e}")
        sys.exit(2)

    total = len(data)
    failures = []
    for idx, it in enumerate(data):
        if not isinstance(it, dict):
            failures.append((idx, "Not a dict"))
            continue
        issues = validate_inject(it, idx)
        if issues:
            failures.append((idx, issues))

    print(f"Total inject blocks: {total}")
    print(f"Failures: {len(failures)}")
    if failures:
        for f in failures[:10]:
            idx, detail = f
            print(f" - Inject at index {idx}: {detail}")

if __name__ == "__main__":
    main()