# app.py
import streamlit as st
import random
import plotly.graph_objects as go
from openai import AzureOpenAI

from data import ATTACK_VECTORS, SIMULATED_OSINT
from prompts import SYSTEM_PERSONA, build_scenario_prompt, build_vciso_prompt, ScenarioReport, UnifiedEngagementReport 
from export import create_pdf, create_pptx, create_vciso_pdf, create_vciso_pptx

st.set_page_config(page_title="Planet IT Strategic Advisory Platform", page_icon="🪐", layout="wide")

keys_to_init = ['vciso_obj', 'vciso_pdf', 'vciso_pptx', 'scenario_obj', 'mdr_case', 'pdf_bytes', 'pptx_bytes', 'recs', 'report_ready', 'selected_mode']
for key in keys_to_init:
    if key not in st.session_state:
        st.session_state[key] = None
if 'report_ready' not in st.session_state:
    st.session_state['report_ready'] = False

def return_to_dashboard():
    st.session_state['selected_mode'] = None
    st.session_state['report_ready'] = False
    st.session_state['vciso_obj'] = None
    st.session_state['scenario_obj'] = None

class CyberScenarioGenerator:
    def __init__(self, api_key, endpoint, deployment, api_version):
        self.deployment = deployment
        self.client = AzureOpenAI(api_key=api_key, api_version=api_version, azure_endpoint=endpoint) if api_key else None
    
    def fetch_osint(self, vendor):
        options = SIMULATED_OSINT.get(vendor, [])
        return random.choice(options) if options else ""

    def generate_recommendations(self, inputs):
        recs = ["🪐 **PLANET IT STRATEGIC ROADMAP & ADVISORY**"]
        
        # --- Advisory & Services ---
        if inputs.get('last_tabletop') in ["Never", "Over 12 months ago"]: 
            recs.append("• [Secureworks Incident Response Preparedness]: Update your IR plan and test it against ransomware scenarios.")
        if inputs.get('insurance_status') == "Policy Exists (Untested)": 
            recs.append("• **Insurance Readiness Assessment:** Map your current controls against your cyber insurance policy to ensure payout in a breach.")
        
        recs.append("\n⚙️ **PLANET IT RECOMMENDED ARCHITECTURE**")
        
        # --- The Core: Planet IT Managed SOC ---
        if inputs.get('mdr_provider', 'None') != "Sophos MDR": 
            recs.append("• **[Planet IT Managed SOC]:** A vendor-agnostic, 24/7 threat hunting service to unify your telemetry and guarantee response times.")

        # --- Email Security Logic (Mimecast vs Sophos) ---
        high_reg_industries = ["Finance", "Healthcare", "Education"]
        if inputs.get('industry') in high_reg_industries or inputs.get('email', 'None') == "Mimecast":
            recs.append("• **[Mimecast Advanced Email & Collaboration]:** Recommended due to your industry's strict compliance, eDiscovery, and archiving requirements.")
        else:
            recs.append("• **[Sophos Email Security]:** Integrate your email telemetry directly into the Planet IT SOC for consolidated visibility.")

        # --- Perimeter & Edge Logic (Fortinet vs Sophos) ---
        if int(inputs.get('users', 0)) > 1000 or inputs.get('firewall') == "Fortinet":
            recs.append("• **[Fortinet FortiGate Secure SD-WAN]:** Maintain and optimise your enterprise-grade edge routing and Zero Trust Network Access (ZTNA).")
        else:
            recs.append("• **[Sophos Firewall]:** Deploy to leverage 'Synchronized Security', allowing your firewalls to isolate compromised endpoints automatically.")

        # --- Cloud & Identity ---
        if inputs.get('workspace_license') in ["M365 E3", "M365 E5", "M365 Business Premium"]:
            recs.append(f"• **[Microsoft Defender & Entra ID Optimization]:** You are paying for {inputs.get('workspace_license')}. Engage Planet IT to properly configure conditional access and identity protection.")
        
        return recs

    def call_llm_structured(self, prompt, response_model):
        if not self.client: return None
        try:
            response = self.client.beta.chat.completions.parse(
                model=self.deployment, messages=[{"role": "system", "content": SYSTEM_PERSONA}, {"role": "user", "content": prompt}],
                response_format=response_model, temperature=0.7
            )
            return response.choices[0].message.parsed
        except Exception as e:
            st.error(f"LLM Error: {e}")
            return None

try:
    az_key = st.secrets["AZURE_OPENAI_API_KEY"]
    az_endpoint = st.secrets["AZURE_OPENAI_ENDPOINT"]
    az_deployment = st.secrets["AZURE_OPENAI_DEPLOYMENT"]
    az_api_version = st.secrets.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
except Exception:
    az_key, az_endpoint, az_deployment, az_api_version = None, None, None, None

app_engine = CyberScenarioGenerator(api_key=az_key, endpoint=az_endpoint, deployment=az_deployment, api_version=az_api_version)

with st.sidebar:
    st.title("🪐 Planet IT Menu")
    if st.session_state['selected_mode'] is not None:
        st.button("🏠 Return to Dashboard", on_click=return_to_dashboard, use_container_width=True)
    st.divider()
    st.caption("Planet IT Strategic Advisory Engine")

if st.session_state['selected_mode'] is None:
    st.title("Planet IT Advisory Platform")
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.markdown("### 📈 vCISO Strategic Assessment")
            if st.button("Launch vCISO Assessment ➔", type="primary", use_container_width=True):
                st.session_state['selected_mode'] = "📈 vCISO Assessment"
                st.rerun()
    with col2:
        with st.container(border=True):
            st.markdown("### 🔥 Tactical Threat Simulator")
            if st.button("Launch Threat Simulator ➔", type="primary", use_container_width=True):
                st.session_state['selected_mode'] = "🔥 Threat Simulator"
                st.rerun()

else:
    app_mode = st.session_state['selected_mode']
    st.title(app_mode)
    
    client_inputs = {"savviness": "Tier 2: Basic Compliance"}

    with st.expander("⚙️ Client Discovery & Estate Configuration", expanded=not st.session_state['report_ready']):
        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True):
                st.subheader("🏢 Engagement Profile")
                client_inputs["customer_name"] = st.text_input("Customer Name", "Acme Corp")
                client_inputs["industry"] = st.selectbox("Industry Vertical", ["Manufacturing", "Finance", "Healthcare", "Retail", "Technology", "Education"])
                client_inputs["users"] = st.number_input("Number of Users", min_value=1, value=500)
                client_inputs["critical_infra"] = st.text_input("Crown Jewels", "ERP System")
        with col2:
            with st.container(border=True):
                st.subheader("💻 Core Technology Stack")
                c1, c2 = st.columns(2)
                with c1:
                    client_inputs["mdr_provider"] = st.selectbox("Current MDR", ["None", "Sophos MDR", "CrowdStrike", "Other"])
                    client_inputs["endpoint"] = st.selectbox("Endpoint Protection", ["Sophos", "Microsoft Defender", "Other"])
                    client_inputs["firewall"] = st.selectbox("Firewall", ["Fortinet", "Palo Alto", "Sophos", "Other"])
                with c2:
                    client_inputs["identity"] = st.selectbox("Identity Provider", ["Microsoft Entra ID (Azure AD)", "Okta", "On-Prem AD"])
                    client_inputs["workspace_license"] = st.selectbox("Workspace Licensing", ["None / On-Prem", "M365 Business Premium", "M365 E3", "M365 E5", "Google Workspace Standard", "Google Workspace Enterprise"])
                    client_inputs["cloud_env"] = st.selectbox("Cloud Infrastructure", ["AWS", "Microsoft Azure", "GCP", "Multi-Cloud", "None (On-Prem)"])

        if app_mode == "📈 vCISO Assessment":
            col3, col4 = st.columns(2)
            with col3:
                with st.container(border=True):
                    st.subheader("💰 Financials & Resourcing")
                    client_inputs["revenue_band"] = st.selectbox("Est. Annual Revenue", ["< £5M", "£5M - £20M", "£20M - £100M", "£100M+"])
                    client_inputs["downtime_cost"] = st.selectbox("Est. Downtime Cost/Hr", ["< £10k", "£10k - £50k", "£50k+"])
                    client_inputs["security_ftes"] = st.selectbox("Dedicated Security FTEs", ["0 (IT wears all hats)", "1-2 (Small Team)", "3+ (Dedicated SecOps)"])
                    client_inputs["budget_trend"] = st.selectbox("IT Budget Trend", ["Decreasing", "Flat", "Increasing"])
            with col4:
                with st.container(border=True):
                    st.subheader("☁️ Modern Attack Surface")
                    client_inputs["saas_sprawl"] = st.selectbox("SaaS Application Sprawl", ["< 20 Core Apps", "20 - 50 Apps", "50+ Apps (Unmanaged)"])
                    client_inputs["identity_controls"] = st.selectbox("Identity Controls", ["Basic Passwords", "MFA (SMS/App)", "Conditional Access & MFA", "JIT / PIM"])
                    client_inputs["data_location"] = st.selectbox("Data Location / Sovereignty", ["UK Only", "EU/UK", "Global / Unknown"])
                    
            col5, col6 = st.columns(2)
            with col5:
                with st.container(border=True):
                    st.subheader("🧮 Security Culture & Hygiene")
                    client_inputs["phishing_frequency"] = st.selectbox("Phishing Simulations", ["Never", "Annually", "Monthly / Quarterly"])
                    client_inputs["training_maturity"] = st.selectbox("Security Training", ["None", "Annual Compliance Video", "Continuous with active coaching"])
                    client_inputs["admin_rights"] = st.selectbox("Endpoint Privileges", ["Most users are Local Admins", "Only IT/Devs are Local Admins", "Zero Trust (No Local Admins/LAPS)"])
            with col6:
                with st.container(border=True):
                    st.subheader("⚖️ GRC, Compliance & Resilience")
                    target_compliance = st.multiselect("Target Frameworks", ["ISO27001", "NIS2 Directive", "PCI:DSS", "Cyber Essentials Plus"])
                    client_inputs["target_compliance"] = ", ".join(target_compliance) if target_compliance else "None specified"
                    client_inputs["current_cert"] = st.selectbox("Current Baseline Cert", ["None", "Cyber Essentials (CE)", "ISO27001"])
                    client_inputs["insurance_status"] = st.selectbox("Cyber Insurance", ["None", "Policy Exists (Untested)", "Policy mapped to active IR Plan"])
                    client_inputs["last_tabletop"] = st.selectbox("Tabletop Exercise", ["Never", "Over 12 months ago", "Within last 12 months"])
                    client_inputs["ir_plan_review"] = st.selectbox("IR Plan Review", ["No formal plan", "Over 12 months ago", "Within last 12 months"])

        elif app_mode == "🔥 Threat Simulator":
            client_inputs["custom_scenario"] = st.text_input("Custom Threat Scenario Override (Optional)", placeholder="e.g., Ransomware via MSP")

        generate_btn = st.button(f"🚀 Generate {app_mode.split()[1]}", type="primary", use_container_width=True)

    if generate_btn:
        st.session_state['client_inputs'] = client_inputs
        st.session_state['report_ready'] = False 
        
        with st.spinner("Analysing estate and generating business insights..."):
            if app_mode == "📈 vCISO Assessment":
                unified_obj = app_engine.call_llm_structured(build_vciso_prompt(client_inputs), UnifiedEngagementReport)
                if unified_obj:
                    st.session_state['vciso_obj'] = unified_obj
                    st.session_state['vciso_pdf'] = create_vciso_pdf(client_inputs, unified_obj.executive_pdf_content)
                    st.session_state['vciso_pptx'] = create_vciso_pptx(client_inputs, unified_obj.technical_pptx_content, unified_obj.executive_pdf_content)
                    st.session_state['report_ready'] = True
                    
            elif app_mode == "🔥 Threat Simulator":
                scenario_obj = app_engine.call_llm_structured(build_scenario_prompt(client_inputs, "", random.choice(ATTACK_VECTORS), client_inputs.get("custom_scenario", "")), ScenarioReport)
                if scenario_obj:
                    st.session_state['scenario_obj'] = scenario_obj
                    st.session_state['mdr_case'] = scenario_obj.mdr_case_log
                    st.session_state['recs'] = app_engine.generate_recommendations(client_inputs)
                    st.session_state['pdf_bytes'] = create_pdf(client_inputs, scenario_obj, st.session_state['recs'], st.session_state['mdr_case'])
                    st.session_state['pptx_bytes'] = create_pptx(client_inputs, scenario_obj, st.session_state['recs'], st.session_state['mdr_case'])
                    st.session_state['report_ready'] = True
        st.rerun()

    if st.session_state['report_ready']:
        if app_mode == "📈 vCISO Assessment" and st.session_state['vciso_obj']:
            exec_report = st.session_state['vciso_obj'].executive_pdf_content
            tech_report = st.session_state['vciso_obj'].technical_pptx_content
            
            tab_exec, tab_tech = st.tabs(["👔 Boardroom Summary (PDF)", "⚙️ Operational Execution (PPTX)"])
            
            with tab_exec:
                st.success("### 📊 Financial & Strategic Overview")
                f1, f2, f3 = st.columns(3)
                with f1: st.metric("Estimated Financial Exposure", exec_report.financial_analysis.estimated_financial_exposure)
                with f2: st.metric("Peer Benchmark Target", "Industry Avg")
                with f3: st.metric("Immediate Budget Ask", exec_report.financial_analysis.immediate_budgetary_ask)
                
                st.info(f"**Peer Benchmarking:** {exec_report.financial_analysis.peer_benchmark_statement}")
                
                st.markdown("### 🚨 Top 3 Business Risks")
                for risk in exec_report.top_3_business_risks: st.markdown(f"- {risk}")
                
                st.divider()
                st.subheader("💡 License Security Optimization")
                st.info(exec_report.executive_prose.license_security_analysis)

                st.divider()
                st.subheader("Domain Gap Analysis")
                for domain in exec_report.domain_assessments:
                    with st.expander(f"{domain.domain_name} — Score: {domain.numeric_maturity_score}/5.0", expanded=False):
                        st.markdown(f"**Current State:** {domain.current_state_analysis}")
                        st.markdown(f"**Risk Exposure Context:** {getattr(domain, 'risk_exposure_summary', 'Data unavailable.')}")
                        
                        st.markdown("**🚨 Real-World Risk Scenario:**")
                        st.error(getattr(domain, 'real_world_risk_scenario', 'Data unavailable.'))
                        
                        st.markdown("**Recommended Solutions:**")
                        for sol in domain.recommended_solutions: 
                            if isinstance(sol, str): 
                                st.markdown(f"- 🛡️ {sol}")
                            else: 
                                st.markdown(f"- 🛡️ **{sol.solution_name}**: {sol.description}")
                                st.markdown(f"   *Rationale*: {getattr(sol, 'strategic_rationale', '')}")
                            
            with tab_tech:
                st.warning(f"**Operational Reality Check:**\n{tech_report.operational_reality_statement}")
                st.subheader("⚡ High-Impact Quick Wins")
                for win in tech_report.high_impact_quick_wins:
                    st.markdown(f"- **{win.effort_vs_impact}**: {win.task}")
                
                st.divider()
                st.subheader("Target Operating Model")
                st.success(tech_report.target_operating_model)
                st.subheader("Engineering Phases")
                for phase in tech_report.implementation_phases:
                    st.markdown(f"#### {phase.phase_name}")
                    for task in phase.engineering_tasks: st.markdown(f"- {task}")
                        
            st.divider()
            col1, col2 = st.columns(2)
            with col1: st.download_button("📄 Download PDF (Executive Tear-Sheet)", data=st.session_state['vciso_pdf'], file_name=f"{client_inputs['customer_name']}_ExecSummary.pdf", mime="application/pdf", use_container_width=True)
            with col2: st.download_button("📊 Download PPTX (Technical Roadmap)", data=st.session_state['vciso_pptx'], file_name=f"{client_inputs['customer_name']}_TechRoadmap.pptx", use_container_width=True)

        elif app_mode == "🔥 Threat Simulator" and st.session_state['scenario_obj']:
            st.write("Threat Simulator Ready. Download below.")
            st.download_button("📄 Download PDF Report", data=st.session_state['pdf_bytes'], file_name=f"MDR.pdf", mime="application/pdf")