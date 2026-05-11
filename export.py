# export.py
import io
import re
import os
from fpdf import FPDF
from pptx import Presentation
from pptx.util import Pt, Inches
from pptx.dml.color import RGBColor
import matplotlib.pyplot as plt
import numpy as np

PLANET_IT_DARK_BLUE = RGBColor(0, 32, 96) 
PLANET_IT_LIGHT_BLUE = RGBColor(0, 102, 204)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(BASE_DIR, "planet_it_master_template.pptx")

def clean_text(text, mode="pdf"):
    if not text: return ""
    text = text.replace('\xa0', ' ').replace('\t', ' ')
    text = text.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    text = text.replace('–', '-').replace('—', '-') 
    text = text.replace('### ', '').replace('## ', '').replace('# ', '')
    return text.encode('ascii', 'ignore').decode('ascii').strip()

# ==========================================
# PDF ENGINE 
# ==========================================
class ReportPDF(FPDF):
    def header(self):
        self.set_fill_color(0, 32, 96) 
        self.rect(0, 0, 210, 20, 'F')   
        self.set_y(6)
        self.set_font('helvetica', 'B', 12)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, 'Planet IT Security Advisory & Assessment', align='R', ln=True)
        self.set_y(25)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

def robust_multi_cell(pdf, w, h, txt, align="L", fill=False):
    safe_txt = clean_text(txt, "pdf")
    if safe_txt:
        pdf.set_x(pdf.l_margin) 
        pdf.multi_cell(w=w, h=h, txt=safe_txt, align=align, fill=fill)
        pdf.set_x(pdf.l_margin) 

def generate_radar_chart(domain_assessments):
    categories = [d.domain_name.replace(' & ', '\n& ') for d in domain_assessments]
    levels = [d.numeric_maturity_score for d in domain_assessments]
    categories = [*categories, categories[0]]
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
    plt.clf()
    plt.close('all')
    return buf

def draw_estate_summary(pdf, inputs):
    pdf.ln(2)
    pdf.set_font("helvetica", "B", 12)
    pdf.set_text_color(0, 32, 96) 
    pdf.cell(0, 8, "Client Estate & Environmental Summary", ln=True)
    pdf.set_draw_color(200, 200, 200) 
    pdf.set_line_width(0.5)
    pdf.line(pdf.get_x(), pdf.get_y(), 195, pdf.get_y()) 
    pdf.ln(2)
    pdf.set_text_color(0, 0, 0)
    pdf.set_fill_color(245, 245, 245) 
    pdf.set_font("helvetica", "", 9)
    summary_text = (
        f"MDR Provider: {inputs.get('mdr_provider', 'N/A')} | Endpoint: {inputs.get('endpoint', 'N/A')}\n"
        f"Firewall: {inputs.get('firewall', 'N/A')} | Workspace License: {inputs.get('workspace_license', 'N/A')}\n"
        f"Identity: {inputs.get('identity', 'N/A')} | Cloud Env: {inputs.get('cloud_env', 'N/A')}\n"
        f"Target Compliance: {inputs.get('target_compliance', 'None')} | Target Users: {inputs.get('users', 'N/A')}"
    )
    for line in summary_text.split('\n'):
        pdf.cell(w=0, h=6, txt=f"  {line}", ln=True, fill=True)
    pdf.ln(4)

def create_vciso_pdf(inputs, exec_obj):
    pdf = ReportPDF()
    
    # --- PAGE 1: THE BOARDROOM TEAR-SHEET ---
    pdf.add_page()
    pdf.set_font("helvetica", "B", 18)
    pdf.cell(w=0, h=10, txt="Executive Boardroom Tear-Sheet", ln=True, align="C")
    draw_estate_summary(pdf, inputs)
    
    # Financials Block
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 8, " Financial Exposure & Benchmarking", ln=True, fill=True)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(60, 8, "Est. Financial Exposure:")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 8, exec_obj.financial_analysis.estimated_financial_exposure, ln=True)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(60, 8, "Immediate Budget Ask:")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 8, exec_obj.financial_analysis.immediate_budgetary_ask, ln=True)
    pdf.ln(2)
    pdf.set_font("helvetica", "I", 10)
    robust_multi_cell(pdf, 0, 5, f"Peer Benchmark: {exec_obj.financial_analysis.peer_benchmark_statement}")
    pdf.ln(4)
    
    # Top 3 Risks
    pdf.set_font("helvetica", "B", 12)
    pdf.set_text_color(204, 0, 0)
    pdf.cell(0, 8, " Top 3 Critical Business Risks", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "", 10)
    for risk in exec_obj.top_3_business_risks:
        robust_multi_cell(pdf, 0, 6, f"• {risk}")
    
    # Radar Chart 
    chart_buf = generate_radar_chart(exec_obj.domain_assessments)
    pdf.image(chart_buf, x=45, y=180, w=120)

    # --- PAGE 2: EXECUTIVE PROSE & SETUP ---
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.set_text_color(0, 32, 96) 
    pdf.cell(0, 8, "Executive Posture Summary", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)
    
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 6, "Current Setup & Posture Analysis", ln=True)
    pdf.set_font("helvetica", "", 10)
    robust_multi_cell(pdf, 0, 5, exec_obj.executive_prose.current_setup_summary)
    pdf.ln(4)

    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(0, 128, 0) # Green
    pdf.cell(0, 6, "Current Strengths", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "", 10)
    for strength in exec_obj.executive_prose.current_strengths: robust_multi_cell(pdf, 0, 5, f"• {strength}")
    pdf.ln(4)

    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(204, 0, 0) # Red
    pdf.cell(0, 6, "Primary Weaknesses", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "", 10)
    for weakness in exec_obj.executive_prose.current_weaknesses: robust_multi_cell(pdf, 0, 5, f"• {weakness}")
    pdf.ln(4)
    
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(0, 32, 96) 
    pdf.cell(0, 6, "Cloud & Workspace License Optimization", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "", 10)
    robust_multi_cell(pdf, 0, 5, exec_obj.executive_prose.license_security_analysis)
    pdf.ln(4)
    
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(204, 0, 0)
    pdf.cell(0, 6, "The Cost of Inaction", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "", 10)
    robust_multi_cell(pdf, 0, 5, exec_obj.cost_of_inaction)
    pdf.ln(4)

    # --- PAGE 3: STRATEGIC ALIGNMENT ---
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.set_text_color(0, 32, 96) 
    pdf.cell(0, 8, "Strategic Alignment & Roadmap", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    pdf.set_font("helvetica", "B", 12)
    pdf.set_text_color(0, 32, 96)
    pdf.cell(0, 8, " Compliance & Framework Alignment", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "", 10)
    robust_multi_cell(pdf, 0, 5, exec_obj.compliance_alignment)
    pdf.ln(6)

    pdf.set_font("helvetica", "B", 12)
    pdf.set_text_color(0, 32, 96) 
    pdf.cell(0, 8, " Strategic Phased Roadmap", ln=True)
    pdf.set_text_color(0, 0, 0)
    for phase in exec_obj.high_level_roadmap:
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(0, 6, phase.phase, ln=True)
        pdf.set_font("helvetica", "", 10)
        robust_multi_cell(pdf, 0, 5, phase.summary)
        pdf.ln(4)

    # --- PAGE 4: DETAILED DOMAIN GAP ANALYSIS ---
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.set_text_color(0, 32, 96) 
    pdf.cell(0, 8, "Deep-Dive Domain Analysis", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    for domain in exec_obj.domain_assessments:
        # Domain Header
        pdf.set_font("helvetica", "B", 14)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(w=0, h=10, txt=f" {domain.domain_name} - Maturity: {domain.numeric_maturity_score}/5.0", ln=True, fill=True)
        pdf.ln(2)
        
        # Current State & Risk Exposure
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(0, 6, "State of the Estate:", ln=True)
        pdf.set_font("helvetica", "", 10)
        robust_multi_cell(pdf, 0, 5, domain.current_state_analysis)
        pdf.ln(2)
        
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(0, 6, "Risk Exposure Context:", ln=True)
        pdf.set_font("helvetica", "", 10)
        safe_risk_exposure = getattr(domain, 'risk_exposure_summary', 'Context unavailable.')
        robust_multi_cell(pdf, 0, 5, safe_risk_exposure)
        pdf.ln(2)
        
        # Real-World Scenario
        pdf.set_font("helvetica", "B", 10)
        pdf.set_text_color(204, 0, 0) 
        pdf.cell(0, 6, "Real-World Threat Scenario:", ln=True)
        pdf.set_font("helvetica", "I", 9)
        safe_scenario = getattr(domain, 'real_world_risk_scenario', 'Scenario data unavailable.')
        robust_multi_cell(pdf, 0, 5, safe_scenario)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(4)
        
        # Recommended Solutions (Deep Dive)
        pdf.set_font("helvetica", "B", 11)
        pdf.set_text_color(0, 32, 96)
        pdf.cell(0, 6, "Advisory Recommendations & Strategic Rationale:", ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)
        
        for rec in domain.recommended_solutions:
            sol_name = getattr(rec, 'solution_name', 'Solution')
            desc = getattr(rec, 'description', '')
            val = getattr(rec, 'business_value', '')
            rationale = getattr(rec, 'strategic_rationale', 'Rationale unavailable.')
            
            # Formatted Recommendation Block
            pdf.set_font("helvetica", "B", 10)
            pdf.cell(0, 5, f"• {sol_name}", ln=True)
            
            pdf.set_font("helvetica", "", 9)
            pdf.set_x(pdf.l_margin + 5) # Indent the details slightly
            robust_multi_cell(pdf, 0, 5, f"What it is: {desc}")
            pdf.set_x(pdf.l_margin + 5)
            robust_multi_cell(pdf, 0, 5, f"Business Value: {val}")
            pdf.set_x(pdf.l_margin + 5)
            robust_multi_cell(pdf, 0, 5, f"Strategic Rationale: {rationale}")
            pdf.ln(4)
            
        pdf.ln(8) # Space before next domain

    return bytes(pdf.output())

# ==========================================
# POWERPOINT ENGINE 
# ==========================================
def add_text_block(slide, text, left, top, width, height, font_size=12, bold=False, rgb=(0,0,0)):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = clean_text(text, "pptx")
    p.font.size = Pt(font_size)
    p.font.bold = bold
    p.font.color.rgb = RGBColor(*rgb)
    return tf

def load_template_or_fail():
    if not os.path.exists(TEMPLATE_PATH):
        raise FileNotFoundError(f"CRITICAL ERROR: Cannot find the master template at: {TEMPLATE_PATH}.")
    return Presentation(TEMPLATE_PATH)

def wipe_existing_slides(prs):
    for i in range(len(prs.slides) - 1, -1, -1):
        rId = prs.slides._sldIdLst[i].rId
        prs.part.drop_rel(rId)
        del prs.slides._sldIdLst[i]

def create_vciso_pptx(inputs, tech_obj, exec_obj):
    prs = load_template_or_fail()
    wipe_existing_slides(prs) 
    content_layout = prs.slide_layouts[1] if len(prs.slide_layouts) > 1 else prs.slide_layouts[0]
        
    slide1 = prs.slides.add_slide(content_layout)
    add_text_block(slide1, "OPERATIONAL DEPLOYMENT ROADMAP", Inches(0.5), Inches(2.5), Inches(9), Inches(1), font_size=36, bold=True, rgb=(0,32,96))
    
    slide2 = prs.slides.add_slide(content_layout)
    add_text_block(slide2, "Operational Reality Check", Inches(0.5), Inches(0.5), Inches(9), Inches(0.5), font_size=24, bold=True, rgb=(0,32,96))
    add_text_block(slide2, tech_obj.operational_reality_statement, Inches(0.5), Inches(1.5), Inches(9), Inches(2), font_size=14)

    slide3 = prs.slides.add_slide(content_layout)
    add_text_block(slide3, "Immediate High-Impact Actions", Inches(0.5), Inches(0.5), Inches(9), Inches(0.5), font_size=24, bold=True, rgb=(0,32,96))
    tf_qw = add_text_block(slide3, "", Inches(0.5), Inches(1.5), Inches(9), Inches(4), font_size=14)
    for win in tech_obj.high_impact_quick_wins:
        p = tf_qw.add_paragraph()
        p.text = f"[{win.effort_vs_impact}] {clean_text(win.task, 'pptx')}"
        p.font.size = Pt(12)

    for phase in tech_obj.implementation_phases:
        slide_ph = prs.slides.add_slide(content_layout)
        add_text_block(slide_ph, phase.phase_name, Inches(0.5), Inches(0.5), Inches(9), Inches(0.5), font_size=24, bold=True, rgb=(0,32,96))
        
        tf_tasks = add_text_block(slide_ph, "Engineering Tasks:", Inches(0.5), Inches(1.5), Inches(4.3), Inches(0.5), font_size=14, bold=True)
        for task in phase.engineering_tasks:
            p = tf_tasks.add_paragraph()
            p.text = f"• {clean_text(task, 'pptx')}"
            p.font.size = Pt(11)

    pptx_stream = io.BytesIO()
    prs.save(pptx_stream)
    return pptx_stream.getvalue()

def create_pdf(inputs, scenario_obj, recs, mdr_case): return b''
def create_pptx(inputs, scenario_obj, recs, mdr_case): return b''