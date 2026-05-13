# pages/1_🌐_Unified_Enterprise_Audit.py
import streamlit as st
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core import LLMEngine
from prompts import SYSTEM_PERSONA, build_unified_audit_prompt, UnifiedEngagementReport
from export import create_advisory_pdf, create_advisory_pptx

st.set_page_config(page_title="Enterprise Audit", page_icon="🌐", layout="wide")
st.title("🌐 Unified Enterprise Security & Operations Audit")
st.markdown("A holistic assessment covering GRC, Financial Cyber Risk, Security Architecture, and IT Operations (Patching/Backup).")

if 'unified_obj' not in st.session_state:
    st.session_state['unified_obj'] = None

client_inputs = {}

with st.expander("⚙️ Comprehensive Client Discovery", expanded=not st.session_state['unified_obj']):
    st.subheader("1. Profile & Core Technology Stack")
    col1, col2, col3 = st.columns(3)
    with col1:
        client_inputs["customer_name"] = st.text_input("Customer Name", "Acme Corp")
        client_inputs["industry"] = st.selectbox("Industry", ["Manufacturing", "Finance", "Healthcare", "Retail", "Technology", "Education"])
        client_inputs["users"] = st.number_input("Users", min_value=1, value=500)
    with col2:
        client_inputs["mdr_provider"] = st.selectbox("Current MDR", ["None", "Sophos MDR", "CrowdStrike", "Other"])
        client_inputs["endpoint"] = st.selectbox("Endpoint", ["Sophos", "Microsoft Defender", "Other"])
        client_inputs["firewall"] = st.selectbox("Firewall", ["Fortinet", "Palo Alto", "Sophos", "Other"])
    with col3:
        client_inputs["identity"] = st.selectbox("Identity", ["Microsoft Entra ID", "Okta", "On-Prem AD"])
        client_inputs["workspace_license"] = st.selectbox("Workspace License", ["None", "M365 Business Premium", "M365 E3", "M365 E5", "Google Workspace"])
        client_inputs["cloud_env"] = st.selectbox("Cloud", ["AWS", "Azure", "GCP", "None (On-Prem)"])

    st.divider()
    st.subheader("2. Financials & IT Resourcing")
    f1, f2, f3, f4 = st.columns(4)
    with f1: client_inputs["revenue_band"] = st.selectbox("Annual Revenue", ["< £5M", "£5M - £20M", "£20M - £100M", "£100M+"])
    with f2: client_inputs["downtime_cost"] = st.selectbox("Downtime Cost/Hr", ["< £10k", "£10k - £50k", "£50k+"])
    with f3: client_inputs["security_ftes"] = st.selectbox("IT/Security FTEs", ["0 (No dedicated IT)", "1-2 (Small Team)", "3-5", "6+"])
    with f4: client_inputs["budget_trend"] = st.selectbox("IT Budget Trend", ["Decreasing", "Flat", "Increasing"])

    st.divider()
    st.subheader("3. IT Operations & Data Resilience (N-able Matrix)")
    o1, o2 = st.columns(2)
    with o1:
        client_inputs["patching_strategy"] = st.selectbox("OS & 3rd Party Patching", ["Manual / Ad-Hoc", "WSUS / Basic GPO", "Legacy RMM", "Automated & Verified"])
        client_inputs["asset_visibility"] = st.selectbox("Asset Management", ["Excel Spreadsheets", "Basic Network Scans", "Real-time RMM Agent"])
    with o2:
        client_inputs["server_backup"] = st.selectbox("Server Infrastructure Backup", ["On-Premise NAS/Tape Only", "Legacy Cloud (Slow Recovery)", "Immutable Cloud Backup"])
        client_inputs["m365_backup"] = st.selectbox("Microsoft 365 Backup", ["None (Relying on MS Retention)", "Third-Party Cloud Backup"])

    st.divider()
    st.subheader("4. GRC, Culture & Modern Attack Surface")
    g1, g2, g3 = st.columns(3)
    with g1:
        client_inputs["saas_sprawl"] = st.selectbox("SaaS Sprawl", ["< 20 Apps", "20 - 50 Apps", "50+ Apps (Unmanaged)"])
        client_inputs["identity_controls"] = st.selectbox("Identity Controls", ["Basic Passwords", "MFA (SMS/App)", "Conditional Access & MFA", "JIT / PIM"])
        client_inputs["phishing_frequency"] = st.selectbox("Phishing Sims", ["Never", "Annually", "Monthly / Quarterly"])
    with g2:
        client_inputs["admin_rights"] = st.selectbox("Endpoint Privileges", ["Most users are Local Admins", "Zero Trust (LAPS)"])
        target_comp = st.multiselect("Target Frameworks", ["ISO27001", "NIS2 Directive", "Cyber Essentials Plus"])
        client_inputs["target_compliance"] = ", ".join(target_comp) if target_comp else "None specified"
    with g3:
        client_inputs["current_cert"] = st.selectbox("Current Certs", ["None", "Cyber Essentials (CE)", "ISO27001"])
        client_inputs["insurance_status"] = st.selectbox("Cyber Insurance", ["None", "Policy Exists", "Policy mapped to IR Plan"])

generate_btn = st.button("🚀 Generate Unified Enterprise Audit", type="primary", use_container_width=True)

if generate_btn:
    llm_client = LLMEngine.get_client()
    deployment = st.secrets.get("AZURE_OPENAI_DEPLOYMENT", "")
    
    with st.spinner("Analyzing Security, GRC, and IT Operations to build a Unified Roadmap..."):
        prompt = build_unified_audit_prompt(client_inputs)
        unified_obj = LLMEngine.generate_structured_report(llm_client, deployment, SYSTEM_PERSONA, prompt, UnifiedEngagementReport)
        
        if unified_obj:
            st.session_state['unified_obj'] = unified_obj
            st.session_state['unified_pdf'] = create_advisory_pdf(client_inputs, unified_obj.executive_pdf_content, "Unified Enterprise Security & Operations Audit")
            st.session_state['unified_pptx'] = create_advisory_pptx(client_inputs, unified_obj.technical_pptx_content, unified_obj.executive_pdf_content, "ENTERPRISE DEPLOYMENT ROADMAP")

if st.session_state['unified_obj']:
    st.success("✅ Unified Enterprise Audit Generated successfully.")
    
    # Render quick overview to screen
    st.info(f"**Co-Managed Operations Takeaway:** {st.session_state['unified_obj'].executive_pdf_content.it_operations_analysis.co_managed_opportunities}")
    
    c1, c2 = st.columns(2)
    with c1: st.download_button("📄 Download Unified PDF", data=st.session_state['unified_pdf'], file_name=f"{client_inputs['customer_name']}_Unified_Audit.pdf", mime="application/pdf", use_container_width=True)
    with c2: st.download_button("📊 Download Technical PPTX", data=st.session_state['unified_pptx'], file_name=f"{client_inputs['customer_name']}_Unified_Roadmap.pptx", use_container_width=True)