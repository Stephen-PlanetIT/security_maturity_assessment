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
                if name and narrative:
                    lines.append(f"{name}: {narrative}")
                elif narrative:
                    lines.append(narrative)
                elif name:
                    lines.append(str(name))
            else:
                lines.append(str(it))
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
from config import get_config, ConfigKey
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
    """Recursively escape &, <, > in all string values of a dict for safe DOCX XML embedding."""
    if _depth > 10:
        return d
    def _escape_str(s: str) -> str:
        # Escape raw XML-sensitive characters without double-escaping existing entities
        s = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#[0-9]+;|#x[0-9A-Fa-f]+;)', '&amp;', s)
        s = s.replace('<', '&lt;').replace('>', '&gt;')
        return s
    if isinstance(d, dict):
        escaped = {}
        for key, value in d.items():
            if isinstance(value, str):
                escaped[key] = _escape_str(value)
            elif isinstance(value, list):
                escaped[key] = [_escape_str(v) if isinstance(v, str) else v for v in value]
            elif isinstance(value, dict):
                escaped[key] = _xml_escape_dict(value, _depth=_depth + 1)
            else:
                escaped[key] = value
        return escaped
    # If a non-dict is passed, escape if it's a string; otherwise return as-is
    return _escape_str(d) if isinstance(d, str) else d


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

def create_threat_docx(client_inputs: dict, scenario_obj, recs: list, mdr_case: str) -> bytes:
    """Generates a Microsoft Word (.docx) document for the Threat Simulator using docxtpl."""
    template_path = os.path.join(os.path.dirname(__file__), "planet_it_threat_scenario_template.docx")
    doc = DocxTemplate(template_path)
    # --- QUALITY PIPELINE (Threat Report DOCX) ---
    try:
        if 'process_threat_report' in globals() and callable(process_threat_report) and (quality_gate_enabled() if callable(quality_gate_enabled) else True):
            scenario_obj, mdr_case, recs, _quality = process_threat_report(client_inputs, scenario_obj, recs, mdr_case)
    except Exception:
        pass

    # Structure the context variables mirroring the template structure
    # Initialize with existing fields for backwards compatibility
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
        raise
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
    ts_text = ts_text if 'ts_text' in locals() else _format_threat_scenarios(getattr(report_data, "threat_scenarios", None))
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
    if data is not None:
        if hasattr(data, "model_dump"):
            dd = data.model_dump()
            labels = list(dd.keys())
            values = list(dd.values())
        elif isinstance(data, dict):
            labels = list(data.keys())
            values = list(data.values())
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

    # Build per-domain weighted contribution percents from radar_chart_data and MATURITY_WEIGHTS
    domain_weighted_pct_map = {}
    try:
        if "dd" in locals() and isinstance(dd, dict):
            def _norm_score(v):
                try:
                    fv = float(v)
                except Exception:
                    fv = 1.0
                if fv < 0: fv = 0.0
                if fv > 3: fv = 3.0
                return fv
            for dname, rkey in _DOMAIN_TO_RADAR.items():
                if rkey in dd and rkey in MATURITY_WEIGHTS:
                    s = _norm_score(dd.get(rkey, 1))
                    w = MATURITY_WEIGHTS.get(rkey, 0.0)
                    pct = int(round(w * (s / 3.0) * 100))
                    if pct < 0: pct = 0
                    if pct > 100: pct = 100
                    domain_weighted_pct_map[dname] = pct
    except Exception:
        domain_weighted_pct_map = {}

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
    context = {
        # Keep {{ threat_scenarios }} as a literal placeholder for post-render injection
        # Threat_scenarios" : "{{ threat_scenarios }}",
        # Also support templates using capitalised placeholder name
        "Threat_scenarios": "{{ threat_scenarios }}",
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
    }
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
        raise
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
