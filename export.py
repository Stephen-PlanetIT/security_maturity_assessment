# export.py
import io
import re
import textwrap
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
    draw_section_header(pdf, "Client Estate Summary")
    pdf.set_fill_color(245, 245, 245) 
    pdf.set_font("helvetica", "", 10)
    
    comp_list = inputs.get('compliance', [])
    comp_str = ", ".join(comp_list) if comp_list else "None Specified"
    
    summary_text = (
        f"Industry: {inputs['industry']} | Users: {inputs['users']} | Endpoints: {inputs['endpoints']}\n"
        f"Critical Asset: {inputs['critical_infra']}\n"
        f"Compliance Targets: {comp_str}\n"
        f"MDR Provider: {inputs.get('mdr_provider', 'Unknown')} | Endpoint: {inputs['endpoint']}\n"
        f"Firewall: {inputs['firewall']} | Email: {inputs['email']}"
    )
    for line in summary_text.split('\n'):
        robust_multi_cell(pdf, 0, 7, f"  {line}", fill=True)
    pdf.ln(4)

# ==========================================
# VCISO ASSESSMENT EXPORTS
# ==========================================
def generate_radar_chart(domain_assessments):
    categories = [d.domain_name.replace(' & ', '\n& ') for d in domain_assessments]
    categories = [*categories, categories[0]]
    levels = []
    for d in domain_assessments:
        match = re.search(r'\d+', d.current_maturity_level)
        levels.append(int(match.group()) if match else 1)
    levels = [*levels, levels[0]]
    label_loc = np.linspace(start=0, stop=2 * np.pi, num=len(levels))
    fig = plt.figure(figsize=(6, 5))
    ax = plt.subplot(polar=True)
    ax.plot(label_loc, levels, color='#002060', linewidth=2)
    ax.fill(label_loc, levels, color='#002060', alpha=0.25)
    ax.set_ylim(0, 5)
    plt.thetagrids(np.degrees(label_loc), labels=categories)
    plt.tight_layout()
    
    # Save to a temporary physical file instead of a BytesIO stream
    tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    plt.savefig(tmpfile.name, format='png', dpi=300, transparent=True)
    plt.close(fig)
    
    return tmpfile.name

def create_vciso_pdf(inputs, vciso_obj):
    pdf = ReportPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 18)
    robust_multi_cell(pdf, 0, 12, "vCISO Maturity Assessment & Strategic Roadmap", align="C")
    
    pdf.set_font("helvetica", "I", 11)
    pdf.set_text_color(100, 100, 100) 
    robust_multi_cell(pdf, 0, 6, f"Prepared for: {inputs['customer_name']} | By: {inputs.get('consultant_name', 'Advisor')}", align="C")
    
    pdf.set_text_color(0, 0, 0) 
    pdf.ln(8)
    
    draw_estate_summary(pdf, inputs)
    draw_section_header(pdf, "Executive Summary & Risk Analysis")
    robust_multi_cell(pdf, 0, 5, vciso_obj.executive_summary)
    
    pdf.ln(4)
    robust_multi_cell(pdf, 0, 6, "### Compliance & Framework Alignment:")
    robust_multi_cell(pdf, 0, 5, vciso_obj.compliance_alignment)
    
    pdf.ln(4)
    robust_multi_cell(pdf, 0, 6, "### THE COST OF INACTION:")
    robust_multi_cell(pdf, 0, 5, vciso_obj.cost_of_inaction)
    
    # Generate chart to temp file, inject into PDF, then delete the temp file
    chart_path = generate_radar_chart(vciso_obj.domain_assessments)
    pdf.image(chart_path, x=45, w=120)
    os.remove(chart_path)
    
    pdf.add_page()
    draw_section_header(pdf, "Detailed Domain Analysis")
    for domain in vciso_obj.domain_assessments:
        robust_multi_cell(pdf, 0, 8, f"### {domain.domain_name} - {domain.current_maturity_level}")
        robust_multi_cell(pdf, 0, 5, f"Analysis: {domain.current_state_analysis}")
        
        robust_multi_cell(pdf, 0, 6, "### Zero-Cost Quick Wins:")
        for win in domain.vendor_agnostic_quick_wins:
            robust_multi_cell(pdf, 0, 5, f"- {win}")
        
        robust_multi_cell(pdf, 0, 6, "### Strategic Recommendations:")
        for sol in domain.recommended_solutions:
            robust_multi_cell(pdf, 0, 5, f"- {sol}")

    draw_section_header(pdf, "Partnership Roadmap & Success Metrics")
    robust_multi_cell(pdf, 0, 6, "### 12-Month Success Metrics (KPIs):")
    for kpi in vciso_obj.success_metrics:
        robust_multi_cell(pdf, 0, 5, f"- {kpi}")
        
    for phase in vciso_obj.phased_roadmap:
        robust_multi_cell(pdf, 0, 6, f"### {clean_text(phase.phase_name, 'pdf')}")
        for milestone in phase.milestones:
            robust_multi_cell(pdf, 0, 5, f"- {milestone}")
    
    pdf.ln(4)
    robust_multi_cell(pdf, 0, 6, "### Advisory Engagement Cadence:")
    for meeting in vciso_obj.engagement_cadence:
        robust_multi_cell(pdf, 0, 5, f"- {meeting}")

    return pdf.output(dest='S').encode('latin-1')

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
    
    draw_section_header(pdf, "2. Attack Timeline")
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
        
    return pdf.output(dest='S').encode('latin-1')

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