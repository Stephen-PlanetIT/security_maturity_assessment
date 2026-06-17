# export.py
import io
import re
import textwrap
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Inches
from fpdf import FPDF
from pptx import Presentation
from pptx.util import Pt, Inches
from pptx.dml.color import RGBColor
import matplotlib.pyplot as plt
import numpy as np
import os
import tempfile

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

    if mode == "pptx":
        text = text.replace('### ', '').replace('## ', '').replace('# ', '')
        text = text.replace('**', '').replace('*', '').replace('`', '')
        text = text.replace('//// ', '')
    
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
        self.set_fill_color(0, 32, 96) 
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
            pdf.set_text_color(0, 32, 96) 
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
    pdf.set_text_color(0, 32, 96) 
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
    pdf.set_text_color(0, 32, 96) # Dark Blue branding
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

# ==========================================
# VCISO ASSESSMENT EXPORTS
# ==========================================
def generate_radar_chart(domain_assessments):
    # Extract categories (do NOT duplicate the first one for the labels)
    categories = [d.domain_name.replace(' & ', '\n& ') for d in domain_assessments]
    
    levels = []
    for d in domain_assessments:
        match = re.search(r'\d+', str(d.current_maturity_level))
        levels.append(int(match.group()) if match else 1)
        
    # Append the first value ONLY to the data array to close the circular line plot
    levels = [*levels, levels[0]]
    label_loc = np.linspace(start=0, stop=2 * np.pi, num=len(levels))
    
    fig = plt.figure(figsize=(7, 6)) # Slightly larger canvas for full family labels
    ax = plt.subplot(polar=True)
    ax.plot(label_loc, levels, color='#002060', linewidth=2)
    ax.fill(label_loc, levels, color='#002060', alpha=0.25)
    
    # Map to the new 1-3 Phase Resiliency Matrix
    ax.set_ylim(0, 3.2)
    ax.set_yticks([1, 2, 3])
    ax.set_yticklabels(['Phase 1', 'Phase 2', 'Phase 3'], color='grey', size=8)
    
    # thetagrids must only receive unique angles (drop the 360-degree overlapping point)
    plt.thetagrids(np.degrees(label_loc[:-1]), labels=categories, fontsize=9)
    plt.tight_layout()
    
    tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    plt.savefig(tmpfile.name, format='png', dpi=300, transparent=True)
    plt.close(fig)
    
    return tmpfile.name

import io
import re
from docxtpl import DocxTemplate

def clean_markdown(text):
    """Strips Markdown bold/italic artifacts from the LLM response."""
    if not text: return ""
    return re.sub(r'[*_]', '', text)

import io
from docxtpl import DocxTemplate

def create_vciso_docx(client_inputs: dict, report_data) -> bytes:
    template_path = os.path.join(os.path.dirname(__file__), "planet_it_vciso_template.docx")
    doc = DocxTemplate(template_path)
    
    # --- 1. Generate the Radar Chart Image ---
    # Convert Pydantic model to list for plotting
    data = report_data.radar_chart_data
    labels = list(data.model_dump().keys())
    values = list(data.model_dump().values())
    
# Plotting logic
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    values += values[:1]
    angles += angles[:1]
    
    fig, ax = plt.subplots(figsize=(4, 4), subplot_kw=dict(polar=True))
    ax.fill(angles, values, color='#003366', alpha=0.25)
    ax.plot(angles, values, color='#003366', linewidth=2)
    
    # --- NEW: HARD LOCK THE AXIS TO THE 3-PILLAR FRAMEWORK ---
    ax.set_ylim(0, 3) # Force the chart to a max radius of 3
    ax.set_yticks([1, 2, 3]) # Draw the three ring lines
    ax.set_yticklabels(["Reactive", "Proactive", "Adaptive"], color="grey", size=8) # Label the rings
    
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, size=9)
    
    chart_buffer = io.BytesIO()
    plt.savefig(chart_buffer, format='png', bbox_inches='tight')
    chart_buffer.seek(0)
    plt.close()
    
    # Create the InlineImage object
    chart_image = InlineImage(doc, chart_buffer, width=Inches(4))

    # 2. Map the frontend inputs and backend LLM data to the template's Jinja2 tags
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
        
        # --- Current Technology Stack Data ---
        "mdr_provider": client_inputs.get("mdr_provider", "None"),
        "endpoint": client_inputs.get("endpoint", "Unknown"),
        "endpoint_posture": client_inputs.get("endpoint_posture", "Unknown"), # NEW
        "firewall": client_inputs.get("firewall", "Unknown"),
        "identity": client_inputs.get("identity", "Unknown"),
        "email": client_inputs.get("email", "Unknown"),
        "m365_license": client_inputs.get("m365_license", "Unknown"), # NEW
        "savviness": client_inputs.get("savviness", "Unknown"),
        
        # --- Operational Telemetry & Validation ---
        "pentest_status": client_inputs.get("pentest_status", "Unknown"),
        "vuln_scanning": client_inputs.get("vuln_scanning", "Unknown"),
        "remote_access": client_inputs.get("remote_access", "Unknown"), # NEW
        "saas_backup": client_inputs.get("saas_backup", "Unknown"), # NEW
        "ir_readiness": client_inputs.get("ir_readiness", "Unknown"), # NEW
        "mfa_status": client_inputs.get("mfa_status", "Unknown"), # NEW
        "patching": client_inputs.get("patching", "Unknown"), # NEW
        "backups": client_inputs.get("backups", "Unknown"), # NEW
        "insurance": client_inputs.get("insurance", "Unknown"), # NEW
        "rto": client_inputs.get("rto", "Unknown"), # NEW
        "advanced_controls": client_inputs.get("advanced_controls", "None"), # NEW
        
        # --- Strategic LLM Generated Data ---
        "radar_chart": chart_image,
        "exec_summary": report_data.executive_summary,
        "matrix_mapping": report_data.resiliency_matrix_mapping,
        "compliance_alignment": report_data.compliance_alignment,
        "cost_of_inaction": report_data.cost_of_inaction,
        "domains": report_data.domain_assessments,
        "roadmap": report_data.phased_roadmap,
        "success_metrics": report_data.success_metrics,
        "engagement_cadence": report_data.engagement_cadence,
        "consultant_discovery_guide": report_data.consultant_discovery_guide
    }

    # 3. Render the document, replacing all {{ tags }} and {% loops %}
    doc.render(context)
    
    # 4. Save to a BytesIO buffer (Memory) instead of the local hard drive
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    # Return the raw bytes to app.py for the st.download_button
    return buffer.getvalue()

# --- Keep your existing create_pdf, create_pptx, and create_vciso_pptx functions below this ---
def create_vciso_pptx(inputs, vciso_obj):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "vCISO Strategic Security Roadmap"
    slide.placeholders[1].text = f"Prepared for: {inputs['customer_name']}\nAdvisor: {inputs.get('consultant_name', 'Advisor')}"
    
    slide2 = prs.slides.add_slide(prs.slide_layouts[1])
    slide2.shapes.title.text = "Executive Summary"
    tf = slide2.shapes.placeholders[1].text_frame
    tf.text = clean_text(vciso_obj.executive_summary, "pptx")

    pptx_stream = io.BytesIO()
    prs.save(pptx_stream)
    return pptx_stream.getvalue()

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

def create_pptx(inputs, scenario_obj, recs, mdr_case):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "Breach Simulation"
    slide.placeholders[1].text = f"Target: {inputs['customer_name']}"
    
    slide2 = prs.slides.add_slide(prs.slide_layouts[1])
    slide2.shapes.title.text = "Attack Narrative"
    text_preview = scenario_obj.narrative[:500] + "..." if len(scenario_obj.narrative) > 500 else scenario_obj.narrative
    slide2.placeholders[1].text = clean_text(text_preview, "pptx")
    
    slide3 = prs.slides.add_slide(prs.slide_layouts[1])
    slide3.shapes.title.text = "MDR Investigation Log"
    mdr_preview = mdr_case[:500] + "..." if len(mdr_case) > 500 else mdr_case
    slide3.placeholders[1].text = clean_text(mdr_preview, "pptx")
    
    pptx_stream = io.BytesIO()
    prs.save(pptx_stream)
    return pptx_stream.getvalue()

def create_threat_docx(client_inputs: dict, scenario_obj, recs: list, mdr_case: str) -> bytes:
    """Generates a Microsoft Word (.docx) document for the Threat Simulator using docxtpl."""
    template_path = os.path.join(os.path.dirname(__file__), "planet_it_threat_scenario_template.docx")
    doc = DocxTemplate(template_path)
    
    # Structure the context variables mirroring the template structure
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
        "threat_narrative": scenario_obj.narrative,
        "threat_timeline": scenario_obj.timeline,
        "threat_timeline_without_sophos": scenario_obj.timelines.without_sophos if hasattr(scenario_obj, 'timelines') else [],
        "threat_timeline_with_sophos": scenario_obj.timelines.with_sophos if hasattr(scenario_obj, 'timelines') else scenario_obj.timeline,
        "mdr_case_log": mdr_case,
        "recommendations": recs,
    }
    
    # Render the docx template with our context mapping
    doc.render(context)
    
    # Save document into a BytesIO memory stream
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    return buffer.getvalue()