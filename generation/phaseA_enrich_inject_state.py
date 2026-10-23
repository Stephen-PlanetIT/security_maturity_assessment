#!/usr/bin/env python3
"""
Phase A enrichment: canonical InjectState alignment for GenerationContract v1.1.

This script reads generation/per_inject_state_map_complete_v1.1.json and enriches entries
to ensure artefact metadata fields exist when artefacts are present, and that
root_cause_reveal subfields exist. It writes an enriched copy to
generation/per_inject_state_map_complete_v1.1.enriched.json.

Notes:
- This is a preparatory step for Phase B; no structural changes to existing export paths.
- It does not perform validation beyond enrichment; full validation should run via generation/validate_v1_1.py.
"""

import json

def enrich_inject(item: dict) -> dict:
    if not isinstance(item, dict):
        return item
    # Ensure artefact metadata blocks exist when artefact_reference is present
    artefact_present = "artefact_reference" in item or "artefact_type" in item
    artefact_fields = ["artefact_source","artefact_date","artefact_purpose","artefact_class","artefact_author","artefact_knowledge_level","artefact_audience"]
    if artefact_present:
        for field in artefact_fields:
            item.setdefault(field, "")

    # Ensure root_cause_reveal has required subfields
    root = item.get("root_cause_reveal")
    if not isinstance(root, dict):
        item["root_cause_reveal"] = {
            "hidden_context": "",
            "facilitator_visible_context": "",
            "wrap_up_reveal_point": ""
        }
    else:
        for sub in ["hidden_context","facilitator_visible_context","wrap_up_reveal_point"]:
            root.setdefault(sub, "")

    # Ensure progression anchors exist (even if empty for now)
    item.setdefault("next_inject_trigger", "")
    item.setdefault("previous_inject_id", "")

    return item

def main():
    in_path = "generation/per_inject_state_map_complete_v1.1.json"
    out_path = "generation/per_inject_state_map_complete_v1.1.enriched.json"
    with open(in_path, "r") as f:
        data = json.load(f)

    enriched = [enrich_inject(x) for x in data]
    with open(out_path, "w") as f:
        json.dump(enriched, f, indent=2)

    print(f"WROTE {out_path}")

if __name__ == "__main__":
    main()