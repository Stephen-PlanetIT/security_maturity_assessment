# export.py
import io
import json
import re
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from fpdf import FPDF
from data import format_governance_narrative
import matplotlib.pyplot as plt
import numpy as np
import os
import tempfile

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
    
    
    # Render the docx template with our context mapping
    doc.render(_xml_escape_dict(context))
    
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
        return

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


def create_maturity_docx(client_inputs: dict, report_data) -> bytes:
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

    # 2) Domains & Roadmap derivation with safe defaults
    domains_list = []
    domain_items = getattr(report_data, "domain_assessments", None) or getattr(report_data, "domains", None) or []
    if not isinstance(domain_items, list):
        domain_items = []
    for item in domain_items:
        if hasattr(item, "model_dump"):
            domains_list.append(_xml_escape_dict(item.model_dump()))
        elif isinstance(item, dict):
            domains_list.append(_xml_escape_dict(item))
        else:
            domains_list.append(_xml_escape_dict({"domain_name": getattr(item, "domain_name", None) or getattr(item, "name", str(item))}))

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
        "threat_scenarios": "{{ threat_scenarios }}",
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
        "matrix_mapping": report_data.resiliency_matrix_mapping if hasattr(report_data, "resiliency_matrix_mapping") else "",
        "cost_of_inaction": report_data.cost_of_inaction if hasattr(report_data, "cost_of_inaction") else "",
        "domains": domains_list,
        "roadmap": roadmap_list,
        "compliance_alignment": compliance_alignment_list,
        "success_metrics": getattr(report_data, "success_metrics", ""),
        "engagement_cadence": getattr(report_data, "engagement_cadence", ""),
        "consultant_discovery_guide": getattr(report_data, "consultant_discovery_guide", ""),
        "compliance_alignment_render": compliance_alignment_render,
        "partnership_outline": getattr(report_data, "partnership_outline", ""),
    }
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
    doc.render(_xml_escape_dict(context))

    # Post-render: inject formatted threat scenarios with proper Word styling
    threat_scenarios_data_for_inject = getattr(report_data, "threat_scenarios", None)
    if threat_scenarios_data_for_inject and isinstance(threat_scenarios_data_for_inject, list):
        _inject_threat_scenarios_after_render(doc, threat_scenarios_data_for_inject)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()
