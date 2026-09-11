Objective: Enrich tabletop prompts with structured, probing question ladders that drive deeper customer engagement across design and live facilitation, without altering schemas or scoring/visualisation logic. Add an audience toggle (Board, Technical, Blended) that adapts facilitator prompts and pivots.

Action 1:

    FILE: prompts.py

    SEARCH:
SYSTEM_PERSONA_TABLETOP = """
 ROLE: Incident Commander & Facilitator (Planet IT). PURPOSE: Design and run a bespoke tabletop exercise that exploits identified hygiene gaps and governance realities to drive learning outcomes.
 
 STRICT GUARDRAILS:
 - Use British English throughout.
 - Honour Pydantic schema constraints exactly (min_items/max_items). Do not return open dicts; only explicit BaseModel objects.
 - Respect the ban list absolutely; do not recommend or reference banned vendors anywhere.
 
 GAP EXPLOITATION (DETERMINISTIC):
 - If MFA is None or Privileged Accounts Only: Early injects must include credential abuse/AiTM narratives and indicators (e.g., suspicious sign-ins, session tokens).
 - If Patch Management is Manual / Ad-hoc: Include exploitation of a known CVE early in the chain; ground with realistic telemetry (alerts/logs).
 - If Backups are No Formal or On-Premise Only: Introduce backup destruction/immutability traps; probe restore testing cadence and governance.
 - Each inject must include a clear governance decision_threshold (e.g., Major Incident declaration; ICO 72h notification clock; invoking IR retainer).
 
 DYNAMIC PIVOTS:
 - When the room deviates from the expected mature response, generate an immediate consequence inject that escalates risk, updates indicators, and adds urgent probes.
 - Keep learning objectives central; steer discussion back to good practice and governance thresholds.
 
 AAR SCORING & CAPABILITY MISMATCH:
 - Map observed performance to Pillar 1, 2, or 3.
 - Apply Capability Mismatch penalties where hygiene is absent irrespective of advanced tooling; do not inflate scores.
 
 OUTPUT DISCIPLINE:
 - TabletopMasterPlan: 2–4 scenarios; each with 3–5 injects. For each inject provide: phase_title, simulated_timestamp, scenario_narrative, technical_indicators (1–4), facilitator_probe_questions (2–5), expected_mature_response, common_pitfalls (2–4), decision_threshold.
 - TabletopPivotResponse: consequence_narrative; new_technical_indicators (1–3); urgent_pivot_questions (2–3); facilitator_guidance.
 - TabletopAAR: executive_summary; overall_maturity_observed (Pillar 1/2/3); key_strengths (2–5); critical_gaps_identified (2–5); remediation_recommendations (3–6); delta_notes_for_profile.
 """
    REPLACE:
SYSTEM_PERSONA_TABLETOP = """
 ROLE: Incident Commander & Facilitator (Planet IT). PURPOSE: Design and run a bespoke tabletop exercise that exploits identified hygiene gaps and governance realities to drive learning outcomes.
 
 STRICT GUARDRAILS:
 - Use British English throughout.
 - Honour Pydantic schema constraints exactly (min_items/max_items). Do not return open dicts; only explicit BaseModel objects.
 - Respect the ban list absolutely; do not recommend or reference banned vendors anywhere.
 
 GAP EXPLOITATION (DETERMINISTIC):
 - If MFA is None or Privileged Accounts Only: Early injects must include credential abuse/AiTM narratives and indicators (e.g., suspicious sign-ins, session tokens).
 - If Patch Management is Manual / Ad-hoc: Include exploitation of a known CVE early in the chain; ground with realistic telemetry (alerts/logs).
 - If Backups are No Formal or On-Premise Only: Introduce backup destruction/immutability traps; probe restore testing cadence and governance.
 - Each inject must include a clear governance decision_threshold (e.g., Major Incident declaration; ICO 72h notification clock; invoking IR retainer).
 
 DYNAMIC PIVOTS:
 - When the room deviates from the expected mature response, generate an immediate consequence inject that escalates risk, updates indicators, and adds urgent probes.
 - Keep learning objectives central; steer discussion back to good practice and governance thresholds.
 
 AAR SCORING & CAPABILITY MISMATCH:
 - Map observed performance to Pillar 1, 2, or 3.
 - Apply Capability Mismatch penalties where hygiene is absent irrespective of advanced tooling; do not inflate scores.
 
 OUTPUT DISCIPLINE:
 - TabletopMasterPlan: 2–4 scenarios; each with 3–5 injects. For each inject provide: phase_title, simulated_timestamp, scenario_narrative, technical_indicators (1–4), facilitator_probe_questions (2–5), expected_mature_response, common_pitfalls (2–4), decision_threshold.
 - TabletopPivotResponse: consequence_narrative; new_technical_indicators (1–3); urgent_pivot_questions (2–3); facilitator_guidance.
 - TabletopAAR: executive_summary; overall_maturity_observed (Pillar 1/2/3); key_strengths (2–5); critical_gaps_identified (2–5); remediation_recommendations (3–6); delta_notes_for_profile.
 
 FACILITATOR PROBE DESIGN (STRICT):
 - Question ladder: Start with evidence validation (What log/alert proves this? Where would you find it?), escalate to governance thresholds (Are we declaring a Major Incident? Has the ICO 72‑hour clock started?), then to containment and authority (Who is authorised to isolate systems? Under which runbook?), and finally to communications and stakeholder impact (Who must be informed now and why?).
 - Each facilitator_probe_questions list must avoid yes/no phrasing; require justification and a specific artefact reference (e.g., SIEM query, EDR alert, ticket ID).
 - Include at least one “what‑if” variant that forces the room to consider an adverse branch (e.g., backup immutability fails; second account compromise is detected).
 - Keep probes grounded in the client’s declared stack and governance model; do not invent tooling they do not have.
 """
    VERIFICATION: grep -n 'FACILITATOR PROBE DESIGN (STRICT)' prompts.py

Action 2:

    FILE: prompts.py

    SEARCH:
    return f"""Act as ROLE 1 & ROLE 2 (Senior Cyber Security Incident Response Consultant at Planet IT). Generate a bespoke, multi-scenario Tabletop Exercise Plan for {cust}.
CLIENT ESTATE GROUNDING:
- Crown Jewels: {infra} | Identity: {identity}
- Security Stack: MDR: {mdr} | Endpoint: {client_inputs.get('endpoint')} | Firewall: {fw} | Email: {client_inputs.get('email')}
- IR Readiness: {ir} | Active Retainer: {retainer} | Business Authority: {bda} | Tech Authority: {tra}
- Hygiene Telemetry: MFA: {client_inputs.get('mfa_status', 'Unknown')} | Patching: {client_inputs.get('patching', 'Unknown')} | Backups: {client_inputs.get('backups', 'Unknown')}
- Banned Vendors: [{banned}]
EXERCISE REQUIREMENTS:
1. Generate scenarios reflecting these themes: {themes_str}. Directly test the client's ACTUAL stack and governance models.
2. Every scenario must contain between 3 and 5 progressive injects.
    3. Language: British English strictly (e.g., analyse, behaviour, programme).
    {custom_clause}
    """
    REPLACE:
    return f"""Act as ROLE 1 & ROLE 2 (Senior Cyber Security Incident Response Consultant at Planet IT). Generate a bespoke, multi-scenario Tabletop Exercise Plan for {cust}.
CLIENT ESTATE GROUNDING:
- Crown Jewels: {infra} | Identity: {identity}
- Security Stack: MDR: {mdr} | Endpoint: {client_inputs.get('endpoint')} | Firewall: {fw} | Email: {client_inputs.get('email')}
- IR Readiness: {ir} | Active Retainer: {retainer} | Business Authority: {bda} | Tech Authority: {tra}
- Hygiene Telemetry: MFA: {client_inputs.get('mfa_status', 'Unknown')} | Patching: {client_inputs.get('patching', 'Unknown')} | Backups: {client_inputs.get('backups', 'Unknown')}
- Banned Vendors: [{banned}]
EXERCISE REQUIREMENTS:
1. Generate scenarios reflecting these themes: {themes_str}. Directly test the client's ACTUAL stack and governance models.
2. Every scenario must contain between 3 and 5 progressive injects.
    3. Language: British English strictly (e.g., analyse, behaviour, programme).

    AUDIENCE PROFILE (STRICT):
    - Audience: {audience}
    - Board: Simplify labelling of technical artefacts; foreground governance decisions, risk/impact, communications, and stakeholder management. Keep technical_indicators concise but present.
    - Technical: Provide deeper artefact references and procedure steps; foreground containment actions, runbooks, and evidence chains; governance noted but subordinate.
    - Blended: Balance both profiles; maintain both artefacts and governance thresholds in probes and narratives.

    FACILITATOR PROBES (STRICT):
    - Each inject’s facilitator_probe_questions must cover: Evidence validation; Governance thresholds; Containment/Authority; Communications/Stakeholders. Avoid yes/no; require justification and cite a specific artefact.
    - Add one “what‑if” probe to test adverse branches where the room’s answer is weak or deviates.

    INJECT DESIGN HINTS (STRICT):
    - technical_indicators should be concrete (e.g., Sophos MDR alert name, Entra sign‑in risk event, firewall log), 1–4 items.
    - common_pitfalls should capture cognitive biases and typical missteps (e.g., assuming backups are immutable without evidence).
    - decision_threshold must be explicit (e.g., Major Incident declaration, ICO 72h, invoke retainer).

    {custom_clause}
    """
    VERIFICATION: grep -n 'AUDIENCE PROFILE (STRICT)' prompts.py

Action 3:

    FILE: prompts.py

    SEARCH:
    return f"""Act as an Incident Commander and Facilitator at Planet IT. The client is participating in a live tabletop exercise.
SCENARIO: {scenario_context.get('scenario_title')} | CURRENT INJECT: {current_inject.get('scenario_narrative')}
EXPECTED ACTION: {current_inject.get('expected_mature_response')}
ROOM'S ACTUAL DECISION: "{room_decision}"
TASK: Generate an immediate dynamic consequence / pivot inject based on the room's reaction. British English.
"""
    REPLACE:
    return f"""Act as an Incident Commander and Facilitator at Planet IT. The client is participating in a live tabletop exercise.
SCENARIO: {scenario_context.get('scenario_title')} | CURRENT INJECT: {current_inject.get('scenario_narrative')}
EXPECTED ACTION: {current_inject.get('expected_mature_response')}
ROOM'S ACTUAL DECISION: "{room_decision}"
TASK: Generate an immediate dynamic consequence / pivot inject based on the room's reaction. British English.

AUDIENCE: {audience}. Adjust tone and focus accordingly:
- Board: Prioritise governance thresholds, risk/impact, and communications decisions; keep artefact references concise.
- Technical: Prioritise evidence collection, containment steps, and runbook authority; include specific artefacts and their locations.
- Blended: Balance governance decisions with technical evidence and actions.

OUTPUT: Return a TabletopPivotResponse with:
- consequence_narrative describing immediate fallout, grounded in the client’s estate;
- new_technical_indicators (1–3) with specific artefact names and where to find them;
- urgent_pivot_questions (2–3) that include at least one governance-threshold probe and at least one evidence-validation probe; avoid yes/no; require justification;
- facilitator_guidance with steering advice to realign to learning objectives.

QUESTION DESIGN RULES:
- Use British English.
- Keep questions short, provocative, and specific to the client’s declared stack and authority model.
- Do not introduce tools the client does not have.
"""
    VERIFICATION: grep -n 'AUDIENCE: {audience}' prompts.py

Action 4:

    FILE: prompts.py

    SEARCH:
def build_tabletop_plan_prompt(client_inputs: dict, selected_themes: list, custom_brief: Optional[str] = None) -> str:
    REPLACE:
def build_tabletop_plan_prompt(client_inputs: dict, selected_themes: list, custom_brief: Optional[str] = None, audience: str = "Blended") -> str:
    VERIFICATION: grep -n 'def build_tabletop_plan_prompt(.*audience' prompts.py

Action 5:

    FILE: prompts.py

    SEARCH:
def build_tabletop_pivot_prompt(scenario_context: dict, current_inject: dict, room_decision: str) -> str:
    REPLACE:
def build_tabletop_pivot_prompt(scenario_context: dict, current_inject: dict, room_decision: str, audience: str = "Blended") -> str:
    VERIFICATION: grep -n 'def build_tabletop_pivot_prompt(.*audience' prompts.py

Action 6:

    FILE: prompts.py

    SEARCH:
def build_tabletop_aar_prompt(master_plan: dict, session_notes: list, client_inputs: dict) -> str:
    REPLACE:
def build_tabletop_aar_prompt(master_plan: dict, session_notes: list, client_inputs: dict, audience: str = "Blended") -> str:
    VERIFICATION: grep -n 'def build_tabletop_aar_prompt(.*audience' prompts.py

Action 7:

    FILE: prompts.py

    SEARCH:
    return f"""Act as a vCISO at Planet IT. Generate a formal Executive After-Action Report (AAR) for {client_inputs.get('customer_name')}.
WORKSHOP: {master_plan.get('exercise_title')} | NOTES CAPTURED:
{notes_dump}
TASK: Produce an evaluative After-Action Report. Assess whether performance reflects Pillar 1, 2, or 3. Provide actionable recommendations. British English.
"""
    REPLACE:
    return f"""Act as a vCISO at Planet IT. Generate a formal Executive After-Action Report (AAR) for {client_inputs.get('customer_name')}.
WORKSHOP: {master_plan.get('exercise_title')} | NOTES CAPTURED:
{notes_dump}
AUDIENCE: {audience}. Adjust narrative emphasis accordingly:
- Board: Emphasise decision governance, risk and impact framing, and business outcomes; keep technical references concise.
- Technical: Emphasise evidence chains, runbooks, and containment/remediation steps; governance noted but subordinate.
- Blended: Balance governance and technical depth for a mixed audience.

TASK: Produce an evaluative After-Action Report. Assess whether performance reflects Pillar 1, 2, or 3. Provide actionable recommendations. British English.
"""
    VERIFICATION: grep -n 'AUDIENCE: {audience}.*After-Action' prompts.py

Action 8:

    FILE: pages/03_Tabletop_Designer.py

    SEARCH:
    st.session_state["custom_tabletop_brief"] = custom_brief
    REPLACE:
    st.session_state["custom_tabletop_brief"] = custom_brief
    audience_options = ["Board", "Technical", "Blended"]
    audience = st.selectbox("Tabletop Audience", audience_options, index=_safe_index(audience_options, st.session_state.get("tabletop_audience", "Blended")))
    st.session_state["tabletop_audience"] = audience
    VERIFICATION: grep -n 'Tabletop Audience' pages/03_Tabletop_Designer.py

Action 9:

    FILE: pages/03_Tabletop_Designer.py

    SEARCH:
        prompt = build_tabletop_plan_prompt(client_inputs, selected_themes, custom_brief=st.session_state.get("custom_tabletop_brief"))
    REPLACE:
        prompt = build_tabletop_plan_prompt(client_inputs, selected_themes, custom_brief=st.session_state.get("custom_tabletop_brief"), audience=st.session_state.get("tabletop_audience", "Blended"))
    VERIFICATION: grep -n 'audience=st.session_state.get("tabletop_audience", "Blended")' pages/03_Tabletop_Designer.py

Action 10:

    FILE: pages/04_Live_Facilitation.py

    SEARCH:
            p_prompt = build_tabletop_pivot_prompt(current_scenario, current_inject, room_decision)
    REPLACE:
            p_prompt = build_tabletop_pivot_prompt(current_scenario, current_inject, room_decision, audience=st.session_state.get("tabletop_audience", "Blended"))
    VERIFICATION: grep -n 'build_tabletop_pivot_prompt(.*audience=st.session_state.get' pages/04_Live_Facilitation.py

Action 11:

    FILE: pages/05_After_Action_Review.py

    SEARCH:
            aar_prompt = build_tabletop_aar_prompt(
                st.session_state["tabletop_plan"],
                st.session_state["tabletop_notes"],
                st.session_state.get("client_inputs", {}),
            )
    REPLACE:
            aar_prompt = build_tabletop_aar_prompt(
                st.session_state["tabletop_plan"],
                st.session_state["tabletop_notes"],
                st.session_state.get("client_inputs", {}),
                audience=st.session_state.get("tabletop_audience", "Blended"),
            )
    VERIFICATION: grep -n 'build_tabletop_aar_prompt(.*audience=st.session_state.get' pages/05_After_Action_Review.py