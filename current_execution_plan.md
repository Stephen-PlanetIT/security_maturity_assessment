Objective: Persist and propagate immediate consequence injects into AAR prompts and DOCX exports.

Action 1:

    FILE: pages/04_Live_Facilitation.py

    SEARCH: 
            if pivot:
                try:
                    st.warning(f"**CONSEQUENCE:** {pivot.consequence_narrative}")
                    st.markdown("**Urgent Probes:**")
                    for q in pivot.urgent_pivot_questions:
                        st.write(f"- {q}")
                except Exception:
                    # Fallback if pivot is dict-like
                    st.warning("**CONSEQUENCE:** See generated pivot above.")

    REPLACE: 
            if pivot:
                try:
                    st.warning(f"**CONSEQUENCE:** {pivot.consequence_narrative}")
                    st.markdown("**Urgent Probes:**")
                    for q in pivot.urgent_pivot_questions:
                        st.write(f"- {q}")
                    # Persist immediate inject for AAR/export
                    try:
                        st.session_state.setdefault("immediate_injects", [])
                        st.session_state["immediate_injects"].append({
                            "scenario_index": s_idx,
                            "inject_index": i_idx,
                            "scenario_title": current_scenario.get("scenario_title"),
                            "phase_title": current_inject.get("phase_title"),
                            "consequence_narrative": pivot.consequence_narrative,
                            "new_technical_indicators": getattr(pivot, "new_technical_indicators", []),
                            "urgent_pivot_questions": getattr(pivot, "urgent_pivot_questions", []),
                            "facilitator_guidance": getattr(pivot, "facilitator_guidance", "")
                        })
                    except Exception:
                        pass
                except Exception:
                    # Fallback if pivot is dict-like
                    st.warning("**CONSEQUENCE:** See generated pivot above.")

    VERIFICATION: python -c "compile(open('pages/04_Live_Facilitation.py').read(), 'pages/04_Live_Facilitation.py', 'exec'); print('OK')"

Action 2:

    FILE: pages/04_Live_Facilitation.py

    SEARCH:
                 saved_path = persist_tabletop_session(
                     st.session_state.get(\"tabletop_plan\", {}),
                     st.session_state.get(\"tabletop_notes\", []),
                     st.session_state.get(\"client_inputs\", {}),
                     st.session_state.get(\"tabletop_audience\", \"Blended\"),
                 )

    REPLACE:
                 saved_path = persist_tabletop_session(
                     st.session_state.get("tabletop_plan", {}),
                     st.session_state.get("tabletop_notes", []),
                     st.session_state.get("client_inputs", {}),
                     st.session_state.get("tabletop_audience", "Blended"),
                     st.session_state.get("immediate_injects", []),
                 )

    VERIFICATION: python -c "compile(open('pages/04_Live_Facilitation.py').read(), 'pages/04_Live_Facilitation.py', 'exec'); print('OK')"

Action 3:

    FILE: consultation_helpers.py

    SEARCH:
def persist_tabletop_session(
    plan: Dict[str, Any],
    notes: List[Dict[str, Any]],
    client_inputs: Dict[str, Any] | None = None,
    audience: str | None = None,
) -> str | None:

    REPLACE:
def persist_tabletop_session(
    plan: Dict[str, Any],
    notes: List[Dict[str, Any]],
    client_inputs: Dict[str, Any] | None = None,
    audience: str | None = None,
    immediate_injects: List[Dict[str, Any]] | None = None,
) -> str | None:

    VERIFICATION: python -c "import consultation_helpers; print('OK')"

Action 4:

    FILE: consultation_helpers.py

    SEARCH:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "saved_at": datetime.datetime.utcnow().isoformat() + "Z",
            "audience": (audience or ""),
            "plan": sanitise_nested(plan or {}),
            "notes": sanitise_nested(notes or []),
            "client_inputs": sanitise_nested(client_inputs or {}),
        }

    REPLACE:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "saved_at": datetime.datetime.utcnow().isoformat() + "Z",
            "audience": (audience or ""),
            "plan": sanitise_nested(plan or {}),
            "notes": sanitise_nested(notes or []),
            "immediate_injects": sanitise_nested(immediate_injects or []),
            "client_inputs": sanitise_nested(client_inputs or {}),
        }

    VERIFICATION: python -c "import consultation_helpers; print('OK')"

Action 5:

    FILE: pages/05_After_Action_Review.py

    SEARCH:
            st.session_state["tabletop_plan"] = saved.get("plan", {})
            st.session_state["tabletop_notes"] = saved.get("notes", [])
            st.session_state["client_inputs"] = saved.get("client_inputs", {})
            st.session_state["tabletop_audience"] = saved.get("audience", "Blended")

    REPLACE:
            st.session_state["tabletop_plan"] = saved.get("plan", {})
            st.session_state["tabletop_notes"] = saved.get("notes", [])
            st.session_state["client_inputs"] = saved.get("client_inputs", {})
            st.session_state["tabletop_audience"] = saved.get("audience", "Blended")
            st.session_state["immediate_injects"] = saved.get("immediate_injects", [])

    VERIFICATION: python -c "compile(open('pages/05_After_Action_Review.py').read(), 'pages/05_After_Action_Review.py', 'exec'); print('OK')"

Action 6:

    FILE: pages/05_After_Action_Review.py

    SEARCH:
            aar_prompt = build_tabletop_aar_prompt(
                st.session_state["tabletop_plan"],
                st.session_state["tabletop_notes"],
                st.session_state.get("client_inputs", {}),
                audience=st.session_state.get("tabletop_audience", "Blended"),
            )

    REPLACE:
            aar_prompt = build_tabletop_aar_prompt(
                st.session_state["tabletop_plan"],
                st.session_state["tabletop_notes"],
                st.session_state.get("client_inputs", {}),
                audience=st.session_state.get("tabletop_audience", "Blended"),
                immediate_injects=st.session_state.get("immediate_injects", []),
            )

    VERIFICATION: python -c "compile(open('pages/05_After_Action_Review.py').read(), 'pages/05_After_Action_Review.py', 'exec'); print('OK')"

Action 7:

    FILE: pages/05_After_Action_Review.py

    SEARCH:
            aar_docx = create_tabletop_aar_docx(
                st.session_state.get("tabletop_plan", {}),
                st.session_state.get("tabletop_notes", []),
                aar
            )

    REPLACE:
            aar_docx = create_tabletop_aar_docx(
                st.session_state.get("tabletop_plan", {}),
                st.session_state.get("tabletop_notes", []),
                aar,
                st.session_state.get("immediate_injects", []),
            )

    VERIFICATION: python -c "compile(open('pages/05_After_Action_Review.py').read(), 'pages/05_After_Action_Review.py', 'exec'); print('OK')"

Action 8:

    FILE: prompts.py

    SEARCH:
def build_tabletop_aar_prompt(master_plan: dict, session_notes: list, client_inputs: dict, audience: str = "Blended") -> str:
    notes_dump = "\\n".join([f"- Phase: {n['phase']} | Action: {n['decision']} | Facilitator Observations: {n['notes']}" for n in session_notes])
    return f"""Act as a vCISO at Planet IT. Generate a formal Executive After-Action Report (AAR) for {client_inputs.get('customer_name')}.
WORKSHOP: {master_plan.get('exercise_title')} | NOTES CAPTURED:
{notes_dump}
AUDIENCE: {audience}. Adjust narrative emphasis accordingly:
- Board: Emphasise decision governance, risk and impact framing, and business outcomes; keep technical references concise.
- Technical: Emphasise evidence chains, runbooks, and containment/remediation steps; governance noted but subordinate.
- Blended: Balance governance and technical depth for a mixed audience.

    TASK: Produce an evaluative After-Action Report. Assess whether performance reflects Pillar 1, 2, or 3. Provide actionable recommendations.
    STRICT OUTPUT RULES:
    - Use British English throughout.
    - Populate all exercise-level fields exactly as defined (date/time as ISO strings).
    - Observations must be returned as Observation objects: key_strengths, critical_gaps_identified.
    - Do NOT append rationales to gap summaries; populate Observation.rationale instead.
    - Provide capability_assessments with per-capability maturity and rationale.
    - Return improvement_actions as ImprovementAction objects (replacing flat remediation lists); include priority, owner, target_date/timeframe and closure_evidence.
    - Populate decisions_and_open_items with DecisionRecord entries as applicable.
    - Populate participant_feedback and facilitator_observations (narrative) where available.
    - Populate follow_up_assurance with validation/approval status and retest arrangements.
    - Provide profile_changes if any deltas versus prior exercises are asserted.
    - Honour min_items/max_items constraints for all List fields.
    - Keep recommendations actionable and proportional; avoid vendor lock-in language; align with observed governance thresholds.
"""

    REPLACE:
def build_tabletop_aar_prompt(master_plan: dict, session_notes: list, client_inputs: dict, audience: str = "Blended", immediate_injects: list | None = None) -> str:
    notes_dump = "\\n".join([f"- Phase: {n['phase']} | Action: {n['decision']} | Facilitator Observations: {n['notes']}" for n in session_notes])
    inj_dump = ""
    try:
        if immediate_injects:
            lines = []
            for ii in immediate_injects:
                try:
                    s = ii.get("scenario_title", "")
                    p = ii.get("phase_title", "")
                    cn = ii.get("consequence_narrative", "")
                    qs = ii.get("urgent_pivot_questions", []) or []
                    lines.append(f"- Scenario: {s} | Inject: {p} | Consequence: {cn} | Urgent probes: " + "; ".join([str(x) for x in qs]))
                except Exception:
                    continue
            inj_dump = "\\n".join(lines)
    except Exception:
        inj_dump = ""
    return f"""Act as a vCISO at Planet IT. Generate a formal Executive After-Action Report (AAR) for {client_inputs.get('customer_name')}.
WORKSHOP: {master_plan.get('exercise_title')} | NOTES CAPTURED:
{notes_dump}
IMMEDIATE CONSEQUENCE INJECTS:
{inj_dump}
AUDIENCE: {audience}. Adjust narrative emphasis accordingly:
- Board: Emphasise decision governance, risk and impact framing, and business outcomes; keep technical references concise.
- Technical: Emphasise evidence chains, runbooks, and containment/remediation steps; governance noted but subordinate.
- Blended: Balance governance and technical depth for a mixed audience.

    TASK: Produce an evaluative After-Action Report. Assess whether performance reflects Pillar 1, 2, or 3. Provide actionable recommendations.
    STRICT OUTPUT RULES:
    - Use British English throughout.
    - Populate all exercise-level fields exactly as defined (date/time as ISO strings).
    - Observations must be returned as Observation objects: key_strengths, critical_gaps_identified.
    - Do NOT append rationales to gap summaries; populate Observation.rationale instead.
    - Provide capability_assessments with per-capability maturity and rationale.
    - Return improvement_actions as ImprovementAction objects (replacing flat remediation lists); include priority, owner, target_date/timeframe and closure_evidence.
    - Populate decisions_and_open_items with DecisionRecord entries as applicable.
    - Populate participant_feedback and facilitator_observations (narrative) where available.
    - Populate follow_up_assurance with validation/approval status and retest arrangements.
    - Provide profile_changes if any deltas versus prior exercises are asserted.
    - Honour min_items/max_items constraints for all List fields.
    - Keep recommendations actionable and proportional; avoid vendor lock-in language; align with observed governance thresholds.
"""

    VERIFICATION: python -c "from prompts import build_tabletop_aar_prompt; print('OK')"

Action 9:

    FILE: export.py

    SEARCH:
def create_tabletop_aar_docx(master_plan: dict, session_notes: list, aar_obj) -> bytes:

    REPLACE:
def create_tabletop_aar_docx(master_plan: dict, session_notes: list, aar_obj, immediate_injects: list | None = None) -> bytes:

    VERIFICATION: python -c "import export; print('OK')"

Action 10:

    FILE: export.py

    SEARCH:
    # Lessons learned derived deterministically from session notes
    lessons_learned = []
    if isinstance(session_notes, list):
        for n in session_notes:
            try:
                phase = (n.get("phase", "") if isinstance(n, dict) else "")
                decision = (n.get("decision", "") if isinstance(n, dict) else "")
                notes = (n.get("notes", "") if isinstance(n, dict) else "")
                line = " | ".join([x for x in [phase, decision, notes] if str(x).strip()])
                if line:
                    lessons_learned.append(clean_text(line))
            except Exception:
                continue

    REPLACE:
    # Lessons learned derived deterministically from session notes + immediate injects
    lessons_learned = []
    if isinstance(session_notes, list):
        for n in session_notes:
            try:
                phase = (n.get("phase", "") if isinstance(n, dict) else "")
                decision = (n.get("decision", "") if isinstance(n, dict) else "")
                notes = (n.get("notes", "") if isinstance(n, dict) else "")
                line = " | ".join([x for x in [phase, decision, notes] if str(x).strip()])
                if line:
                    lessons_learned.append(clean_text(line))
            except Exception:
                continue
    # Append immediate injects to ensure presence in export even if template lacks placeholders
    try:
        if isinstance(immediate_injects, list):
            for ii in immediate_injects:
                try:
                    s = ii.get("scenario_title", "")
                    p = ii.get("phase_title", "")
                    cn = ii.get("consequence_narrative", "")
                    qs = ii.get("urgent_pivot_questions", []) or []
                    line = "[IMMEDIATE INJECT] " + " | ".join([x for x in [s, p, cn, "; ".join([str(x) for x in qs])] if str(x).strip()])
                    if line:
                        lessons_learned.append(clean_text(line))
                except Exception:
                    continue
    except Exception:
        pass

    VERIFICATION: python -c "import export; print('OK')"

Action 11:

    FILE: pages/05_After_Action_Review.py

    SEARCH:
    st.write(getattr(aar, "executive_summary", ""))

    REPLACE:
    st.write(getattr(aar, "executive_summary", ""))
    with st.expander("Client Feeders", expanded=False):
        try:
            client = getattr(aar, "customer_name", "") or ""
            ex_title = getattr(aar, "exercise_title", "") or ""
            ex_id = getattr(aar, "exercise_id", "") or ""
            ex_date = getattr(aar, "exercise_date", "") or ""
            stime = getattr(aar, "start_time", "") or ""
            etime = getattr(aar, "end_time", "") or ""
            loc = getattr(aar, "exercise_location", "") or ""
            delivery = getattr(aar, "delivery_mode", "") or ""
            audience = getattr(aar, "audience_profile", "") or ""
            report_status = getattr(aar, "report_status", "") or ""
            report_version = getattr(aar, "report_version", "") or ""
            info_class = getattr(aar, "information_classification", "") or ""
            feeders = [
                f"Client\t{client}",
                f"Exercise\t{ex_title} ({ex_id})",
                f"Date, time and location\t{ex_date} | {stime}–{etime} | {loc}",
                f"Delivery and audience\t{delivery} | {audience}",
            ]
            # Facilitators
            try:
                facs = []
                for p in getattr(aar, "facilitators", []) or []:
                    try:
                        name = getattr(p, "name", None) or (p.get("name") if isinstance(p, dict) else "")
                        role = getattr(p, "role", None) or (p.get("role") if isinstance(p, dict) else "")
                        func = getattr(p, "function", None) or (p.get("function") if isinstance(p, dict) else "")
                        facs.append(f"{name} — {role} ({func})")
                    except Exception:
                        continue
                if facs:
                    feeders.append("Facilitators\t" + "; ".join(facs))
            except Exception:
                pass
            # Functions represented
            try:
                funcs = []
                for p in getattr(aar, "participants", []) or []:
                    try:
                        func = getattr(p, "function", None) or (p.get("function") if isinstance(p, dict) else "")
                        if func:
                            funcs.append(func)
                    except Exception:
                        continue
                if funcs:
                    feeders.append("Functions represented\t" + ", ".join(funcs))
            except Exception:
                pass
            # Scenarios exercised
            try:
                scns = []
                for s in getattr(aar, "scenarios", []) or []:
                    try:
                        sid = getattr(s, "id", None) or (s.get("id") if isinstance(s, dict) else "")
                        title = getattr(s, "title", None) or (s.get("title") if isinstance(s, dict) else "")
                        if sid or title:
                            scns.append(f"{sid} — {title}" if sid and title else (sid or title))
                    except Exception:
                        continue
                if scns:
                    feeders.append("Scenarios exercised\t" + "; ".join(scns))
            except Exception:
                pass
            feeders.append(f"Overall maturity observed\t{getattr(aar, 'overall_maturity_observed', 'Unknown')}")
            if report_status or report_version or info_class:
                feeders.append(f"Report control\t{report_status} | Version {report_version} | {info_class}")
            st.code("\\n".join(feeders), language="text")
        except Exception:
            st.info("Client feeder fields are unavailable or incomplete in the AAR object.")

    VERIFICATION: python -c "compile(open('pages/05_After_Action_Review.py').read(), 'pages/05_After_Action_Review.py', 'exec'); print('OK')"

Action 12:

    FILE: export.py

    SEARCH:
        try:
            ctx.update({
                "improvement_actions": improvement_actions,
                "capability_assessments": capability_assessments,
                "decisions_and_open_items": decisions_open,
                "participant_feedback": participant_feedback or ctx.get("participants_feedback", []),
                "profile_changes": profile_changes,
                "scenarios": scenarios_render,
            })
        except Exception:
            pass

    REPLACE:
        try:
            ctx.update({
                "improvement_actions": improvement_actions,
                "capability_assessments": capability_assessments,
                "decisions_and_open_items": decisions_open,
                "participant_feedback": participant_feedback or ctx.get("participants_feedback", []),
                "profile_changes": profile_changes,
                "scenarios": scenarios_render,
                # Explicit feeder keys to align with DOCX placeholders
                "exercise_id": getattr(aar_obj, "exercise_id", "") or "",
                "exercise_date": getattr(aar_obj, "exercise_date", "") or "",
                "start_time": getattr(aar_obj, "start_time", "") or "",
                "end_time": getattr(aar_obj, "end_time", "") or "",
                "exercise_location": getattr(aar_obj, "exercise_location", "") or "",
                "delivery_mode": getattr(aar_obj, "delivery_mode", "") or "",
                "audience_profile": getattr(aar_obj, "audience_profile", "") or "",
                "report_status": getattr(aar_obj, "report_status", "") or "",
                "report_version": getattr(aar_obj, "report_version", "") or "",
                "information_classification": getattr(aar_obj, "information_classification", "") or "",
                # Surface facilitators/participants/scenarios for Jinja loops
                "facilitators": _to_dict_list(getattr(aar_obj, "facilitators", [])),
                "participants": _to_dict_list(getattr(aar_obj, "participants", [])),
            })
        except Exception:
            pass

    VERIFICATION: python -c "import export; print('OK')"