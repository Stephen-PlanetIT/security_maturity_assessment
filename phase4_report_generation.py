#!/usr/bin/env python3
"""
Phase 4 Report Generation
───────────────────────────
Generate a BRANDED report using the new pipeline through the EXISTING export pipeline.
No new architecture, no new processing layers.

Input files (pipeline outputs):
  - exports/authoritative_facts.json
  - exports/domain_packages.json
  - exports/specialist_assessments.json
  - exports/consultant_assessments.json

Output:
  - exports/branded/planet_it_BRANDED_report.docx
  - exports/branded/BRANDED_radar_chart.png (if applicable)
  - exports/branded/export_context_snapshot_phase4.json (audit trail)

Usage:
  python phase4_report_generation.py
"""
from __future__ import annotations
import json
import os
import sys
import copy
from datetime import datetime

# ── Paths ────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")
BRANDED_OUT = os.path.join(EXPORTS_DIR, "branded")
os.makedirs(BRANDED_OUT, exist_ok=True)

PIPELINE_FILES = {
    "authoritative_facts": os.path.join(EXPORTS_DIR, "authoritative_facts.json"),
    "domain_packages": os.path.join(EXPORTS_DIR, "domain_packages.json"),
    "specialist_assessments": os.path.join(EXPORTS_DIR, "specialist_assessments.json"),
    "consultant_assessments": os.path.join(EXPORTS_DIR, "consultant_assessments.json"),
}

# ── Load pipeline outputs ────────────────────────────────────────────────
def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    print("=== Phase 4: BRANDED Report Generation (Existing Export Pipeline) ===")
    print()

    # 1. Load all pipeline outputs
    pipeline_data = {}
    for key, path in PIPELINE_FILES.items():
        if not os.path.exists(path):
            print(f"  ✗ Missing: {path}")
            continue
        data = load_json(path)
        pipeline_data[key] = data
        count = len(data) if isinstance(data, dict) else 0
        print(f"  ✓ Loaded: {os.path.basename(path)} ({count} keys)")

    if not pipeline_data:
        print("ERROR: No pipeline data found. Run phases 1-3 first.")
        sys.exit(1)

    print()

    # 2. Extract consultant assessments (the ground truth for BRANDED report)
    consultant_data = pipeline_data.get("consultant_assessments", {})
    if not consultant_data:
        print("ERROR: consultant_assessments.json is empty or missing.")
        sys.exit(1)

    customer_id = consultant_data.get("customer_id", "BRANDED")
    assessments = consultant_data.get("consultant_assessments", {})

    print(f"  Customer: {customer_id}")
    print(f"  Domains assessed: {list(assessments.keys())}")
    for domain, assessment in assessments.items():
        conf = assessment.get("confidence", 0.0)
        strengths = len(assessment.get("strengths", []))
        gaps = len(assessment.get("gaps", []))
        print(f"    - {domain}: confidence={conf}, strengths={strengths}, gaps={gaps}")
    print()

    # 3. Build render context from consultant assessments
    # This feeds the EXISTING export.py templates — no new rendering logic.
    render_context = {
        "customer_name": customer_id,
        "report_month_year": datetime.now().strftime("%B %Y"),
        "consultant_name": "Automated Pipeline (Phase 4)",
        "account_manager_name": "",
        "approver_name": "",
        "overall_confidence": round(
            sum(a.get("confidence", 0) for a in assessments.values()) / max(len(assessments), 1), 2
        ),
    }

    # Build domain_assessments list from consultant assessments (matching export.py expected format)
    domain_assessments = []
    for domain, assessment in assessments.items():
        domain_assessments.append({
            "domain": domain,
            "confidence": assessment.get("confidence", 0.0),
            "executive_summary": assessment.get("executive_summary", ""),
            "strengths": assessment.get("strengths", []),
            "risks": assessment.get("risks", []),
            "gaps": assessment.get("gaps", []),
            "known_unknowns": assessment.get("known_unknowns", []),
        })
    render_context["domain_assessments"] = domain_assessments

    # Radar scores from consultant confidence (1-3 scale mapped)
    radar_scores = {}
    for domain, assessment in assessments.items():
        conf = assessment.get("confidence", 0.0)
        # Map 0.0-1.0 to 1-3 scale: 0.0→1, 0.5→2, 1.0→3
        if conf < 0.3:
            radar_scores[domain] = 1
        elif conf < 0.7:
            radar_scores[domain] = 2
        else:
            radar_scores[domain] = 3
    render_context["radar_chart_data"] = radar_scores

    # Overall maturity from radar scores (imported from export.py)
    try:
        sys.path.insert(0, BASE_DIR)
        from export import compute_overall_maturity_percent
        maturity_pct, category = compute_overall_maturity_percent(radar_scores)
        render_context["overall_maturity_percent"] = maturity_pct
        render_context["maturity_category"] = category
    except Exception as e:
        print(f"  ⚠ Maturity computation skipped: {e}")
        render_context["overall_maturity_percent"] = 0
        render_context["maturity_category"] = "Unknown"

    print("  Render context built:")
    for key, val in render_context.items():
        if isinstance(val, (list, dict)) and len(str(val)) > 200:
            print(f"    {key}: <{type(val).__name__} [{len(val)} items]>")
        else:
            print(f"    {key}: {val}")
    print()

    # 4. Invoke existing export pipeline
    print("  Invoking existing export pipeline...")
    try:
        from export import create_maturity_docx, _xml_escape_dict

        # Prepare validated context for template rendering
        escaped_context = _xml_escape_dict(render_context)

        # Template path — use the standard Planet IT maturity template
        template_path = os.path.join(
            BASE_DIR,
            "planet_it_maturity_assessment_template_v2.docx"
        )
        if not os.path.exists(template_path):
            template_path = os.path.join(BASE_DIR, "planet_it_maturity_assessment_template.docx")

        if not os.path.exists(template_path):
            print("  ✗ No DOCX template found. Skipping DOCX export.")
        else:
            output_path = os.path.join(BRANDED_OUT, f"BRANDED_maturity_report.docx")
            doc = DocxTemplate(template_path)

            # Apply context to template
            for key, value in escaped_context.items():
                doc.merge_field(key, value)

            # Save
            doc.save(output_path)
            print(f"  ✓ DOCX exported: {output_path}")

    except ImportError as e:
        print(f"  ⚠ Export import skipped: {e}")
    except Exception as e:
        print(f"  ⚠ DOCX export failed: {e}")

    # Try PPTX export if template exists
    try:
        from export import create_pptx_report

        template_path = os.path.join(BASE_DIR, "planet_it_tabletop_template.pptx")
        if os.path.exists(template_path):
            output_path = os.path.join(BRANDED_OUT, f"BRANDED_presenter.pptx")
            create_pptx_render(
                pptx_context=render_context,
                template_path=template_path,
                output_path=output_path,
            )
            print(f"  ✓ PPTX exported: {output_path}")
    except ImportError:
        pass
    except Exception as e:
        print(f"  ⚠ PPTX export skipped: {e}")

    # 5. Write audit trail
    audit_path = os.path.join(BRANDED_OUT, "export_context_snapshot_phase4.json")
    audit_trail = {
        "phase": 4,
        "timestamp": datetime.now().isoformat(),
        "customer_id": customer_id,
        "pipeline_data_loaded": list(PIPELINE_FILES.keys()),
        "assessments_summary": {
            domain: {
                "confidence": a.get("confidence"),
                "strengths_count": len(a.get("strengths", [])),
                "gaps_count": len(a.get("gaps", [])),
            }
            for domain, a in assessments.items()
        },
        "render_context_keys": list(render_context.keys()),
        "radar_scores": radar_scores,
        "overall_maturity_percent": render_context["overall_maturity_percent"],
        "maturity_category": render_context["maturity_category"],
    }
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(audit_trail, f, indent=2)
    print(f"  ✓ Audit trail: {audit_path}")

    print()
    print("=== Phase 4 Report Generation Complete ===")
    print(f"Output directory: {BRANDED_OUT}")
    print()
    return render_context, audit_trail


# ── Main ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ctx, audit = main()