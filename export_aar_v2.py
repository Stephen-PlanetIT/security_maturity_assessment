from __future__ import annotations

"""
export_aar_v2.py — Dedicated AAR exporter integrating the aar_renderer transformation,
sanitisation, template schema enforcement and DOCX QA scan.

This module does NOT gate or suppress Planet IT marketing/appendix sections; those
sections remain visible in the template. We only populate/sanitise the dynamic values.
"""

import io
import os
from typing import Any, Dict, List, Optional

from docxtpl import DocxTemplate  # type: ignore
from config import get_config
from aar_renderer import (
    build_aar_context,
    validate_aar_context,
    qa_scan_docx_bytes,
    _detect_template_schema_version,
    SUPPORTED_KEYS,
)

def _append_immediate_injects_to_notes(ctx: Dict[str, Any], immediate_injects: Optional[List[Dict[str, Any]]]) -> None:
    """Append immediate pivot consequences into session_notes_render narrative."""
    try:
        if isinstance(immediate_injects, list) and immediate_injects:
            pivot_lines = []
            for ii in immediate_injects:
                s = str(ii.get("scenario_title", "") or "")
                p = str(ii.get("phase_title", "") or "")
                cn = str(ii.get("consequence_narrative", "") or "")
                qs = "; ".join([str(x) for x in (ii.get("urgent_pivot_questions", []) or [])])
                parts = [x for x in [f"Scenario: {s}" if s else "", f"Inject: {p}" if p else "", f"Consequence: {cn}" if cn else "", f"Urgent probes: {qs}" if qs else ""] if x]
                if parts:
                    pivot_lines.append("- Pivot — " + " | ".join(parts))
            if pivot_lines:
                ctx["session_notes_render"] = (ctx.get("session_notes_render", "") + ("\n" if ctx.get("session_notes_render") else "") + "\n".join(pivot_lines)).strip()
    except Exception:
        # Non-fatal
        pass


def _populate_always_on_marketing(ctx: Dict[str, Any]) -> None:
    """
    Planet IT sections are always visible. Populate dynamic values here.
    If env/secrets are absent, use safe defaults; never hide sections.
    """
    try:
        phone = get_config("PLANET_PHONE", "01235 433900")
        email = get_config("PLANET_EMAIL", "enquiries@planet-it.net")
        address = get_config("PLANET_ADDRESS", "85F Park Drive, Milton Park, Abingdon, OX14 4RY")
        why = get_config("AAR_MARKETING_WHY", "")
        ped = get_config("AAR_MARKETING_PEDIGREE", "")
        assumptions = get_config("AAR_ASSUMPTIONS_TEXT", "")
        tcs = get_config("AAR_TCS_TEXT", "")
        contacts_text = f"Telephone: {phone}\nEmail: {email}\nAddress: {address}"
        ctx.setdefault("marketing_why_planet", (why or "Planet IT is a leading IT partner delivering measurable outcomes across security, cloud and managed services."))
        ctx.setdefault("marketing_pedigree", (ped or "Since 2003, Planet IT has supported over 2,000 clients across multiple industries with security, backup and transformation programmes."))
        ctx.setdefault("marketing_contacts", contacts_text)
        ctx.setdefault("marketing_assumptions_text", (assumptions or ""))
        ctx.setdefault("marketing_tcs_text", (tcs or ""))
    except Exception:
        # Non-fatal
        pass


def create_tabletop_aar_docx_v2(master_plan: dict, session_notes: list, aar_obj, immediate_injects: Optional[List[Dict[str, Any]]] = None) -> bytes:
    """
    Render an AAR using the updated template (planet_it_tabletop_report_template.docx).
    - Enforces template schema marker: template_schema_version: aar_v2_flattened
    - Transforms/sanitises via aar_renderer.build_aar_context
    - Validates context (pre-render) and runs a post-render QA scan
    - Keeps Planet IT sections always visible (values only populated/sanitised)

    Returns the generated DOCX as bytes, or b"" if validation fails.
    """
    # Locate template
    try:
        template_path = os.path.join(os.path.dirname(__file__), "planet_it_tabletop_report_template.docx")
        if not os.path.exists(template_path):
            return b""
        expected = str(get_config("AAR_EXPECTED_TEMPLATE_VERSION", "aar_v2_flattened"))
        actual = _detect_template_schema_version(template_path) or str(get_config("AAR_TEMPLATE_SCHEMA_VERSION_ACTUAL", ""))
        if actual != expected:
            import logging
            logging.getLogger(__name__).error("Template/render-context mismatch. Expected %s but received %s.", expected, (actual or "missing"))
            return b""
        doc = DocxTemplate(template_path)
    except Exception:
        return b""

    # Optional enrichment hook (non-breaking)
    try:
        from quality_pipeline import process_tabletop_aar  # type: ignore
        if callable(process_tabletop_aar):
            try:
                _res = process_tabletop_aar(master_plan, session_notes, aar_obj, {})
                if isinstance(_res, tuple) and len(_res) >= 2:
                    master_plan, aar_obj = _res[0], _res[1]
            except Exception:
                pass
    except Exception:
        pass

    # Build context via renderer
    flags = {"min_aar": str(get_config("AAR_MIN_MODE", "false")).strip().lower() in ("1","true","yes","on")}
    ctx = build_aar_context(master_plan or {}, session_notes or [], aar_obj, flags)

    # Append dynamic pivots to session notes (narrative only)
    _append_immediate_injects_to_notes(ctx, immediate_injects)

    # Ensure Planet IT sections have values (sections stay in template)
    _populate_always_on_marketing(ctx)

    # Pre-render validation (fail closed)
    ok, defects = validate_aar_context(ctx, SUPPORTED_KEYS, strict=True)
    if not ok:
        import logging
        logging.getLogger(__name__).error("AAR context validation failed: %s", defects)
        return b""

    # Alias reconciliation (common aliases -> canonical keys)
    from export import _reconcile_context_for_template, _xml_escape_dict  # reuse existing helpers
    ctx = _reconcile_context_for_template(doc, ctx, extra_alias={
        "ExecutiveSummary": "executive_summary",
        "SessionNotes": "session_notes_render",
        "KeyStrengths": "strengths_render",
        "CriticalGaps": "gaps_render",
        "ImprovementActions": "actions_render",
        "CapabilityHeatmap": "capability_heatmap_text",
        "WhyPlanetIT": "marketing_why_planet",
        "OurPedigree": "marketing_pedigree",
        "ContactDetails": "marketing_contacts",
        "AssumptionsClientResponsibilities": "marketing_assumptions_text",
        "TermsAndConditions": "marketing_tcs_text",
    }, debug=str(get_config("RENDER_DEBUG", "false")).strip().lower() in ("1","true","yes","on"))

    # Render
    try:
        # Ensure human-readable UK timestamp for display; avoids ISO patterns in visible DOCX
        try:
            _iso_src = ctx.get("generated_at", "") or ""
            from datetime import datetime as _dtcls
            if _iso_src:
                _dt = _dtcls.fromisoformat(str(_iso_src).replace('Z', '+00:00'))
                _generated_at_display = _dt.strftime("%-d %B %Y, %H:%M UTC")
            else:
                _generated_at_display = ""
        except Exception:
            _generated_at_display = ""
        ctx["generated_at"] = _generated_at_display
        ctx["generated_at_display"] = _generated_at_display
        doc.render(_xml_escape_dict(ctx))
    except Exception:
        try:
            minimal = {k: (ctx.get(k, "") or "") for k in ctx.keys()}
            doc.render(_xml_escape_dict(minimal))
        except Exception:
            return b""

    buf = io.BytesIO()
    try:
        doc.save(buf)
        buf.seek(0)
        data = buf.getvalue()
    except Exception:
        return b""

    # Post-render QA scan
    ok_doc, qa_issues = qa_scan_docx_bytes(data)
    if not ok_doc:
        import logging
        logging.getLogger(__name__).error("AAR DOCX QA failed: %s", qa_issues)
        return b""

    return data