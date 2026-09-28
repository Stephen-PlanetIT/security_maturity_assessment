from __future__ import annotations
# export.py
import io
import json
import re
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

# Helper: format threat_scenarios into a readable text block for DOCX rendering
def _format_threat_scenarios(ts):
    try:
        if ts is None:
            return ""
        if not isinstance(ts, list):
            ts = [ts]
        lines = []
        for it in ts:
            if isinstance(it, dict):
                name = it.get("name") or it.get("title") or it.get("id", "")
                narrative = it.get("narrative", "")
            else:
                # Handle Pydantic/BaseModel-style objects gracefully
                try:
                    name = getattr(it, "name", None) or getattr(it, "title", None) or getattr(it, "id", "") or ""
                    narrative = getattr(it, "narrative", "") or ""
                except Exception:
                    name, narrative = "", str(it)
            if name and narrative:
                lines.append(f"{name}: {narrative}")
            elif narrative:
                lines.append(narrative)
            elif name:
                lines.append(str(name))
        return "\n\n".join([l for l in lines if l])
    except Exception:
        return ""
from fpdf import FPDF
from data import format_governance_narrative
from consultation_helpers import (
    format_critical_asset_profile,
    format_information_protection_profile,
    format_identity_governance_profile,
    format_saas_governance_profile,
    format_asset_assurance_profile,
    format_monitoring_assurance_profile,
    format_supplier_assurance_profile,
    format_recovery_assurance_profile,
    format_ir_assurance_profile,
)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Arc
import matplotlib.patheffects as pe
import numpy as np
import os
import tempfile
from config import get_config, ConfigKey, is_tabletop_quality_strict
import logging
_LOGGER = logging.getLogger(__name__)
# Suppress noisy third-party logs early to keep console readable
try:
    _mpl_level = str(get_config("MATPLOTLIB_LOG_LEVEL", "WARNING")).strip().upper()
    _http_level = str(get_config("HTTP_LIB_LOG_LEVEL", "WARNING")).strip().upper()
    logging.getLogger("matplotlib").setLevel(getattr(logging, _mpl_level, logging.WARNING))
    logging.getLogger("matplotlib.font_manager").setLevel(getattr(logging, _mpl_level, logging.WARNING))
    logging.getLogger("httpx").setLevel(getattr(logging, _http_level, logging.WARNING))
    logging.getLogger("httpcore").setLevel(getattr(logging, _http_level, logging.WARNING))
except Exception:
    pass
# Suppress noisy third-party logs as early as possible to avoid console flooding
try:
    _mpl_level = str(get_config("MATPLOTLIB_LOG_LEVEL", "WARNING")).strip().upper()
    _http_level = str(get_config("HTTP_LIB_LOG_LEVEL", "WARNING")).strip().upper()
    logging.getLogger("matplotlib").setLevel(getattr(logging, _mpl_level, logging.WARNING))
    logging.getLogger("matplotlib.font_manager").setLevel(getattr(logging, _mpl_level, logging.WARNING))
    logging.getLogger("httpx").setLevel(getattr(logging, _http_level, logging.WARNING))
    logging.getLogger("httpcore").setLevel(getattr(logging, _http_level, logging.WARNING))
except Exception:
    pass
# Monte Carlo model removed per specification — no import
import re as _re
# Precompiled XML safety regexes (module‑scope, reused by _xml_escape_dict)
AMP_RE = re.compile(r'&(?!amp;|lt;|gt;|quot;|apos;|#[0-9]+;|#x[0-9A-Fa-f]+;)')
INVALID_XML_RE = re.compile(r'[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD]')

def _normalise_key(key: str) -> str:
    try:
        return _re.sub(r"[^a-z0-9]+", "", str(key).lower())
    except Exception:
        return str(key)

def _reconcile_context_for_template(doc, context: dict, extra_alias: dict = None, debug: bool = False) -> dict:
    """
    Reconcile the render context against the template's declared variables.
    - Apply a fixed alias map for common variants.
    - Apply simple normalisation-based mappings for missing keys.
    - Fill any remaining missing keys with safe defaults (empty string).
    Returns a new context dict suitable for doc.render().
    """
    try:
        required = set(doc.get_undeclared_template_variables() or [])
    except Exception:
        required = set()
    if not required:
        return context

    ctx = dict(context) if context is not None else {}
    fixed_alias = {
        "Threat_scenarios": "threat_scenarios",
        "ThreatScenarios": "threat_scenarios",
        "Threat_Scenarios": "threat_scenarios",
        "Success_Criteria": "success_metrics_render",
        "SuccessCriteria": "success_metrics_render",
        "ComplianceAlignment": "compliance_alignment_render",
        "Compliance_Framework": "compliance_alignment_render",
        "Compliance": "compliance_alignment_render",
        # Reinforce common maturity aliases if present in context
        "Exec_Summary": "exec_summary",
        "ExecutiveSummary": "exec_summary",
        "Matrix_Mapping": "matrix_mapping",
        "Roadmap": "roadmap",
        "Radar_Chart": "radar_chart",
        "Maturity_Gauge": "maturity_gauge",
        # Programme: list and controls aliases
        "ProgrammeOptions": "programme_options",
        "Programme_Options": "programme_options",
        "ProgrammeControls": "programme_controls_render",
        "Programme_Controls": "programme_controls_render",
    }
    if isinstance(extra_alias, dict):
        fixed_alias.update(extra_alias)
    for alias, real in fixed_alias.items():
        if alias in required and real in ctx and (alias not in ctx or not ctx.get(alias)):
            ctx[alias] = ctx.get(real, "")

    # Normalised mapping for missing vars
    for var in list(required):
        if var in ctx and ctx.get(var) not in (None, ""):
            continue
        norm = _normalise_key(var)
        found = None
        for k in ctx.keys():
            if _normalise_key(k) == norm:
                found = k
                break
        if found and (var not in ctx or ctx.get(var) in (None, "")):
            ctx[var] = ctx.get(found, "")

    # Final guard: fill any truly missing with safe defaults
    for var in required:
        if var not in ctx or ctx.get(var) is None:
            ctx[var] = ""  # default to empty string for safety

    if debug:
        try:
            missing = sorted([v for v in required if not ctx.get(v)])
            if missing:
                print("DOCX_UNDECLARED_FILL", missing)
        except Exception:
            pass
    return ctx
try:
    from quality_pipeline import process_maturity_report, process_threat_report, get_quality_thresholds, quality_gate_enabled
except Exception:  # Safe fallback if module unavailable
    process_maturity_report = None
    process_threat_report = None
    get_quality_thresholds = None
    quality_gate_enabled = None

# ===== Maturity Gauge (document-only) =====
# Weighted model (Option A): sums to 1.00, elevated Culture
MATURITY_WEIGHTS = {
    # Identity
    "iam": 0.10,
    "privileged_access": 0.07,
    # Endpoint & Network
    "endpoint": 0.10,
    "network": 0.07,
    # Messaging & Cloud
    "email": 0.04,
    "cloud": 0.09,
    # SaaS & Data
    "saas": 0.06,
    "data_security": 0.07,
    # Operations & Assurance
    "secops": 0.12,
    "testing": 0.04,
    "supplier": 0.05,
    "resilience": 0.07,
    "culture": 0.05,
    "grc": 0.04,
    "ai": 0.03,
}

GAUGE_BANDS = [
    ("High Risk", 0, 39),
    ("Needs Attention", 40, 59),
    ("Moderate", 60, 79),
    ("Strong", 80, 100),
]

GAUGE_PALETTE = {
    "High Risk": "#C62828",
    "Needs Attention": "#FB8C00",
    "Moderate": "#FBC02D",
    "Strong": "#2E7D32",
}

def compute_overall_maturity_percent(radar_scores: dict):
    """
    Compute overall maturity percent from radar_chart_data (1–3 per domain),
    using MATURITY_WEIGHTS. Returns (percent:int, category:str).
    Underlying 3-point cap remains intact; we only present a 0–100 label.
    """
    if not isinstance(radar_scores, dict):
        radar_scores = {}
    total = 0.0
    for key, weight in MATURITY_WEIGHTS.items():
        try:
            v = radar_scores.get(key, 1)
            v = 1 if v is None else float(v)
        except Exception:
            v = 1.0
        # Clamp to [1,3]
        if v < 1:
            v = 1.0
        if v > 3:
            v = 3.0
        total += weight * v
    percent = int(round((total / 3.0) * 100))
    if percent < 0:
        percent = 0
    if percent > 100:
        percent = 100
    category = None
    for name, lo, hi in GAUGE_BANDS:
        if lo <= percent <= hi:
            category = name
            break
    if category is None:
        category = "High Risk" if percent < 40 else "Strong"
    return percent, category

def render_maturity_gauge_png(percent: int, category: str, figsize=(3,3), show_center_label=True):
    """
    Render a rounded-ring gauge PNG with smooth band arcs and a category-coloured progress stroke.
    Returns the path to a temporary PNG file.
    """
    # Normalise inputs
    pct = int(max(0, min(100, int(percent))))
    cat_colour = GAUGE_PALETTE.get(category, GAUGE_PALETTE.get("Strong", "#2E7D32"))

    # Geometry and canvas
    R = 1.0           # radius
    LW = 24           # ring thickness (points)
    start_deg = 90    # 12 o'clock

    fig, ax = plt.subplots(figsize=figsize, dpi=240)
    # Expand canvas width to accommodate legend, then reserve a larger right margin
    fig.set_size_inches(figsize[0]*1.5, figsize[1])
    fig.subplots_adjust(left=0.08, right=0.55, top=0.95, bottom=0.08)
    ax.set_aspect('equal')
    ax.axis('off')
    # Prevent cropping of arc patches by fixing axis limits
    ax.set_xlim(-1.2, 1.2)
    ax.set_ylim(-1.2, 1.2)

    # Helper to convert percent to angle (clockwise from 12)
    def to_angle(p):
        return start_deg - (p / 100.0) * 360.0

    # Background track
    bg = Arc((0, 0), 2*R, 2*R, angle=0, theta1=0, theta2=360, linewidth=LW, color="#ECEFF1")
    ax.add_patch(bg)

    # Band strokes up to achieved percent — 0–40–60–80–100
    bands = [
        (0, 40, GAUGE_PALETTE["High Risk"]),
        (40, 60, GAUGE_PALETTE["Needs Attention"]),
        (60, 80, GAUGE_PALETTE["Moderate"]),
        (80, 100, GAUGE_PALETTE["Strong"]),
    ]
    for lo, hi, col in bands:
        seg_lo = lo
        seg_hi = min(hi, pct)
        if seg_hi <= seg_lo:
            continue
        a1, a2 = to_angle(seg_lo) + 0.6, to_angle(seg_hi) - 0.6  # slight gap at joins
        arc = Arc((0, 0), 2*R, 2*R, angle=0, theta1=a2, theta2=a1, linewidth=int(LW * 0.75), color=col)
        arc.set_path_effects([pe.Stroke(linewidth=int(LW * 0.90), foreground='white', alpha=0.12), pe.Normal()])
        ax.add_patch(arc)

    # Progress arc removed — band colouring above fills only up to achieved percent

    # Center label (optional; suppressed for Word where headings render this)
    if show_center_label:
        ax.text(0, 0.05, f"{pct}", ha='center', va='center', fontsize=18, fontweight='bold')
        ax.text(0, -0.16, "/100", ha='center', va='center', fontsize=8, color='#607D8B')
        ax.set_title(f"{category}", fontsize=10, pad=10)

    # Legend aligned to the right, matching band colours
    try:
        handles = [
            Patch(facecolor=GAUGE_PALETTE["Strong"], edgecolor="none", label="Strong (80–100)"),
            Patch(facecolor=GAUGE_PALETTE["Moderate"], edgecolor="none", label="Moderate (60–79)"),
            Patch(facecolor=GAUGE_PALETTE["Needs Attention"], edgecolor="none", label="Needs Attention (40–59)"),
            Patch(facecolor=GAUGE_PALETTE["High Risk"], edgecolor="none", label="High Risk (0–39)"),
        ]
        # Place legend inside the reserved right margin and reduce its footprint
        fig.legend(
            handles=handles,
            loc="center left",
            bbox_to_anchor=(0.60, 0.5),  # nudge further inside the figure
            borderaxespad=0.0,
            frameon=False,
            fontsize=7,
            handlelength=1.2,
            handletextpad=0.6,
            columnspacing=0.6,
        )
    except Exception:
        pass

    tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    try:
        # Save without tight bbox to avoid clipping the ring
        plt.savefig(tmpfile.name, format="png")
        return tmpfile.name
    except Exception:
        plt.close(fig)
        try:
            os.unlink(tmpfile.name)
        except OSError:
            pass
        raise
    finally:
        plt.close(fig)

def _xml_escape_dict(d, _depth=0):
    """Recursively escape &, <, > and coerce None/null-like → "" across dicts/lists/scalars for safe DOCX XML embedding."""
    if _depth > 10:
        return "" if d is None else d
    def _escape_str(s: str) -> str:
        if s is None:
            return ""
        txt = str(s)
        # Normalise sentinel placeholders often leaking into templates
        if txt.strip() in ("None", "null", "[]", "{}"):
            return ""
        # Remove invalid XML 1.0 characters, then escape safely without double-escaping existing entities
        txt = INVALID_XML_RE.sub('', txt)
        txt = AMP_RE.sub('&', txt)
        txt = txt.replace('<', '<').replace('>', '>').replace('"', '"').replace("'", "'")
        return txt

    if isinstance(d, dict):
        escaped = {}
        for key, value in d.items():
            if value is None:
                escaped[key] = ""
            elif isinstance(value, str):
                escaped[key] = _escape_str(value)
            elif isinstance(value, list):
                out_list = []
                for v in value:
                    if v is None:
                        out_list.append("")
                    elif isinstance(v, str):
                        out_list.append(_escape_str(v))
                    elif isinstance(v, dict):
                        out_list.append(_xml_escape_dict(v, _depth=_depth + 1))
                    else:
                        out_list.append(v)
                escaped[key] = out_list
            elif isinstance(value, dict):
                escaped[key] = _xml_escape_dict(value, _depth=_depth + 1)
            else:
                escaped[key] = value
        return escaped
    if isinstance(d, list):
        out_list = []
        for v in d:
            if v is None:
                out_list.append("")
            elif isinstance(v, str):
                out_list.append(_escape_str(v))
            elif isinstance(v, dict):
                out_list.append(_xml_escape_dict(v, _depth=_depth + 1))
            else:
                out_list.append(v)
        return out_list
    if isinstance(d, str):
        return _escape_str(d)
    return "" if d is None else d


# --- CONSULTANT DERIVATIONS & RENDER HELPERS (deterministic; no schema changes) ---
def _priority_weight(p: str) -> int:
    try:
        order = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
        return order.get(str(p).strip().title(), 0)
    except Exception:
        return 0

def _compute_top_priorities_text(improvement_actions) -> str:
    try:
        items = []
        for a in improvement_actions or []:
            try:
                aid = a.get("id") or a.get("Id") or ""
            except Exception:
                aid = ""
            pr = a.get("priority") if isinstance(a, dict) else getattr(a, "priority", "")
            rec = a.get("recommendation") if isinstance(a, dict) else getattr(a, "recommendation", "")
            rat = a.get("rationale") if isinstance(a, dict) else getattr(a, "rationale", "")
            wa = _priority_weight(pr)
            items.append((wa, aid, rec, rat, pr))
        items.sort(key=lambda x: (-x[0], x[1]))
        top = items[:3]
        lines = []
        for idx, (_, aid, rec, rat, pr) in enumerate(top, 1):
            rationale = rat or rec or ""
            lines.append(f"{idx}. {aid} — {pr or 'Priority'}: {rationale}".strip())
        return "\n".join(lines)
    except Exception:
        return ""

def _generate_observation_commentary(obs: dict) -> str:
    try:
        t = str(obs.get("type", "")).strip().lower()
        summary = str(obs.get("summary", "")).strip()
        rationale = str(obs.get("rationale", "")).strip()
        cap = str(obs.get("capability", "")).strip()
        if t == "strength":
            return ("During the exercise, this capability was demonstrated reliably. "
                    "Sustaining this behaviour reduces operational uncertainty and provides a platform for iterative improvement.")
        # gap commentary
        base = ("During discussion, participants identified the issue but deferred immediate containment whilst further validation was undertaken. "
                "Although understandable, this approach may allow an attacker additional time to establish persistence or move laterally.")
        if cap:
            return f"{base} The affected capability was {cap.lower()}, which increases time-to-contain where runbooks are untested."
        return base
    except Exception:
        return ""

def _build_capability_heatmap_text(capability_assessments) -> str:
    try:
        rows = []
        # Header
        rows.append("Capability\tMaturity")
        for ca in capability_assessments or []:
            if isinstance(ca, dict):
                cap = ca.get("capability", "")
                mat = ca.get("maturity", "")
            else:
                cap = getattr(ca, "capability", "")
                mat = getattr(ca, "maturity", "")
            if cap or mat:
                rows.append(f"{cap}\t{mat}")
        return "\n".join(rows)
    except Exception:
        return ""

def _is_empty_value(v) -> bool:
    try:
        if v is None:
            return True
        if isinstance(v, (list, tuple, set, dict)):
            return len(v) == 0
        s = str(v).strip()
        return s == "" or s.lower() in ("unknown", "n/a")
    except Exception:
        return True

def _strip_empty_sections(doc, ctx: dict):
    """
    Remove labelled paragraphs for empty scalar/list sections to avoid blank tables/labels.
    This operates best-effort; safe if anchors are absent.
    """
    try:
        label_map = {
            "Exercise ID": "exercise_id",
            "Location": "exercise_location",
            "Delivery mode": "delivery_mode",
            "Facilitators": "facilitators",
            "Participants": "participants",
            "Report status": "report_status",
            "Version": "report_version",
        }
        # Iterate over all paragraphs and drop those whose labels map to empty values
        paragraphs = list(getattr(doc, "paragraphs", []) or [])
        for p in paragraphs:
            txt = (p.text or "").strip()
            for label, key in label_map.items():
                if txt.startswith(label) and _is_empty_value(ctx.get(key)):
                    try:
                        p._element.getparent().remove(p._element)
                    except Exception:
                        continue
    except Exception:
        pass

def validate_tabletop_master_plan(plan: dict) -> tuple[bool, list[str]]:
    """
    Deterministic validator for TabletopMasterPlan-like dicts.
    Returns (ok, defects). Defect codes:
    - TT-001: Missing exercise_title
    - TT-010: scenarios count outside 2–4
    - TT-101: Scenario missing required field (title/initial_vector/target_assets)
    - TT-120: Injects count outside 3–5 for a scenario
    - TT-201: Inject missing scenario_narrative or expected_mature_response
    - TT-202: Inject missing technical_indicators (>=1) or facilitator_probe_questions (>=2)
    - TT-203: Inject missing decision_threshold
    - TT-301: success_criteria present but empty (advisory)
    - TT-302: evaluation_evidence present but empty (advisory)
    """
    defects: list[str] = []
    try:
        if not isinstance(plan, dict):
            return False, ["TT-000: Plan is not a dict"]
        title = str(plan.get("exercise_title", "")).strip()
        if not title:
            defects.append("TT-001: Missing exercise_title")
        scenarios = plan.get("scenarios") or []
        if not isinstance(scenarios, list):
            scenarios = []
        if not (2 <= len(scenarios) <= 4):
            defects.append("TT-010: scenarios count must be between 2 and 4")
        for si, scn in enumerate(scenarios, 1):
            try:
                stitle = (scn.get("scenario_title", "") if isinstance(scn, dict) else "") or ""
                iv = (scn.get("initial_vector", "") if isinstance(scn, dict) else "") or ""
                ta = scn.get("target_assets", []) if isinstance(scn, dict) else []
                if not stitle or not iv or not (isinstance(ta, list) and len(ta) >= 1):
                    defects.append(f"TT-101: Scenario {si} missing title/initial_vector/target_assets")
                injects = scn.get("injects", []) if isinstance(scn, dict) else []
                if not (isinstance(injects, list) and 3 <= len(injects) <= 5):
                    defects.append(f"TT-120: Scenario {si} injects count must be between 3 and 5")
                for ji, inj in enumerate(injects, 1):
                    try:
                        narr = (inj.get('scenario_narrative', '') if isinstance(inj, dict) else '') or ''
                        exp = (inj.get('expected_mature_response', '') if isinstance(inj, dict) else '') or ''
                        if not narr or not exp:
                            defects.append(f"TT-201: Scenario {si} Inject {ji} missing narrative/expected_mature_response")
                        tis = inj.get('technical_indicators', []) if isinstance(inj, dict) else []
                        fpq = inj.get('facilitator_probe_questions', []) if isinstance(inj, dict) else []
                        if not (isinstance(tis, list) and len(tis) >= 1) or not (isinstance(fpq, list) and len(fpq) >= 2):
                            defects.append(f"TT-202: Scenario {si} Inject {ji} missing indicators/probes")
                        dt = (inj.get('decision_threshold', '') if isinstance(inj, dict) else '') or ''
                        if not dt:
                            defects.append(f"TT-203: Scenario {si} Inject {ji} missing decision_threshold")
                        # Probing fields (strict)
                        syschk = inj.get('systems_to_check', []) if isinstance(inj, dict) else []
                        if not (isinstance(syschk, list) and len(syschk) >= 2):
                            defects.append(f"TT-204: Scenario {si} Inject {ji} missing systems_to_check (>=2)")
                        roles = inj.get('roles_to_engage', []) if isinstance(inj, dict) else []
                        if not (isinstance(roles, list) and len(roles) >= 2):
                            defects.append(f"TT-205: Scenario {si} Inject {ji} missing roles_to_engage (>=2)")
                        runbooks = inj.get('runbook_references', []) if isinstance(inj, dict) else []
                        if not (isinstance(runbooks, list) and len(runbooks) >= 1):
                            defects.append(f"TT-206: Scenario {si} Inject {ji} missing runbook_references (>=1)")
                        hunt = inj.get('evidence_hunt', []) if isinstance(inj, dict) else []
                        if not (isinstance(hunt, list) and len(hunt) >= 2):
                            defects.append(f"TT-207: Scenario {si} Inject {ji} missing evidence_hunt (>=2)")
                        kchecks = inj.get('knowledge_checks', []) if isinstance(inj, dict) else []
                        if not (isinstance(kchecks, list) and len(kchecks) >= 2):
                            defects.append(f"TT-208: Scenario {si} Inject {ji} missing knowledge_checks (>=2)")
                        tb = (inj.get('timebox_hint', '') if isinstance(inj, dict) else '') or ''
                        if not tb:
                            defects.append(f"TT-209: Scenario {si} Inject {ji} missing timebox_hint")
                        # Advisory: if optional fields exist but empty
                        if 'success_criteria' in inj:
                            sc = inj.get('success_criteria') or []
                            if isinstance(sc, list) and len(sc) == 0:
                                defects.append(f"TT-301: Scenario {si} Inject {ji} success_criteria present but empty")
                        if 'evaluation_evidence' in inj:
                            ee = inj.get('evaluation_evidence') or []
                            if isinstance(ee, list) and len(ee) == 0:
                                defects.append(f"TT-302: Scenario {si} Inject {ji} evaluation_evidence present but empty")
                        # Artefact presence and body integrity (strict but advisory gating configurable)
                        arts = inj.get('artefacts', []) if isinstance(inj, dict) else []
                        if not (isinstance(arts, list) and len(arts) >= 1):
                            defects.append(f"TT-210: Scenario {si} Inject {ji} missing artefacts (>=1 required)")
                        else:
                            allowed_types = {"log", "email", "code", "ticket", "screenshot", "configuration"}
                            for idx, ar in enumerate(arts, 1):
                                try:
                                    at = (ar.get('artefact_type') if isinstance(ar, dict) else "") or ""
                                    if at and at not in allowed_types:
                                        defects.append(f"TT-212: Scenario {si} Inject {ji} artefact {idx} has invalid type '{at}'")
                                    body = (ar.get('body') if isinstance(ar, dict) else "") or ""
                                    if len(str(body).strip()) < 60:
                                        defects.append(f"TT-211: Scenario {si} Inject {ji} artefact {idx} body too short or missing (min ~60 chars)")
                                    # TT-213: line-count enforcement by type/profile (heuristic)
                                    try:
                                        lines = [ln for ln in str(body).splitlines() if str(ln).strip()]
                                        lc = len(lines)
                                    except Exception:
                                        lines, lc = [], 0
                                    # Extract profile from metadata if present
                                    prof = ""
                                    try:
                                        meta = ar.get('metadata') if isinstance(ar, dict) else []
                                        if isinstance(meta, list):
                                            for m in meta:
                                                s = str(m).lower()
                                                if s.startswith("profile:"):
                                                    prof = s.split(":", 1)[1].strip()
                                                    break
                                    except Exception:
                                        prof = ""
                                    # Determine minimum lines
                                    min_lines = None
                                    if prof == "sophos/mdr/case":
                                        min_lines = 6
                                    elif at == "log":
                                        min_lines = 5
                                    elif at == "code":
                                        min_lines = 6
                                    elif at == "email":
                                        min_lines = 4
                                    if isinstance(min_lines, int) and lc < min_lines:
                                        defects.append(f"TT-213: Scenario {si} Inject {ji} artefact {idx} insufficient lines for type/profile (min {min_lines})")
                                    # TT-214: required fields for known profiles (contains-check heuristics)
                                    try:
                                        if prof == "sophos/mdr/case":
                                            required_labels = ["Decoded command line:", "Command path:", "Sophos PID:", "Purpose:"]
                                            for lbl in required_labels:
                                                if not any(lbl in ln for ln in lines):
                                                    defects.append(f"TT-214: Scenario {si} Inject {ji} artefact {idx} missing required field '{lbl}' for sophos/mdr/case")
                                                    break
                                        elif prof == "entra/signin":
                                            req_tokens = ["UserPrincipalName=", "AppDisplayName=", "IPAddress="]
                                            joined = "\n".join(lines)
                                            if not all(tok in joined for tok in req_tokens):
                                                defects.append(f"TT-214: Scenario {si} Inject {ji} artefact {idx} missing required tokens for entra/signin")
                                        elif prof == "fortigate/traffic":
                                            req_tokens = ["srcip=", "dstip=", "srcport=", "dstport="]
                                            joined = "\n".join(lines)
                                            if not all(tok in joined for tok in req_tokens):
                                                defects.append(f"TT-214: Scenario {si} Inject {ji} artefact {idx} missing required tokens for fortigate/traffic")
                                        elif prof in ("defender/alert", "sophos/edr"):
                                            req_tokens = ['"timeUtc"', '"alertId"', '"severity"']
                                            joined = "\n".join(lines)
                                            if not all(tok in joined for tok in req_tokens):
                                                defects.append(f"TT-214: Scenario {si} Inject {ji} artefact {idx} missing required fields for {prof}")
                                    except Exception:
                                        pass
                                except Exception:
                                    defects.append(f"TT-211: Scenario {si} Inject {ji} artefact {idx} body too short or missing (min ~60 chars)")
                    except Exception:
                        defects.append(f"TT-299: Scenario {si} Inject {ji} parse error")
            except Exception:
                defects.append(f"TT-199: Scenario {si} parse error")
    except Exception:
        defects.append("TT-999: Unexpected validator error")
    # Additional profile/objectives/scope validation
    try:
        ep = str(plan.get("_exercise_profile", "blended")).lower()
        dp = str(plan.get("_presentation_detail_profile", "standard")).lower()
        if ep not in ("board", "blended", "technical"):
            defects.append("TT-PROFILE-001: Invalid exercise_profile")
        if dp not in ("standard", "detailed"):
            defects.append("TT-PROFILE-002: Invalid presentation_detail_profile")
        # Objectives required non-empty
        objs = plan.get("objectives", [])
        if not isinstance(objs, list) or not any(str(x).strip() for x in objs):
            defects.append("TT-OBJ-001: Objectives must be non-empty")
        # Scope fields required non-empty (support both list and dict legacy)
        scope = plan.get("scope", {})
        if isinstance(scope, dict):
            for k in ("included", "excluded", "assumptions"):
                vals = scope.get(k, [])
                if not isinstance(vals, list) or not any(str(x).strip() for x in vals):
                    defects.append(f"TT-SCOPE-00{k}: Scope field '{k}' must be non-empty")
        else:
            # legacy: treat list scope as 'included' and require non-empty
            if not isinstance(scope, list) or not any(str(x).strip() for x in scope):
                defects.append("TT-SCOPE-LEGACY: Legacy scope list must be non-empty")
    except Exception:
        defects.append("TT-900: Profile/scope validation error")
    ok = not any(d.startswith(("TT-001","TT-010","TT-101","TT-120","TT-201","TT-202","TT-203","TT-204","TT-205","TT-206","TT-207","TT-208","TT-209","TT-PROFILE-","TT-OBJ-","TT-SCOPE-")) for d in defects)
    return ok, defects

def _build_board_summary_text(overall_label: str, overall_percent: int, strengths: list, gaps: list, actions_top3_text: str) -> str:
    try:
        ks = [s.get("summary", "") if isinstance(s, dict) else str(s) for s in strengths or []]
        kg = [g.get("summary", "") if isinstance(g, dict) else str(g) for g in gaps or []]
        ks = [x for x in ks if x][:3]
        kg = [x for x in kg if x][:3]
        lines = []
        lines.append("Overall Assessment")
        lines.append(f"{overall_label} ({overall_percent}/100). The organisation’s cyber resilience reflects this position across core domains.")
        if ks:
            lines.append("\nKey Strengths")
            for x in ks:
                lines.append(f"- {x}")
        if kg:
            lines.append("\nKey Risks")
            for x in kg:
                lines.append(f"- {x}")
        if actions_top3_text:
            lines.append("\nPriority Actions")
            lines.extend(actions_top3_text.splitlines())
        lines.append("\nRecommended Follow-Up Exercise")
        lines.append("Schedule a governance‑focused tabletop to validate incident declaration thresholds, authority pathways, and containment runbooks.")
        return "\n".join(lines)
    except Exception:
        return ""

def _build_rag_summary(report_data, client_inputs: dict, context_dict: dict | None = None) -> list[dict]:
    """
    Build a list of up to three top risks for the RAG summary.
    Each item contains:
      - severity_label: 'RED' | 'AMBER' | 'GREEN'
      - severity_pct: int (e.g., 40 RED, 35 AMBER, 60 GREEN)
      - issue_title: str
      - business_exposure: str
      - priority_action: str
      - suggested_solutions: Optional[List[str]]
    Primary source: executive_summary_action_blocks (heading/risk/actions)
    Secondary: domain_ratings (High Risk domains and lowest percent)
    Fallback: hygiene signals from client_inputs (MFA/Patching/Backups)
    """
    items: list[dict] = []

    def _sev_from_text(txt: str) -> str:
        t = (txt or "").lower()
        if any(k in t for k in ("mfa", "multi-factor", "patch", "patching", "backup", "immutable", "ransomware", "privileged")):
            return "Red"
        return "Amber"

    # 1) Executive Summary Action Blocks
    try:
        blocks = getattr(report_data, "executive_summary_action_blocks", []) or []
        for blk in blocks:
            try:
                heading = getattr(blk, "heading", "") or ""
                risk = getattr(blk, "risk", "") or ""
                acts = getattr(blk, "remediation_actions", []) or []
                sev = _sev_from_text(heading + " " + risk)
                lbl = "RED" if sev == "Red" else ("AMBER" if sev == "Amber" else "GREEN")
                pct = 40 if lbl == "RED" else (35 if lbl == "AMBER" else 60)
                items.append({
                    "severity_label": lbl,
                    "severity_pct": pct,
                    "issue_title": heading or "Top issue",
                    "business_exposure": risk or "",
                    "priority_action": str(acts[0]) if acts else "Prioritise remediation with accountable ownership and evidence.",
                    "suggested_solutions": [str(a) for a in acts][:2],
                })
            except Exception:
                continue
    except Exception:
        pass

    # 2) Domain ratings (High Risk and lowest percent)
    try:
        dr = None
        if isinstance(context_dict, dict):
            dr = context_dict.get("domain_ratings")
        if isinstance(dr, list):
            highs = [d for d in dr if str(d.get("category", "")).strip() == "High Risk"]
            lows = sorted([d for d in dr if isinstance(d.get("percent"), int)], key=lambda x: x.get("percent", 100))
            for d in highs[:2]:
                title = f"Domain: {d.get('domain','Unknown')} in High Risk"
                items.append({
                    "severity_label": "RED",
                    "severity_pct": 40,
                    "issue_title": title,
                    "business_exposure": "Low maturity in this domain materially increases exposure until controls are improved.",
                    "priority_action": "Execute the domain’s top remediation actions with owners and evidence.",
                })
            if not highs and lows:
                d = lows[0]
                title = f"Domain: {d.get('domain','Unknown')} improvement required"
                items.append({
                    "severity_label": "AMBER",
                    "severity_pct": 35,
                    "issue_title": title,
                    "business_exposure": "This domain is comparatively weaker; uplift reduces overall exposure.",
                    "priority_action": "Deliver the domain’s priority improvements and measure evidence.",
                })
    except Exception:
        pass

    # 3) Hygiene fallback (client_inputs) if still empty
    try:
        if not items:
            mfa = str((client_inputs or {}).get("mfa_status", "")).strip()
            patch = str((client_inputs or {}).get("patching", "")).strip()
            bkp = str((client_inputs or {}).get("backups", "")).strip()
            if mfa in ("None", "Privileged Accounts Only") or patch == "Manual / Ad-hoc" or bkp in ("No Formal Backups", "On-Premise Only"):
                items.append({
                    "severity_label": "RED",
                    "severity_pct": 40,
                    "issue_title": "Foundational hygiene gaps",
                    "business_exposure": "Missing universal MFA, automated patching or immutable backups widens the attack surface and prolongs recovery.",
                    "priority_action": "Enforce MFA, automate patching and adopt immutable backups with restore testing.",
                })
    except Exception:
        pass

    # Deduplicate by title and cap to three
    try:
        seen = set()
        dedup = []
        for it in items:
            t = it.get("issue_title", "")
            if t in seen:
                continue
            seen.add(t)
            dedup.append(it)
        items = dedup[:3]
    except Exception:
        items = items[:3] if items else items

    return items

def _adjudicate_known_issues(known_issues_list, rag_list: list[dict]) -> list[dict]:
    """
    Match self-reported issues to top risks (rag_list) using token overlap.
    Returns enriched dicts per issue: issue_text, our_ruling, rationale,
    suggested_remediations, aligned_solutions.
    """
    import re
    def _tok(s):
        s = (s or "").lower()
        return {t for t in re.split(r"[^a-z0-9]+", s) if len(t) >= 3}

    out = []
    rag = rag_list or []
    for it in (known_issues_list or [])[:10]:
        issue = (str(it).strip() if not isinstance(it, dict) else str(it.get("issue_text","")).strip()) or ""
        ruling = ""
        rationale = ""
        rems = []
        sols = []
        itoks = _tok(issue)
        best = None; best_score = 0.0; common = set()
        for r in rag:
            rtoks = _tok(r.get("issue_title",""))
            overlap = len(itoks & rtoks)
            score = overlap / max(len(itoks | rtoks), 1)
            if score > best_score:
                best = r; best_score = score; common = (itoks & rtoks)
        if best:
            title = best.get("issue_title","Top risk")
            lbl = best.get("severity_label","AMBER")
            pct = best.get("severity_pct",35)
            ruling = f"Aligned with top risk: '{title}' ({lbl} {pct}%). Proportionate to observed exposure."
            rationale = f"Matched tokens: {', '.join(sorted(common))}" if common else f"Semantic similarity to '{title}'."
            pa = best.get("priority_action","")
            if pa:
                rems.append(pa)
            ss = best.get("suggested_solutions",[]) or []
            sols = [str(x) for x in ss[:3]]
        else:
            ruling = "Not observed amongst the top three risks; may be context‑specific or lower priority."
            rationale = "No strong token overlap with top risks derived from consultation and domain ratings."
            rems = ["Assign ownership, define acceptance criteria, and plan remediation into the phased roadmap."]
            sols = ["Consultation to validate exposure and, if confirmed, align to relevant workstream."]
        out.append({
            "issue_text": issue or "Issue",
            "our_ruling": ruling,
            "rationale": rationale,
            "suggested_remediations": rems,
            "aligned_solutions": sols
        })
    return out

# --- DISPLAY DERIVATIONS (executive & *_display) ---
def _safe_join(values, sep=", "):
    try:
        vals = []
        for v in (values or []):
            if v is None:
                continue
            vals.append(str(v))
        return sep.join([x for x in vals if x]) if vals else "N/A"
    except Exception:
        return "N/A"

def _first_sentence(text: str) -> str:
    try:
        s = (text or "").strip()
        if not s:
            return ""
        for splitter in (". ", "! ", "? "):
            idx = s.find(splitter)
            if idx != -1:
                return s[:idx+1]
        return s
    except Exception:
        return ""

def _audience_tailor(aud: str) -> str:
    try:
        a = (aud or "Blended").strip().title()
        if a == "Board":
            return "Audience: Board — emphasis on governance thresholds and risk framing."
        if a == "Technical":
            return "Audience: Technical — emphasis on evidence chains and containment runbooks."
        return "Audience: Blended — balanced governance and technical depth."
    except Exception:
        return "Audience: Blended — balanced governance and technical depth."

def _derive_action_displays(actions):
    try:
        for a in actions or []:
            if isinstance(a, dict):
                a.setdefault("supporting_owners_display", _safe_join(a.get("supporting_owners") or []))
                tgt = a.get("target_date") or a.get("target_timeframe") or ""
                a.setdefault("target_display", str(tgt) if str(tgt).strip() else "N/A")
                rd = a.get("review_date") or ""
                a.setdefault("review_date_display", str(rd) if str(rd).strip() else "N/A")
                a.setdefault("dependencies_display", _safe_join(a.get("dependencies") or []))
    except Exception:
        pass
    return actions

def _derive_feedback_displays(feedback):
    try:
        for f in feedback or []:
            if isinstance(f, dict):
                try:
                    cb = f.get("confidence_before")
                    ca = f.get("confidence_after")
                    if cb is not None and ca is not None:
                        delta = float(ca) - float(cb)
                        sign = "+" if delta >= 0 else ""
                        f.setdefault("confidence_change_display", f"{sign}{int(delta)}")
                    else:
                        f.setdefault("confidence_change_display", "N/A")
                except Exception:
                    f.setdefault("confidence_change_display", "N/A")
    except Exception:
        pass
    return feedback

def _derive_followup_displays(fua):
    try:
        d = {}
        if not fua:
            d["outstanding_evidence_display"] = "N/A"
            d["disputed_findings_display"] = "N/A"
            d["retest_required_display"] = "N/A"
            d["action_review_date_display"] = "N/A"
            d["assurance_method_display"] = "N/A"
            return d
        getv = lambda name, default=None: getattr(fua, name, default) if hasattr(fua, name) else (fua.get(name, default) if isinstance(fua, dict) else default)
        d["outstanding_evidence_display"] = _safe_join(getv("outstanding_evidence", []) or [])
        d["disputed_findings_display"] = _safe_join(getv("disputed_findings", []) or [])
        rr = getv("retest_required", None)
        d["retest_required_display"] = "Yes" if bool(rr) else "No"
        ard = getv("action_review_date", "")
        d["action_review_date_display"] = str(ard) if str(ard).strip() else "N/A"
        am = getv("assurance_method", "")
        d["assurance_method_display"] = str(am) if str(am).strip() else "N/A"
        return d
    except Exception:
        return {
            "outstanding_evidence_display": "N/A",
            "disputed_findings_display": "N/A",
            "retest_required_display": "N/A",
            "action_review_date_display": "N/A",
            "assurance_method_display": "N/A",
        }

# --- TEXT CLEANER (UNICODE SAFE) ---
def clean_text(text, mode="pdf"):
    if not text: return ""
    text = text.replace('\xa0', ' ').replace('\t', ' ')
    text = text.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    text = text.replace('–', '-').replace('—', '-') 
    
    text = text.replace('```markdown', '').replace('```', '')
    text = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', r'\1 (\2)', text)
    
    if mode == "pdf":
        text = text.replace('🎯', 'KPI:').replace('✅', '[DONE]').replace('🗓️', 'DATE:').replace('🛡️', 'REC:')
        text = text.replace('🟢', 'WIN:').replace('⚙️', 'SYSTEM:').replace('🔄', 'UPDATE:')
        text = text.replace('🔍', '').replace('💻', '').replace('📚', '').replace('🔥', '').replace('📈', '')

    return text.encode('ascii', 'ignore').decode('ascii').strip()

def chunk_long_words(text):
    words = text.split(' ')
    safe_words = []
    for word in words:
        if len(word) > 75:
            chunked = ' '.join([word[i:i+75] for i in range(0, len(word), 75)])
            safe_words.append(chunked)
        else:
            safe_words.append(word)
    return ' '.join(safe_words)

# --- PDF ENGINE ---
class ReportPDF(FPDF):
    def header(self):
        self.set_fill_color(35, 80, 106) 
        self.rect(0, 0, 210, 20, 'F')   
        self.set_y(6)
        self.set_font('helvetica', 'B', 12)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, 'Security Advisory & Strategic Assessment', align='R', ln=True)
        self.set_y(25)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

def robust_multi_cell(pdf, w, h, txt, align="L", fill=False):
    """A smart Markdown parser that renders visual hierarchy in the PDF."""
    safe_txt = clean_text(txt, "pdf")
    paragraphs = safe_txt.split('\n')

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        pdf.set_x(10)

        # 1. Detect Headers
        if re.match(r'^(#+|////)\s*', para):
            header_text = re.sub(r'^(#+|////)\s*', '', para)
            header_text = header_text.replace('**', '') 
            pdf.ln(4)
            pdf.set_font("helvetica", "B", 11)
            pdf.set_text_color(35, 80, 106) 
            pdf.multi_cell(w=0, h=6, txt=header_text, align="L")
            pdf.set_font("helvetica", "", 10)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(1.5)

        # 2. Detect Bullet Points
        elif re.match(r'^[-*]\s+', para):
            bullet_text = re.sub(r'^[-*]\s+', '', para)
            bullet_text = bullet_text.replace('**', '') 
            safe_para = chunk_long_words(bullet_text)
            pdf.set_x(15) 
            try:
                pdf.multi_cell(w=0, h=5, txt=f"- {safe_para}", align=align, fill=fill)
            except Exception:
                pdf.multi_cell(w=0, h=5, txt="[PDF Rendering Error: Bullet point failed]", align=align)
            pdf.ln(1.5)

        # 3. Normal Paragraph Text
        else:
            para = para.replace('**', '') 
            safe_para = chunk_long_words(para)
            try:
                pdf.multi_cell(w=0, h=5, txt=safe_para, align=align, fill=fill)
            except Exception:
                pdf.multi_cell(w=0, h=5, txt="[PDF Rendering Error: Paragraph text failed]", align=align)
            pdf.ln(3) 

def draw_section_header(pdf, title):
    pdf.ln(5)
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(35, 80, 106) 
    robust_multi_cell(pdf, 0, 8, title)
    pdf.set_draw_color(200, 200, 200) 
    pdf.set_line_width(0.5)
    pdf.line(pdf.get_x(), pdf.get_y(), 195, pdf.get_y()) 
    pdf.ln(4)
    pdf.set_text_color(0, 0, 0)

def draw_estate_summary(pdf, inputs):
    def safe_get(key, default="N/A"):
        val = inputs.get(key, default)
        if isinstance(val, list):
            return ", ".join(val) if val else default
        return str(val) if val else default

    pdf.set_font("helvetica", "B", 13)
    pdf.set_text_color(35, 80, 106) # Dark Blue branding
    pdf.cell(0, 8, "Customer Estate & Engagement Profile", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    def draw_row(label, value):
        pdf.set_x(pdf.l_margin) # Hard-reset the carriage return to the left margin
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(50, 6, label + ":", border=0)
        pdf.set_font("helvetica", "", 10)

        # Fallback to "N/A" if the string is empty to prevent multi_cell from hanging
        safe_string = str(value).strip() if str(value).strip() else "N/A"
        if safe_string == "Unknown":
            safe_string = "Not established during consultation"
        pdf.multi_cell(0, 6, safe_string, border=0)

    # --- Group 1: Organisational Profile ---
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, "Organisational Profile", ln=True)
    pdf.set_text_color(0, 0, 0)
    
    draw_row("Industry", safe_get('industry'))
    draw_row("Headcount", safe_get('users', safe_get('headcount')))
    draw_row("Endpoints / Servers", f"{safe_get('endpoints')} / {safe_get('servers')}")
    draw_row("Target Compliance", safe_get('compliance'))
    draw_row("Crown Jewels", safe_get('critical_infra'))
    # Business Services & Sensitive Data (from structured critical_asset_profile if available)
    try:
        cap = inputs.get('critical_asset_profile', {}) or {}
        bs = ", ".join([str(x) for x in (cap.get('business_services') or [])]) if isinstance(cap.get('business_services'), list) else str(cap.get('business_services') or "")
        sd = ", ".join([str(x) for x in (cap.get('sensitive_data_types') or [])]) if isinstance(cap.get('sensitive_data_types'), list) else str(cap.get('sensitive_data_types') or "")
        if (bs or sd):
            draw_row("Business Services", bs or "N/A")
            draw_row("Sensitive Data", sd or "N/A")
    except Exception:
        pass
    draw_row("Managed Service Status", safe_get('managed_service_status'))
    draw_row("Co-Managed Service Units", safe_get('co_managed_units', 0))
    pdf.ln(3)

    # --- Group 2: Technology Stack ---
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, "Current Technology Stack", ln=True)
    pdf.set_text_color(0, 0, 0)

    draw_row("MDR / SOC Provider", safe_get('mdr_provider'))
    draw_row("Endpoint Security", safe_get('endpoint'))
    draw_row("Network Firewall", safe_get('firewall'))
    draw_row("Identity & Access", safe_get('identity'))
    draw_row("Email Security", safe_get('email'))
    draw_row("Cloud Environment", safe_get('cloud_env'))
    # Structured evidence summaries (compact, omit empty)
    try:
        ip = format_information_protection_profile(inputs.get('information_protection_profile', {}))
        if ip:
            draw_row("Information Protection", ip)
    except Exception:
        pass
    try:
        idg = format_identity_governance_profile(inputs.get('identity_governance_profile', {}))
        if idg:
            draw_row("Identity Governance", idg)
    except Exception:
        pass
    try:
        saas = format_saas_governance_profile(inputs.get('saas_governance_profile', {}))
        if saas:
            draw_row("SaaS Governance", saas)
    except Exception:
        pass
    try:
        aa = format_asset_assurance_profile(inputs.get('asset_assurance_profile', {}))
        if aa:
            draw_row("Asset Assurance", aa)
    except Exception:
        pass
    try:
        mon = format_monitoring_assurance_profile(inputs.get('monitoring_assurance_profile', {}))
        if mon:
            draw_row("Monitoring Coverage", mon)
    except Exception:
        pass
    try:
        sup = format_supplier_assurance_profile(inputs.get('supplier_assurance_profile', {}), inputs.get('third_party_access_profile', {}))
        if sup:
            draw_row("Supplier & 3rd-Party", sup)
    except Exception:
        pass
    try:
        rec = format_recovery_assurance_profile(inputs.get('recovery_assurance_profile', {}))
        if rec:
            draw_row("Recovery Assurance", rec)
    except Exception:
        pass
    try:
        ir = format_ir_assurance_profile(inputs.get('incident_response_assurance_profile', {}))
        if ir:
            draw_row("Incident Response", ir)
    except Exception:
        pass
    pdf.ln(3)

    # --- Group 3: Operations & Validation ---
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, "Operations & Validation", ln=True)
    pdf.set_text_color(0, 0, 0)

    # Trim the lengthy culture tier string for the PDF
    culture = safe_get('savviness')
    if "-" in culture: 
        culture = culture.split("-")[0].strip()
        
    draw_row("Security Culture", culture)
    draw_row("Internal SOC Team", safe_get('in_house_team'))
    draw_row("Penetration Testing", safe_get('pentest_status'))
    draw_row("Vuln Scanning", safe_get('vuln_scanning'))
    
    notes = safe_get('validation_notes', '')
    if notes and notes != "N/A" and notes.lower() != "none":
        draw_row("Validation Notes", notes)

    # Add a visual separator before the Exec Summary begins
    pdf.ln(4)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y())
    pdf.set_draw_color(0, 0, 0)
    pdf.ln(6)

# ==========================================================
# CYBERSECURITY MATURITY ASSESSMENT EXPORTS
# ==========================================================
def generate_radar_chart_from_values(labels, values, max_radius=3, figsize=(4, 4)):
    """
    Generate a radar chart from raw label/value pairs.
    Hard-capped to max radius 3 (Three-Pillar Cyber Resiliency Matrix).
    Returns the path to a temporary PNG file.
    """
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    # Clamp values to [0, max_radius] to respect the hard cap of the Three-Pillar Matrix
    values_clamped = [min(max_radius, max(0, v)) for v in values]
    for label, original, clamped in zip(labels, values, values_clamped):
        if original != clamped:
            import logging
            logging.getLogger(__name__).warning(
                f"Radar chart value for '{label}' clamped from {original} to {clamped}"
            )
    values_closed = values_clamped + values_clamped[:1]
    angles_closed = angles + angles[:1]
    
    fig, ax = plt.subplots(figsize=figsize, subplot_kw=dict(polar=True))
    ax.fill(angles_closed, values_closed, color='#23506A', alpha=0.25)
    ax.plot(angles_closed, values_closed, color='#23506A', linewidth=2)
    
    # Hard lock to the 3-pillar framework
    ax.set_ylim(0, max_radius)
    ax.set_yticks(list(range(1, max_radius+1)))
    ax.set_yticklabels(["Reactive", "Proactive", "Adaptive"], color="grey", size=8)
    
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, size=9)
    
    tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    try:
        plt.savefig(tmpfile.name, format='png', bbox_inches='tight')
        return tmpfile.name
    except Exception:
        plt.close(fig)
        try:
            os.unlink(tmpfile.name)
        except OSError:
            pass
        raise
    finally:
        plt.close(fig)


def _normalize_kd(kd):
    """Normalise key_deliverables to a bullet-text string.
    - If kd is a list, render as bullet points joined by newlines.
    - If kd is a string that resembles a JSON array, parse it and render if successful.
    - Otherwise, return the string value or an empty string.
    """
    if isinstance(kd, list):
        return "\n".join(f"• {str(item)}" for item in kd)
    if isinstance(kd, str):
        s = kd.strip()
        if not s:
            return ""
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return "\n".join(f"• {str(item)}" for item in parsed)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        return s
    return ""

# ==========================================
# THREAT SIMULATOR EXPORTS
# ==========================================
def create_pdf(inputs, scenario_obj, recs, mdr_case):
    pdf = ReportPDF()
    # --- QUALITY PIPELINE (Threat Report PDF) ---
    try:
        if 'process_threat_report' in globals() and callable(process_threat_report) and (quality_gate_enabled() if callable(quality_gate_enabled) else True):
            scenario_obj, mdr_case, recs, _quality = process_threat_report(inputs, scenario_obj, recs, mdr_case)
    except Exception:
        pass
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    robust_multi_cell(pdf, 0, 10, "Tactical Threat Simulation Report", align='C')
    draw_estate_summary(pdf, inputs)
    
    draw_section_header(pdf, "1. Threat Narrative")
    robust_multi_cell(pdf, 0, 5, scenario_obj.narrative)
    
    # --- DUAL TIMELINE: WITHOUT SOPHOS ---
    draw_section_header(pdf, "2a. Attack Timeline (Without Sophos MDR)")
    if hasattr(scenario_obj, 'timelines') and hasattr(scenario_obj.timelines, 'without_sophos'):
        for t_event in scenario_obj.timelines.without_sophos:
            robust_multi_cell(pdf, 0, 5, f"- [{t_event.timestamp}] {t_event.event_description}")
    else:
        # Fallback: render the first half of the timeline as "without Sophos"
        robust_multi_cell(pdf, 0, 5, "[No unmitigated timeline available — attack was fully intercepted by Sophos MDR prior to objective completion.]")
    
    # --- DUAL TIMELINE: WITH SOPHOS ---
    draw_section_header(pdf, "2b. Attack Timeline (With Sophos MDR)")
    for t_event in scenario_obj.timeline:
        robust_multi_cell(pdf, 0, 5, f"- [{t_event.timestamp}] {t_event.event_description}")
        
    pdf.add_page()
    draw_section_header(pdf, "3. Simulated MDR Case Log")
    robust_multi_cell(pdf, 0, 5, mdr_case)
    
    draw_section_header(pdf, "4. Security Testing & Advisory")
    for rec in recs:
        if rec.startswith("• "): 
            rec = rec.replace("• ", "- ")
        robust_multi_cell(pdf, 0, 5, rec)
        
    # Grab the raw output from the FPDF engine
    raw_pdf = pdf.output(dest='S')
    
    # If the library returned an old-school string, encode it
    if isinstance(raw_pdf, str):
        return raw_pdf.encode('latin-1')
        
    # If it's a modern fpdf2 bytearray, safely cast it to bytes
    return bytes(raw_pdf)

def create_tabletop_aar_docx(master_plan: dict, session_notes: list, aar_obj, immediate_injects: list | None = None) -> bytes:
    """
    Render an AAR using a docxtpl template (planet_it_tabletop_report_template.docx).
    Context derives strictly from TabletopAAR and session notes; optional deterministic
    enrichment is applied if process_tabletop_aar is available in quality_pipeline.
    Returns bytes suitable for Streamlit download.
    """
    try:
        template_path = os.path.join(os.path.dirname(__file__), "planet_it_tabletop_report_template.docx")
        if not os.path.exists(template_path):
            # Fail closed with empty payload if template is missing
            return b""
        doc = DocxTemplate(template_path)
    except Exception:
        return b""

    # Extract safe scalars
    try:
        exercise_title = master_plan.get("exercise_title") if isinstance(master_plan, dict) else getattr(master_plan, "exercise_title", "")
    except Exception:
        exercise_title = ""
    try:
        client_name = master_plan.get("client_name") if isinstance(master_plan, dict) else getattr(master_plan, "client_name", "")
    except Exception:
        client_name = ""

    # Lessons learned derived deterministically from session notes + immediate injects
    lessons_learned = []
    if isinstance(session_notes, list):
        for n in session_notes:
            try:
                phase = (n.get("phase", "") if isinstance(n, dict) else "")
                decision = (n.get("decision", "") if isinstance(n, dict) else "")
                notes = (n.get("notes", "") if isinstance(n, dict) else "")
                line = " | ".join([x for x in [phase, decision, notes] if str(x).strip()])
                if line:
                    lessons_learned.append(clean_text(line))
            except Exception:
                continue
    # Append immediate injects to ensure presence in export even if template lacks placeholders
    try:
        if isinstance(immediate_injects, list):
            for ii in immediate_injects:
                try:
                    s = ii.get("scenario_title", "")
                    p = ii.get("phase_title", "")
                    cn = ii.get("consequence_narrative", "")
                    qs = ii.get("urgent_pivot_questions", []) or []
                    line = "[IMMEDIATE INJECT] " + " | ".join([x for x in [s, p, cn, "; ".join([str(x) for x in qs])] if str(x).strip()])
                    if line:
                        lessons_learned.append(clean_text(line))
                except Exception:
                    continue
    except Exception:
        pass

    # Optional deterministic enrichment (Option C)
    critical_gap_pairs = []
    evidence_map_override = []
    try:
        from quality_pipeline import process_tabletop_aar  # optional hook
        if callable(process_tabletop_aar):
            try:
                # Provide client_inputs if available in context to aid deterministic reasons
                client_inputs = {}
                try:
                    # Attempt to import from current session context if available at call sites
                    client_inputs = {}
                except Exception:
                    client_inputs = {}
                _result = process_tabletop_aar(master_plan, session_notes, aar_obj, client_inputs)
                if isinstance(_result, tuple):
                    if len(_result) >= 2 and isinstance(_result[1], list):
                        critical_gap_pairs = _result[1]
                    if len(_result) >= 3 and isinstance(_result[2], list):
                        evidence_map_override = _result[2]
            except Exception:
                critical_gap_pairs = []
                evidence_map_override = []
    except Exception:
        critical_gap_pairs = []
        evidence_map_override = []

    # Assemble render context for docxtpl
    try:
        def _to_dict_list(obj_list):
            out = []
            for o in obj_list or []:
                try:
                    out.append(o.model_dump() if hasattr(o, "model_dump") else dict(o))
                except Exception:
                    try:
                        out.append(json.loads(str(o)))
                    except Exception:
                        out.append({"value": str(o)})
            return out
        key_strengths = _to_dict_list(getattr(aar_obj, "key_strengths", []))
        critical_gaps = _to_dict_list(getattr(aar_obj, "critical_gaps_identified", []))
        improvement_actions = _to_dict_list(getattr(aar_obj, "improvement_actions", []))
        capability_assessments = _to_dict_list(getattr(aar_obj, "capability_assessments", []))
        decisions_open = _to_dict_list(getattr(aar_obj, "decisions_and_open_items", []))
        participant_feedback = _to_dict_list(getattr(aar_obj, "participant_feedback", []))
        profile_changes = _to_dict_list(getattr(aar_obj, "profile_changes", []))
        # Deterministic enrichments for AAR export (no schema changes)
        try:
            # Commentary for observations
            for o in key_strengths:
                if isinstance(o, dict) and not o.get("commentary"):
                    o["commentary"] = _generate_observation_commentary(o)
            for o in critical_gaps:
                if isinstance(o, dict) and not o.get("commentary"):
                    o["commentary"] = _generate_observation_commentary(o)
        except Exception:
            pass
        # Compute Top 3 priorities text
        try:
            top_priorities_text = _compute_top_priorities_text(improvement_actions)
        except Exception:
            top_priorities_text = ""
        # Capability heatmap text from capability assessments (if any)
        try:
            capability_heatmap_text = _build_capability_heatmap_text(capability_assessments)
        except Exception:
            capability_heatmap_text = ""
        # Governance defaults (runtime only; no hardcoded secrets/paths)
        try:
            from datetime import datetime, timezone
            _generated_at_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
        except Exception:
            _generated_at_iso = ""
        # Human-readable UK timestamp for display; avoids ISO patterns in visible DOCX
        try:
            _iso_src = getattr(aar_obj, "generated_at", "") or _generated_at_iso
            from datetime import datetime as _dtcls
            _dt = _dtcls.fromisoformat(str(_iso_src).replace('Z', '+00:00'))
            _generated_at_display = _dt.strftime("%-d %B %Y, %H:%M UTC")
        except Exception:
            _generated_at_display = ""
        # Derive displays for actions, feedback, and follow-up assurance
        try:
            improvement_actions = _derive_action_displays(improvement_actions)
        except Exception:
            pass
        try:
            participant_feedback = participant_feedback or _to_dict_list(getattr(aar_obj, "participant_feedback", []))
            participant_feedback = _derive_feedback_displays(participant_feedback)
        except Exception:
            pass
        try:
            follow_up_assurance_display = _derive_followup_displays(getattr(aar_obj, "follow_up_assurance", None))
        except Exception:
            follow_up_assurance_display = {}
        scenarios_render = _to_dict_list(getattr(aar_obj, "scenarios", []))
        # Back-compat: map legacy remediation_recommendations into simple actions if improvement_actions empty
        recs = getattr(aar_obj, "remediation_recommendations", []) or []
        if not improvement_actions and isinstance(recs, list) and recs:
            improvement_actions = [
                {
                    "id": f"ACT-{i+1:02d}",
                    "category": "process",
                    "recommendation": str(r),
                    "priority": "Medium",
                    "supporting_owners": [],
                    "dependencies": [],
                    "finding_references": [],
                    "scenario_references": [],
                    "rationale": "",
                    "risk_addressed": "",
                    "status": "Proposed",
                    "acceptance_criteria": "",
                    "closure_evidence": "",
                    "validation_method": ""
                } for i, r in enumerate(recs[:10])
            ]
        ctx = {
            "customer_name": client_name or "",
            "exercise_title": exercise_title or "",
            "executive_summary": getattr(aar_obj, "executive_summary", "") or "",
            "overall_maturity_observed": getattr(aar_obj, "overall_maturity_observed", "Unknown") or "Unknown",
            # Session metadata
            "generated_at": _generated_at_display,
            "generated_at_display": _generated_at_display,
            "report_version": getattr(aar_obj, "report_version", "") or "1.0",
            "report_status": getattr(aar_obj, "report_status", "") or "Draft",
            "facilitator_reviewed": getattr(aar_obj, "facilitator_reviewed", False) or False,
            "session_date": getattr(aar_obj, "session_date", "") or "",
            "location": getattr(aar_obj, "location", "") or "",
            "audience": getattr(aar_obj, "audience", "") or "",
            "facilitator": getattr(aar_obj, "facilitator", "") or "",
            "exercise_overview": getattr(aar_obj, "exercise_overview", "") or "",
            "scenario_context": getattr(aar_obj, "scenario_context", "") or "",
            # Objectives and boundaries
            "objectives": getattr(aar_obj, "objectives", []) or [],
            "scope": getattr(aar_obj, "scope", []) or [],
            "assumptions": getattr(aar_obj, "assumptions", []) or [],
            # Scenario/capability coverage
            "scenarios_exercised": getattr(aar_obj, "scenarios_exercised", []) or [],
            "capabilities_exercised": getattr(aar_obj, "capabilities_exercised", []) or [],
            # Evidence-led evaluation
            "key_strengths": key_strengths,
            "critical_gaps_identified": critical_gaps,
            "evidence_map": (evidence_map_override if evidence_map_override else getattr(aar_obj, "evidence_map", []) or []),
            "maturity_rationale": getattr(aar_obj, "maturity_rationale", "") or "",
            # Improvement plan
            "remediation_recommendations": recs,
            "improvement_opportunities": getattr(aar_obj, "improvement_opportunities", []) or [],
            "improvement_plan": getattr(aar_obj, "improvement_plan", []) or [],
            # Feedback and follow-ups
            "participants_feedback": getattr(aar_obj, "participants_feedback", []) or [],
            "facilitator_observations": getattr(aar_obj, "facilitator_observations", []) or [],
            "follow_up_exercise_requirements": getattr(aar_obj, "follow_up_exercise_requirements", []) or [],
            "follow_up_actions": getattr(aar_obj, "follow_up_actions", []) or [],
            # Lessons learned & profile
            "lessons_learned": lessons_learned,
            "delta_notes_for_profile": getattr(aar_obj, "delta_notes_for_profile", "") or "",
            # Optional enrichment pairs: [{"gap": "...", "reason": "..."}]
            "critical_gap_pairs": critical_gap_pairs,
        }
        # Inject newly supported structured fields if present
        try:
            ctx.update({
                "improvement_actions": improvement_actions,
                "capability_assessments": capability_assessments,
                "decisions_and_open_items": decisions_open,
                "participant_feedback": participant_feedback or ctx.get("participants_feedback", []),
                "profile_changes": profile_changes,
                "scenarios": scenarios_render,
                # Explicit feeder keys to align with DOCX placeholders
                "exercise_id": getattr(aar_obj, "exercise_id", "") or "",
                "exercise_date": getattr(aar_obj, "exercise_date", "") or "",
                "start_time": getattr(aar_obj, "start_time", "") or "",
                "end_time": getattr(aar_obj, "end_time", "") or "",
                "exercise_location": getattr(aar_obj, "exercise_location", "") or "",
                "delivery_mode": getattr(aar_obj, "delivery_mode", "") or "",
                "audience_profile": getattr(aar_obj, "audience_profile", "") or "",
                "report_status": getattr(aar_obj, "report_status", "") or "",
                "report_version": getattr(aar_obj, "report_version", "") or "",
                "information_classification": getattr(aar_obj, "information_classification", "") or "",
                # Surface facilitators/participants for Jinja loops
                "facilitators": _to_dict_list(getattr(aar_obj, "facilitators", [])),
                "participants": _to_dict_list(getattr(aar_obj, "participants", [])),
            })
        except Exception:
            pass
    except Exception:
        ctx = {
            "customer_name": client_name or "",
            "exercise_title": exercise_title or "",
            "executive_summary": "",
            "overall_maturity_observed": "Unknown",
            "key_strengths": [],
            "critical_gaps_identified": [],
            "remediation_recommendations": [],
            "lessons_learned": lessons_learned,
            "delta_notes_for_profile": "",
            "critical_gap_pairs": [],
        }

    # Inject executive/display summaries prior to reconcile
    try:
        # Executive top strength/risk
        ets = ""
        if key_strengths:
            s1 = key_strengths[0]
            ets = (s1.get("summary") if isinstance(s1, dict) else str(s1)) or ""
        etr = ""
        if critical_gaps:
            g1 = critical_gaps[0]
            etr = (g1.get("summary") if isinstance(g1, dict) else str(g1)) or ""
        # Executive priority action
        epa = ""
        try:
            if top_priorities_text:
                lines = top_priorities_text.splitlines()
                epa = lines[0] if lines else ""
        except Exception:
            epa = ""
        if not epa and improvement_actions:
            ia1 = improvement_actions[0]
            epa = (ia1.get("recommendation") if isinstance(ia1, dict) else getattr(ia1, "recommendation", "")) or ""
        # Follow-up position
        try:
            fr = ctx.get("facilitator_reviewed", False)
        except Exception:
            fr = False
        try:
            fra = getattr(aar_obj, "facilitator_reviewed_at", "") or ""
        except Exception:
            fra = ""
        try:
            fua = getattr(aar_obj, "follow_up_assurance", None)
            val = getattr(fua, "factual_validation_status", None) if fua is not None else None
            val = val if val is not None else (fua.get("factual_validation_status") if isinstance(fua, dict) else None)
        except Exception:
            val = None
        executive_follow_up_position = "Validation: {v}; Retest: {r}; Approval: {a}".format(
            v=(str(val) if val else "N/A"),
            r=("Yes" if (follow_up_assurance_display.get("retest_required_display") == "Yes") else "No"),
            a=(fra if str(fra).strip() else "N/A"),
        )
        # Business impact summary
        bis = _first_sentence(ctx.get("maturity_rationale", "") or getattr(aar_obj, "maturity_rationale", "") or ctx.get("executive_summary", ""))
        # Cost of inaction summary (fallback)
        coi_sum = ctx.get("cost_of_inaction_summary", "") or getattr(aar_obj, "cost_of_inaction_summary", "") or ctx.get("cost_of_inaction", "")
        # Priority actions summary
        pas = top_priorities_text or ""
        # Audience tailoring summary
        aud = ctx.get("audience_profile") or getattr(aar_obj, "audience_profile", "") or ctx.get("audience", "")
        ats = _audience_tailor(aud)
        # Approved distribution and facilitator review displays
        appr = getattr(aar_obj, "approved_distribution", None)
        approved_distribution_display = _safe_join(appr or [])
        facilitator_review_display = "Reviewed ({ts})".format(ts=fra) if fr else "Not reviewed"
        # Inject into ctx
        ctx.update({
            "executive_top_strength": ets,
            "executive_top_risk": etr,
            "executive_priority_action": epa,
            "executive_follow_up_position": executive_follow_up_position,
            "business_impact_summary": bis,
            "cost_of_inaction_summary": coi_sum or "",
            "priority_actions_summary": pas,
            "audience_tailoring_summary": ats,
            "approved_distribution_display": approved_distribution_display,
            "facilitator_review_display": facilitator_review_display,
            "follow_up_assurance_display": follow_up_assurance_display,
        })
    except Exception:
        pass

    # Reconcile aliases and escape XML-sensitive content
    try:
        debug = str(get_config("RENDER_DEBUG", "false")).strip().lower() in ("1","true","yes","on")
    except Exception:
        debug = False
    try:
        ctx = _reconcile_context_for_template(doc, ctx, debug=debug)
    except Exception:
        pass
    try:
        safe_ctx = _xml_escape_dict(ctx)
    except Exception:
        safe_ctx = ctx

    try:
        doc.render(safe_ctx)
    except Exception:
        # Fail closed; return empty payload if docxtpl render fails
        return b""

    # Strip empty sections (labels) and attach derived sections before saving
    try:
        # Add AI-assisted board summary and Top 3 priorities into context if placeholders exist
        ctx.setdefault("top_priorities", [])
        ctx.setdefault("top_priorities_text", top_priorities_text)
        # Build a concise board summary text (uses overall maturity label/score + strengths/gaps + priorities)
        try:
            overall_label = ctx.get("overall_maturity_observed", "Unknown")
            try:
                # Attempt to reuse maturity gauge percent from maturity report where applicable; fallback empty
                overall_percent = 0
            except Exception:
                overall_percent = 0
            board_summary_text = _build_board_summary_text(
                overall_label,
                overall_percent,
                ctx.get("key_strengths", []),
                ctx.get("critical_gaps_identified", []),
                top_priorities_text
            )
        except Exception:
            board_summary_text = ""
        if board_summary_text:
            ctx.setdefault("board_summary", board_summary_text)
        if capability_heatmap_text:
            ctx.setdefault("capability_heatmap_text", capability_heatmap_text)
    except Exception:
        pass
    try:
        _strip_empty_sections(doc, ctx)
    except Exception:
        pass
    buf = io.BytesIO()
    try:
        doc.save(buf)
        buf.seek(0)
        return buf.getvalue()
    except Exception:
        return b""

def create_threat_docx(client_inputs: dict, scenario_obj, recs: list, mdr_case: str) -> bytes:
    """Generates a Microsoft Word (.docx) document for the Threat Simulator using docxtpl."""
    template_path = os.path.join(os.path.dirname(__file__), "planet_it_threat_scenario_template.docx")
    doc = DocxTemplate(template_path)
    # Initialise safe local defaults to prevent NameError in Threat export context
    try:
        from types import SimpleNamespace
        report_data = SimpleNamespace()
    except Exception:
        report_data = None
    def _as_list(value):
        if isinstance(value, list):
            return value
        if value is None or value == "":
            return []
        return [value]
    compliance_alignment_render = ""
    _succ_render = ""
    ts_text = ""
    # --- QUALITY PIPELINE (Threat Report DOCX) ---
    try:
        if 'process_threat_report' in globals() and callable(process_threat_report) and (quality_gate_enabled() if callable(quality_gate_enabled) else True):
            scenario_obj, mdr_case, recs, _quality = process_threat_report(client_inputs, scenario_obj, recs, mdr_case)
    except Exception:
        pass

    # Structure the context variables mirroring the template structure
    # Initialize with existing fields for backwards compatibility
    # Compute RAG summary and adjudicated known issues (context-only; no post-render injection)
    try:
        rag_summary = _build_rag_summary(report_data, client_inputs, {"domain_ratings": domain_ratings})
    except Exception:
        rag_summary = []
    try:
        adjudicated_known_issues = _adjudicate_known_issues(client_inputs.get("known_issues") or [], rag_summary)
    except Exception:
        adjudicated_known_issues = []
        
        # Render Programme Controls into a deterministic ASCII-safe string if present
        programme_controls_render = ""
        try:
            pc = getattr(report_data, "programme_controls", None)
            if pc is not None:
                def _getattr(o, name, default=""):
                    try:
                        return getattr(o, name, default)
                    except Exception:
                        return default
                def _get(o, name, default=""):
                    if isinstance(o, dict):
                        return o.get(name, default)
                    return _getattr(o, name, default)
                pcs = [
                    ("Phishing simulations", _get(pc, "phishing_simulations", "")),
                    ("Security training programme", _get(pc, "security_training_programme", "")),
                    ("Endpoint privileges", _get(pc, "endpoint_privileges", "")),
                    ("Reporting routes", _get(pc, "reporting_routes", "")),
                    ("Follow-up coaching", _get(pc, "followup_coaching", "")),
                    ("Role-based training", _get(pc, "role_based_training", "")),
                    ("Leadership engagement", _get(pc, "leadership_engagement", "")),
                    ("Policy acknowledgement", _get(pc, "policy_acknowledgement", "")),
                ]
                metrics = []
                pfr = _get(pc, "phish_failure_rate_90d", None)
                rr = _get(pc, "report_rate_90d", None)
                ccs = _get(pc, "calculated_culture_score", None)
                ctier = _get(pc, "culture_tier", "")
                if pfr is not None:
                    metrics.append(f"Phish failure (90d): {int(pfr)}%")
                if rr is not None:
                    metrics.append(f"Report rate (90d): {int(rr)}%")
                if ccs is not None:
                    metrics.append(f"Culture score: {int(ccs)}/14")
                if ctier:
                    metrics.append(f"Culture tier: {ctier}")
                lines = [f"- {k}: {str(v)}" for k, v in pcs if str(v).strip()]
                if metrics:
                    lines.append("- Metrics: " + "; ".join(metrics))
                programme_controls_render = "\n".join(lines)
        except Exception:
            programme_controls_render = ""
        
        context = {
        # --- Organisational Profile ---
        "customer_name": client_inputs.get("customer_name", "Customer"),
        "consultant_name": client_inputs.get("consultant_name", "Planet IT Consultant"),
        "industry": client_inputs.get("industry", "Unknown"),
        "users": client_inputs.get("users", "0"),
        "endpoints": client_inputs.get("endpoints", "0"),
        "servers": client_inputs.get("servers", "0"),
        "operating_systems": client_inputs.get("operating_systems", "Unknown"),
        "cloud_env": client_inputs.get("cloud_env", "Unknown"),
        "in_house_team": client_inputs.get("in_house_team", "Unknown"),
        "compliance": client_inputs.get("compliance", "None"),
        "critical_infra": client_inputs.get("critical_infra", "Unknown"),
        "managed_service_status": client_inputs.get("managed_service_status", "None"),
        "co_managed_units": client_inputs.get("co_managed_units", 0),
        
        # --- Technology Stack ---
        "mdr_provider": client_inputs.get("mdr_provider", "None"),
        "endpoint": client_inputs.get("endpoint", "Unknown"),
        "endpoint_posture": client_inputs.get("endpoint_posture", "Unknown"),
        "firewall": client_inputs.get("firewall", "Unknown"),
        "identity": client_inputs.get("identity", "Unknown"),
        "email": client_inputs.get("email", "Unknown"),
        "m365_license": client_inputs.get("m365_license", "Unknown"),
        "savviness": client_inputs.get("savviness", "Unknown"),
        
        # --- Operational Telemetry & Validation ---
        "pentest_status": client_inputs.get("pentest_status", "Unknown"),
        "vuln_scanning": client_inputs.get("vuln_scanning", "Unknown"),
        "remote_access": client_inputs.get("remote_access", "Unknown"),
        "saas_backup": client_inputs.get("saas_backup", "Unknown"),
        "ir_readiness": client_inputs.get("ir_readiness", "Unknown"),
        "mfa_status": client_inputs.get("mfa_status", "Unknown"),
        "patching": client_inputs.get("patching", "Unknown"),
        "backups": client_inputs.get("backups", "Unknown"),
        "insurance": client_inputs.get("insurance", "Unknown"),
        "rto": client_inputs.get("rto", "Unknown"),
        "advanced_controls": client_inputs.get("advanced_controls", "None"),
        
        # --- Dual Timeline Context ---
        "threat_narrative": getattr(scenario_obj, "narrative", ""),
        "threat_timeline": getattr(scenario_obj, "timeline", []),
        "threat_timeline_without_sophos": getattr(scenario_obj, "timelines", None).without_sophos if hasattr(scenario_obj, 'timelines') else [],
        "threat_timeline_with_sophos": getattr(scenario_obj, "timelines", None).with_sophos if hasattr(scenario_obj, 'timelines') else getattr(scenario_obj, "timeline", []),
        "mdr_case_log": mdr_case,
        "recommendations": recs,
    }
    # Pre-render alias hydration to reduce template fragility
    try:
        ts_text = _format_threat_scenarios(getattr(report_data, "threat_scenarios", None))
        for alias in ("threat_scenarios", "ThreatScenarios", "Threat_Scenarios", "threat_scenarios_alt"):
            if not context.get(alias):
                context[alias] = ts_text
    except Exception:
        pass
    succ_list = _as_list(getattr(report_data, "success_metrics", None))
    succ_render = "\n".join([f"- {x}" for x in succ_list]) if succ_list else ""
    # Prepopulate alias mappings so templates with various keys render content
    # Use local computed succ_render for all success-related aliases
    if "success_metrics_render" not in locals():
        compliance_alias_guard = None
    # If the template uses different alias names, ensure they're present
    # Ensure aliases map to local render strings to avoid empty placeholders in template
    for _alias in ("success_metrics_render", "success_criteria", "Success_Criteria"):
        if not context.get(_alias):
            context[_alias] = succ_render
    # Compliance alignment: ensure we have a local render string (compat aliasing)
    try:
        comp_render = compliance_alignment_render if 'compliance_alignment_render' in locals() else ""
        if comp_render:
            for _alias in ("ComplianceAlignment", "Compliance_Framework", "compliance_alignment", "compliance_render"):
                if not context.get(_alias):
                    context[_alias] = comp_render
    except Exception:
        pass
    # Threat scenarios: provide a capitalised alias if missing
    if not context.get("Threat_scenarios") and ts_text:
        context["Threat_scenarios"] = ts_text
    # CAP and Partnership aliasing
    if not context.get("CAP_Summary") and getattr(report_data, "cap_summary", None):
        context["CAP_Summary"] = getattr(report_data, "cap_summary", "")
    if not context.get("Partnership") and getattr(report_data, "partnership_outline", ""):
        context["Partnership"] = getattr(report_data, "partnership_outline", "")
    if not context.get("Partnership_Details") and getattr(report_data, "partnership_details", ""):
        context["Partnership_Details"] = getattr(report_data, "partnership_details", "")
        
    # Hardened aliasing for common keys to reduce template fragility
    try:
        for alias in ("success_metrics_render", "success_criteria", "Success_Criteria"):
            if not context.get(alias):
                context[alias] = _succ_render
        comp_render = compliance_alignment_render if 'compliance_alignment_render' in locals() else ""
        for alias in ("ComplianceAlignment", "Compliance_Framework", "Compliance"):
            if not context.get(alias):
                context[alias] = comp_render
    except Exception:
        pass

    # NEW: If envelope-based threat scenario is provided, render the outline parts into separate placeholders
    outline_text = ""
    exec_summary_text = ""
    timeline_text = ""
    impact_text = ""
    mitigations_text = ""
    try:
        outline = getattr(scenario_obj, "outline", None)
        if isinstance(outline, dict):
            exec_summary_text = outline.get("executive_summary", "")
            timeline_list = outline.get("timeline", []) or []
            timeline_text = "\n".join([f"- {t}" for t in timeline_list]) if isinstance(timeline_list, list) else str(timeline_list)
            title_out = outline.get("title", "Threat Scenario Outline")
            outline_text = title_out if title_out else "Threat Scenario Outline"
            impact_text = outline.get("impact", "")
            mitigations_list = outline.get("mitigations", []) or []
            if isinstance(mitigations_list, list):
                mitigations_text = "\n".join([f"- {m}" for m in mitigations_list])
            else:
                mitigations_text = str(mitigations_list)
        # If an envelope is used, try to render the outline block into a single string as well
        envelope_outline = getattr(outline, "outline", None) if not isinstance(outline, dict) else None
    except Exception:
        envelope_outline = None

    if outline is not None and isinstance(outline, dict):
        # Map into the new placeholders used by the template if present
        context.update({
            "ThreatScenarioOutline": outline_text,
            "ThreatScenarioExecutiveSummary": exec_summary_text,
            "ThreatScenarioTimeline": timeline_text,
            "ThreatScenarioImpact": impact_text,
            "ThreatScenarioMitigations": mitigations_text,
        })
    # Precompute Threat Scenarios & Success Criteria aliases before rendering
    ts_text = _format_threat_scenarios(getattr(report_data, "threat_scenarios", None))
    # Normalise common variants to reduce template fragility
    for alias in ("threat_scenarios", "Threat_scenarios", "Threat_Scenarios", "ThreatScenarios", "threat_scenarios_alt"):
        context[alias] = ts_text
        context["Threat_Scenarios"] = ts_text

    _succ = _as_list(getattr(report_data, "success_metrics", None))
    _succ_render = "\\n".join([f"- {x}" for x in _succ]) if _succ else ""
    context["success_metrics_render"] = _succ_render
    context["success_criteria"] = _succ_render
    context["Success_Criteria"] = _succ_render

    # Ensure CAP and compliance aliases are wired to local renders
    cap_summary_text = getattr(report_data, "cap_summary", None)
    if not cap_summary_text:
        cap_summary_text = format_critical_asset_profile(client_inputs.get("critical_asset_profile", {}))
    context["cap_summary"] = cap_summary_text
    context["CAP_Summary"] = cap_summary_text
    context["CAP"] = cap_summary_text
    if not context.get("ComplianceAlignment") and not context.get("Compliance_Framework"):
        comp_render = compliance_alignment_render if 'compliance_alignment_render' in locals() else ""
        if comp_render:
            context["ComplianceAlignment"] = comp_render
            context["Compliance_Framework"] = comp_render
    # Always expose a compliance_render alias as well
    context["compliance_alignment_render"] = compliance_alignment_render
    context["compliance_alignment"] = compliance_alignment_render
    context["success_criteria"] = _succ_render
    context["Success_Criteria"] = _succ_render

    # Compliance aliases
    compliance_render = compliance_alignment_render if 'compliance_alignment_render' in locals() else ""
    context["ComplianceAlignment"] = compliance_render or compliance_render
    context["Compliance_Framework"] = compliance_render or compliance_render
    # Precompute Threat Scenarios & Success Criteria aliases before rendering
    ts_text = _format_threat_scenarios(getattr(report_data, "threat_scenarios", None))
    context["threat_scenarios"] = ts_text
    context["Threat_scenarios"] = ts_text

    _succ = _as_list(getattr(report_data, "success_metrics", None))
    _succ_render = "\n".join([f"- {x}" for x in _succ]) if _succ else ""
    context["success_metrics_render"] = _succ_render
    context["success_criteria"] = _succ_render
    context["Success_Criteria"] = _succ_render

    # Compliance aliases (map to the same string if available)
    compliance_render = compliance_alignment_render if 'compliance_alignment_render' in locals() else ""
    context["ComplianceAlignment"] = compliance_render
    context["Compliance_Framework"] = compliance_render
    # Broaden alias coverage for common template placeholders to reduce render fragility
    try:
        alias_candidates = [
            "Threat_scenarios_alias",
            "Threat_Scenarios",
            "ThreatScenarios",
            "threat_scenarios_alt",
            "Compliance",
            "ComplianceAlignment",
            "Compliance_Framework",
            "Cost_of_inaction",
            "SuccessCriteria",
            "Cost_of_Inaction",
            "Success_Criteria",
        ]
        for a in alias_candidates:
            if a not in context or context.get(a) in ("", None):
                # Map newly known aliases to existing content where reasonable
                if a.lower().find("threat") != -1:
                    context[a] = ts_text
                elif a.lower().find("compliance") != -1:
                    context[a] = compliance_render
                elif a.lower().find("success") != -1:
                    context[a] = _succ_render
                elif a.lower().find("cost") != -1:
                    context[a] = getattr(report_data, 'cost_of_inaction', '') or ''
    except Exception:
        pass
    # Diagnostics (opt-in)
    # Unconditionally log a small render-start message to aid troubleshooting
    try:
        _LOGGER.debug("DOCX render starting: context_keys=%d", len(context.keys()))
        undeclared = []
        try:
            undeclared = doc.get_undeclared_template_variables()
            _LOGGER.debug("DOCX render undeclared placeholders (pre-render): %s", undeclared)
        except Exception:
            pass
    except Exception:
        pass
    try:
        if str(get_config("RENDER_DEBUG", "false")).strip().lower() in ("1","true","yes","on"):
            undeclared = undeclared or []
            _LOGGER.info(
                "DOCX render debug: context_keys=%d; undeclared=%s",
                len(context.keys()),
                sorted(list(undeclared)) if isinstance(undeclared, (set, list, tuple)) else undeclared
            )
            _LOGGER.info(
                "DOCX render debug: threat_scenarios_present=%s; compliance_alignment_len=%s; success_metrics_len=%s",
                bool(getattr(report_data, "threat_scenarios", None)),
                len(getattr(report_data, "compliance_alignment", []) or []),
                len(getattr(report_data, "success_metrics", []) or [])
            )
    except Exception:
        pass
    # Pre-render reconciliation and diagnostics
    try:
        context = _reconcile_context_for_template(doc, context, debug=bool(get_config("RENDER_DEBUG", "false")))
    except Exception:
        pass
    print("DOCX_RENDER_START", "context_keys=", len(context.keys()))
    try:
        if str(get_config("RENDER_DEBUG", "false")).strip().lower() in ("1","true","yes","on"):
            try:
                undeclared = doc.get_undeclared_template_variables()
            except Exception:
                undeclared = []
            print("DOCX_UNDECLARED", sorted(list(undeclared)) if isinstance(undeclared, (set, list, tuple)) else undeclared)
    except Exception:
        pass
    try:
        doc.render(_xml_escape_dict(context))
    except Exception as e:
        try:
            print("DOCX_RENDER_FAIL", repr(e))
        except Exception:
            pass
        # Fallback: render with minimal, safely-escaped context instead of crashing
        minimal = {k: (context.get(k, "") or "") for k in context.keys()}
        try:
            doc.render(_xml_escape_dict(minimal))
        except Exception:
            return b""
    else:
        print("DOCX_RENDER_FINISH")
    # Post-render: inject threat scenarios into the final document if any are present
    try:
        ts_for_inject = getattr(report_data, "threat_scenarios", None)
        if isinstance(ts_for_inject, list) and ts_for_inject:
            _inject_threat_scenarios_after_render(doc, ts_for_inject)
    except Exception:
        pass
    # Before rendering the template, ensure critical aliases exist even if upstream data is sparse
    try:
        if not context.get("threat_scenarios") and getattr(report_data, "threat_scenarios", None):
            ts_text = _format_threat_scenarios(getattr(report_data, "threat_scenarios", None))
            if ts_text:
                context["threat_scenarios"] = ts_text
                context["Threat_scenarios"] = ts_text
                context["Threat_Scenarios"] = ts_text
        if not context.get("cap_summary") and getattr(report_data, "cap_summary", None):
            context["cap_summary"] = getattr(report_data, "cap_summary", "")
            context["CAP_Summary"] = getattr(report_data, "cap_summary", "")
        if not context.get("compliance_alignment_render") and 'compliance_alignment_render' in locals():
            if compliance_alignment_render:
                context["ComplianceAlignment"] = compliance_alignment_render
                context["Compliance_Framework"] = compliance_alignment_render
                context["compliance_alignment_render"] = compliance_alignment_render
                context["compliance_alignment"] = compliance_alignment_render
    except Exception:
        pass

    # Save document into a BytesIO memory stream
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def _inject_threat_scenarios_after_render(doc, threat_scenarios):
    """
    Inject formatted threat scenario content into the Word document.
    Parses the raw threat_scenarios list and creates proper Word formatting:
    bold headers, italic types, section headings, bullets, and paragraphs.
    Inserts content at the {{ threat_scenarios }} placeholder position.
    """
    import re as _re
    from docx.shared import Pt
    from docx.oxml import OxmlElement
    from docx.text.paragraph import Paragraph

    if not threat_scenarios or not isinstance(threat_scenarios, list) or len(threat_scenarios) == 0:
        return

    # Find the {{ threat_scenarios }} placeholder paragraph
    placeholder_element = None
    body_parent = None
    for paragraph in doc.paragraphs:
        if '{{ threat_scenarios }}' in paragraph.text:
            placeholder_element = paragraph._element
            body_parent = paragraph._parent
            break

    if placeholder_element is None:
        try:
            _LOGGER.warning("Threat scenarios placeholder not found in DOCX template; attempting alternative placeholder search.")
        except Exception:
            pass
        return

    # Simple, robust text replacement helper to catch any leftover literal placeholders in the document
    def _replace_text_in_docx(target_doc, old_text: str, new_text: str):
        if not old_text:
            return
        if new_text is None:
            new_text = ""
        # Replace in paragraphs
        for para in target_doc.paragraphs:
            if old_text in para.text:
                # Replace in the text of the paragraph (best-effort)
                para.text = para.text.replace(old_text, new_text)
                # Attempt to replace within runs as well
                for run in para.runs:
                    if old_text in run.text:
                        run.text = run.text.replace(old_text, new_text)
        # Replace in table cells
        for table in getattr(target_doc, 'tables', []):
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        if old_text in para.text:
                            para.text = para.text.replace(old_text, new_text)
                            for run in para.runs:
                                if old_text in run.text:
                                    run.text = run.text.replace(old_text, new_text)

    # Compute the text to inject from threat_scenarios
    ts_text = ts_text if 'ts_text' in locals() else _format_threat_scenarios(threat_scenarios)
    # Inject/replace the exact placeholders across common variants
    if ts_text:
        _replace_text_in_docx(doc, '{{ threat_scenarios }}', ts_text)
        _replace_text_in_docx(doc, '{{ Threat_scenarios }}', ts_text)


    # Helper: create a new paragraph inserted after the given element
    def _new_para_after(prev_el, style=None):
        new_p = OxmlElement('w:p')
        prev_el.addnext(new_p)
        para = Paragraph(new_p, body_parent)
        if style:
            para.style = style
        return para, new_p

    # Track the last inserted element; start inserting after the placeholder
    last_el = [placeholder_element]  # Use list for mutability in nested helpers

    # Helper: parse Markdown-text and add formatted runs to a paragraph
    def _add_formatted_text(para, text):
        """Parse **bold**, *italic*, `inline code`, and [text](url) links in a line and add as runs."""
        # Pattern: Markdown link [text](url), double-star bold, single-star italic, inline code
        pattern = _re.compile(r'\[([^\]]+)\]\(([^)]+)\)|\*\*(.+?)\*\*|(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)|`(.+?)`')
        last_end = 0
        for match in pattern.finditer(text):
            if match.start() > last_end:
                para.add_run(text[last_end:match.start()])
            if match.group(1) is not None and match.group(2) is not None:  # [text](url) Markdown link
                run = para.add_run(f"{match.group(1)} ({match.group(2)})")
                run.italic = True
            elif match.group(3):  # **bold**
                run = para.add_run(match.group(3))
                run.bold = True
            elif match.group(4):  # *italic* (single star, non-overlapping)
                run = para.add_run(match.group(4))
                run.italic = True
            elif match.group(5):  # `code`
                run = para.add_run(match.group(5))
                run.font.name = 'Courier New'
            last_end = match.end()
        if last_end < len(text):
            para.add_run(text[last_end:])

    # Helper: add a blank paragraph spacer
    def _add_spacer():
        spacer, new_el = _new_para_after(last_el[0])
        spacer.paragraph_format.space_after = Pt(6)
        last_el[0] = new_el

    # Helper: render a single block of markdown lines into Word paragraphs
    def _render_markdown_block(lines, last_el_ref):
        """Process a block of markdown lines (split by \n) into Word paragraphs.
        Handles: ### headers, -/* bullets, 1. ordered lists, plain paragraphs."""
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            # Section headers: ### Section ... or ## Section ...
            if _re.match(r'^#{1,4}\s+', line):
                header_text = _re.sub(r'^#{1,4}\s+', '', line)
                h_para, new_el = _new_para_after(last_el_ref[0])
                last_el_ref[0] = new_el
                h_run = h_para.add_run(header_text)
                h_run.bold = True
                h_run.font.size = Pt(11)
                h_para.paragraph_format.space_before = Pt(8)
                i += 1
                continue

            # Ordered list items: 1. 2. 3. etc.
            if _re.match(r'^\d+\.\s+', line):
                item_text = _re.sub(r'^\d+\.\s+', '', line)
                li_para, new_el = _new_para_after(last_el_ref[0], style='List Number')
                last_el_ref[0] = new_el
                _add_formatted_text(li_para, item_text)
                i += 1
                continue

            # Unordered bullet points: - item or * item
            if _re.match(r'^[-*]\s+', line):
                bullet_text = _re.sub(r'^[-*]\s+', '', line)
                b_para, new_el = _new_para_after(last_el_ref[0], style='List Bullet')
                last_el_ref[0] = new_el
                _add_formatted_text(b_para, bullet_text)
                i += 1
                continue

            # Plain paragraph
            p_para, new_el = _new_para_after(last_el_ref[0])
            last_el_ref[0] = new_el
            _add_formatted_text(p_para, line)
            i += 1

    # Build content for each scenario
    for scenario in threat_scenarios:
        name = scenario.get("name", "Threat Scenario") if isinstance(scenario, dict) else getattr(scenario, "name", "Threat Scenario")
        incident_type = scenario.get("incident_type", "") if isinstance(scenario, dict) else getattr(scenario, "incident_type", "")
        narrative = scenario.get("narrative", "") if isinstance(scenario, dict) else getattr(scenario, "narrative", "")

        # Scenario title: bold name + italic type
        title_para, new_el = _new_para_after(last_el[0])
        last_el[0] = new_el
        title_run = title_para.add_run(name)
        title_run.bold = True
        title_run.font.size = Pt(13)
        if incident_type:
            type_run = title_para.add_run(f" ({incident_type})")
            type_run.italic = True
        title_para.paragraph_format.space_before = Pt(12)
        title_para.paragraph_format.space_after = Pt(6)

        # Narrative: split into paragraph blocks by double-newline, then parse each block
        if narrative:
            blocks = narrative.split('\n\n')
            for block in blocks:
                block = block.strip()
                if not block:
                    continue
                block_lines = block.split('\n')
                _render_markdown_block(block_lines, last_el)
                _add_spacer()

    # Remove the original placeholder paragraph
    placeholder_element.getparent().remove(placeholder_element)


def _inject_monte_carlo_section_after_render(doc, mc, mc_text: str = ""):
    """
    Insert a formatted Monte Carlo section at the {{ monte_carlo_section }} anchor, if present; otherwise append at end.
    Renders:
      - Heading: "Monte Carlo Risk Analysis"
      - Summary line with breach probability, AAL, P50/P90/P95/CVaR95
      - Consultant’s interpretation (LLM narrative) if provided
      - Deterministic interpretation paragraph (fallback)
      - Top Exposure Drivers as bullet points (if provided)
      - Assumptions as bullet points (if provided)
    """
    from docx.shared import Pt
    from docx.oxml import OxmlElement
    from docx.text.paragraph import Paragraph

    # Do not return early; we may still need to remove the placeholder even if MC is unavailable
    mc_valid = isinstance(mc, dict) and bool(mc)

    def _new_para_after(prev_el, body_parent, style=None):
        new_p = OxmlElement('w:p')
        prev_el.addnext(new_p)
        para = Paragraph(new_p, body_parent)
        if style:
            try:
                para.style = style
            except Exception:
                pass
        return para, new_p

    def _append_para(doc_obj, style=None):
        para = doc_obj.add_paragraph()
        if style:
            try:
                para.style = style
            except Exception:
                pass
        return para

    # Locate anchor using tolerant regex (supports NBSP and underscores), scanning body and table cells
    placeholder_element = None
    body_parent = None
    try:
        import re as _re_norm
    except Exception:
        _re_norm = re

    ANCHOR_PATTERNS = [
        _re_norm.compile("\\{\\{\\s*monte[\\s_\\u00A0]*carlo[\\s_\\u00A0]*section\\s*\\}\\}", _re_norm.IGNORECASE),
        _re_norm.compile("\\{\\{\\s*mc[\\s_\\u00A0]*section\\s*\\}\\}", _re_norm.IGNORECASE),
    ]

    def _iter_all_paragraphs(doc_obj):
        for p in doc_obj.paragraphs:
            yield p
        for tbl in getattr(doc_obj, 'tables', []) or []:
            for row in tbl.rows:
                for cell in row.cells:
                    for cp in cell.paragraphs:
                        yield cp

    for paragraph in _iter_all_paragraphs(doc):
        txt = (paragraph.text or '').replace('\u00A0', ' ')
        if any(pat.search(txt) for pat in ANCHOR_PATTERNS):
            placeholder_element = paragraph._element
            body_parent = paragraph._parent
            break

    # If MC data is unavailable, remove the placeholder if found and stop
    if not mc_valid:
        if placeholder_element is not None and body_parent is not None:
            placeholder_element.getparent().remove(placeholder_element)
        return

    def _render(after_el=None, body_parent_ref=None):
        # Heading
        if after_el is not None and body_parent_ref is not None:
            h_para, new_el = _new_para_after(after_el, body_parent_ref)
        else:
            h_para = _append_para(doc)
            new_el = None
        run = h_para.add_run("Monte Carlo Risk Analysis")
        run.bold = True
        run.font.size = Pt(13)

        # Summary line
        br = float(mc.get('breach_probability_pct', 0.0))
        aal = float(mc.get('aal_gbp', 0.0))
        p50 = float(mc.get('p50_gbp', 0.0))
        p90 = float(mc.get('p90_gbp', 0.0))
        p95 = float(mc.get('p95_gbp', 0.0))
        cvar95 = float(mc.get('cvar95_gbp', 0.0))
        summary_text = (
            f"Estimated annual breach probability: {br:.1f}% | AAL: £{aal:,.0f} | "
            f"P50: £{p50:,.0f} | P90: £{p90:,.0f} | P95: £{p95:,.0f} | CVaR95: £{cvar95:,.0f}"
        )
        if after_el is not None and body_parent_ref is not None:
            s_para, new_el = _new_para_after(new_el or after_el, body_parent_ref)
        else:
            s_para = _append_para(doc)
        s_para.add_run(summary_text)

        # Consultant’s interpretation (LLM) and deterministic fallback
        if isinstance(mc_text, str) and mc_text.strip():
            if after_el is not None and body_parent_ref is not None:
                ci_head, new_el = _new_para_after(new_el, body_parent_ref)
            else:
                ci_head = _append_para(doc)
            ci_run = ci_head.add_run("Consultant’s interpretation")
            ci_run.bold = True
            ci_run.font.size = Pt(11)
            if after_el is not None and body_parent_ref is not None:
                ci_para, new_el = _new_para_after(new_el, body_parent_ref)
            else:
                ci_para = _append_para(doc)
            ci_para.add_run(str(mc_text))

        expl = mc.get('explanation')
        if expl:
            if after_el is not None and body_parent_ref is not None:
                i_head, new_el = _new_para_after(new_el, body_parent_ref)
            else:
                i_head = _append_para(doc)
            i_run = i_head.add_run("What these numbers mean")
            i_run.bold = True
            i_run.font.size = Pt(11)
            if after_el is not None and body_parent_ref is not None:
                i_para, new_el = _new_para_after(new_el, body_parent_ref)
            else:
                i_para = _append_para(doc)
            i_para.add_run(str(expl))

        # Top Exposure Drivers (if any)
        drivers = mc.get('drivers') or []
        if drivers:
            if after_el is not None and body_parent_ref is not None:
                d_head, new_el = _new_para_after(new_el, body_parent_ref)
            else:
                d_head = _append_para(doc)
            d_run = d_head.add_run("Top Exposure Drivers")
            d_run.bold = True
            d_run.font.size = Pt(11)
            for d in drivers[:3]:
                if after_el is not None and body_parent_ref is not None:
                    d_para, new_el = _new_para_after(new_el, body_parent_ref, style='List Bullet')
                else:
                    d_para = _append_para(doc, style='List Bullet')
                d_para.add_run(str(d))

        # Optional assumptions
        assumptions = mc.get('assumptions', []) or []
        if assumptions:
            if after_el is not None and body_parent_ref is not None:
                a_head, new_el = _new_para_after(new_el, body_parent_ref)
            else:
                a_head = _append_para(doc)
            a_run = a_head.add_run("Assumptions")
            a_run.bold = True
            a_run.font.size = Pt(11)
            for a in assumptions:
                if after_el is not None and body_parent_ref is not None:
                    b_para, new_el = _new_para_after(new_el, body_parent_ref, style='List Bullet')
                else:
                    b_para = _append_para(doc, style='List Bullet')
                b_para.add_run(str(a))

    # [Removed duplicate Monte Carlo rendering block to prevent NameError and double insertion]

    if placeholder_element is not None and body_parent is not None:
        _render(after_el=placeholder_element, body_parent_ref=body_parent)
        placeholder_element.getparent().remove(placeholder_element)
    else:
        _render(after_el=None, body_parent_ref=None)


def create_maturity_docx(client_inputs: dict, report_data, mc_consultative_interpretation: str = "", mc_data=None) -> bytes:
    """
    Cybersecurity Maturity Assessment Word export: renders a Word document using planet_it_maturity_assessment_template.docx.
    Derives domains_list and roadmap_list from report_data defensively.
    Returns bytes of the generated document.
    """
    template_path = os.path.join(os.path.dirname(__file__), "planet_it_maturity_assessment_template.docx")
    doc = DocxTemplate(template_path)
    context = {}
    # Ensure programme locals exist on all paths before context assembly
    programme_options = []
    programme_controls_render = ""

    # Fallback: If the active template does not declare the partnership placeholder,
    # attempt to fall back to the versioned template with the dedicated placeholder.
    try:
        undeclared = doc.get_undeclared_template_variables()
    except Exception:
        undeclared = []
    if isinstance(undeclared, (set, list, tuple)) and "partnership_details" not in undeclared:
        alt_path = os.path.join(os.path.dirname(__file__), "planet_it_maturity_assessment_template_v2.docx")
        if os.path.exists(alt_path):
            template_path = alt_path
            doc = DocxTemplate(template_path)

    # --- QUALITY PIPELINE (Maturity Report) ---
    try:
        if 'process_maturity_report' in globals() and callable(process_maturity_report) and (quality_gate_enabled() if callable(quality_gate_enabled) else True):
            report_data, _quality = process_maturity_report(client_inputs, report_data)
            thr = get_quality_thresholds() if callable(get_quality_thresholds) else {}
            if isinstance(_quality, dict) and not _quality.get('passed', True):
                raise RuntimeError("Quality gate failed: Report did not meet minimum thresholds for authenticity, repetition, commercial balance, or executive readability.")
    except Exception:
        # Fail open: continue export without blocking if pipeline errors
        pass

    # Normalise potential None/scalar optional context fields to list forms for template rendering
    def _as_list(value):
        if isinstance(value, list):
            return value
        if value is None or value == "":
            return []
        return [value]

    # 1) Radar chart image
    data = getattr(report_data, "radar_chart_data", None)
    labels = []
    values = []
    dd = {}
    if data is not None:
        if hasattr(data, "model_dump"):
            dd = data.model_dump()
            labels = list(dd.keys())
            values = list(dd.values())
        elif isinstance(data, dict):
            dd = dict(data)
            labels = list(dd.keys())
            values = list(dd.values())
    chart_path = generate_radar_chart_from_values(labels, values, figsize=(4, 4))
    try:
        with open(chart_path, "rb") as f:
            chart_buffer = io.BytesIO(f.read())
    finally:
        try:
            os.unlink(chart_path)
        except OSError:
            pass
    chart_image = InlineImage(doc, chart_buffer, width=Inches(4))
    # Compute and render overall maturity gauge (document-only)
    overall_percent, overall_category = compute_overall_maturity_percent(dict(zip(labels, values)) if labels and values else {})
    gauge_path = render_maturity_gauge_png(overall_percent, overall_category, show_center_label=True)
    try:
        with open(gauge_path, "rb") as gf:
            gauge_buffer = io.BytesIO(gf.read())
    finally:
        try:
            os.unlink(gauge_path)
        except OSError:
            pass
    maturity_gauge_image = InlineImage(doc, gauge_buffer, width=Inches(2.5))
    # Monte Carlo model removed — do not compute or include MC data
    mc = None

    # --- Domain rating summary (map 1–3 to 0–100 and categorise) ---
    domain_ratings = []
    def _categorise_percent(p):
        for n, lo, hi in GAUGE_BANDS:
            if lo <= p <= hi:
                return n
        return "High Risk" if p < 40 else "Strong"
    # Track pillar distribution while building ratings (v: 1→Pillar 1, 2→Pillar 2, 3→Pillar 3)
    pillar_counts = {"Pillar 1": 0, "Pillar 2": 0, "Pillar 3": 0}
    if labels and values:
        for lbl, val in zip(labels, values):
            try:
                v = float(val)
            except Exception:
                v = 1.0
            if v < 0:
                v = 0.0
            if v > 3:
                v = 3.0
            # Increment pillar counts using nearest-integer style mapping
            if v <= 1.5:
                pillar_counts["Pillar 1"] += 1
            elif v <= 2.5:
                pillar_counts["Pillar 2"] += 1
            else:
                pillar_counts["Pillar 3"] += 1
            pct_val = int(round((v / 3.0) * 100))
            category_val = _categorise_percent(pct_val)
            domain_ratings.append({"domain": lbl, "percent": pct_val, "category": category_val})
    domain_ratings_bullets = "\n".join([f"- {d['domain']}: {d['category']} ({d['percent']}/100)" for d in domain_ratings])
    # Render a concise pillar distribution string for template usage
    maturity_pillar_distribution = (
        f"Domains by Pillar — Pillar 1: {pillar_counts['Pillar 1']}, "
        f"Pillar 2: {pillar_counts['Pillar 2']}, "
        f"Pillar 3: {pillar_counts['Pillar 3']}"
    )
    # Caption for the gauge: category + score + approximate pillar (derived from overall percent)
    try:
        approx_pillar = int(round((overall_percent / 100.0) * 3.0))
    except Exception:
        approx_pillar = 1
    if approx_pillar < 1:
        approx_pillar = 1
    if approx_pillar > 3:
        approx_pillar = 3
    maturity_gauge_caption = (
        f"Overall: {overall_category} ({overall_percent}/100) — approx. Pillar {approx_pillar} weighted across core domains"
    )

    # Precompute per-domain weighted contribution percents from radar dd and MATURITY_WEIGHTS
    domain_weighted_pct_map = {}
    try:
        def _norm_score(v):
            try:
                fv = float(v)
            except Exception:
                fv = 1.0
            if fv < 0:
                fv = 0.0
            if fv > 3:
                fv = 3.0
            return fv
        _DOMAIN_TO_RADAR = {
            "Identity & Access Management": "iam",
            "Privileged Access & Identity Governance": "privileged_access",
            "Endpoint & Device Security": "endpoint",
            "Network & Remote Access Security": "network",
            "Email & Collaboration Security": "email",
            "Cloud & Infrastructure Security": "cloud",
            "SaaS & Application Governance": "saas",
            "Data Security & Information Protection": "data_security",
            "Security Operations & Response": "secops",
            "Security Validation & Testing": "testing",
            "Supplier & Third-Party Security": "supplier",
            "Operational Resilience & Backup": "resilience",
            "Security Culture & Awareness": "culture",
            "Governance, Risk & Compliance": "grc",
            "AI Governance & Security": "ai",
        }
        if isinstance(dd, dict):
            for dname, rkey in _DOMAIN_TO_RADAR.items():
                if rkey in dd and rkey in MATURITY_WEIGHTS:
                    s = _norm_score(dd.get(rkey, 1))
                    w = MATURITY_WEIGHTS.get(rkey, 0.0)
                    pct = int(round(w * (s / 3.0) * 100))
                    if pct < 0:
                        pct = 0
                    if pct > 100:
                        pct = 100
                    domain_weighted_pct_map[dname] = pct
    except Exception:
        domain_weighted_pct_map = {}

    # Build a structured Security Rating dict for the template (no post-render injection)
    try:
        # Primary strengths/gaps derived from executive summary content
        exec_actions = getattr(report_data, "executive_summary_actions", []) or []
        exec_blocks = getattr(report_data, "executive_summary_action_blocks", []) or []
        primary_strengths = [str(x) for x in exec_actions[:3]]
        primary_gaps = []
        for b in exec_blocks[:3]:
            if isinstance(b, dict):
                primary_gaps.append(str(b.get("risk", "")))
            else:
                try:
                    primary_gaps.append(str(getattr(b, "risk", "")))
                except Exception:
                    primary_gaps.append("")
        primary_gaps = [x for x in primary_gaps if x]

        # Weighted areas derived from domain_weighted_pct_map and radar scores
        weighted_areas = []
        try:
            # dd is available when radar_chart_data was model_dumped to dict
            def _indicative_score(key):
                try:
                    v = float(dd.get(key, 1))
                except Exception:
                    v = 1.0
                # clamp 1..3
                if v < 1: v = 1.0
                if v > 3: v = 3.0
                return int(round(v))

            def _domain_rationale(domain_name: str, radar_key: str, weighted_pct: int) -> str:
                """
                Build a concise rationale for the weighted maturity table using existing LLM output:
                - First sentence of business_impact_narrative (if available)
                - Why it matters: weighted_contribution %, indicative score band
                - Executive risk context from executive_summary_action_blocks (first sentence)
                - Priority uplift via the first recommended solution (if present)
                British English; concise; no claims about scoring changes.
                """
                rationale_bits = []

                # 1) Domain business impact (primary)
                try:
                    doms = getattr(report_data, "domain_assessments", []) or getattr(report_data, "domains", []) or []
                    imp = ""
                    rec0 = ""
                    for d in doms:
                        if isinstance(d, dict):
                            name = d.get("domain_name") or d.get("name")
                            if str(name).strip() == str(domain_name).strip():
                                imp = d.get("business_impact_narrative", "") or ""
                                recs = d.get("recommended_solutions", []) or []
                                if isinstance(recs, list) and recs:
                                    rec0 = str(recs[0])
                                break
                        else:
                            name = getattr(d, "domain_name", None) or getattr(d, "name", None)
                            if str(name).strip() == str(domain_name).strip():
                                imp = getattr(d, "business_impact_narrative", "") or ""
                                recs = getattr(d, "recommended_solutions", []) or []
                                if isinstance(recs, list) and recs:
                                    rec0 = str(recs[0])
                                break
                    from_text = _first_sentence(str(imp)) if imp else ""
                    if from_text:
                        rationale_bits.append(from_text)
                except Exception:
                    pass

                # 2) Why it matters (weight and score)
                try:
                    score = _indicative_score(radar_key) if radar_key else 1
                    band = "Reactive" if score == 1 else ("Proactive" if score == 2 else "Adaptive")
                    rationale_bits.append(f"Weighted contribution {int(weighted_pct)}% ({band} control posture observed).")
                except Exception:
                    pass

                # 3) Executive risk linkage (if any)
                try:
                    blks = getattr(report_data, "executive_summary_action_blocks", []) or []
                    clue = ""
                    for b in blks:
                        try:
                            hdr = (b.get("heading","") if isinstance(b, dict) else getattr(b, "heading", "")) or ""
                            risk = (b.get("risk","") if isinstance(b, dict) else getattr(b, "risk", "")) or ""
                            txt = f"{hdr} {risk}".lower()
                            tokens = (domain_name.lower().split() + [str(radar_key).lower()]) if radar_key else domain_name.lower().split()
                            if any(t for t in tokens if t and t in txt):
                                clue = _first_sentence(risk or hdr)
                                break
                        except Exception:
                            continue
                    if clue:
                        rationale_bits.append(clue)
                except Exception:
                    pass

                # 4) Priority uplift (solution hint)
                try:
                    if 'rec0' in locals() and rec0:
                        rationale_bits.append(f"Priority uplift via: {rec0}.")
                except Exception:
                    pass

                # Fallback if empty
                try:
                    if not any(str(x).strip() for x in rationale_bits):
                        score = _indicative_score(radar_key) if radar_key else 1
                        band = "Reactive" if score == 1 else ("Proactive" if score == 2 else "Adaptive")
                        rationale_bits = [f"Current posture: {band}. Focus this area to reduce exposure and improve operational resilience."]
                except Exception:
                    rationale_bits = ["Focus this area to reduce exposure and improve operational resilience."]

                return " ".join([str(x).strip() for x in rationale_bits if str(x).strip()])
        except Exception:
            def _indicative_score(_): return 1

        for dname, pct in (domain_weighted_pct_map or {}).items():
            rkey = _DOMAIN_TO_RADAR.get(dname)
            wt = int(round(MATURITY_WEIGHTS.get(rkey, 0.0) * 100)) if rkey in MATURITY_WEIGHTS else 0
            weighted_areas.append({
                "area": dname,
                    "weight_percent": wt,
                    "indicative_score": _indicative_score(rkey) if rkey else 1,
                    "weighted_contribution": int(pct),
                    "rationale": _domain_rationale(dname, rkey, pct),
                })

        # Maturity bands (static legend used by template)
        maturity_bands = [
            {"score_range": "0–39", "rating": "High Risk", "meaning": "Foundational gaps and reactive posture"},
            {"score_range": "40–59", "rating": "Needs Attention", "meaning": "Proactive improvement underway"},
            {"score_range": "60–79", "rating": "Moderate", "meaning": "Controls maturing; governance stabilising"},
            {"score_range": "80–100", "rating": "Strong", "meaning": "Adaptive and evidence-led resilience"},
        ]

        # Snapshot and statements
        security_rating = {
            "overall_score": int(overall_percent),
            "maturity_rating": str(overall_category),
            "snapshot": {
                "overall_score": int(overall_percent),
                "maturity_rating": str(overall_category),
                "direction_of_travel": "Stable",
                "primary_strengths": primary_strengths,
                "primary_gaps": primary_gaps,
                "board_level_takeaway": "Focus on priority controls that reduce operational disruption and data exposure risk.",
            },
            "weighted_areas": weighted_areas,
            "maturity_bands": maturity_bands,
            "executive_interpretation": "This weighted view balances identity, operations and recovery controls to reflect operational resilience.",
            "score_statement": f"Overall: {overall_category} ({overall_percent}/100).",
            "caveat": ("This score reflects a point-in-time maturity view based on the assessment discussion and supporting notes. "
                       "It is not a certification or independently tested technical rating."),
        }
    except Exception:
        # Fail-closed safe default
        security_rating = {
            "overall_score": 0,
            "maturity_rating": "High Risk",
            "snapshot": {
                "overall_score": 0, "maturity_rating": "High Risk",
                "direction_of_travel": "Stable",
                "primary_strengths": [], "primary_gaps": [],
                "board_level_takeaway": ""
            },
            "weighted_areas": [], "maturity_bands": [],
            "executive_interpretation": "", "score_statement": "", "caveat": ""
        }

    # Derived board summary and capability heatmap text (Maturity) prior to context assembly
    try:
        # Capability heatmap (Detection/Response/Recovery) derived from radar if available
        def _pillar_label(v):
            try:
                fv = float(v)
            except Exception:
                fv = 1.0
            if fv <= 1.5:
                return "Reactive"
            elif fv <= 2.5:
                return "Proactive"
            return "Adaptive"
        capability_heatmap_text_maturity = ""
        if labels and values:
            # Map representative capabilities
            radar_map = dict(zip(labels, values))
            det = _pillar_label(radar_map.get("secops", 1))
            resp = _pillar_label(radar_map.get("secops", 1))
            rec = _pillar_label(radar_map.get("resilience", 1))
            capability_heatmap_text_maturity = "Capability\tMaturity\nDetection\t{d}\nResponse\t{r}\nRecovery\t{rc}".format(
                d=det, r=resp, rc=rec
            )
        # Board summary for maturity report (uses gauge category/percent and executive actions)
        try:
            actions_top3_text = "\n".join([f"{i+1}. {x}" for i, x in enumerate(getattr(report_data, "executive_summary_actions", [])[:3])])
        except Exception:
            actions_top3_text = ""
        board_summary_text_maturity = _build_board_summary_text(overall_category, overall_percent, [], [], actions_top3_text)
    except Exception:
        capability_heatmap_text_maturity = ""
        board_summary_text_maturity = ""
    # 2) Domains & Roadmap derivation with safe defaults
    domains_list = []

    # Map standard domain names to radar keys used in radar_chart_data
    _DOMAIN_TO_RADAR = {
        "Identity & Access Management": "iam",
        "Privileged Access & Identity Governance": "privileged_access",
        "Endpoint & Device Security": "endpoint",
        "Network & Remote Access Security": "network",
        "Email & Collaboration Security": "email",
        "Cloud & Infrastructure Security": "cloud",
        "SaaS & Application Governance": "saas",
        "Data Security & Information Protection": "data_security",
        "Security Operations & Response": "secops",
        "Security Validation & Testing": "testing",
        "Supplier & Third-Party Security": "supplier",
        "Operational Resilience & Backup": "resilience",
        "Security Culture & Awareness": "culture",
        "Governance, Risk & Compliance": "grc",
        "AI Governance & Security": "ai",
    }

    # domain_weighted_pct_map precomputed earlier

    domain_items = getattr(report_data, "domain_assessments", None) or getattr(report_data, "domains", None) or []
    if not isinstance(domain_items, list):
        domain_items = []
    for item in domain_items:
        if hasattr(item, "model_dump"):
            _d = item.model_dump()
            _name = _d.get("domain_name") or _d.get("name")
            _d["weighted_contribution_percent"] = domain_weighted_pct_map.get(_name)
            domains_list.append(_xml_escape_dict(_d))
        elif isinstance(item, dict):
            _name = item.get("domain_name") or item.get("name")
            _d = dict(item)
            _d["weighted_contribution_percent"] = domain_weighted_pct_map.get(_name)
            domains_list.append(_xml_escape_dict(_d))
        else:
            _fallback = {"domain_name": getattr(item, "domain_name", None) or getattr(item, "name", str(item))}
            _fallback["weighted_contribution_percent"] = domain_weighted_pct_map.get(_fallback.get("domain_name"))
            domains_list.append(_xml_escape_dict(_fallback))

    roadmap_list = []
    phases = getattr(report_data, "phased_roadmap", None) or getattr(report_data, "roadmap", None) or []
    if not isinstance(phases, list):
        phases = []
    for phase in phases:
        if hasattr(phase, "model_dump"):
            phase_dict = _xml_escape_dict(phase.model_dump())
        elif isinstance(phase, dict):
            phase_dict = _xml_escape_dict(phase)
        else:
            phase_dict = _xml_escape_dict({"phase": getattr(phase, "phase", "Phase")})

        # Normalise key_deliverables in the roadmap to avoid bracketed list representations
        if "key_deliverables" in phase_dict:
            phase_dict["key_deliverables"] = _normalize_kd(phase_dict["key_deliverables"])

        roadmap_list.append(phase_dict)

    compliance_alignment_list = []
    if getattr(report_data, "compliance_alignment", None):
        compliance_alignment_list = [_xml_escape_dict(c.model_dump()) for c in report_data.compliance_alignment]

    compliance_alignment_structured = []
    for item in compliance_alignment_list:
        if isinstance(item, dict):
            standard = item.get("standard", "")
            gaps = item.get("critical_gaps", item.get("gaps", []))
            fill_plan_raw = item.get("fill_plan", [])
        else:
            standard = getattr(item, "standard", "")
            gaps = getattr(item, "critical_gaps", getattr(item, "gaps", []))
            fill_plan_raw = getattr(item, "fill_plan", [])
        if not isinstance(gaps, list):
            gaps = [gaps] if gaps else []
        fill_plan = []
        for gp in fill_plan_raw:
            if isinstance(gp, dict):
                gap_description = gp.get("gap_description", "")
                recommended_actions = gp.get("recommended_actions", [])
                owner = gp.get("owner", "")
                due_by = gp.get("due_by", "")
            else:
                gap_description = getattr(gp, "gap_description", "")
                recommended_actions = getattr(gp, "recommended_actions", [])
                owner = getattr(gp, "owner", "")
                due_by = getattr(gp, "due_by", "")
            fill_plan.append({
                "gap_description": gap_description,
                "recommended_actions": recommended_actions,
                "owner": owner or "",
                "due_by": due_by or "",
            })
        compliance_alignment_structured.append({
            "standard": standard,
            "gaps": gaps,
            "fill_plan": fill_plan,
        })

    compliance_alignment_render = ""
    if compliance_alignment_structured:
        parts = []
        for comp in compliance_alignment_structured:
            gaps_text = "; ".join([str(g) for g in comp.get("gaps", [])])
            actions_per_gap = []
            for gp in comp.get("fill_plan", []):
                acts_text = "; ".join([str(a) for a in gp.get("recommended_actions", [])])
                extras = []
                owner = gp.get("owner", "")
                due_by = gp.get("due_by", "")
                if owner:
                    extras.append(f"Owner: {owner}")
                if due_by:
                    extras.append(f"Due: {due_by}")
                if extras:
                    acts_text = f"{acts_text} (" + ", ".join(extras) + ")"
                actions_per_gap.append(f"{gp.get('gap_description','')}: {acts_text}")
            plan_text = " | ".join(actions_per_gap)
            parts.append(f"Standard: {comp.get('standard','')} | Gaps: {gaps_text} | Actions: {plan_text}")
        compliance_alignment_render = "\n\n".join(parts)
    # Compute RAG summary and adjudicated known issues (context-only; no post-render injection)
    try:
        rag_summary = _build_rag_summary(report_data, client_inputs, {"domain_ratings": domain_ratings})
    except Exception:
        rag_summary = []
    try:
        adjudicated_known_issues = _adjudicate_known_issues(client_inputs.get("known_issues") or [], rag_summary)
    except Exception:
        adjudicated_known_issues = []
        
        # Build 'programme_options' list for template loops if present
        programme_options = []
        try:
            po_src = getattr(report_data, "programme_options", None)
            if isinstance(po_src, list) and po_src:
                tmp = []
                for it in po_src[:10]:
                    if isinstance(it, dict):
                        tmp.append({
                            "solution": it.get("solution",""),
                            "why_this_fits": it.get("why_this_fits",""),
                            "cost_band": it.get("cost_band",""),
                        })
                    else:
                        tmp.append({
                            "solution": str(it),
                            "why_this_fits": "",
                            "cost_band": "",
                        })
                programme_options = [_xml_escape_dict(x) for x in tmp]
            else:
                # Fallback A: derive from executive_summary_action_blocks
                tmp = []
                blks = getattr(report_data, "executive_summary_action_blocks", []) or []
                def _cost_band_from_text(s):
                    t = (s or "").lower()
                    if any(k in t for k in ("mdr","out-of-hours","24/7","response")):
                        return "High / TBC"
                    if any(k in t for k in ("tabletop","response-plan","recovery")):
                        return "Medium initially; High if backup licensing is added"
                    if any(k in t for k in ("vulnerability","scanning","ftp","remediation")):
                        return "Medium to High / TBC"
                    return "TBC following discovery"
                for b in blks[:6]:
                    try:
                        if isinstance(b, dict):
                            heading = b.get("heading","")
                            risk = b.get("risk","")
                            acts = b.get("remediation_actions",[]) or []
                        else:
                            heading = getattr(b, "heading", "") or ""
                            risk = getattr(b, "risk", "") or ""
                            acts = getattr(b, "remediation_actions", []) or []
                        act0 = acts[0] if isinstance(acts, list) and acts else ""
                        solution = str(act0 or heading or "")
                        why_fit = _first_sentence(str(risk or heading or ""))
                        cost_band = _cost_band_from_text(solution + " " + why_fit)
                        if solution:
                            tmp.append({
                                "solution": solution,
                                "why_this_fits": why_fit,
                                "cost_band": cost_band,
                            })
                    except Exception:
                        continue
                # Fallback B: derive from domain_assessments if still empty
                if not tmp:
                    das = getattr(report_data, "domain_assessments", []) or []
                    for da in das:
                        try:
                            if isinstance(da, dict):
                                recs = da.get("recommended_solutions", []) or []
                                why = da.get("business_impact_narrative","") or ""
                            else:
                                recs = getattr(da, "recommended_solutions", []) or []
                                why = getattr(da, "business_impact_narrative", "") or ""
                            for r in (recs or [])[:1]:
                                cb = _cost_band_from_text(str(r) + " " + str(why))
                                tmp.append({
                                    "solution": str(r),
                                    "why_this_fits": _first_sentence(str(why)),
                                    "cost_band": cb,
                                })
                        except Exception:
                            continue
                # Deduplicate and cap to top 4
                seen = set(); out = []
                for it in tmp:
                    key = it["solution"]
                    if key in seen:
                        continue
                    seen.add(key); out.append(it)
                programme_options = [_xml_escape_dict(x) for x in out[:4]]
        except Exception:
            programme_options = []
        
        # Render Programme Controls into a deterministic ASCII-safe string if present
        programme_controls_render = ""
        try:
            pc = getattr(report_data, "programme_controls", None)
            if pc is not None:
                def _getattr(o, name, default=""):
                    try:
                        return getattr(o, name, default)
                    except Exception:
                        return default
                def _get(o, name, default=""):
                    if isinstance(o, dict):
                        return o.get(name, default)
                    return _getattr(o, name, default)
                pcs = [
                    ("Phishing simulations", _get(pc, "phishing_simulations", "")),
                    ("Security training programme", _get(pc, "security_training_programme", "")),
                    ("Endpoint privileges", _get(pc, "endpoint_privileges", "")),
                    ("Reporting routes", _get(pc, "reporting_routes", "")),
                    ("Follow-up coaching", _get(pc, "followup_coaching", "")),
                    ("Role-based training", _get(pc, "role_based_training", "")),
                    ("Leadership engagement", _get(pc, "leadership_engagement", "")),
                    ("Policy acknowledgement", _get(pc, "policy_acknowledgement", "")),
                ]
                metrics = []
                pfr = _get(pc, "phish_failure_rate_90d", None)
                rr = _get(pc, "report_rate_90d", None)
                ccs = _get(pc, "calculated_culture_score", None)
                ctier = _get(pc, "culture_tier", "")
                if pfr is not None:
                    metrics.append(f"Phish failure (90d): {int(pfr)}%")
                if rr is not None:
                    metrics.append(f"Report rate (90d): {int(rr)}%")
                if ccs is not None:
                    metrics.append(f"Culture score: {int(ccs)}/14")
                if ctier:
                    metrics.append(f"Culture tier: {ctier}")
                lines = [f"- {k}: {str(v)}" for k, v in pcs if str(v).strip()]
                if metrics:
                    lines.append("- Metrics: " + "; ".join(metrics))
                programme_controls_render = "\n".join(lines)
        except Exception:
            programme_controls_render = ""
        
    context = {
        "security_rating": security_rating,
        "threat_scenarios": _format_threat_scenarios(getattr(report_data, "threat_scenarios", None)),
        "Threat_scenarios": _format_threat_scenarios(getattr(report_data, "threat_scenarios", None)),
        # New derived executive sections (optional placeholders)
        "capability_heatmap_text": capability_heatmap_text_maturity,
        "board_summary": board_summary_text_maturity,
        # CAP compact summary for overview section
        "cap_summary": format_critical_asset_profile(client_inputs.get("critical_asset_profile", {})),
        # Monte Carlo placeholder removed
        "customer_name": client_inputs.get("customer_name", "Customer"),
        
        # New optional alias fields for template compatibility
        "cost_of_inaction": getattr(report_data, "cost_of_inaction", ""),
        "cost_of_inaction_summary": getattr(report_data, "cost_of_inaction_summary", ""),
        # Success metrics aliases
        "success_metrics": getattr(report_data, "success_metrics", []),
        "success_metrics_render": getattr(report_data, "success_metrics_render", ""),
        # Aliases for success criteria
        "success_criteria": getattr(report_data, "success_metrics_render", ""),
        "Success_Criteria": getattr(report_data, "success_metrics_render", ""),
        # Compliance alignment aliases
        "compliance_alignment": getattr(report_data, "compliance_alignment_render", ""),
        "ComplianceAlignment": getattr(report_data, "compliance_alignment_render", ""),
        "Compliance_Framework": getattr(report_data, "compliance_alignment_render", ""),
        # Generic partnership alias
        "Partnership": getattr(report_data, "partnership_outline", "") or getattr(report_data, "partnership_details", ""),
        "consultant_name": client_inputs.get("consultant_name", "Planet IT Consultant"),
        "industry": client_inputs.get("industry", "Unknown"),
        "users": client_inputs.get("users", "0"),
        "endpoints": client_inputs.get("endpoints", "0"),
        "servers": client_inputs.get("servers", "0"),
        "operating_systems": client_inputs.get("operating_systems", "Unknown"),
        "cloud_env": client_inputs.get("cloud_env", "Unknown"),
        "in_house_team": client_inputs.get("in_house_team", "Unknown"),
        "compliance": client_inputs.get("compliance", "None"),
        "critical_infra": client_inputs.get("critical_infra", "Unknown"),
        "managed_service_status": client_inputs.get("managed_service_status", "None"),
        "co_managed_units": client_inputs.get("co_managed_units", 0),
        "mdr_provider": client_inputs.get("mdr_provider", "None"),
        "endpoint": client_inputs.get("endpoint", "Unknown"),
        "endpoint_posture": client_inputs.get("endpoint_posture", "Unknown"),
        "firewall": client_inputs.get("firewall", "Unknown"),
        "identity": client_inputs.get("identity", "Unknown"),
        "email": client_inputs.get("email", "Unknown"),
        "m365_license": client_inputs.get("m365_license", "Unknown"),
        "savviness": client_inputs.get("savviness", "Unknown"),
        # --- Radar Chart Image ---
        "radar_chart": chart_image,
        "maturity_gauge": maturity_gauge_image,
        "domain_ratings": domain_ratings,
        "domain_ratings_bullets": domain_ratings_bullets,
        # Gauge context strings (optional in template)
        "maturity_gauge_caption": maturity_gauge_caption,
        "maturity_pillar_distribution": maturity_pillar_distribution,
        "maturity_score": f"{overall_percent}/100",
        "maturity_score_category": overall_category,
        # Monte Carlo outputs removed from context
        "pentest_status": client_inputs.get("pentest_status", "Unknown"),
        "vuln_scanning": client_inputs.get("vuln_scanning", "Unknown"),
        "remote_access": client_inputs.get("remote_access", "Unknown"),
        "saas_backup": client_inputs.get("saas_backup", "Unknown"),
        "ir_readiness": client_inputs.get("ir_readiness", "Unknown"),
        "mfa_status": client_inputs.get("mfa_status", "Unknown"),
        "patching": client_inputs.get("patching", "Unknown"),
        "backups": client_inputs.get("backups", "Unknown"),
        "insurance": client_inputs.get("insurance", "Unknown"),
        "rto": client_inputs.get("rto", "Unknown"),
        "advanced_controls": client_inputs.get("advanced_controls", "None"),
        "exec_summary": report_data.executive_summary if hasattr(report_data, "executive_summary") else "",
        "executive_summary_actions": getattr(report_data, "executive_summary_actions", []) or [],
        "executive_summary_actions_bullets": "\n".join([f"- {x}" for x in getattr(report_data, "executive_summary_actions", [])]) if getattr(report_data, "executive_summary_actions", None) else "",
        "executive_summary_actions_numbered": "\n".join([f"{i+1}. {x}" for i, x in enumerate(getattr(report_data, "executive_summary_actions", []))]) if getattr(report_data, "executive_summary_actions", None) else "",
        "executive_summary_action_blocks": getattr(report_data, "executive_summary_action_blocks", []) or [],
        "executive_summary_actions_word": ("\n\n".join([
            f"{idx+1}. {getattr(blk, 'heading', '')}\nFinding: {getattr(blk, 'finding', '')}\nRisk: {getattr(blk, 'risk', '')}\n\nRemediation actions:\n" + "\n".join([f"{i+1}. {act}" for i, act in enumerate(getattr(blk, 'remediation_actions', []) or [])])
            for idx, blk in enumerate(getattr(report_data, 'executive_summary_action_blocks', []) or [])
        ]) if getattr(report_data, 'executive_summary_action_blocks', None) else ""),
        "matrix_mapping": report_data.resiliency_matrix_mapping if hasattr(report_data, "resiliency_matrix_mapping") else "",
        "cost_of_inaction": report_data.cost_of_inaction if hasattr(report_data, "cost_of_inaction") else "",
        "domains": (domains_list if domains_list is not None else []),
        "roadmap": (roadmap_list if roadmap_list is not None else []),
        "compliance_alignment": (compliance_alignment_list if compliance_alignment_list is not None else []),
        "success_metrics": _as_list(getattr(report_data, "success_metrics", None)),
        "engagement_cadence": _as_list(getattr(report_data, "engagement_cadence", None)),
        "consultant_discovery_guide": _as_list(getattr(report_data, "consultant_discovery_guide", None)),
        "compliance_alignment_render": compliance_alignment_render,
        "partnership_outline": getattr(report_data, "partnership_outline", ""),
        # Programme options list for DOCX table loop
        "programme_options": programme_options,
        # Programme controls bindings and aliases (template compatibility)
        "programme_controls_render": programme_controls_render,
        "programme_controls": programme_controls_render,
        "ProgrammeControls": programme_controls_render,
        "Programme_Controls": programme_controls_render,
    }
    # Adjudicated Known Issues and RAG summary (context-only, no post-render injection)
    context["rag_summary"] = rag_summary
    context["adjudicated_known_issues"] = adjudicated_known_issues

    # Safety: ensure critical structured objects exist (avoid Jinja accessing attributes on strings)
    try:
        # security_rating must be a dict with keys like 'snapshot'
        if not isinstance(context.get("security_rating"), dict):
            try:
                context["security_rating"] = security_rating
            except Exception:
                context["security_rating"] = {
                    "overall_score": 0,
                    "maturity_rating": "",
                    "snapshot": {
                        "overall_score": 0,
                        "maturity_rating": "",
                        "direction_of_travel": "",
                        "primary_strengths": [],
                        "primary_gaps": [],
                        "board_level_takeaway": ""
                    },
                    "weighted_areas": [],
                    "maturity_bands": [],
                    "executive_interpretation": "",
                    "score_statement": "",
                    "caveat": ""
                }
        # Lists used by template loops should be lists (not strings)
        if not isinstance(context.get("domains"), list):
            context["domains"] = domains_list if isinstance(domains_list, list) else []
        if not isinstance(context.get("roadmap"), list):
            context["roadmap"] = roadmap_list if isinstance(roadmap_list, list) else []
        if "cap_summary" not in context:
            context["cap_summary"] = format_critical_asset_profile(client_inputs.get("critical_asset_profile", {}))
        if not isinstance(context.get("programme_options"), list):
            context["programme_options"] = []
    except Exception:
        pass

    # Ensure programme_options is populated for template loop even if earlier assembly path was skipped
    try:
        if "programme_options" not in context or not isinstance(context.get("programme_options"), list) or not context.get("programme_options"):
            tmp = []
            po_src = getattr(report_data, "programme_options", None)
            if isinstance(po_src, list) and po_src:
                for it in po_src[:10]:
                    if isinstance(it, dict):
                        tmp.append({
                            "solution": it.get("solution", ""),
                            "why_this_fits": it.get("why_this_fits", ""),
                            "cost_band": it.get("cost_band", ""),
                        })
                    else:
                        tmp.append({
                            "solution": str(it),
                            "why_this_fits": "",
                            "cost_band": "",
                        })
            if not tmp:
                blks = getattr(report_data, "executive_summary_action_blocks", []) or []
                def _cost_band_from_text(s):
                    t = (s or "").lower()
                    if any(k in t for k in ("mdr", "out-of-hours", "24/7", "response")):
                        return "High / TBC"
                    if any(k in t for k in ("tabletop", "response-plan", "recovery")):
                        return "Medium initially; High if backup licensing is added"
                    if any(k in t for k in ("vulnerability", "scanning", "ftp", "remediation")):
                        return "Medium to High / TBC"
                    return "TBC following discovery"
                for b in blks[:6]:
                    try:
                        heading = b.get("heading", "") if isinstance(b, dict) else getattr(b, "heading", "") or ""
                        risk = b.get("risk", "") if isinstance(b, dict) else getattr(b, "risk", "") or ""
                        acts = b.get("remediation_actions", []) if isinstance(b, dict) else getattr(b, "remediation_actions", []) or []
                        act0 = acts[0] if isinstance(acts, list) and acts else ""
                        solution = str(act0 or heading or "")
                        why_fit = _first_sentence(str(risk or heading or ""))
                        if solution:
                            tmp.append({
                                "solution": solution,
                                "why_this_fits": why_fit,
                                "cost_band": _cost_band_from_text(solution + " " + why_fit),
                            })
                    except Exception:
                        continue
            if not tmp:
                das = getattr(report_data, "domain_assessments", []) or []
                for da in das:
                    try:
                        if isinstance(da, dict):
                            recs = da.get("recommended_solutions", []) or []
                            why = da.get("business_impact_narrative", "") or ""
                        else:
                            recs = getattr(da, "recommended_solutions", []) or []
                            why = getattr(da, "business_impact_narrative", "") or ""
                        for r in (recs or [])[:1]:
                            tmp.append({
                                "solution": str(r),
                                "why_this_fits": _first_sentence(str(why)),
                                "cost_band": "TBC following discovery",
                            })
                    except Exception:
                        continue
            # Deduplicate and cap to 4
            seen = set(); out = []
            for it in tmp:
                key = it.get("solution", "")
                if not key or key in seen:
                    continue
                seen.add(key); out.append(it)
            if out:
                context["programme_options"] = [_xml_escape_dict(x) for x in out[:4]]
        # Ensure other essential context keys exist if earlier assembly path was skipped
        if "customer_name" not in context:
            context["customer_name"] = client_inputs.get("customer_name", "Customer")
        if "radar_chart" not in context:
            context["radar_chart"] = chart_image
        if "maturity_gauge" not in context:
            context["maturity_gauge"] = maturity_gauge_image
        if "domain_ratings" not in context:
            context["domain_ratings"] = domain_ratings
        if "domain_ratings_bullets" not in context:
            context["domain_ratings_bullets"] = domain_ratings_bullets
        if "maturity_gauge_caption" not in context:
            context["maturity_gauge_caption"] = maturity_gauge_caption
        if "maturity_pillar_distribution" not in context:
            context["maturity_pillar_distribution"] = maturity_pillar_distribution
    except Exception:
        # Non-fatal; template reconciler will fill blanks
        pass

    # Legacy template fallback: render plain-text for {{ rag_section }} and {{ known_issues_section }}
    # This avoids post-render injections and ensures immediate in-place content until docxtpl loops are added.
    def _render_rag_text(_rag):
        try:
            lines = []
            for r in (_rag or []):
                lbl = str(r.get("severity_label", "")).title()
                pct = r.get("severity_pct", "")
                title = r.get("issue_title", "")
                lines.append(f"{lbl} {pct}% — {title}".strip())
                be = r.get("business_exposure", "")
                if be:
                    lines.append(f"  Exposure: {be}")
                pa = r.get("priority_action", "")
                if pa:
                    lines.append(f"  Action: {pa}")
            return "\n".join(lines) if lines else "N/A"
        except Exception:
            return "N/A"

    def _render_known_issues_text(_kis):
        try:
            out = []
            for i, ki in enumerate((_kis or []), 1):
                out.append(f"{i}. Issue: {ki.get('issue_text','')}")
                rul = ki.get("our_ruling", "")
                if rul:
                    out.append(f"   Ruling: {rul}")
                rat = ki.get("rationale", "")
                if rat:
                    out.append(f"   Rationale: {rat}")
                rems = ki.get("suggested_remediations") or []
                if rems:
                    out.append("   Remediations: " + "; ".join([str(x) for x in rems]))
                sols = ki.get("aligned_solutions") or []
                if sols:
                    out.append("   Solutions: " + "; ".join([str(x) for x in sols]))
            return "\n".join(out) if out else "N/A"
        except Exception:
            return "N/A"

    # Populate anchors only if not pre-populated elsewhere
    if not context.get("rag_section"):
        context["rag_section"] = _render_rag_text(rag_summary)
    if not context.get("known_issues_section"):
        context["known_issues_section"] = _render_known_issues_text(adjudicated_known_issues)
    # Ensure a stable baseline set of keys for the template, even if some fields are missing from LLM outputs
    try:
        # Threat scenarios: if not present, fill from local ts_text
        if not context.get("threat_scenarios"):
            if ts_text:
                context["threat_scenarios"] = ts_text
                context["Threat_scenarios"] = ts_text
                context["Threat_Scenarios"] = ts_text
        # Compliance alignment: force local render into common aliases
        if 'compliance_alignment_render' in locals() and compliance_alignment_render:
            context.setdefault("ComplianceAlignment", compliance_alignment_render)
            context.setdefault("Compliance_Framework", compliance_alignment_render)
            context.setdefault("compliance_alignment_render", compliance_alignment_render)
            context.setdefault("compliance_alignment", compliance_alignment_render)
        # Cost of Inaction fields
        if not context.get("cost_of_inaction") and getattr(report_data, "cost_of_inaction", ""):
            context["cost_of_inaction"] = getattr(report_data, "cost_of_inaction", "")
        if not context.get("cost_of_inaction_summary") and getattr(report_data, "cost_of_inaction_summary", ""):
            context["cost_of_inaction_summary"] = getattr(report_data, "cost_of_inaction_summary", "")
        # CAP & partnership fallbacks
        if not context.get("cap_summary") and getattr(report_data, "cap_summary", ""):
            context["cap_summary"] = getattr(report_data, "cap_summary", "")
            context["CAP_Summary"] = getattr(report_data, "cap_summary", "")
        if not context.get("partnership_details") and getattr(report_data, "partnership_details", ""):
            context["partnership_details"] = getattr(report_data, "partnership_details", "")
        if not context.get("partnership_outline") and getattr(report_data, "partnership_outline", ""):
            context["partnership_outline"] = getattr(report_data, "partnership_outline", "")
        # Threat intelligence context
        if not context.get("threat_intelligence_context") and getattr(report_data, "threat_intelligence_context", ""):
            context["threat_intelligence_context"] = getattr(report_data, "threat_intelligence_context", "")
    except Exception:
        pass
    # Threat intelligence: populate from the LLM-generated report data
    context["threat_intelligence_context"] = getattr(report_data, "threat_intelligence_context", "") or ""
    # Partnership governance: ensure both raw and rendered forms are populated in the context
    partnership_details = getattr(report_data, "partnership_details", "")
    partnership_links = getattr(report_data, "partnership_links", [])
    partnerships_render = format_governance_narrative(
        narrative=partnership_details,
        links=partnership_links if isinstance(partnership_links, list) else [str(partnership_links)]
    ) if partnership_details or partnership_links else ""

    # Always provide the raw detail string to the template so {{ partnership_details }} renders
    context["partnership_details"] = partnership_details if partnership_details is not None else ""
    # Provide a rendered narrative for any governance links, with a safe fallback
    context["partnership_details_render"] = partnerships_render
    context["partnership_links"] = partnerships_render if partnerships_render else ""
    context["partnership_links_render"] = partnerships_render
    monetary_cost = getattr(report_data, "monetary_cost_of_inaction", None)
    monetary_cost_text = ""
    if monetary_cost:
        amount = getattr(monetary_cost, "amount_gbp", None)
        if amount is None and isinstance(monetary_cost, (int, float)):
            amount = monetary_cost
        if amount is not None:
            monetary_cost_text = f"£{float(amount):,.2f}"
        src = getattr(monetary_cost, "source", None)
        if src:
            monetary_cost_text += f" | Source: {src}"
        rationale = getattr(monetary_cost, "rationale", None)
        if rationale:
            monetary_cost_text += f" | Rationale: {rationale}"
    context["monetary_cost_of_inaction"] = monetary_cost_text
    # Derive a human-readable cost summary (prefer the LLM-generated one, fall back to monetary_cost_of_inaction)
    context["cost_of_inaction_summary"] = getattr(report_data, "cost_of_inaction_summary", None) or monetary_cost_text

    partnership_outline = getattr(report_data, "partnership_outline", None)
    if partnership_outline:
        context["partnership_outline"] = partnership_outline
    else:
        context["partnership_outline"] = ""
    # Proactive Testing, IR and DR programme fields (optional)
    context["proactive_testing_programme"] = getattr(report_data, "proactive_testing_programme", "") or ""
    context["incident_response_plan_outline"] = getattr(report_data, "incident_response_plan_outline", "") or ""
    context["disaster_recovery_plan_outline"] = getattr(report_data, "disaster_recovery_plan_outline", "") or ""

    # Ensure required template variables have non-empty defaults from client_inputs or 'N/A'
    try:
        required_vars = set(doc.get_undeclared_template_variables() or [])
    except Exception:
        required_vars = set()
    if isinstance(required_vars, set):
        for var in required_vars:
            if var not in context or context.get(var) in (None, "", []):
                # Prefer client_inputs if available and non-empty
                if isinstance(client_inputs, dict) and var in client_inputs:
                    val = client_inputs.get(var)
                    context[var] = val if val not in (None, "", []) else "N/A"
                else:
                    context[var] = "N/A"

    # Pre-render reconciliation to align template placeholders with context
    try:
        debug = str(get_config("RENDER_DEBUG", "false")).strip().lower() in ("1","true","yes","on")
        context = _reconcile_context_for_template(doc, context, debug=debug)
    except Exception:
        pass
    print("DOCX_RENDER_START", "context_keys=", len(context.keys()))
    try:
        if str(get_config("RENDER_DEBUG", "false")).strip().lower() in ("1","true","yes","on"):
            undeclared = []
            try:
                undeclared = doc.get_undeclared_template_variables()
            except Exception:
                undeclared = []
            print("DOCX_UNDECLARED", sorted(list(undeclared)) if isinstance(undeclared, (list, set, tuple)) else undeclared)
    except Exception:
        pass
    try:
        doc.render(_xml_escape_dict(context))
    except Exception as e:
        try:
            print("DOCX_RENDER_FAIL", repr(e))
        except Exception:
            pass
        # Fallback: attempt minimal safely-escaped context to avoid crashing export
        minimal = {k: (context.get(k, "") or "") for k in context.keys()}
        try:
            doc.render(_xml_escape_dict(minimal))
        except Exception:
            return b""
    else:
        print("DOCX_RENDER_FINISH")

    # Post-render: inject formatted threat scenarios with proper Word styling
    threat_scenarios_data_for_inject = getattr(report_data, "threat_scenarios", None)
    if threat_scenarios_data_for_inject and isinstance(threat_scenarios_data_for_inject, list):
        _inject_threat_scenarios_after_render(doc, threat_scenarios_data_for_inject)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()

# ==========================================
# TABLETOP EXPORT PIPELINE
# ==========================================
import io
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import PP_PLACEHOLDER

# Local contract exceptions for PPTX template enforcement
class TemplateContractError(Exception):
    pass

class ValidationError(Exception):
    pass

# --- PPTX STYLE HELPERS (branding-safe) ---
def _apply_para_style(p, font_size_pt=14, rgb=(50, 50, 50), bold=False):
    try:
        p.font.size = Pt(font_size_pt)
        p.font.color.rgb = RGBColor(*rgb)
        p.font.bold = bold
    except Exception:
        pass

def _add_heading(tf, text, font_size_pt=15, rgb=(35, 80, 106)):
    p = tf.add_paragraph()
    p.text = text
    _apply_para_style(p, font_size_pt=font_size_pt, rgb=rgb, bold=True)
    try:
        p.space_after = Pt(6)
    except Exception:
        pass
    return p

def _add_bullet(tf, text, font_size_pt=14, rgb=(50, 50, 50)):
    p = tf.add_paragraph()
    p.text = f"• {text}"
    _apply_para_style(p, font_size_pt=font_size_pt, rgb=rgb, bold=False)
    return p

def _add_textbox(slide, left_in, top_in, width_in, height_in, text=""):
    tx = slide.shapes.add_textbox(Inches(left_in), Inches(top_in), Inches(width_in), Inches(height_in))
    tf = tx.text_frame
    tf.text = text or ""
    return tx, tf

def _embed_picture(slide, image_path, left_in=6.0, top_in=1.5, width_in=3.0):
    try:
        if image_path and isinstance(image_path, str) and len(image_path) > 0 and os.path.exists(image_path):
            slide.shapes.add_picture(image_path, Inches(left_in), Inches(top_in), width=Inches(width_in))
            return True
    except Exception:
        pass
    return False

def create_tabletop_pptx(master_plan_data: dict) -> bytes:
    """Generate a clean slide deck for presentation using python-pptx."""
    # Preflight validation (strict gating configurable)
    try:
        strict_flag = is_tabletop_quality_strict()
    except Exception:
        strict_flag = True
    # Ensure default independent profiles and record migration notices if omitted (do not infer from any other fields)
    try:
        if not isinstance(master_plan_data, dict):
            master_plan_data = {}
        mig = master_plan_data.get("_migration_notices", []) or []
        if not master_plan_data.get("_exercise_profile"):
            master_plan_data["_exercise_profile"] = "blended"
            mig.append("Applied default exercise_profile=blended")
        if not master_plan_data.get("_presentation_detail_profile"):
            master_plan_data["_presentation_detail_profile"] = "standard"
            mig.append("Applied default presentation_detail_profile=standard")
        if mig:
            master_plan_data["_migration_notices"] = mig
    except Exception:
        pass
    ok, defects = (True, [])
    try:
        ok, defects = validate_tabletop_master_plan(master_plan_data if isinstance(master_plan_data, dict) else {})
    except Exception:
        pass
    if strict_flag and not ok:
        # Fail closed to avoid distributing incomplete decks
        return b""
    try:
        template_path = get_config("TABLETOP_TEMPLATE_DECK", os.path.join(os.path.dirname(__file__), "planet_it_tabletop_template.pptx"))
    except Exception:
        template_path = os.path.join(os.path.dirname(__file__), "planet_it_tabletop_template.pptx")

    # Safe accessors (dict or object)
    def _dict_get(obj, key, default=None):
        try:
            if isinstance(obj, dict):
                return obj.get(key, default)
            v = getattr(obj, key, default)
            return v if v is not None else default
        except Exception:
            return default

    # Remove all original slides from the template while preserving theme/masters
    def _clear_all_template_slides(p):
        try:
            sld_id_lst = p.slides._sldIdLst
            for sld_id in list(sld_id_lst):
                rId = sld_id.rId
                p.part.drop_rel(rId)
                sld_id_lst.remove(sld_id)
        except Exception:
            # If this fails, continue using the template as-is
            pass

    if os.path.exists(template_path):
        prs = Presentation(template_path)
    else:
        prs = Presentation()

    NAVY = RGBColor(35, 80, 106)
    DARK_GRAY = RGBColor(50, 50, 50)

    # Presentation profile (Minimal/Standard/Detailed) controls slide verbosity
    try:
        _ppt_profile = str(get_config("TABLETOP_PRESENTATION_PROFILE", "Standard")).strip().lower()
    except Exception:
        _ppt_profile = "standard"
    show_probing = (_ppt_profile == "detailed")

    # Title slide (skip if static front present)
    def _has_static(prs_obj, tag):
        try:
            return any(any(getattr(sh, "name", "") == tag for sh in s.shapes) for s in prs_obj.slides)
        except Exception:
            return False
    _static_front_present = _has_static(prs, "STATIC_01_PLANET_FRONT_PAGE")
    # Do not hard-fail here; allow fallback mode to handle untagged templates below
    # Compute static indices and insertion anchor between HOW_EXERCISE_WORKS and HOTWASH
    def _find_static_index(tag: str):
        for i, s in enumerate(prs.slides):
            try:
                if any(getattr(sh, "name", "") == tag for sh in s.shapes):
                    return i
            except Exception:
                continue
        return None
    cover_idx = _find_static_index("STATIC_01_PLANET_FRONT_PAGE")
    who_idx = _find_static_index("STATIC_02_PLANET_WHO_WE_ARE")
    rules_idx = _find_static_index("STATIC_02B_PLANET_RULES_OF_ENGAGEMENT")
    roles_idx = _find_static_index("STATIC_02C_PLANET_ROLES_RESPONSIBILITIES")
    how_idx = _find_static_index("STATIC_02D_PLANET_HOW_EXERCISE_WORKS")
    hotwash_idx = _find_static_index("STATIC_02E_PLANET_HOTWASH")
    follow_idx = _find_static_index("STATIC_02F_PLANET_FOLLOW_UP_PROCESS")
    wrap_idx = _find_static_index("STATIC_03_PLANET_WRAP_UP")
    required_indices = [cover_idx, who_idx, rules_idx, roles_idx, how_idx, hotwash_idx, follow_idx, wrap_idx]
    # Static contract enforcement with graceful fallback for untagged templates
    fallback_mode = False
    if any(i is None for i in required_indices) or not (cover_idx < who_idx < rules_idx < roles_idx < how_idx < hotwash_idx < follow_idx < wrap_idx):
        # If required static tags/order are not present, operate in append-only fallback mode
        fallback_mode = True
    insert_anchor = (how_idx + 1) if not fallback_mode else len(prs.slides)
    def _insert_slide(layout):
        nonlocal insert_anchor
        sldIdLst = prs.slides._sldIdLst
        new_slide = prs.slides.add_slide(layout)
        if not fallback_mode:
            try:
                sld = sldIdLst[-1]
                sldIdLst.remove(sld)
                sldIdLst.insert(insert_anchor, sld)
            except Exception:
                pass
            insert_anchor += 1
            return prs.slides[insert_anchor - 1]
        # Fallback: simply append without attempting to reposition
        return new_slide


    # Scenarios and injects
    # Agenda slide disabled — use static agenda slide present in the template; no dynamic agenda generation.
    # Dynamic agenda disabled (placeholders branch removed)
    # Dynamic agenda disabled (else branch removed)

    # Dynamic agenda disabled (agenda speaker notes removed)
    # Optional Maturity Overview slide (if radar_chart_data present)
    try:
        _radar_data = _dict_get(master_plan_data, "radar_chart_data", None)
        _labels = []
        _values = []
        if isinstance(_radar_data, dict):
            _labels = list(_radar_data.keys())
            _values = [float(_radar_data[k]) for k in _labels]
        if _labels and _values:
            _radar_path = generate_radar_chart_from_values(_labels, _values, figsize=(3.5, 3.5))
            _overall_percent, _overall_category = compute_overall_maturity_percent(dict(zip(_labels, _values)))
            _gauge_path = render_maturity_gauge_png(_overall_percent, _overall_category, figsize=(3,3), show_center_label=True)
            mo_layout = prs.slide_layouts[5] if len(prs.slide_layouts) > 5 else prs.slide_layouts[1]
            mo = _insert_slide(mo_layout)
            if mo.shapes.title:
                mo.shapes.title.text = f"Maturity Overview — {_overall_category} ({_overall_percent}/100)"
            try:
                pic1 = mo.shapes.add_picture(_radar_path, Inches(1.0), Inches(1.8), width=Inches(4.0))
                try:
                    cNvPr = pic1._element.xpath('.//p:cNvPr')
                    if cNvPr:
                        cNvPr[0].set('descr', 'Radar Image')
                except Exception:
                    pass
            except Exception:
                pass
            try:
                pic2 = mo.shapes.add_picture(_gauge_path, Inches(5.5), Inches(1.8), width=Inches(3.0))
                try:
                    cNvPr = pic2._element.xpath('.//p:cNvPr')
                    if cNvPr:
                        cNvPr[0].set('descr', 'Gauge Image')
                except Exception:
                    pass
            except Exception:
                pass
            try:
                if os.path.exists(_radar_path): os.unlink(_radar_path)
                if os.path.exists(_gauge_path): os.unlink(_gauge_path)
            except Exception:
                pass
    except Exception:
        pass
    scenarios = _dict_get(master_plan_data, "scenarios", []) or []
    # Resolve layouts deterministically for Scenario Title and Inject slides
    scn_title_layout = prs.slide_layouts[6] if len(prs.slide_layouts) > 6 else prs.slide_layouts[0]
    # Enforce Scenario Title layout name contract
    if getattr(scn_title_layout, "name", "") != "Scenario Title":
        raise TemplateContractError("Layout 6 must be named 'Scenario Title'")
    inject_layout = prs.slide_layouts[7] if len(prs.slide_layouts) > 7 else (prs.slide_layouts[1] if len(prs.slide_layouts) > 1 else prs.slide_layouts[0])
    # Filter included scenarios (exclude reserve/appendix_only) and validate titles
    included_scenarios = []
    for _sc in (scenarios or []):
        _status = (_dict_get(_sc, "status", "") or "").strip().lower()
        if _status in {"reserve", "appendix_only", "appendix-only"}:
            continue
        _title_chk = (_dict_get(_sc, "scenario_title", "") or "").strip()
        if not _title_chk:
            raise ValidationError("Included scenario is missing a participant-safe title")
        included_scenarios.append(_sc)
    if not included_scenarios:
        raise ValidationError("At least one included scenario is required")
    for scn_idx, scn in enumerate(included_scenarios, 1):
        scn_title = _dict_get(scn, "scenario_title", f"Scenario {scn_idx}")
        scn_theme = _dict_get(scn, "scenario_theme", "")
        initial_vector = _dict_get(scn, "initial_vector", "")

        scn_title_slide = _insert_slide(scn_title_layout)
        # Title: "Scenario {ordinal}" only
        try:
            # Prefer placeholder index 0 (Title), else fallback to shapes.title
            if len(scn_title_slide.placeholders) > 0:
                scn_title_slide.placeholders[0].text = f"Scenario {scn_idx}"
            elif scn_title_slide.shapes.title:
                scn_title_slide.shapes.title.text = f"Scenario {scn_idx}"
        except Exception:
            if scn_title_slide.shapes.title:
                scn_title_slide.shapes.title.text = f"Scenario {scn_idx}"
        # Subtitle: participant-safe scenario title only (no theme/vector/hidden info)
        try:
            safe_subtitle = (_dict_get(scn, "scenario_title", "") or "").strip()
            if len(scn_title_slide.placeholders) > 1:
                scn_title_slide.placeholders[1].text = safe_subtitle
            else:
                tx = scn_title_slide.shapes.add_textbox(Inches(1.0), Inches(3.0), Inches(8.0), Inches(1.5))
                tx.text_frame.text = safe_subtitle
        except Exception:
            pass
        # Attach minimal metadata for validation (stored in notes to avoid visual mutation)
        try:
            ns = scn_title_slide.notes_slide
            md_lines = (ns.notes_text_frame.text or "").splitlines()
            md_lines.append("SCENARIO_MD: " + json.dumps({
                "dynamic_slide_type": "SCENARIO_START",
                "scenario_id": _dict_get(scn, "id", ""),
                "scenario_ordinal": scn_idx,
                "layout_index": 6,
                "layout_name": "Scenario Title",
            }))
            ns.notes_text_frame.text = "\n".join([ln for ln in md_lines if ln is not None and ln != ""])
        except Exception:
            pass

        base_injects = _dict_get(scn, "injects", []) or []
        client_injects = _dict_get(scn, "client_injects", []) or []
        injects = base_injects + client_injects

        for inj_idx, inj in enumerate(injects, 1):
            ts = _dict_get(inj, "simulated_timestamp", "")
            phase = _dict_get(inj, "phase_title", "")
            narrative = _dict_get(inj, "scenario_narrative", "")
            qlist = _dict_get(inj, "facilitator_probe_questions", []) or []
            artefact_img = _dict_get(inj, "artefact_image_path", "")
            references = _dict_get(inj, "references", []) or []

            # Inject A — Participant-facing evidence
            slide_a = _insert_slide(inject_layout)
            if slide_a.shapes.title:
                slide_a.shapes.title.text = f"Inject {inj_idx}a — " + (phase or "Evidence")
            if len(slide_a.placeholders) > 1:
                tf_a = slide_a.placeholders[1].text_frame
                try:
                    tf_a.clear()
                except Exception:
                    tf_a.text = ""
                if narrative:
                    p = tf_a.add_paragraph()
                    p.text = narrative or ""
                    _apply_para_style(p, font_size_pt=15, rgb=(50, 50, 50))
                    try:
                        p.space_after = Pt(12)
                    except Exception:
                        pass
                # Render structured artefacts (if provided)
                arts = _dict_get(inj, "artefacts", []) or []
                if arts:
                    try:
                        _add_heading(tf_a, "Evidence Artefacts:", font_size_pt=13, rgb=(35, 80, 106))
                        for ar in arts[:3]:
                            try:
                                at = _dict_get(ar, "artefact_type", "")
                                ttl = _dict_get(ar, "title", "")
                                src = _dict_get(ar, "source_system", "")
                                line = f"[{at}] {ttl or '(untitled)'} — {src}".strip()
                                _add_bullet(tf_a, line, font_size_pt=12, rgb=(50, 50, 50))
                                # Add an excerpt from the artefact body (wrapped/truncated)
                                excerpt = ""
                                body = _dict_get(ar, "body", "") or ""
                                if isinstance(body, str) and body.strip():
                                    try:
                                        # Keep first N non-empty lines (configurable); cap ~500 chars
                                        lines = [ln for ln in body.splitlines() if str(ln).strip()]
                                        try:
                                            max_lines = int(get_config("TABLETOP_ARTEFACT_MAX_LINES", 8))
                                        except Exception:
                                            max_lines = 8
                                        excerpt = "\n".join(lines[:max_lines])[:500]
                                    except Exception:
                                        excerpt = body[:500]
                                if not excerpt:
                                    # Synthesize a safe [SIMULATED] excerpt as fallback
                                    if at == "log":
                                        excerpt = "[SIMULATED]\n2026-09-16T08:12:31Z EXO: Suspicious sign-in detected for user [REDACTED] from IP 203.0.113.24 (Anomalous Location)\n2026-09-16T08:12:59Z CA: Conditional Access policy triggered — Session flagged (High risk)"
                                    elif at == "email":
                                        excerpt = "[SIMULATED]\nFrom: finance@company.example\nTo: ap@vendor.example\nSubject: Urgent: Payment Update\nX-Simulated: true\nBody: Requesting invoice reroute to new account ending *4321. [REDACTED]"
                                    elif at == "code":
                                        excerpt = "[SIMULATED]\n#!/bin/bash\n# Downloader (benign sample)\ncurl -fsSL http://example.invalid/ioc -o /tmp/ioc.txt\nsha256sum /tmp/ioc.txt # [REDACTED]"
                                    elif at == "ticket":
                                        excerpt = "[SIMULATED]\nID: SR-20260916-1042 | Status: Open | Queue: Incident Management\nSummary: Unusual sign-ins observed; evaluate MFA enforcement and block risk session."
                                    else:
                                        excerpt = "[SIMULATED] Evidence excerpt not provided by LLM; facilitator to reference guide."
                                # Render excerpt as a small paragraph(s)
                                # Render excerpt lines (monospaced for logs/code/configuration or when render_hint=monospace)
                                try:
                                    max_lines_render = int(get_config("TABLETOP_ARTEFACT_MAX_LINES", 8))
                                except Exception:
                                    max_lines_render = 8
                                rh = _dict_get(ar, "render_hint", "")
                                mono = (str(rh).strip().lower() == "monospace") or (at in ("log", "code", "configuration"))
                                for ln in str(excerpt).splitlines()[:max_lines_render]:
                                    pex = tf_a.add_paragraph()
                                    pex.text = ln
                                    _apply_para_style(pex, font_size_pt=11, rgb=(50, 50, 50))
                                    if mono:
                                        try:
                                            pex.font.name = "Courier New"
                                        except Exception:
                                            pass
                            except Exception:
                                continue
                    except Exception:
                        pass
            else:
                txa, tf_a = _add_textbox(slide_a, 1.0, 2.0, 8.5, 4.5, text=narrative or "")
            # Optional artefact image on A
            _embed_picture(slide_a, artefact_img, left_in=6.0, top_in=1.5, width_in=3.0)
            # Notes for A (with deterministic metadata)
            try:
                ns_a = slide_a.notes_slide
                ntf_a = ns_a.notes_text_frame
                lines_a = []
                emr = _dict_get(inj, "expected_mature_response", "")
                if emr: lines_a.append("What Good Looks Like: " + str(emr))
                dt = _dict_get(inj, "decision_threshold", "")
                if dt: lines_a.append("Decision Threshold: " + str(dt))
                arts = _dict_get(inj, "artefacts", []) or []
                if isinstance(arts, list) and arts:
                    lines_a.append("Artefacts:")
                    for ar in arts[:3]:
                        at = _dict_get(ar, "artefact_type", "")
                        ttl = _dict_get(ar, "title", "")
                        src = _dict_get(ar, "source_system", "")
                        lines_a.append(f"- {at}: {ttl} ({src})")
                        # Append full artefact body for facilitator reference
                        body_full = _dict_get(ar, "body", "") or ""
                        if body_full:
                            lines_a.append("Artefact Body (full):")
                            lines_a.append(str(body_full))
                lines_a.append(f"DYNAMIC_SLIDE_TYPE: INJECT_EVIDENCE_A")
                lines_a.append(f"SCENARIO_ORDINAL: {scn_idx}")
                lines_a.append(f"INJECT_ORDINAL: {inj_idx}")
                ntf_a.text = "\n".join([ln for ln in lines_a if ln])
            except Exception:
                pass

            # Inject B — Questions for the room
            slide_b = _insert_slide(inject_layout)
            if slide_b.shapes.title:
                slide_b.shapes.title.text = f"Inject {inj_idx}b — Questions for the room"
            if len(slide_b.placeholders) > 1:
                tf_b = slide_b.placeholders[1].text_frame
                try:
                    tf_b.clear()
                except Exception:
                    tf_b.text = ""
                _add_heading(tf_b, "Key Questions for the Room:", font_size_pt=15, rgb=(35, 80, 106))
                for q in qlist:
                    _add_bullet(tf_b, q, font_size_pt=14, rgb=(50, 50, 50))
                # Probing sections (Detailed profile only)
                if show_probing:
                    _add_heading(tf_b, "Systems to Check:", font_size_pt=13, rgb=(35, 80, 106))
                    for s in (_dict_get(inj, "systems_to_check", []) or [])[:3]:
                        _add_bullet(tf_b, s, font_size_pt=12, rgb=(50, 50, 50))
                    _add_heading(tf_b, "Roles to Engage:", font_size_pt=13, rgb=(35, 80, 106))
                    for r in (_dict_get(inj, "roles_to_engage", []) or [])[:3]:
                        _add_bullet(tf_b, r, font_size_pt=12, rgb=(50, 50, 50))
                    _add_heading(tf_b, "Runbooks:", font_size_pt=13, rgb=(35, 80, 106))
                    for rb in (_dict_get(inj, "runbook_references", []) or [])[:3]:
                        _add_bullet(tf_b, rb, font_size_pt=12, rgb=(50, 50, 50))
                    _add_heading(tf_b, "Evidence Hunt:", font_size_pt=13, rgb=(35, 80, 106))
                    for ev in (_dict_get(inj, "evidence_hunt", []) or [])[:3]:
                        _add_bullet(tf_b, ev, font_size_pt=12, rgb=(50, 50, 50))
                    _add_heading(tf_b, "Knowledge Checks:", font_size_pt=13, rgb=(35, 80, 106))
                    for kc in (_dict_get(inj, "knowledge_checks", []) or [])[:3]:
                        _add_bullet(tf_b, kc, font_size_pt=12, rgb=(50, 50, 50))
                    _add_heading(tf_b, "Timebox:", font_size_pt=13, rgb=(35, 80, 106))
                    tb = _dict_get(inj, "timebox_hint", "")
                    if tb:
                        _add_bullet(tf_b, tb, font_size_pt=12, rgb=(50, 50, 50))
                    if references:
                        _add_heading(tf_b, "References:", font_size_pt=13, rgb=(35, 80, 106))
                        for r in references:
                            _add_bullet(tf_b, r, font_size_pt=12, rgb=(50, 50, 50))
            else:
                txb, tf_b = _add_textbox(slide_b, 1.0, 2.0, 8.5, 4.5, text="")
                _add_heading(tf_b, "Key Questions for the Room:", font_size_pt=15, rgb=(35, 80, 106))
                for q in qlist:
                    _add_bullet(tf_b, q, font_size_pt=14, rgb=(50, 50, 50))
            # Notes for B (with deterministic metadata)
            try:
                ns_b = slide_b.notes_slide
                ntf_b = ns_b.notes_text_frame
                lines_b = []
                lines_b.append(f"DYNAMIC_SLIDE_TYPE: INJECT_QUESTIONS_B")
                lines_b.append(f"SCENARIO_ORDINAL: {scn_idx}")
                lines_b.append(f"INJECT_ORDINAL: {inj_idx}")
                ntf_b.text = "\n".join([ln for ln in lines_b if ln])
            except Exception:
                pass

    # Scenario Title sequence validation within the dynamic region
    try:
        # Build list of scenario start slides between HOW_EXERCISE_WORKS and HOTWASH
        def _get_md(sl):
            try:
                for ln in (sl.notes_slide.notes_text_frame.text or "").splitlines():
                    if ln.startswith("SCENARIO_MD: "):
                        return json.loads(ln[len("SCENARIO_MD: "):])
            except Exception:
                return {}
            return {}
        dyn_slides = []
        if how_idx is not None and hotwash_idx is not None and hotwash_idx > how_idx:
            for i in range(how_idx + 1, hotwash_idx):
                dyn_slides.append(prs.slides[i])
        starts = []
        for s in dyn_slides:
            md = _get_md(s)
            if md.get("dynamic_slide_type") == "SCENARIO_START":
                starts.append((prs.slides.index(s), s, md))
        if len(starts) != len(included_scenarios):
            raise ValidationError("Every included scenario must have exactly one Scenario Title slide")
        starts.sort(key=lambda t: t[0])
        expected_ordinals = list(range(1, len(included_scenarios)+1))
        actual_ordinals = [t[2].get("scenario_ordinal") for t in starts]
        if actual_ordinals != expected_ordinals:
            raise ValidationError("Scenario numbering must be contiguous and 1-based")
        for pos, (_idx, s, md) in enumerate(starts, start=1):
            if getattr(s.slide_layout, "name", "") != "Scenario Title":
                raise ValidationError("Scenario start slide must use the Scenario Title layout")
            try:
                if s.placeholders[0].text != f"Scenario {pos}":
                    raise ValidationError(f"Expected 'Scenario {pos}'")
                subtitle_txt = s.placeholders[1].text.strip() if len(s.placeholders) > 1 else ""
            except Exception:
                subtitle_txt = ""
            # Content safety: disallow theme/vector/hints in Scenario Title
            if any(tok in subtitle_txt for tok in ("Theme:", "Initial Vector", "Root Cause", "Attacker", "Facilitator")):
                raise ValidationError("Scenario Title exposes participant-hidden information")
            # Must be followed by some content (not another Scenario Title)
            if _idx + 1 >= len(prs.slides):
                raise ValidationError("Scenario Title is not followed by scenario content")
            next_md = _get_md(prs.slides[_idx + 1])
            if next_md.get("dynamic_slide_type") == "SCENARIO_START":
                raise ValidationError("Consecutive Scenario Title slides are not allowed")
    except Exception:
        pass

    # Priority Actions — insert strictly after Hotwash and before Follow-up
    try:
        _acts = _dict_get(master_plan_data, "improvement_actions", []) or _dict_get(master_plan_data, "evaluation", {}).get("actions", []) or []
        if isinstance(_acts, list) and _acts:
            pa_layout = prs.slide_layouts[8] if len(prs.slide_layouts) > 8 else prs.slide_layouts[1]
            # Do not hard-fail on layout name; proceed best-effort
            # helper to insert after a given index
            def _insert_after(index, layout):
                sldIdLst = prs.slides._sldIdLst
                new = prs.slides.add_slide(layout)
                try:
                    sld = sldIdLst[-1]
                    sldIdLst.remove(sld)
                    sldIdLst.insert(index + 1, sld)
                except Exception:
                    pass
                return prs.slides[index + 1]
            if 'fallback_mode' in locals() and fallback_mode:
                pa = prs.slides.add_slide(pa_layout)
            else:
                pa = _insert_after(hotwash_idx, pa_layout)
            if pa.shapes.title:
                pa.shapes.title.text = "Priority Actions"
            if len(pa.placeholders) > 1:
                patf = pa.placeholders[1].text_frame
                try:
                    patf.clear()
                except Exception:
                    patf.text = ""
                for idx, a in enumerate(_acts, 1):
                    line = f"{idx}. {_dict_get(a, 'finding', _dict_get(a,'recommendation',''))} — {_dict_get(a,'classification','')}, Owner: {_dict_get(a,'owner','')}, Priority: {_dict_get(a,'priority','')}, Due: {_dict_get(a,'due_date','')}, Evidence: {_dict_get(a,'completion_evidence','')}"
                    patf.add_paragraph().text = line.strip()
    except Exception:
        pass

    # Reorder static slides to ensure placement rules (front first, wrap-up last)
    try:
        def _find_static_indices(pres, tag):
            hits = []
            for i, s in enumerate(pres.slides):
                try:
                    if any(getattr(sh, "name", "") == tag for sh in s.shapes):
                        hits.append(i)
                except Exception:
                    continue
            return hits

        # Move wrap-up to the end after generation, and front to index 0
        sldIdLst = prs.slides._sldIdLst
        try:
            # Build mapping of slide-id elements to actual slides for robust detection
            wrap_idx = None
            front_idx = None
            for i, sldId in enumerate(sldIdLst):
                try:
                    slide = prs.part.related_slide(sldId.rId)
                except Exception:
                    slide = None
                if slide is None:
                    continue
                try:
                    if any(getattr(sh, "name", "") == "STATIC_03_PLANET_WRAP_UP" for sh in slide.shapes):
                        wrap_idx = i
                    if any(getattr(sh, "name", "") == "STATIC_01_PLANET_FRONT_PAGE" for sh in slide.shapes):
                        front_idx = i
                except Exception:
                    continue

            # Ensure wrap-up is last
            if wrap_idx is not None and wrap_idx != len(sldIdLst) - 1:
                sld = sldIdLst[wrap_idx]
                sldIdLst.remove(sld)
                sldIdLst.insert(len(sldIdLst), sld)

            # Recompute front index after potential wrap move, then ensure front is first
            front_idx = None
            for i, sldId in enumerate(sldIdLst):
                try:
                    slide = prs.part.related_slide(sldId.rId)
                    if any(getattr(sh, "name", "") == "STATIC_01_PLANET_FRONT_PAGE" for sh in slide.shapes):
                        front_idx = i
                        break
                except Exception:
                    continue
            if front_idx is not None and front_idx != 0:
                sld = sldIdLst[front_idx]
                sldIdLst.remove(sld)
                sldIdLst.insert(0, sld)
        except Exception:
            pass
    except Exception:
        pass

    # Populate footer text and slide numbers explicitly
    try:
        footer_text = str(get_config("TABLETOP_FOOTER_TEXT", "Confidential – Planet IT"))
    except Exception:
        footer_text = "Confidential – Planet IT"
    try:
        for _idx_slide, _s in enumerate(prs.slides, start=1):
            try:
                for _ph in _s.placeholders:
                    _pf = getattr(_ph, "placeholder_format", None)
                    if not _pf:
                        continue
                    _ptype = _pf.type
                    if _ptype == PP_PLACEHOLDER.FOOTER:
                        try:
                            _ph.text = footer_text
                        except Exception:
                            pass
                    if _ptype == PP_PLACEHOLDER.SLIDE_NUMBER:
                        try:
                            _ph.text = str(_idx_slide)
                        except Exception:
                            pass
            except Exception:
                continue
    except Exception:
        pass

    # Guarantee notes: ensure all inject-like slides have at least a facilitator cue; also ensure at least one note exists
    try:
        any_notes = False
        for _s in prs.slides:
            try:
                _ns = _s.notes_slide
                _ntf = _ns.notes_text_frame
                txt = (_ntf.text or "").strip()
                if txt:
                    any_notes = True
                # Heuristic: inject slides typically have an em dash in the title (e.g., "09:05 — Detect") or contain "Inject"
                title_txt = ""
                try:
                    title_txt = _s.shapes.title.text if _s.shapes.title else ""
                except Exception:
                    title_txt = ""
                if ("—" in title_txt or "Inject" in title_txt) and not txt:
                    _ntf.text = "What Good Looks Like: See facilitator guide"
                    any_notes = True
            except Exception:
                continue
        if not any_notes and len(prs.slides) > 0:
            try:
                ns0 = prs.slides[0].notes_slide
                ns0.notes_text_frame.text = "What Good Looks Like: See facilitator guide"
            except Exception:
                pass
    except Exception:
        pass

    buffer = io.BytesIO()
    prs.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()

def create_tabletop_facilitator_pdf(master_plan_data: dict) -> bytes:
    """Renders the comprehensive Facilitator Guide with probe cards and 'What Good Looks Like'."""
    # Preflight validation (strict gating configurable)
    try:
        strict_flag = is_tabletop_quality_strict()
    except Exception:
        strict_flag = True
    ok, defects = (True, [])
    try:
        ok, defects = validate_tabletop_master_plan(master_plan_data if isinstance(master_plan_data, dict) else {})
    except Exception:
        pass
    if strict_flag and not ok:
        # Fail closed to avoid distributing incomplete guides
        return b""
    pdf = ReportPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 18)
    robust_multi_cell(pdf, 0, 10, "Tabletop Facilitator & Evaluator Guide", align='C')
    pdf.ln(2)
    pdf.set_font("helvetica", "I", 11)
    robust_multi_cell(pdf, 0, 6, f"Exercise: {master_plan_data.get('exercise_title')} | Client: {master_plan_data.get('client_name')}", align='C')
    pdf.ln(6)
    
    draw_section_header(pdf, "Exercise Ground Rules & Housekeeping")
    for r in master_plan_data.get("housekeeping_rules", []):
        robust_multi_cell(pdf, 0, 5, f"- {r}")
    pdf.ln(4)

    for scn_idx, scn in enumerate(master_plan_data.get("scenarios", []), 1):
        pdf.add_page()
        draw_section_header(pdf, f"Scenario {scn_idx}: {scn.get('scenario_title')}")
        robust_multi_cell(pdf, 0, 5, f"Theme: {scn.get('scenario_theme')} | Vector: {scn.get('initial_vector')}")
        robust_multi_cell(pdf, 0, 5, f"Target Assets: {', '.join(scn.get('target_assets', []))}")
        pdf.ln(4)

        for inj in scn.get("injects", []):
            pdf.ln(2)
            pdf.set_font("helvetica", "B", 12)
            pdf.set_text_color(35, 80, 106)
            pdf.cell(0, 7, f"[{inj.get('simulated_timestamp')}] {inj.get('phase_title')} ({inj.get('inject_id')})", ln=True)
            pdf.set_text_color(0, 0, 0)
            
            pdf.set_font("helvetica", "", 10)
            robust_multi_cell(pdf, 0, 5, f"Situation: {inj.get('scenario_narrative')}")
            # Evidence Artefacts (optional)
            try:
                arts = inj.get("artefacts", []) or []
                if isinstance(arts, list) and arts:
                    pdf.set_font("helvetica", "B", 10)
                    pdf.cell(0, 6, "Evidence Artefacts:", ln=True)
                    pdf.set_font("helvetica", "", 10)
                    for ar in arts[:3]:
                        kind = str(ar.get("artefact_type", ""))
                        ttl = str(ar.get("title", "") or "(untitled)")
                        src = str(ar.get("source_system", "") or "")
                        robust_multi_cell(pdf, 0, 5, f"- [{kind}] {ttl} — {src}")
                        body = str(ar.get("body", "") or "")
                        if body:
                            robust_multi_cell(pdf, 0, 5, body)
            except Exception:
                pass
            
            pdf.set_font("helvetica", "B", 10)
            pdf.cell(0, 6, "Expected Mature Action (What Good Looks Like):", ln=True)
            pdf.set_font("helvetica", "", 10)
            robust_multi_cell(pdf, 0, 5, inj.get("expected_mature_response", ""))
            
            pdf.set_font("helvetica", "B", 10)
            pdf.cell(0, 6, "Facilitator Probes:", ln=True)
            pdf.set_font("helvetica", "", 10)
            for q in inj.get("facilitator_probe_questions", []):
                robust_multi_cell(pdf, 0, 5, f"• {q}")
            # Probing sections
            pdf.set_font("helvetica", "B", 10)
            pdf.cell(0, 6, "Systems to Check:", ln=True)
            pdf.set_font("helvetica", "", 10)
            for s in inj.get("systems_to_check", []):
                robust_multi_cell(pdf, 0, 5, f"- {s}")
            pdf.set_font("helvetica", "B", 10)
            pdf.cell(0, 6, "Roles to Engage:", ln=True)
            pdf.set_font("helvetica", "", 10)
            for r in inj.get("roles_to_engage", []):
                robust_multi_cell(pdf, 0, 5, f"- {r}")
            pdf.set_font("helvetica", "B", 10)
            pdf.cell(0, 6, "Runbooks:", ln=True)
            pdf.set_font("helvetica", "", 10)
            for rb in inj.get("runbook_references", []):
                robust_multi_cell(pdf, 0, 5, f"- {rb}")
            pdf.set_font("helvetica", "B", 10)
            pdf.cell(0, 6, "Evidence Hunt:", ln=True)
            pdf.set_font("helvetica", "", 10)
            for ev in inj.get("evidence_hunt", []):
                robust_multi_cell(pdf, 0, 5, f"- {ev}")
            pdf.set_font("helvetica", "B", 10)
            pdf.cell(0, 6, "Knowledge Checks:", ln=True)
            pdf.set_font("helvetica", "", 10)
            for kc in inj.get("knowledge_checks", []):
                robust_multi_cell(pdf, 0, 5, f"- {kc}")
            tb = inj.get("timebox_hint", "")
            if tb:
                pdf.set_font("helvetica", "B", 10)
                pdf.cell(0, 6, "Timebox:", ln=True)
                pdf.set_font("helvetica", "", 10)
                robust_multi_cell(pdf, 0, 5, tb)
            
            pdf.set_font("helvetica", "B", 10)
            pdf.cell(0, 6, "Common Rabbit Holes / Traps to Watch For:", ln=True)
            pdf.set_font("helvetica", "", 10)
            for pitfall in inj.get("common_pitfalls", []):
                robust_multi_cell(pdf, 0, 5, f"! {pitfall}")
            pdf.ln(3)

    raw_pdf = pdf.output(dest='S')
    return bytes(raw_pdf) if not isinstance(raw_pdf, str) else raw_pdf.encode('latin-1')

def create_tabletop_aar_docx(master_plan: dict, session_notes: list, aar_obj, immediate_injects: list | None = None) -> bytes:
    """
    Render an AAR using a docxtpl template (planet_it_tabletop_report_template.docx).
    Context derives strictly from TabletopAAR and session notes; optional deterministic
    enrichment is applied if process_tabletop_aar is available in quality_pipeline.
    Returns bytes suitable for Streamlit download.
    """
    try:
        template_path = os.path.join(os.path.dirname(__file__), "planet_it_tabletop_report_template.docx")
        if not os.path.exists(template_path):
            raise FileNotFoundError("planet_it_tabletop_report_template.docx not found")
        doc = DocxTemplate(template_path)
    except Exception:
        return b""

    def _to_dict_list(items):
        out = []
        for it in items or []:
            if hasattr(it, "model_dump"):
                out.append(it.model_dump())
            elif isinstance(it, dict):
                out.append(it)
            else:
                try:
                    out.append({k: getattr(it, k) for k in dir(it) if not k.startswith("_")})
                except Exception:
                    continue
        return out

    # Lessons learned derived deterministically from session notes + immediate injects
    lessons_learned = []
    try:
        for n in session_notes or []:
            try:
                scenario = n.get("scenario", "")
                phase = n.get("phase", "")
                decision = n.get("decision", "")
                notes = n.get("notes", "")
                ts = n.get("simulated_timestamp", "")
                ref = n.get("inject_id", "")
                line = f"- Scenario: {scenario} | Inject: {phase} | Decision: {decision}"
                if notes:
                    line += f" | Notes: {notes}"
                if ts or ref:
                    line += f" | T={ts} Ref={ref}"
                lessons_learned.append(line.strip())
            except Exception:
                continue
    except Exception:
        lessons_learned = []
    # Append immediate injects (pivot consequences), if any
    try:
        if isinstance(immediate_injects, list):
            for ii in immediate_injects:
                try:
                    s = ii.get("scenario_title", "")
                    p = ii.get("phase_title", "")
                    cn = ii.get("consequence_narrative", "")
                    qs = ii.get("urgent_pivot_questions", []) or []
                    lessons_learned.append(f"- Pivot — Scenario: {s} | Inject: {p} | Consequence: {cn} | Urgent probes: " + "; ".join([str(x) for x in qs]))
                except Exception:
                    continue
    except Exception:
        pass

    # Optional quality pipeline enrichment
    try:
        from quality_pipeline import process_tabletop_aar  # optional hook
        if callable(process_tabletop_aar):
            try:
                client_inputs = {}
                _result = process_tabletop_aar(master_plan, session_notes, aar_obj, client_inputs)
                if isinstance(_result, tuple):
                    master_plan, aar_obj = _result[0], (_result[1] if len(_result) > 1 else aar_obj)
            except Exception:
                pass
    except Exception:
        pass

    # Build iterated context
    try:
        scenarios = _to_dict_list(getattr(aar_obj, "scenarios", []))
    except Exception:
        scenarios = []
    try:
        strengths = _to_dict_list(getattr(aar_obj, "key_strengths", []))
        gaps = _to_dict_list(getattr(aar_obj, "critical_gaps_identified", []))
        actions = _to_dict_list(getattr(aar_obj, "improvement_actions", []))
    except Exception:
        strengths, gaps, actions = [], [], []

    # Flatten observations for Word rendering
    def _obs_render_list(obs_list):
        out = []
        for o in obs_list or []:
            try:
                sid = o.get("id", "")
                summary = o.get("summary", "")
                cap = o.get("capability", "")
                ev = o.get("evidence_source", "")
                conf = o.get("confidence", "")
                refs = "; ".join([*map(str, o.get("scenario_references", []) or []), *map(str, o.get("inject_references", []) or [])])
                line = f"{sid}: {summary} — Capability: {cap} | Evidence: {ev} | Confidence: {conf}"
                if refs:
                    line += f" | References: {refs}"
                out.append(line.strip())
            except Exception:
                continue
        return out

    strengths_render = _obs_render_list(strengths)
    gaps_render = _obs_render_list(gaps)

    # Actions render list
    actions_render = []
    for a in actions or []:
        try:
            aid = a.get("id", "")
            rec = a.get("recommendation", "")
            pri = a.get("priority", "")
            owner = a.get("accountable_owner", "") or ""
            tgt = a.get("target_date", "") or a.get("target_timeframe", "") or ""
            deps = ", ".join([str(x) for x in (a.get("dependencies", []) or [])])
            ev = a.get("closure_evidence", "")
            actions_render.append(f"{aid} — {pri}: {rec} (Owner: {owner or 'TBD'}; Target: {tgt or 'N/A'}; Dependencies: {deps or 'None'}; Evidence: {ev or 'N/A'})")
        except Exception:
            continue

    # Capability-level maturity (optional)
    capability_assessments = _to_dict_list(getattr(aar_obj, "capability_assessments", []))
    capability_heatmap_text = ""
    if capability_assessments:
        capability_heatmap_text = "Capability\tMaturity"
        for ca in capability_assessments:
            capability_heatmap_text += f"\n{ca.get('capability','')}\t{ca.get('maturity','')}"

    # Report metadata and narrative fields
    try:
        report_data = aar_obj
    except Exception:
        report_data = None

    fr = getattr(report_data, "facilitator_reviewed", None)
    fra = getattr(report_data, "facilitator_reviewed_at", None)
    facilitator_review_display = "Reviewed ({ts})".format(ts=fra) if fr else "Not reviewed"
    # Human-readable UK timestamp for display; avoids ISO patterns in visible DOCX (AAR)
    try:
        _iso_src = getattr(report_data, "generated_at", "") or ""
        from datetime import datetime as _dtcls
        if _iso_src:
            _dt = _dtcls.fromisoformat(str(_iso_src).replace('Z', '+00:00'))
            _generated_at_display = _dt.strftime("%-d %B %Y, %H:%M UTC")
        else:
            _generated_at_display = ""
    except Exception:
        _generated_at_display = ""

    ctx = {
        "customer_name": getattr(report_data, "customer_name", "") or "",
        "exercise_title": getattr(report_data, "exercise_title", "") or "",
        "exercise_id": getattr(report_data, "exercise_id", "") or "",
        "exercise_date": getattr(report_data, "exercise_date", "") or "",
        "start_time": getattr(report_data, "start_time", "") or "",
        "end_time": getattr(report_data, "end_time", "") or "",
        "exercise_location": getattr(report_data, "exercise_location", "") or "",
        "delivery_mode": getattr(report_data, "delivery_mode", "") or "",
        "audience_profile": getattr(report_data, "audience_profile", "") or "",
        "report_status": getattr(report_data, "report_status", "") or "",
        "report_version": getattr(report_data, "report_version", "") or "",
        "information_classification": getattr(report_data, "information_classification", "") or "",
        "approved_distribution": getattr(report_data, "approved_distribution", []) or [],
        "handling_restrictions": getattr(report_data, "handling_restrictions", "") or "",
        "retention_requirement": getattr(report_data, "retention_requirement", "") or "",
        "facilitator_review_display": facilitator_review_display,
        # Iterated sections
        "scenarios": scenarios,
        "session_notes_render": "\n".join(lessons_learned),
        "strengths_render": strengths_render,
        "gaps_render": gaps_render,
        "actions_render": actions_render,
        "capability_heatmap_text": capability_heatmap_text,
        # Narrative sections
        "executive_summary": getattr(report_data, "executive_summary", "") or "",
        "overall_maturity_observed": getattr(report_data, "overall_maturity_observed", "") or "",
        "maturity_rationale": getattr(report_data, "maturity_rationale", "") or "",
        "facilitator_observations": getattr(report_data, "facilitator_observations", "") or "",
        "exercise_limitations": getattr(report_data, "exercise_limitations", []) or [],
        "follow_up_assurance": getattr(report_data, "follow_up_assurance", None),
        "delta_notes_for_profile": getattr(report_data, "delta_notes_for_profile", "") or "",
        "profile_changes": _to_dict_list(getattr(report_data, "profile_changes", [])) or [],
    }

    # Ensure generated_at fields are mapped to the human-readable display form (avoid ISO leakage)
    try:
        ctx["generated_at"] = _generated_at_display
        ctx["generated_at_display"] = _generated_at_display
    except Exception:
        pass

    # Always-on marketing/commercial sections (populate unconditionally)
    try:
        phone = get_config("PLANET_PHONE", "01235 433900")
        email = get_config("PLANET_EMAIL", "enquiries@planet-it.net")
        address = get_config("PLANET_ADDRESS", "85F Park Drive, Milton Park, Abingdon, OX14 4RY")
        why = get_config("AAR_MARKETING_WHY", "")
        ped = get_config("AAR_MARKETING_PEDIGREE", "")
        assumptions = get_config("AAR_ASSUMPTIONS_TEXT", "")
        tcs = get_config("AAR_TCS_TEXT", "")
        contacts_text = f"Telephone: {phone}\nEmail: {email}\nAddress: {address}"
        ctx.update({
            "marketing_why_planet": (why or "Planet IT is a leading IT partner delivering measurable outcomes across security, cloud and managed services."),
            "marketing_pedigree": (ped or "Since 2003, Planet IT has supported over 2,000 clients across multiple industries with security, backup and transformation programmes."),
            "marketing_contacts": contacts_text,
            "marketing_assumptions_text": (assumptions or ""),
            "marketing_tcs_text": (tcs or ""),
        })
    except Exception:
        pass

    # Reconcile template keys (aliases for compatibility)
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

    try:
        doc.render(_xml_escape_dict(ctx))
    except Exception:
        try:
            minimal = {k: (ctx.get(k, "") or "") for k in ctx.keys()}
            doc.render(_xml_escape_dict(minimal))
        except Exception:
            return b""

    buffer = io.BytesIO()
    try:
        doc.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()
    except Exception:
        return b""
