"""Verify maturity templates load and render correctly against the actual context used by export.py:create_maturity_docx."""
from docxtpl import DocxTemplate
from docx.shared import Inches
import io, os

# Minimal structurally correct context dict - empty lists/strings for iterable placeholders
# Missing radar_chart InlineImage placeholder - templates may use {{ radar_chart }}
# We test that the template parses and renders without XML errors

for t in ['planet_it_maturity_assessment_template.docx', 'planet_it_maturity_assessment_template_v2.docx']:
    doc = DocxTemplate(t)
    tc = {
        'customer_name': 'TestCorp', 'consultant_name': 'TestConsultant',
        'industry': 'Technology', 'users': '250', 'endpoints': '300',
        'servers': '50', 'operating_systems': 'Windows/Linux', 'cloud_env': 'Azure',
        'in_house_team': 'Yes', 'compliance': 'ISO 27001', 'critical_infra': 'CRM, ERP',
        'mdr_provider': 'Sophos MDR', 'endpoint': 'Sophos Intercept X',
        'endpoint_posture': 'Managed', 'firewall': 'Sophos XG', 'identity': 'Entra ID P1',
        'email': 'M365 EOP', 'm365_license': 'Business Premium',
        'savviness': 'Proactive', 'pentest_status': 'Annual', 'vuln_scanning': 'Quarterly',
        'remote_access': 'VPN + Conditional Access', 'saas_backup': 'Yes',
        'ir_readiness': 'Plan exists, untested', 'mfa_status': 'Enforced',
        'patching': 'Automated via RMM', 'backups': 'Immutable, daily',
        'insurance': 'Cyber insurance in place', 'rto': '4 hours',
        'advanced_controls': 'EDR, SIEM',
        'exec_summary': 'Executive summary text here.',
        'matrix_mapping': 'Matrix mapping text here.',
        'cost_of_inaction': 'Cost of inaction text here.',
        'domains': [{'domain_name': 'Identity', 'score': 2, 'narrative': 'Good posture'}],
        'roadmap': [{'phase': 'Phase 1', 'key_deliverables': 'Deliverable A'}],
        'compliance_alignment': [],
        'success_metrics': 'Metric text',
        'engagement_cadence': 'Monthly',
        'consultant_discovery_guide': ['Question 1', 'Question 2'],
        'compliance_alignment_render': 'Compliance render text.',
        'partnership_outline': '',
        'threat_intelligence_context': '',
        'partnership_details': '',
        'partnership_links': '',
        'partnership_links_render': '',
        'monetary_cost_of_inaction': '£50,000',
        'cost_of_inaction_summary': 'Summary text.',
        'partnership_details_render': '',
        'threat_scenarios': 'Test Threat Scenario\n==============\nNarrative text here.',
    }
    try:
        doc.render(tc)
        print(t + ': render=OK')
    except Exception as e:
        print(t + ': render=FAILED - ' + str(e))
