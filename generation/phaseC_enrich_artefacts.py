#!/usr/bin/env python3
"""
Phase C: Artefact taxonomy, gating, and question quality

Reads generation/per_inject_state_map_complete_v1.1.enriched.json and:
- Enforces a canonical artefact_class taxonomy for artefacts
- Derives artefact_class from artefact_type when artefact_class is missing
- Ensures artefact metadata fields exist when artefacts are present
- Derives a "questions" surface per inject from remaining_unknowns and decisions_required

Outputs: writes back to generation/per_inject_state_map_complete_v1.1.enriched.json
"""
import json
from typing import Optional

TYPE_TO_CLASS = {
    "email": "email",
    "log": "log",
    "document": "document",
    "prompt": "prompt",
    "dashboard": "dashboard",
    "memo": "memo",
    "ticket": "ticket",
    "image": "image",
    "code": "code"
}

def canonical_artifact_class(a_type: Optional[str]) -> Optional[str]:
    if not a_type:
        return None
    t = str(a_type).lower().strip()
    return TYPE_TO_CLASS.get(t, "other")

def enrich_inject(item: dict) -> dict:
    if not isinstance(item, dict):
        return item

    # Artefact metadata enrichment
    artefact_present = "artefact_reference" in item or "artefact_type" in item
    artefact_fields = [
        "artefact_source","artefact_date","artefact_purpose",
        "artefact_class","artefact_author","artefact_knowledge_level","artefact_audience"
    ]
    if artefact_present:
        for field in artefact_fields:
            item.setdefault(field, "")

        # Derive artefact_class if missing
        if not item.get("artefact_class"):
            ac = canonical_artifact_class(item.get("artefact_type"))
            if ac:
                item["artefact_class"] = ac

    # Root-cause reveal: ensure subfields exist
    root = item.get("root_cause_reveal")
    if not isinstance(root, dict):
        item["root_cause_reveal"] = {
            "hidden_context": "",
            "facilitator_visible_context": "",
            "wrap_up_reveal_point": ""
        }
    else:
        for sub in ("hidden_context","facilitator_visible_context","wrap_up_reveal_point"):
            root.setdefault(sub, "")

    # Ensure progression anchors exist (even if empty)
    item.setdefault("next_inject_trigger", "")
    item.setdefault("previous_inject_id", "")

    # Derive a simple questions surface if not present
    if "questions" not in item or not isinstance(item["questions"], list):
        ru = item.get("remaining_unknowns", []) or []
        dec = item.get("decisions_required", []) or []
        questions = []
        for q in ru:
            if isinstance(q, str) and q.strip():
                questions.append(q.strip())
        for q in dec:
            if isinstance(q, str) and q.strip():
                if q not in questions:
                    questions.append(q.strip())
        item["questions"] = questions

    return item

def main():
    in_path = "generation/per_inject_state_map_complete_v1.1.enriched.json"
    out_path = in_path  # overwrite in place
    with open(in_path, "r") as f:
        data = json.load(f)

    enriched = [enrich_inject(x) for x in data]
    with open(out_path, "w") as f:
        json.dump(enriched, f, indent=2)

    print("Phase C enrichment complete; wrote", out_path)

if __name__ == "__main__":
    main()