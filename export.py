# export.py
import io
import re
import os
from fpdf import FPDF
from pptx import Presentation
from pptx.util import Pt, Inches
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
import matplotlib.pyplot as plt
import numpy as np

# --- BRANDING COLORS ---
SOPHOS_DARK_BLUE = RGBColor(0, 32, 96)
SOPHOS_LIGHT_BLUE = RGBColor(0, 102, 204)

# --- TEXT CLEANER ---
def clean_text(text, mode="pdf"):
    if not text: return ""
    text = text.replace('\xa0', ' ').replace('\t', ' ')
    text = text.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    text = text.replace('–', '-').replace('—', '-') 
    if mode == "pdf":
        text = text.replace('🎯', 'KPI:').replace('✅', '[DONE]').replace('🗓️', 'DATE:').replace('🛡️', 'REC:')
        text = text.replace('🟢', 'WIN:').replace('£', 'GBP ') 
    text = text.replace('### ', '').replace('## ', '').replace('# ', '')
    if mode in ["mdr", "pptx"]:
        text = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', r'\1', text)
        text = text.replace('**', '').replace('*', '').replace('`', '')
        text = text.replace('🎯', '').replace('✅', '').replace('🛡️', '').replace('🟢', '')
    return text.encode('ascii', 'ignore').decode('ascii').strip()

# ==========================================
# PDF ENGINE (For the PDFExecutiveSummary)
# ==========================================
class ReportPDF(FPDF):
    def header(self):
        self.set_fill_color(0, 32, 96) 
        self.rect(0, 0, 210, 20, 'F')   
        self.set_y(6)
        self.set_font('helvetica', 'B', 12)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, 'Executive Security Assessment', align='R', ln=True)
        self.set_y(25)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

def robust_multi_cell(pdf, w, h, txt, align="L", fill=False):
    safe_txt = clean_text(txt, "pdf")
    pdf.multi_cell(w=w, h=h, txt=safe_txt, align=align, fill=fill)

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

def create_vciso_pdf(inputs, exec_obj):
    pdf = ReportPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 18)
    pdf.cell(w=0, h=12, txt="Executive Security Maturity Assessment", ln=True, align="C")
    pdf.ln(4)
    
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(0, 32, 96) 
    pdf.cell(0, 8, "Executive Risk Summary", ln=True)
    pdf.set_font("helvetica", "", 11)
    pdf.set_text_color(0, 0, 0)
    robust_multi_cell(pdf, 0, 5, exec_obj.executive_summary)
    pdf.ln(4)
    
    chart_buf = generate_radar_chart(exec_obj.domain_assessments)
    pdf.image(chart_buf, x=45, w=120)
    
    pdf.add_page()
    for domain in exec_obj.domain_assessments:
        pdf.set_font("helvetica", "B", 12)
        pdf.set_text_color(0, 32, 96)
        pdf.cell(w=0, h=8, txt=f"{domain.domain_name} - Score: {domain.numeric_maturity_score}/5.0", ln=True)
        pdf.set_font("helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)
        robust_multi_cell(pdf, 0, 5, f"{domain.current_state_analysis}")
        pdf.ln(4)

    return bytes(pdf.output())

# ==========================================
# POWERPOINT ENGINE (For the PPTXTechnicalRoadmap)
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

def create_vciso_pptx(inputs, tech_obj, exec_obj):
    # Template Injection Logic
    template_path = "sophos_master_template.pptx"
    
    if os.path.exists(template_path):
        prs = Presentation(template_path)
        blank_layout = prs.slide_layouts[6] if len(prs.slide_layouts) > 6 else prs.slide_layouts[0]
    else:
        prs = Presentation()
        prs.slide_width = Inches(10)
        prs.slide_height = Inches(7.5)
        blank_layout = prs.slide_layouts[6]
        
    # --- SLIDE 1: Title ---
    slide1 = prs.slides.add_slide(blank_layout)
    add_text_block(slide1, "TECHNICAL DEPLOYMENT ROADMAP", Inches(0.5), Inches(2.5), Inches(9), Inches(1), font_size=36, bold=True, rgb=(0,32,96))
    add_text_block(slide1, f"Customer: {inputs.get('customer_name', 'Client')}", Inches(0.5), Inches(3.5), Inches(9), Inches(0.5), font_size=18)

    # --- SLIDE 2: Architecture State ---
    slide2 = prs.slides.add_slide(blank_layout)
    add_text_block(slide2, "Current Architecture Analysis", Inches(0.5), Inches(0.5), Inches(9), Inches(0.5), font_size=24, bold=True, rgb=(0,32,96))
    add_text_block(slide2, tech_obj.architecture_current_state, Inches(0.5), Inches(1.5), Inches(9), Inches(4), font_size=12)

    # --- SLIDE 3: Target Operating Model ---
    slide3 = prs.slides.add_slide(blank_layout)
    add_text_block(slide3, "Target Operating Model (TOM)", Inches(0.5), Inches(0.5), Inches(9), Inches(0.5), font_size=24, bold=True, rgb=(0,32,96))
    add_text_block(slide3, tech_obj.target_operating_model, Inches(0.5), Inches(1.5), Inches(9), Inches(4), font_size=12)

    # --- SLIDES 4+: Implementation Phases ---
    for phase in tech_obj.implementation_phases:
        slide_ph = prs.slides.add_slide(blank_layout)
        add_text_block(slide_ph, phase.phase_name, Inches(0.5), Inches(0.5), Inches(9), Inches(0.5), font_size=24, bold=True, rgb=(0,32,96))
        
        # Engineering Tasks
        tf_tasks = add_text_block(slide_ph, "Engineering Tasks:", Inches(0.5), Inches(1.5), Inches(4.3), Inches(0.5), font_size=14, bold=True)
        for task in phase.engineering_tasks:
            p = tf_tasks.add_paragraph()
            p.text = f"• {clean_text(task, 'pptx')}"
            p.font.size = Pt(11)
            
        # Products
        tf_prod = add_text_block(slide_ph, "Solutions Deployed:", Inches(5.2), Inches(1.5), Inches(4.3), Inches(0.5), font_size=14, bold=True)
        for prod in phase.sophos_products_deployed:
            p = tf_prod.add_paragraph()
            p.text = f"• {clean_text(prod, 'pptx')}"
            p.font.size = Pt(11)

    pptx_stream = io.BytesIO()
    prs.save(pptx_stream)
    return pptx_stream.getvalue()

# (Tactical Threat Simulator export logic remains unchanged)
def create_pdf(inputs, scenario_obj, recs, mdr_case): ...
def create_pptx(inputs, scenario_obj, recs, mdr_case): ...