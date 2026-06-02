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

# --- TEXT CLEANER (UNICODE SAFE) ---
def clean_text(text, mode="pdf"):
    if not text: return ""
    text = text.replace('\xa0', ' ').replace('\t', ' ')
    text = text.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    text = text.replace('–', '-').replace('—', '-') 
    
    # PDF-Specific Emoji Stripping (Helvetica compatibility)
    if mode == "pdf":
        text = text.replace('🎯', 'KPI:').replace('✅', '[DONE]').replace('🗓️', 'DATE:').replace('🛡️', 'REC:')
        text = text.replace('🟢', 'WIN:')

    text = text.replace('### ', '').replace('## ', '').replace('# ', '')
    
    if mode == "mdr":
        text = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', r'\1 (\2)', text)
        text = text.replace('**', '').replace('*', '').replace('`', '')
    elif mode == "pptx":
        text = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', r'\1: \2', text)
        text = text.replace('**', '').replace('*', '')
    
    return text.encode('ascii', 'ignore').decode('ascii').strip()

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

def draw_section_header(pdf, title):
    pdf.ln(5)
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(0, 32, 96) 
    pdf.cell(0, 8, title, ln=True)
    pdf.set_draw_color(200, 200, 200) 
    pdf.set_line_width(0.5)
    pdf.line(pdf.get_x(), pdf.get_y(), 195, pdf.get_y()) 
    pdf.ln(4)
    pdf.set_text_color(0, 0, 0)

def robust_multi_cell(pdf, w, h, txt, align="L"):
    safe_txt = clean_text(txt, "pdf")
    pdf.multi_cell(w=w, h=h, txt=safe_txt, align=align)

def draw_estate_summary(pdf, inputs):
    draw_section_header(pdf, "Client Estate Summary")
    pdf.set_fill_color(245, 245, 245) 
    pdf.set_font("helvetica", "", 10)
    summary_text = (
        f"Industry: {inputs['industry']} | Users: {inputs['users']} | Endpoints: {inputs['endpoints']}\n"
        f"Critical Asset: {inputs['critical_infra']}\n"
        f"MDR Provider: {inputs.get('mdr_provider', 'Unknown')} | Endpoint: {inputs['endpoint']}\n"
        f"Firewall: {inputs['firewall']} | Email: {inputs['email']}"
    )
    for line in summary_text.split('\n'):
        pdf.cell(w=0, h=7, txt=f"  {line}", ln=True, fill=True)
    pdf.ln(6)

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
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=300, transparent=True)
    buf.seek(0)
    plt.close(fig)
    return buf

def create_vciso_pdf(inputs, vciso_obj):
    pdf = ReportPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 18)
    pdf.cell(w=0, h=12, txt="vCISO Maturity Assessment & Strategic Roadmap", ln=True, align="C")
    pdf.set_font("helvetica", "I", 11)
    pdf.set_text_color(100, 100, 100) 
    pdf.cell(w=0, h=6, txt=f"Prepared for: {inputs['customer_name']} | By: {inputs.get('consultant_name', 'Advisor')}", ln=True, align="C")
    pdf.set_text_color(0, 0, 0) 
    pdf.ln(8)
    
    draw_estate_summary(pdf, inputs)
    draw_section_header(pdf, "Executive Summary & Risk Analysis")
    robust_multi_cell(pdf, 0, 5, vciso_obj.executive_summary)
    pdf.ln(2)
    pdf.set_font("helvetica", "B", 10)
    pdf.set_text_color(150, 0, 0)
    pdf.cell(0, 5, "THE COST OF INACTION:", ln=True)
    pdf.set_font("helvetica", "", 10)
    robust_multi_cell(pdf, 0, 5, vciso_obj.cost_of_inaction)
    pdf.set_text_color(0, 0, 0)
    
    chart_buf = generate_radar_chart(vciso_obj.domain_assessments)
    pdf.image(chart_buf, x=45, w=120)
    
    pdf.add_page()
    draw_section_header(pdf, "Detailed Domain Analysis")
    for domain in vciso_obj.domain_assessments:
        pdf.set_font("helvetica", "B", 12)
        pdf.set_text_color(0, 32, 96)
        pdf.cell(w=0, h=8, txt=f"{domain.domain_name} - {domain.current_maturity_level}", ln=True)
        pdf.set_font("helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)
        robust_multi_cell(pdf, 0, 5, f"Analysis: {domain.current_state_analysis}")
        pdf.ln(2)
        
        pdf.set_font("helvetica", "B", 9)
        pdf.cell(0, 5, "Zero-Cost Quick Wins:", ln=True)
        pdf.set_font("helvetica", "", 9)
        for win in domain.vendor_agnostic_quick_wins:
            pdf.cell(0, 5, f"  - {clean_text(win, 'pdf')}", ln=True)
        pdf.ln(2)
        pdf.set_font("helvetica", "B", 9)
        pdf.cell(0, 5, "Strategic Recommendations:", ln=True)
        pdf.set_font("helvetica", "", 9)
        for sol in domain.recommended_solutions:
            pdf.cell(0, 5, f"  - {clean_text(sol, 'pdf')}", ln=True)
        pdf.ln(4)

    draw_section_header(pdf, "Partnership Roadmap & Success Metrics")
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 6, "12-Month Success Metrics (KPIs):", ln=True)
    pdf.set_font("helvetica", "", 10)
    for kpi in vciso_obj.success_metrics:
        pdf.cell(0, 5, f"  - {clean_text(kpi, 'pdf')}", ln=True)
        
    pdf.ln(4)
    for phase in vciso_obj.phased_roadmap:
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(0, 6, clean_text(phase.phase_name, 'pdf'), ln=True)
        pdf.set_font("helvetica", "", 9)
        for milestone in phase.milestones:
            pdf.cell(0, 5, f"  - {clean_text(milestone, 'pdf')}", ln=True)
    
    pdf.ln(4)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 6, "Advisory Engagement Cadence:", ln=True)
    pdf.set_font("helvetica", "", 10)
    for meeting in vciso_obj.engagement_cadence:
        pdf.cell(0, 5, f"  - {clean_text(meeting, 'pdf')}", ln=True)

    return bytes(pdf.output())

def create_vciso_pptx(inputs, vciso_obj):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "vCISO Strategic Security Roadmap"
    slide.placeholders[1].text = f"Prepared for: {inputs['customer_name']}\nAdvisor: {inputs.get('consultant_name', 'Advisor')}"
    
    # Adding a simple risk slide to avoid empty presentations
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
    pdf.cell(0, 10, "Tactical Threat Simulation Report", ln=True, align='C')
    draw_estate_summary(pdf, inputs)
    robust_multi_cell(pdf, 0, 5, scenario_obj.narrative)
    return bytes(pdf.output())

def create_pptx(inputs, scenario_obj, recs, mdr_case):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "Breach Simulation"
    slide.placeholders[1].text = f"Target: {inputs['customer_name']}"
    
    slide2 = prs.slides.add_slide(prs.slide_layouts[1])
    slide2.shapes.title.text = "Attack Narrative"
    text_preview = scenario_obj.narrative[:500] + "..." if len(scenario_obj.narrative) > 500 else scenario_obj.narrative
    slide2.placeholders[1].text = clean_text(text_preview, "pptx")
    
    pptx_stream = io.BytesIO()
    prs.save(pptx_stream)
    return pptx_stream.getvalue()