from typing import List, Dict, Any
import json
import sys

class InjectStateRuntimeError(Exception):
    pass

def load_inject_map(path: str) -> List[Dict[str, Any]]:
    with open(path, 'r') as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise InjectStateRuntimeError("Inject map should be a list of inject dicts")
    return data

def participant_view(inject: Dict[str, Any]) -> Dict[str, Any]:
    # Sanitize to participant-visible fields only
    return {
        "known_facts_before": inject.get("known_facts_before", []),
        "new_confirmed_facts": inject.get("new_confirmed_facts", []),
        "remaining_unknowns": inject.get("remaining_unknowns", []),
        "business_impact_introduction_point": inject.get("business_impact_introduction_point", ""),
        "stakeholder_pressure_introduction_point": inject.get("stakeholder_pressure_introduction_point", ""),
        "decisions_required": inject.get("decisions_required", [])
    }

def is_inject_valid_maybe(inject: Dict[str, Any]) -> bool:
    # Basic mandatory fields (allow absence of some RC1.1+ fields for backward compatibility)
    mandatory = [
        "inject_id","slide_reference","scenario_id",
        "known_facts_before","new_confirmed_facts","remaining_unknowns",
        "business_impact_introduction_point","stakeholder_pressure_introduction_point",
        "decisions_required"
    ]
    for k in mandatory:
        if k not in inject:
            return False
    if not isinstance(inject["known_facts_before"], list) or len(inject["known_facts_before"]) < 1:
        return False
    if not isinstance(inject["new_confirmed_facts"], list) or len(inject["new_confirmed_facts"]) < 1:
        return False
    if not isinstance(inject["remaining_unknowns"], list) or len(inject["remaining_unknowns"]) < 1:
        return False
    if not isinstance(inject["decisions_required"], list) or len(inject["decisions_required"]) < 1:
        return False
    if not isinstance(inject["slide_reference"], str) or not inject["slide_reference"].strip():
        return False
    return True

def run_path(map_path: str) -> List[Dict[str, Any]]:
    inj = load_inject_map(map_path)
    # Produce participant views for injects that are structurally valid
    return [participant_view(i) for i in inj if isinstance(i, dict) and is_inject_valid_maybe(i)]

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 generation/inject_state_runtime.py <path_to_inject_map.json>")
        sys.exit(2)
    path = sys.argv[1]
    views = run_path(path)
    print(json.dumps(views, indent=2))

if __name__ == "__main__":
    main()