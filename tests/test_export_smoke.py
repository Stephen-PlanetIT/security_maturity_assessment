from prompts import MaturityReport, DomainAssessment, RadarChartData
from export import create_maturity_docx

def _report():
    doms = [DomainAssessment(
        domain_name=f"D{i}",
        current_maturity_level='Pillar 2: Proactive Cybersecurity',
        current_state_analysis='Paragraph one. Paragraph two.',
        business_impact_narrative='Impact narrative.',
        critical_gaps=['G1','G2'],
        vendor_agnostic_quick_wins=['Q1','Q2'],
        recommended_solutions=['R1','R2','R3'],
        remediation_rationale='Why.',
        shared_responsibility='Split.',
        gap_remediation_steps=['S1','S2','S3']
    ) for i in range(15)]
    rc = RadarChartData(iam=2, privileged_access=2, endpoint=2, network=2, email=2, cloud=2, saas=2, data_security=2, secops=2, testing=2, supplier=2, resilience=2, culture=2, grc=2, ai=2)
    return MaturityReport(
        executive_summary='ES',
        executive_summary_actions=['A — B','C — D','E — F'],
        executive_summary_action_blocks=[
            {'heading':'H1','finding':'F','risk':'R','remediation_actions':['x','y','z','w']},
            {'heading':'H2','finding':'F','risk':'R','remediation_actions':['x','y','z','w']},
            {'heading':'H3','finding':'F','risk':'R','remediation_actions':['x','y','z','w']},
        ],
        radar_chart_data=rc,
        resiliency_matrix_mapping='Pillar 2: Proactive Cybersecurity',
        cost_of_inaction='COI',
        monetary_cost_of_inaction=None,
        partnership_details='',
        compliance_alignment=None,
        microsoft_healthchecks_recommendations='',
        domain_assessments=doms,
        phased_roadmap=[{'phase_title':'Phase 1: Foundational Hygiene','timeline':'0-3','primary_objective':'o','key_deliverables':['k1','k2','k3'], 'estimated_effort':'e','milestones':['m1','m2','m3'],'resource_requirements':'r','business_value_delivered':'v'},
                        {'phase_title':'Phase 2: Active Managed Defence','timeline':'3-9','primary_objective':'o','key_deliverables':['k1','k2','k3'], 'estimated_effort':'e','milestones':['m1','m2','m3'],'resource_requirements':'r','business_value_delivered':'v'},
                        {'phase_title':'Phase 3: Adaptive Governance & Resilience','timeline':'10-18+','primary_objective':'o','key_deliverables':['k1','k2','k3'], 'estimated_effort':'e','milestones':['m1','m2','m3'],'resource_requirements':'r','business_value_delivered':'v'}],
        success_metrics=['s1','s2','s3'],
        engagement_cadence=['c1','c2','c3'],
        consultant_discovery_guide=['q1','q2','q3','q4','q5']
    )

def test_docx_succeeds_with_minimal_inputs():
    r = _report()
    ci = {'customer_name':'X','industry':'Tech','users':1}
    out = create_maturity_docx(ci, r)
    assert isinstance(out, (bytes, bytearray)) and len(out) > 1000
