#!/usr/bin/env python3
"""Tag Catalogue auto-generation scaffold

This utility scans the existing prompts.py and data.py models to extract
taggable fields used by the Tag Catalogue (TAGS_REFERENCE) and emits a
JSON dump suitable for CI hooks or local review. It is intentionally light-
weight and safe to run in development environments without requiring a DB.

Usage:
  python tools/generate_tag_catalog.py --out TAGS_REFERENCE.json
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # project root (SecUseCase folder)
PROMPTS_PATH = ROOT / "prompts.py"
DATA_PATH = ROOT / "data.py"
EXPORT_PATH = ROOT / "export.py"
APP_PATH = ROOT / "app.py"


def extract_fields_from_prompts():
    """Extract MaturityReport fields from prompts.py via simple regex scanning.
    This approach scans all Field(...) definitions and collects their metadata.
    """
    text = PROMPTS_PATH.read_text(encoding="utf-8")
    fields = []
    # Generic field pattern across the file
    pattern = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([A-Za-z0-9_\[\]']+)\s*=\s*Field\(description=\"(.*)\"\)", re.M)
    for match in pattern.finditer(text):
        name, dtype, desc = match.group(1), match.group(2), match.group(3)
        fields.append({
            "name": name,
            "data_type": dtype,
            "source": "prompts.py",
            "schema_path": f"MaturityReport.{name}",
            "description": desc,
        })
    return fields


def extract_fields_from_data():
    """Extract governance-related constants and narrative helpers from data.py."""
    text = DATA_PATH.read_text(encoding="utf-8")
    tags = []
    # Extract FULLY_MANAGED_URL / CO_MANAGED_URL if present
    for name in ["FULLY_MANAGED_URL", "CO_MANAGED_URL"]:
        m = re.search(rf"{name}\s*=\s*['\"]([^'\"]+)['\"]", text)
        if m:
            tags.append({
                "name": name.lower(),
                "data_type": "str",
                "source": "data.py",
                "schema_path": f"GOVERNANCE.{name}",
                "description": f"URL for {name.replace('_', ' ')} governance model.",
                "example_value": m.group(1),
            })
    return tags


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=None, help="Output path for JSON dump (optional).")
    args = parser.parse_args()

    results = []
    # Gather prompts-based fields
    results.extend(extract_fields_from_prompts())
    # Gather data/const-based governance items
    results.extend(extract_fields_from_data())

    out = {
        "tags": results,
        "source": {
            "prompts.py": str(PROMPTS_PATH),
            "data.py": str(DATA_PATH),
            "export.py": str(EXPORT_PATH),
            "app.py": str(APP_PATH),
        },
    }

    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    else:
        print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
