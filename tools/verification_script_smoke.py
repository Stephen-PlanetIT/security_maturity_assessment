#!/usr/bin/env python3
import json
import sys
import os

from core import LLMEngine
from config import get_config, ConfigKey
from prompts import build_maturity_prompt, SYSTEM_PERSONA, MaturityReport, MaturityHeader
from export import create_maturity_docx


def main() -> int:
    # Initialise Azure client
    client = LLMEngine.get_client()
    if not client:
        print("SMOKE: client init failed")
        return 1

    # Resolve deployment from config
    deployment = get_config(ConfigKey.AZURE_DEPLOYMENT, "gpt-4o")

    # Load sample profile (acts as client_inputs)
    try:
        with open("examples/sample_profile_full.json", "r") as f:
            profile = json.load(f)
    except Exception as e:
        print("SMOKE: load profile failed:", e)
        return 1

    # Build maturity prompt (used by hybrid/json paths)
    try:
        maturity_prompt = build_maturity_prompt(profile)
    except Exception as e:
        print("SMOKE: build_maturity_prompt failed:", e)
        maturity_prompt = "{}"

    # Try generation via hybrid → json → composite
    report = None
    path_used = None

    try:
        report = LLMEngine.generate_maturity_report_hybrid(
            client, deployment, SYSTEM_PERSONA, maturity_prompt, MaturityReport
        )
        path_used = "hybrid"
    except Exception as e:
        print("SMOKE: hybrid threw:", e)

    if not report:
        try:
            report = LLMEngine.generate_maturity_report_json_monolithic(
                client, deployment, SYSTEM_PERSONA, maturity_prompt, MaturityReport
            )
            path_used = "json"
        except Exception as e:
            print("SMOKE: json threw:", e)

    if not report:
        try:
            report = LLMEngine.generate_maturity_report_staged_v3(
                client, deployment, SYSTEM_PERSONA, profile, MaturityHeader, MaturityReport
            )
            path_used = "staged_v3"
        except Exception as e:
            print("SMOKE: staged_v3 threw:", e)

    if not report:
        try:
            report = LLMEngine.generate_maturity_report_composite(
                client, deployment, SYSTEM_PERSONA, profile, MaturityReport
            )
            path_used = "composite"
        except Exception as e:
            print("SMOKE: composite threw:", e)

    if not report:
        print("SMOKE: generation failed; last path:", path_used)
        return 1

    print("SMOKE: generation succeeded via", path_used)
    # Content completeness checks
    try:
        da = getattr(report, "domain_assessments", []) or []
        exec_sum = getattr(report, "executive_summary", "") or ""
        coi = getattr(report, "cost_of_inaction", "") or ""
        cg_any = any([(isinstance(getattr(d, 'critical_gaps', []), list) and len(getattr(d, 'critical_gaps', [])) > 0) for d in da])
        actions = getattr(report, "executive_summary_actions", []) or []
        if len(da) < 12 or len(exec_sum) < 300 or len(coi) < 200 or not cg_any or len(actions) < 3:
            print("SMOKE: content incomplete — domains:", len(da), "exec_len:", len(exec_sum), "coi_len:", len(coi), "gaps_present:", cg_any, "actions_len:", len(actions))
            return 1
    except Exception as e:
        print("SMOKE: content check error:", e)
        return 1

    # Export DOCX and write to exports/
    try:
        data = create_maturity_docx(profile, report)
        out_dir = "exports"
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "Smoke_Maturity_Report.docx")
        with open(out_path, "wb") as f:
            f.write(data)
        size = len(data) if data else 0
        print("SMOKE: DOCX bytes:", size, "->", out_path)
        if size < 10240:
            print("SMOKE: DOCX too small; export likely incomplete")
            return 1
        return 0
    except Exception as e:
        print("SMOKE: export failed:", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())