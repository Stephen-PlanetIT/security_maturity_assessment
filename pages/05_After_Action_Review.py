import streamlit as st
from core import LLMEngine
from prompts import build_tabletop_aar_prompt, SYSTEM_PERSONA_TABLETOP, TabletopAAR
from config import get_config, ConfigKey
from consultation_helpers import load_latest_tabletop_session
from ui_shared_sections import render_top_nav

st.set_page_config(page_title="After-Action Review (AAR)", layout="wide", initial_sidebar_state="collapsed")

# Auth-aware guard: if login is enabled and user not signed-in, route to app.py sign-in
def _is_auth_enabled():
    try:
        return str(get_config("AUTH_ENABLED", "false")).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        return False
if _is_auth_enabled() and not st.session_state.get("_auth_user"):
    st.warning("Sign in required to access the AAR page.")
    st.page_link("app.py", label="🔐 Go to Sign In")
    st.stop()

# Branding header
st.title("Planet IT Advisory Engine")

# Top navigation (no sidebar)
render_top_nav(active="tabletop")

st.header("📋 After-Action Review (AAR)")
# Attempt to load a persisted session snapshot if session state is empty
try:
    if not st.session_state.get("tabletop_plan") or not st.session_state.get("tabletop_notes"):
        saved = load_latest_tabletop_session()
        if isinstance(saved, dict):
            st.session_state["tabletop_plan"] = saved.get("plan", {})
            st.session_state["tabletop_notes"] = saved.get("notes", [])
            st.session_state["client_inputs"] = saved.get("client_inputs", {})
            st.session_state["tabletop_audience"] = saved.get("audience", "Blended")
            st.session_state["immediate_injects"] = saved.get("immediate_injects", [])
except Exception:
    pass

# Ensure a generated tabletop plan exists
if not st.session_state.get("tabletop_plan"):
    st.info("No tabletop plan in session. Generate a plan in the Designer page first.")
    st.stop()

# 🧪 Demo helpers — compile notes from prefilled fields
with st.expander("🧪 Demo helpers", expanded=False):
    st.caption("Compile demo notes from the Live Facilitation prefilled fields across all injects.")
    if st.button("Compile demo notes from demo fields"):
        try:
            plan = st.session_state.get("tabletop_plan", {})
            scenarios = plan.get("scenarios", []) or []
            notes_compiled = []
            for si, scen in enumerate(scenarios):
                scen_title = (scen.get("scenario_title") or scen.get("title") or f"Scenario {si+1}")
                injects = scen.get("injects", []) or []
                for ii, inj in enumerate(injects):
                    phase_title = (inj.get("phase_title") or inj.get("intended_capability") or f"Inject {ii+1}")
                    tm = (inj.get("simulated_timestamp") or inj.get("simulated_time") or "")
                    decision = str(st.session_state.get(f"rec_dec_{si}_{ii}", "") or "").strip()
                    eval_notes = str(st.session_state.get(f"rec_eval_{si}_{ii}", "") or "").strip()
                    if decision or eval_notes:
                        notes_compiled.append({
                            "scenario": scen_title,
                            "phase": phase_title,
                            "decision": decision,
                            "notes": eval_notes,
                            "simulated_timestamp": tm,
                        })
            st.session_state["tabletop_notes"] = notes_compiled
            st.success(f"Compiled {len(notes_compiled)} notes from demo fields.")
            st.rerun()
        except Exception as e:
            st.warning(f"Failed to compile demo notes: {e}")

# Capture AAR from notes if available
if not st.session_state.get("tabletop_notes"):
    st.info("No exercise notes captured yet. Use the Live Facilitation page to populate findings.")
else:
    if st.button("Generate After-Action Review (AAR)", type="primary"):
        with st.spinner("Evaluating room performance and synthesising AAR..."):
            client = LLMEngine.get_client()
            deployment = get_config(ConfigKey.AZURE_DEPLOYMENT, "gpt-4o")
            aar_prompt = build_tabletop_aar_prompt(
                st.session_state["tabletop_plan"],
                st.session_state["tabletop_notes"],
                st.session_state.get("client_inputs", {}),
                audience=st.session_state.get("tabletop_audience", "Blended"),
                immediate_injects=st.session_state.get("immediate_injects", []),
            )
            aar_obj = LLMEngine.generate_structured_report(
                client,
                deployment,
                SYSTEM_PERSONA_TABLETOP,
                aar_prompt,
                TabletopAAR,
            )
            if aar_obj:
                st.session_state["aar_result"] = aar_obj
                st.success("After-Action Review generated!")

        # Offline demo mode (no LLM)
        if st.button("Generate AAR (offline demo mode)"):
            try:
                from types import SimpleNamespace
                plan = st.session_state.get("tabletop_plan", {}) or {}
                ci = st.session_state.get("client_inputs", {}) or {}
                # Build scenarios structure from plan to satisfy renderer
                scenarios_ns = []
                for idx, scn in enumerate(plan.get("scenarios", []) or [], 1):
                    injects = scn.get("injects", []) or []
                    scenarios_ns.append({
                        "title": scn.get("scenario_title") or scn.get("title") or f"Scenario {idx}",
                        "summary": scn.get("scenario_theme") or scn.get("initial_vector") or "",
                        "objectives": scn.get("objectives") or [],
                        "capabilities_exercised": scn.get("capabilities_exercised") or [],
                        "expected_outcomes": scn.get("expected_outcomes") or [],
                        "outcome_summary": scn.get("outcome_summary") or "",
                        "injects": [
                            {
                                "simulated_time": inj.get("simulated_timestamp") or inj.get("simulated_time") or "",
                                "information_presented": inj.get("scenario_narrative") or inj.get("information_presented") or "",
                                "intended_capability": inj.get("phase_title") or inj.get("intended_capability") or "",
                                "response_observed": inj.get("expected_mature_response") or "",
                                "decision_owner": "",
                                "outcome": "",
                            } for inj in injects
                        ],
                    })
                aar = SimpleNamespace(
                    customer_name=str(ci.get("customer_name","")),
                    exercise_title=str(ci.get("exercise_title","")),
                    exercise_id=str(ci.get("exercise_id","TTX-DEMO")),
                    exercise_date=str(ci.get("exercise_date","")),
                    start_time=str(ci.get("start_time","")),
                    end_time=str(ci.get("end_time","")),
                    exercise_location=str(ci.get("exercise_location","")),
                    delivery_mode=str(ci.get("delivery_mode","")),
                    audience_profile=str(ci.get("audience_profile","")),
                    report_status="Draft",
                    report_version="1.0",
                    information_classification="Confidential",
                    executive_summary="This After-Action Review was generated in offline demo mode.",
                    overall_maturity_observed="Pillar 2: Proactive",
                    maturity_rationale="Proactive behaviours observed during the tabletop; refine playbooks for faster coordination.",
                    capability_assessments=[{"capability":"Incident Response","maturity":"Pillar 2"}],
                    scenarios=scenarios_ns,
                    key_strengths=[],
                    critical_gaps_identified=[],
                    improvement_actions=[],
                    red_flags=[],
                    facilitator_observations="",
                    exercise_limitations=[],
                    approved_distribution=[],
                    profile_changes=[],
                )
                st.session_state["aar_result"] = aar
                st.success("After-Action Review generated in offline demo mode.")
            except Exception as e:
                st.warning(f"Offline demo mode failed: {e}")

# Display AAR if present

# 🔧 Diagnostics (validation and QA)
with st.expander("🔧 Diagnostics", expanded=False):
    st.caption("Run validation and QA diagnostics on the current AAR/output context (no business-logic changes).")
    if st.button("Run AAR export diagnostics"):
        try:
            # 1) Show template schema
            try:
                from aar_renderer import _detect_template_schema_version as _schema
                schema = _schema("planet_it_tabletop_report_template.docx") or "missing"
                st.info(f"Template schema: {schema}")
            except Exception:
                st.warning("Could not detect template schema marker.")

            # 2) Build context and validate (same path as exporter)
            try:
                from aar_renderer import build_aar_context, validate_aar_context, SUPPORTED_KEYS
                flags = {"min_aar": str(get_config("AAR_MIN_MODE", "false")).strip().lower() in ("1","true","yes","on")}
                ctx = build_aar_context(
                    st.session_state.get("tabletop_plan", {}) or {},
                    st.session_state.get("tabletop_notes", []) or [],
                    st.session_state.get("aar_result"),
                    flags
                )
                ok, defects = validate_aar_context(ctx, SUPPORTED_KEYS, strict=True)
                st.write("Context valid:", ok)
                if defects:
                    st.warning("Validation defects found:")
                    for d in defects:
                        st.write(f"- {d}")
            except Exception as e:
                st.warning(f"Context/validation step failed: {e}")

            # 3) Attempt a diagnostic render and run QA scan (mirrors exporter logic)
            try:
                from docxtpl import DocxTemplate  # type: ignore
                from export import _reconcile_context_for_template, _xml_escape_dict
                doc = DocxTemplate("planet_it_tabletop_report_template.docx")
                ctx2 = _reconcile_context_for_template(doc, ctx, extra_alias={
                    "ExecutiveSummary": "executive_summary",
                    "SessionNotes": "session_notes_render",
                    "KeyStrengths": "strengths_render",
                    "CriticalGaps": "gaps_render",
                    "ImprovementActions": "actions_render",
                    "CapabilityHeatmap": "capability_heatmap_text",
                    "WhyPlanetIT": "marketing_why_planet",
                    "OurPedigree": "marketing_pedigree",
                    "ContactDetails": "marketing_contacts",
                    "AssumptionsClientResponsibilities": "marketing_assumptions_text",
                    "TermsAndConditions": "marketing_tcs_text",
                }, debug=str(get_config("RENDER_DEBUG", "false")).strip().lower() in ("1","true","yes","on"))
                import io
                try:
                    doc.render(_xml_escape_dict(ctx2))
                except Exception:
                    # Retry minimal
                    minimal = {k: (ctx2.get(k, "") or "") for k in ctx2.keys()}
                    doc.render(_xml_escape_dict(minimal))
                buf = io.BytesIO()
                doc.save(buf)
                data = buf.getvalue()
                # QA scan
                from aar_renderer import qa_scan_docx_bytes
                ok_doc, qa_issues = qa_scan_docx_bytes(data)
                st.write("QA passed:", ok_doc)
                if qa_issues:
                    st.error("QA issues:")
                    for q in qa_issues:
                        st.write(f"- {q}")
                if ok_doc and data:
                    st.success("Diagnostic render succeeded. If export still fails, it is likely due to a mismatch in the exporter path. The diagnostic bytes are available for download below.")
                    st.download_button("Download diagnostic AAR (DOCX)", data=data, file_name="AAR_diagnostic.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            except Exception as e:
                st.warning(f"Diagnostic render/QA failed: {e}")
        except Exception as e:
            st.warning(f"Diagnostics failed: {e}")
if st.session_state.get("aar_result"):
    aar = st.session_state["aar_result"]
    st.markdown(f"### Evaluated Performance: `{getattr(aar, 'overall_maturity_observed', 'Unknown')}`")
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
            st.code("\n".join(feeders), language="text")
        except Exception:
            st.info("Client feeder fields are unavailable or incomplete in the AAR object.")

    col_res1, col_res2 = st.columns(2)
    with col_res1:
        st.markdown("#### ✅ Demonstrated Strengths")
        for s in getattr(aar, "key_strengths", []) or []:
            try:
                summary = getattr(s, "summary", None) or (s.get("summary") if isinstance(s, dict) else "")
                capability = getattr(s, "capability", None) or (s.get("capability") if isinstance(s, dict) else "")
                ev = getattr(s, "evidence_source", None) or (s.get("evidence_source") if isinstance(s, dict) else "")
                conf = getattr(s, "confidence", None) or (s.get("confidence") if isinstance(s, dict) else "")
                refs_scn = getattr(s, "scenario_references", None) or (s.get("scenario_references") if isinstance(s, dict) else [])
                refs_inj = getattr(s, "inject_references", None) or (s.get("inject_references") if isinstance(s, dict) else [])
                ref_txt = "; ".join([*map(str, refs_scn or []), *map(str, refs_inj or [])])
                st.markdown(f"- {summary}  \n  Capability: {capability} | Evidence: {ev} | Confidence: {conf}" + (f"  \n  References: {ref_txt}" if ref_txt else ""))
            except Exception:
                st.markdown(f"- {s}")
    with col_res2:
        st.markdown("#### ⚠️ Identified Critical Gaps")
        for g in getattr(aar, "critical_gaps_identified", []) or []:
            try:
                summary = getattr(g, "summary", None) or (g.get("summary") if isinstance(g, dict) else "")
                rationale = getattr(g, "rationale", None) or (g.get("rationale") if isinstance(g, dict) else "")
                capability = getattr(g, "capability", None) or (g.get("capability") if isinstance(g, dict) else "")
                ev = getattr(g, "evidence_source", None) or (g.get("evidence_source") if isinstance(g, dict) else "")
                conf = getattr(g, "confidence", None) or (g.get("confidence") if isinstance(g, dict) else "")
                refs_scn = getattr(g, "scenario_references", None) or (g.get("scenario_references") if isinstance(g, dict) else [])
                refs_inj = getattr(g, "inject_references", None) or (g.get("inject_references") if isinstance(g, dict) else [])
                ref_txt = "; ".join([*map(str, refs_scn or []), *map(str, refs_inj or [])])
                st.markdown(f"- {summary}  \n  Why it matters: {rationale}  \n  Capability: {capability} | Evidence: {ev} | Confidence: {conf}" + (f"  \n  References: {ref_txt}" if ref_txt else ""))
            except Exception:
                st.markdown(f"- {g}")

    # Export AAR (DOCX)
    try:
        from export_aar_v2 import create_tabletop_aar_docx_v2 as _aar_export_fn
    except Exception:
        try:
            from export import create_tabletop_aar_docx as _aar_export_fn
        except Exception:
            _aar_export_fn = None
    aar_docx = None
    try:
        import datetime
        if _aar_export_fn:
            # Populate appendix/governance scalars if missing
            try:
                aar.consultant_name = st.session_state.get("client_inputs", {}).get("consultant_name", "")
            except Exception:
                pass
            try:
                aar.account_manager_name = st.session_state.get("client_inputs", {}).get("account_manager_name", "")
            except Exception:
                pass
            try:
                aar.generated_at = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
            except Exception:
                pass
            aar_docx = _aar_export_fn(
                st.session_state.get("tabletop_plan", {}),
                st.session_state.get("tabletop_notes", []),
                aar,
                st.session_state.get("immediate_injects", []),
            )
    except Exception:
        aar_docx = None
    if aar_docx:
        safe_client = ""
        try:
            safe_client = str(st.session_state.get("client_inputs", {}).get("customer_name", "Client")).strip() or "Client"
        except Exception:
            safe_client = "Client"
        fname = f"AAR_{safe_client}_{datetime.date.today().isoformat()}.docx"
        st.download_button(
            "Download After-Action Review (DOCX)",
            data=aar_docx,
            file_name=fname,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    st.divider()
    st.subheader("🔄 Sync Insights into Client Profile")
    st.caption("Update the client's master profile with these findings to inform future maturity assessments and tabletops.")
    if st.button("Apply Delta to Client Profile"):
        import datetime
        today_str = datetime.date.today().isoformat()
        try:
            st.session_state["client_inputs"]["incident_response_assurance_profile"]["tabletop_status"] = "Within the past year"
            existing_notes = st.session_state["client_inputs"]["incident_response_assurance_profile"].get("notes", "")
            delta = getattr(aar, "delta_notes_for_profile", "")
            st.session_state["client_inputs"]["incident_response_assurance_profile"]["notes"] = (
                f"{existing_notes}\n[{today_str} Tabletop AAR]: {delta}".strip()
            )
            st.success(
                f"Profile updated! The incident_response_assurance_profile now reflects the exercise conducted on {today_str}."
            )
        except Exception:
            st.warning(
                "Failed to sync delta into client profile; ensure client_inputs structure is present."
            )

# Standard footer
try:
    from ui_shared_sections import render_footer
    render_footer(show_divider=True)
except Exception:
    pass
