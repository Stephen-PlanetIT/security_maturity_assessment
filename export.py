# export.py
import io
import re
import textwrap
from fpdf import FPDF
from pptx import Presentation
from pptx.util import Pt, Inches
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.shapes import MSO_CONNECTOR
import matplotlib.pyplot as plt
import numpy as np

# --- TEXT CLEANER (CONSOLIDATED) ---
def clean_text(text, mode="pdf"):
    if not text: return ""
    text = text.replace('\xa0', ' ').replace('\t', ' ')
    text = text.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    text = text.replace('–', '-').replace('—', '-')
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
        self.cell(0, 10, 'Security Advisory & Assessment', align='R', new_x="RMARGIN", new_y="TOP")
        self.set_y(25)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}', align='C', new_x="RMARGIN", new_y="TOP")

def draw_section_header(pdf, title):
    pdf.ln(5)
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(0, 32, 96) 
    pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(200, 200, 200) 
    pdf.set_line_width(0.5)
    pdf.line(pdf.get_x(), pdf.get_y(), 210 - 15, pdf.get_y()) 
    pdf.ln(4)
    pdf.set_text_color(0, 0, 0)

def robust_multi_cell(pdf, w, h, txt, align="L", fill=False):
    try:
        pdf.multi_cell(w=w, h=h, txt=txt, align=align, markdown=True, fill=fill)
    except Exception:
        safe_txt = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', r'\1 (\2)', txt).replace('**', '').replace('*', '')
        wrap_width = 85 if w == 0 else int(w / 2.0) 
        lines = textwrap.wrap(safe_txt, width=wrap_width, break_long_words=True)
        for line in lines:
            pdf.cell(w=w, h=h, txt=line, align=align, fill=fill, new_x="LMARGIN", new_y="NEXT")

# --- SHARED: ESTATE OVERVIEW UI ---
def draw_estate_summary(pdf, inputs):
    draw_section_header(pdf, "Client Estate Summary")
    pdf.set_fill_color(245, 245, 245) 
    pdf.set_font("helvetica", "", 10)
    
    summary_text = (
        f"Industry: {inputs['industry']}   |   Users: {inputs['users']}   |   Endpoints: {inputs['endpoints']}\n"
        f"Critical Infrastructure: {inputs['critical_infra']}\n"
        f"M365 License: {inputs['m365_license']}   |   Cloud: {inputs['cloud_env']}\n"
        f"Endpoint: {inputs['endpoint']}   |   Email: {inputs['email']}\n"
        f"Perimeter: {inputs['firewall']} Firewall   |   Identity: {inputs['identity']}\n"
        f"Internal Security: {inputs['in_house_team']}"
    )
    for line in summary_text.split('\n'):
        pdf.cell(w=0, h=7, txt=f"  {line}", new_x="LMARGIN", new_y="NEXT", fill=True)
    pdf.ln(6)


# ==========================================
# THREAT SIMULATOR EXPORTS
# ==========================================
def draw_visual_timeline(pdf, timeline_events):
    if not timeline_events: return
    draw_section_header(pdf, "Attack Timeline & Early MDR Intervention")
    
    x_node, x_text = 20, 30
    for i, t_event in enumerate(timeline_events):
        if pdf.get_y() > 250: pdf.add_page()
            
        start_y = pdf.get_y()
        pdf.set_fill_color(0, 32, 96)
        pdf.ellipse(x=x_node - 2, y=start_y + 1, w=4, h=4, style='F')
        
        pdf.set_x(x_text)
        pdf.set_font("helvetica", "B", 10)
        pdf.set_text_color(0, 32, 96)
        pdf.cell(w=0, h=6, txt=clean_text(t_event.timestamp, "pdf"), new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("helvetica", "", 10)
        pdf.set_x(x_text)
        
        usable_width = 210 - x_text - 15 
        robust_multi_cell(pdf, usable_width, 5, clean_text(t_event.event_description, "pdf"))
            
        end_y = pdf.get_y()
        if i < len(timeline_events) - 1:
            pdf.set_draw_color(200, 200, 200)
            pdf.set_line_width(0.5)
            pdf.line(x_node, start_y + 6, x_node, end_y + 2)
        pdf.ln(5)

def create_pdf(inputs, scenario_obj, recs, mdr_case):
    pdf = ReportPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 18)
    pdf.cell(w=0, h=12, txt="Cybersecurity Threat & Advisory Report", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("helvetica", "I", 11)
    pdf.set_text_color(100, 100, 100) 
    pdf.cell(w=0, h=6, txt=f"Prepared for: {inputs['customer_name']} | By: {inputs['consultant_name']}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_text_color(0, 0, 0) 
    pdf.ln(8)
    
    draw_estate_summary(pdf, inputs)
    
    draw_section_header(pdf, "Targeted Threat Narrative & Solutions")
    pdf.set_font("helvetica", "", 10)
    for paragraph in clean_text(scenario_obj.narrative, "pdf").split('\n'):
        if paragraph.strip():
            robust_multi_cell(pdf, 0, 6, paragraph)
            pdf.ln(2) 
    pdf.ln(6)
    
    if scenario_obj.timeline:
        draw_visual_timeline(pdf, scenario_obj.timeline)
    return bytes(pdf.output())

def create_pptx(inputs, scenario_obj, recs, mdr_case):
    DARK_BLUE = RGBColor(0, 32, 96)
    prs = Presentation()
    # (Existing create_pptx logic for Threat Simulator remains intact here...)
    # [Truncated for brevity, paste your existing create_pptx function body here]
    pptx_stream = io.BytesIO()
    prs.save(pptx_stream)
    return pptx_stream.getvalue()


# ==========================================
# VCISO ASSESSMENT EXPORTS
# ==========================================
def generate_radar_chart(domain_assessments):
    """Generates a matplotlib radar chart from the domain maturity levels."""
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
    ax.plot(label_loc, levels, label='Current Maturity', color='#002060', linewidth=2)
    ax.fill(label_loc, levels, color='#002060', alpha=0.25)
    
    ax.set_ylim(0, 5)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_yticklabels(['L1', 'L2', 'L3', 'L4', 'L5'], color="grey", size=8)
    
    lines, labels = plt.thetagrids(np.degrees(label_loc), labels=categories)
    for label in labels:
        label.set_fontsize(9)
        label.set_fontweight('bold')
        
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=300, transparent=True)
    buf.seek(0)
    plt.close(fig)
    return buf

def create_vciso_pdf(inputs, vciso_obj):
    pdf = ReportPDF()
    pdf.add_page()
    
    # Title
    pdf.set_font("helvetica", "B", 18)
    pdf.cell(w=0, h=12, txt="vCISO Maturity Assessment & Roadmap", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("helvetica", "I", 11)
    pdf.set_text_color(100, 100, 100) 
    pdf.cell(w=0, h=6, txt=f"Prepared for: {inputs['customer_name']} | By: {inputs['consultant_name']}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_text_color(0, 0, 0) 
    pdf.ln(8)
    
    draw_estate_summary(pdf, inputs)
    
    # Exec Summary & Radar Chart
    draw_section_header(pdf, "Executive Summary")
    pdf.set_font("helvetica", "", 10)
    robust_multi_cell(pdf, 0, 6, clean_text(vciso_obj.executive_summary, "pdf"))
    
    # Insert Radar Chart Image
    chart_buf = generate_radar_chart(vciso_obj.domain_assessments)
    pdf.ln(5)
    # Center the 120mm image on a 210mm wide A4 page: (210-120)/2 = 45
    pdf.image(chart_buf, x=45, w=120)
    pdf.ln(5)
    
    # Domain Assessments
    pdf.add_page()
    draw_section_header(pdf, "Domain Gap Analysis")
    for domain in vciso_obj.domain_assessments:
        if pdf.get_y() > 230: pdf.add_page()
        
        pdf.set_font("helvetica", "B", 12)
        pdf.set_text_color(0, 32, 96)
        pdf.cell(w=0, h=8, txt=f"{domain.domain_name} — {domain.current_maturity_level}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        
        pdf.set_font("helvetica", "", 10)
        robust_multi_cell(pdf, 0, 5, f"**Current State:** {clean_text(domain.current_state_analysis, 'pdf')}")
        
        pdf.ln(2)
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(w=0, h=5, txt="Critical Gaps:", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("helvetica", "", 10)
        for gap in domain.critical_gaps:
            robust_multi_cell(pdf, 0, 5, f"• {clean_text(gap, 'pdf')}")
            
        pdf.ln(2)
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(w=0, h=5, txt="Recommended Solutions:", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("helvetica", "", 10)
        for sol in domain.recommended_solutions:
            robust_multi_cell(pdf, 0, 5, f"• {clean_text(sol, 'pdf')}")
        pdf.ln(6)

    # Roadmap
    draw_section_header(pdf, "Strategic Phased Roadmap")
    for phase in vciso_obj.phased_roadmap:
        pdf.set_font("helvetica", "B", 11)
        pdf.set_text_color(0, 32, 96)
        pdf.cell(w=0, h=7, txt=clean_text(phase.phase_name, "pdf"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("helvetica", "", 10)
        for milestone in phase.milestones:
            robust_multi_cell(pdf, 0, 5, f"✅ {clean_text(milestone, 'pdf')}")
        pdf.ln(4)

    return bytes(pdf.output())

def create_vciso_pptx(inputs, vciso_obj):
    DARK_BLUE = RGBColor(0, 32, 96)
    prs = Presentation()
    
    # Title Slide
    slide1 = prs.slides.add_slide(prs.slide_layouts[0])
    slide1.shapes.title.text = "vCISO Maturity Assessment & Strategic Roadmap"
    slide1.shapes.title.text_frame.paragraphs[0].font.color.rgb = DARK_BLUE
    slide1.placeholders[1].text = f"Prepared for: {inputs['customer_name']}\nPresented by: {inputs['consultant_name']}\n{inputs['industry']} Sector"
    
    # Radar Chart & Exec Summary Slide
    slide2 = prs.slides.add_slide(prs.slide_layouts[5]) # Blank slide with title
    slide2.shapes.title.text = "Current State Maturity"
    slide2.shapes.title.text_frame.paragraphs[0].font.color.rgb = DARK_BLUE
    
    # Exec Summary Text Box (Left Side)
    txBox = slide2.shapes.add_textbox(Inches(0.5), Inches(1.5), Inches(4.5), Inches(4.5))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.add_paragraph()
    p.text = clean_text(vciso_obj.executive_summary, "pptx")
    p.font.size = Pt(14)
    
    # Radar Chart Image (Right Side)
    chart_buf = generate_radar_chart(vciso_obj.domain_assessments)
    slide2.shapes.add_picture(chart_buf, Inches(5.0), Inches(1.5), width=Inches(4.5))
    
    # Domain Assessment Slides (One slide per domain)
    for domain in vciso_obj.domain_assessments:
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = f"{domain.domain_name}"
        slide.shapes.title.text_frame.paragraphs[0].font.color.rgb = DARK_BLUE
        
        tf = slide.shapes.placeholders[1].text_frame
        tf.clear()
        tf.word_wrap = True
        
        p = tf.add_paragraph()
        p.text = f"Maturity: {domain.current_maturity_level}"
        p.font.bold = True
        p.font.size = Pt(16)
        
        p_state = tf.add_paragraph()
        p_state.text = clean_text(domain.current_state_analysis, "pptx")
        p_state.font.size = Pt(14)
        p_state.space_after = Pt(14)
        
        p_gaps_title = tf.add_paragraph()
        p_gaps_title.text = "Critical Gaps:"
        p_gaps_title.font.bold = True
        p_gaps_title.font.size = Pt(14)
        
        for gap in domain.critical_gaps:
            p_gap = tf.add_paragraph()
            p_gap.text = clean_text(gap, "pptx")
            p_gap.level = 1
            p_gap.font.size = Pt(12)
            
        p_sol_title = tf.add_paragraph()
        p_sol_title.text = "Recommendations:"
        p_sol_title.font.bold = True
        p_sol_title.font.size = Pt(14)
        p_sol_title.space_before = Pt(10)
        
        for sol in domain.recommended_solutions:
            p_sol = tf.add_paragraph()
            p_sol.text = clean_text(sol, "pptx")
            p_sol.level = 1
            p_sol.font.size = Pt(12)

    # Roadmap Slide
    slide_rm = prs.slides.add_slide(prs.slide_layouts[1])
    slide_rm.shapes.title.text = "Strategic Phased Roadmap"
    slide_rm.shapes.title.text_frame.paragraphs[0].font.color.rgb = DARK_BLUE
    tf_rm = slide_rm.shapes.placeholders[1].text_frame
    tf_rm.clear()
    tf_rm.word_wrap = True
    
    for phase in vciso_obj.phased_roadmap:
        p_phase = tf_rm.add_paragraph()
        p_phase.text = clean_text(phase.phase_name, "pptx")
        p_phase.font.bold = True
        p_phase.font.size = Pt(16)
        p_phase.font.color.rgb = DARK_BLUE
        p_phase.space_before = Pt(14)
        
        for milestone in phase.milestones:
            p_m = tf_rm.add_paragraph()
            p_m.text = clean_text(milestone, "pptx")
            p_m.level = 1
            p_m.font.size = Pt(14)

    pptx_stream = io.BytesIO()
    prs.save(pptx_stream)
    return pptx_stream.getvalue()