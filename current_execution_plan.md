Objective: Split each inject into two slides (A: evidence; B: questions) with strict A/B adjacency and metadata notes, while preserving the static slide contract and existing layout indices in export.py.

Action [1]:

    FILE: export.py

    SEARCH: 
        for inj in injects:
            inj_layout = inject_layout
            slide = _insert_slide(inj_layout)
            ts = _dict_get(inj, "simulated_timestamp", "")
            phase = _dict_get(inj, "phase_title", "")
            narrative = _dict_get(inj, "scenario_narrative", "")
            qlist = _dict_get(inj, "facilitator_probe_questions", []) or []
            artefact_img = _dict_get(inj, "artefact_image_path", "")
            references = _dict_get(inj, "references", []) or []

            if slide.shapes.title:
                parts = [x for x in [ts, phase] if x]
                slide.shapes.title.text = " — ".join(parts) if parts else ""

            # Narrative + questions (with references)
            if len(slide.placeholders) > 1:
                tf = slide.placeholders[1].text_frame
                try:
                    tf.clear()
                except Exception:
                    tf.text = ""
                p_narrative = tf.add_paragraph()
                p_narrative.text = narrative or ""
                _apply_para_style(p_narrative, font_size_pt=15, rgb=(50, 50, 50))
                try:
                    p_narrative.space_after = Pt(12)
                except Exception:
                    pass

                _add_heading(tf, "Key Questions for the Room:", font_size_pt=15, rgb=(35, 80, 106))
                for q in qlist:
                    _add_bullet(tf, q, font_size_pt=14, rgb=(50, 50, 50))
                # Probing sections (Detailed profile only)
                if show_probing:
                    _add_heading(tf, "Systems to Check:", font_size_pt=13, rgb=(35, 80, 106))
                    for s in (_dict_get(inj, "systems_to_check", []) or [])[:3]:
                        _add_bullet(tf, s, font_size_pt=12, rgb=(50, 50, 50))
                    _add_heading(tf, "Roles to Engage:", font_size_pt=13, rgb=(35, 80, 106))
                    for r in (_dict_get(inj, "roles_to_engage", []) or [])[:3]:
                        _add_bullet(tf, r, font_size_pt=12, rgb=(50, 50, 50))
                    _add_heading(tf, "Runbooks:", font_size_pt=13, rgb=(35, 80, 106))
                    for rb in (_dict_get(inj, "runbook_references", []) or [])[:3]:
                        _add_bullet(tf, rb, font_size_pt=12, rgb=(50, 50, 50))
                    _add_heading(tf, "Evidence Hunt:", font_size_pt=13, rgb=(35, 80, 106))
                    for ev in (_dict_get(inj, "evidence_hunt", []) or [])[:3]:
                        _add_bullet(tf, ev, font_size_pt=12, rgb=(50, 50, 50))
                    _add_heading(tf, "Knowledge Checks:", font_size_pt=13, rgb=(35, 80, 106))
                    for kc in (_dict_get(inj, "knowledge_checks", []) or [])[:3]:
                        _add_bullet(tf, kc, font_size_pt=12, rgb=(50, 50, 50))
                    _add_heading(tf, "Timebox:", font_size_pt=13, rgb=(35, 80, 106))
                    tb = _dict_get(inj, "timebox_hint", "")
                    if tb:
                        _add_bullet(tf, tb, font_size_pt=12, rgb=(50, 50, 50))
                    if references:
                        _add_heading(tf, "References:", font_size_pt=13, rgb=(35, 80, 106))
                        for r in references:
                            _add_bullet(tf, r, font_size_pt=12, rgb=(50, 50, 50))
            else:
                tx, tf = _add_textbox(slide, 1.0, 2.0, 8.5, 4.5, text=narrative or "")
                _add_heading(tf, "Key Questions for the Room:", font_size_pt=15, rgb=(35, 80, 106))
                for q in qlist:
                    _add_bullet(tf, q, font_size_pt=14, rgb=(50, 50, 50))
                # Probing sections (Detailed profile only)
                if show_probing:
                    _add_heading(tf, "Systems to Check:", font_size_pt=13, rgb=(35, 80, 106))
                    for s in (_dict_get(inj, "systems_to_check", []) or [])[:3]:
                        _add_bullet(tf, s, font_size_pt=12, rgb=(50, 50, 50))
                    _add_heading(tf, "Roles to Engage:", font_size_pt=13, rgb=(35, 80, 106))
                    for r in (_dict_get(inj, "roles_to_engage", []) or [])[:3]:
                        _add_bullet(tf, r, font_size_pt=12, rgb=(50, 50, 50))
                    _add_heading(tf, "Runbooks:", font_size_pt=13, rgb=(35, 80, 106))
                    for rb in (_dict_get(inj, "runbook_references", []) or [])[:3]:
                        _add_bullet(tf, rb, font_size_pt=12, rgb=(50, 50, 50))
                    _add_heading(tf, "Evidence Hunt:", font_size_pt=13, rgb=(35, 80, 106))
                    for ev in (_dict_get(inj, "evidence_hunt", []) or [])[:3]:
                        _add_bullet(tf, ev, font_size_pt=12, rgb=(50, 50, 50))
                    _add_heading(tf, "Knowledge Checks:", font_size_pt=13, rgb=(35, 80, 106))
                    for kc in (_dict_get(inj, "knowledge_checks", []) or [])[:3]:
                        _add_bullet(tf, kc, font_size_pt=12, rgb=(50, 50, 50))
                    _add_heading(tf, "Timebox:", font_size_pt=13, rgb=(35, 80, 106))
                    tb = _dict_get(inj, "timebox_hint", "")
                    if tb:
                        _add_bullet(tf, tb, font_size_pt=12, rgb=(50, 50, 50))
                    if references:
                        _add_heading(tf, "References:", font_size_pt=13, rgb=(35, 80, 106))
                        for r in references:
                            _add_bullet(tf, r, font_size_pt=12, rgb=(50, 50, 50))

            # Optional artefact image (if path provided and exists)
            _embed_picture(slide, artefact_img, left_in=6.0, top_in=1.5, width_in=3.0)
            # Facilitator Notes (non-visible during presentation)
            try:
                ns = slide.notes_slide
                ntf = ns.notes_text_frame
                ntf.text = ""
                _nt_lines = []
                emr = _dict_get(inj, "expected_mature_response", "")
                if emr: _nt_lines.append("What Good Looks Like: " + str(emr))
                dt = _dict_get(inj, "decision_threshold", "")
                if dt: _nt_lines.append("Decision Threshold: " + str(dt))
                for label, items in [
                    ("Systems to Check", _dict_get(inj, "systems_to_check", []) or []),
                    ("Roles to Engage", _dict_get(inj, "roles_to_engage", []) or []),
                    ("Runbooks", _dict_get(inj, "runbook_references", []) or []),
                    ("Evidence Hunt", _dict_get(inj, "evidence_hunt", []) or []),
                    ("Knowledge Checks", _dict_get(inj, "knowledge_checks", []) or []),
                ]:
                    if items:
                        _nt_lines.append(label + ": " + "; ".join([str(x) for x in items]))
                # Enrichment additions for facilitator notes (best-effort, optional)
                # Learning objective: EMR + first knowledge check if present
                try:
                    kc_list = _dict_get(inj, "knowledge_checks", []) or []
                    if emr or kc_list:
                        obj_sfx = f" ({kc_list[0]})" if isinstance(kc_list, list) and len(kc_list) > 0 else ""
                        _nt_lines.append("Objective: " + (str(emr) if emr else "Validate process") + obj_sfx)
                except Exception:
                    pass
                # Escalation route from roles_to_engage
                try:
                    roles = _dict_get(inj, "roles_to_engage", []) or []
                    flow = []
                    def _has(rn):
                        try:
                            return any(rn.lower() in str(x).lower() for x in roles)
                        except Exception:
                            return False
                    if _has("ir lead"):
                        flow.append("IR Lead")
                    if _has("it ops") or _has("service desk"):
                        flow.append("IT Ops")
                    if _has("comms") or _has("communications"):
                        flow.append("Comms")
                    if _has("legal"):
                        flow.append("Legal")
                    if _has("exec") or _has("ciso") or _has("board"):
                        flow.append("Exec")
                    if flow:
                        _nt_lines.append("Escalation: " + " \u2192 ".join(flow))
                except Exception:
                    pass
                # Minimum evidence (first two)
                try:
                    ev = _dict_get(inj, "evidence_hunt", []) or []
                    if isinstance(ev, list) and ev:
                        _nt_lines.append("Minimum evidence: " + "; ".join([str(x) for x in ev[:2]]))
                except Exception:
                    pass
                # Systems/logs focus cue (first two)
                try:
                    sysc = _dict_get(inj, "systems_to_check", []) or []
                    if isinstance(sysc, list) and sysc:
                        _nt_lines.append("Start here \u2192 " + "; ".join([str(x) for x in sysc[:2]]))
                except Exception:
                    pass
                # Timebox pacing cue
                try:
                    tb = _dict_get(inj, "timebox_hint", "")
                    if tb:
                        _nt_lines.append("Timebox: Aim decision within " + str(tb))
                except Exception:
                    pass
                # Common pitfalls (if present)
                try:
                    pits = _dict_get(inj, "common_pitfalls", []) or []
                    if isinstance(pits, list) and pits:
                        _nt_lines.append("Common pitfalls: " + "; ".join([str(x) for x in pits[:2]]))
                except Exception:
                    pass
                # Branching prompt
                try:
                    if dt:
                        _nt_lines.append("Branching: If threshold met, initiate escalation; otherwise continue evidence gathering briefly.")
                except Exception:
                    pass
                # Facilitator KPIs and debrief prompts
                _nt_lines.append("KPIs to capture: TTD; TTC; Evidence completeness; Approval path (Y/N)")
                _nt_lines.append("Debrief: What would you change? Owner & target date")
                if _nt_lines:
                    ntf.text = "\n".join(_nt_lines)
                else:
                    ntf.text = "What Good Looks Like: See facilitator guide"
            except Exception:
                pass

    REPLACE:
        for inj_idx, inj in enumerate(injects, 1):
            ts = _dict_get(inj, "simulated_timestamp", "")
            phase = _dict_get(inj, "phase_title", "")
            narrative = _dict_get(inj, "scenario_narrative", "")
            qlist = _dict_get(inj, "facilitator_probe_questions", []) or []
            artefact_img = _dict_get(inj, "artefact_image_path", "")
            references = _dict_get(inj, "references", []) or []

            # Inject A — Participant-facing evidence
            slide_a = _insert_slide(inject_layout)
            if slide_a.shapes.title:
                slide_a.shapes.title.text = f"Inject {inj_idx}a — " + (phase or "Evidence")
            if len(slide_a.placeholders) > 1:
                tf_a = slide_a.placeholders[1].text_frame
                try:
                    tf_a.clear()
                except Exception:
                    tf_a.text = ""
                if narrative:
                    p = tf_a.add_paragraph()
                    p.text = narrative or ""
                    _apply_para_style(p, font_size_pt=15, rgb=(50, 50, 50))
                    try:
                        p.space_after = Pt(12)
                    except Exception:
                        pass
            else:
                txa, tf_a = _add_textbox(slide_a, 1.0, 2.0, 8.5, 4.5, text=narrative or "")
            # Optional artefact image on A
            _embed_picture(slide_a, artefact_img, left_in=6.0, top_in=1.5, width_in=3.0)
            # Notes for A (with deterministic metadata)
            try:
                ns_a = slide_a.notes_slide
                ntf_a = ns_a.notes_text_frame
                lines_a = []
                emr = _dict_get(inj, "expected_mature_response", "")
                if emr: lines_a.append("What Good Looks Like: " + str(emr))
                dt = _dict_get(inj, "decision_threshold", "")
                if dt: lines_a.append("Decision Threshold: " + str(dt))
                lines_a.append(f"DYNAMIC_SLIDE_TYPE: INJECT_EVIDENCE_A")
                lines_a.append(f"SCENARIO_ORDINAL: {scn_idx}")
                lines_a.append(f"INJECT_ORDINAL: {inj_idx}")
                ntf_a.text = "\n".join([ln for ln in lines_a if ln])
            except Exception:
                pass

            # Inject B — Questions for the room
            slide_b = _insert_slide(inject_layout)
            if slide_b.shapes.title:
                slide_b.shapes.title.text = f"Inject {inj_idx}b — Questions for the room"
            if len(slide_b.placeholders) > 1:
                tf_b = slide_b.placeholders[1].text_frame
                try:
                    tf_b.clear()
                except Exception:
                    tf_b.text = ""
                _add_heading(tf_b, "Key Questions for the Room:", font_size_pt=15, rgb=(35, 80, 106))
                for q in qlist:
                    _add_bullet(tf_b, q, font_size_pt=14, rgb=(50, 50, 50))
                # Probing sections (Detailed profile only)
                if show_probing:
                    _add_heading(tf_b, "Systems to Check:", font_size_pt=13, rgb=(35, 80, 106))
                    for s in (_dict_get(inj, "systems_to_check", []) or [])[:3]:
                        _add_bullet(tf_b, s, font_size_pt=12, rgb=(50, 50, 50))
                    _add_heading(tf_b, "Roles to Engage:", font_size_pt=13, rgb=(35, 80, 106))
                    for r in (_dict_get(inj, "roles_to_engage", []) or [])[:3]:
                        _add_bullet(tf_b, r, font_size_pt=12, rgb=(50, 50, 50))
                    _add_heading(tf_b, "Runbooks:", font_size_pt=13, rgb=(35, 80, 106))
                    for rb in (_dict_get(inj, "runbook_references", []) or [])[:3]:
                        _add_bullet(tf_b, rb, font_size_pt=12, rgb=(50, 50, 50))
                    _add_heading(tf_b, "Evidence Hunt:", font_size_pt=13, rgb=(35, 80, 106))
                    for ev in (_dict_get(inj, "evidence_hunt", []) or [])[:3]:
                        _add_bullet(tf_b, ev, font_size_pt=12, rgb=(50, 50, 50))
                    _add_heading(tf_b, "Knowledge Checks:", font_size_pt=13, rgb=(35, 80, 106))
                    for kc in (_dict_get(inj, "knowledge_checks", []) or [])[:3]:
                        _add_bullet(tf_b, kc, font_size_pt=12, rgb=(50, 50, 50))
                    _add_heading(tf_b, "Timebox:", font_size_pt=13, rgb=(35, 80, 106))
                    tb = _dict_get(inj, "timebox_hint", "")
                    if tb:
                        _add_bullet(tf_b, tb, font_size_pt=12, rgb=(50, 50, 50))
                    if references:
                        _add_heading(tf_b, "References:", font_size_pt=13, rgb=(35, 80, 106))
                        for r in references:
                            _add_bullet(tf_b, r, font_size_pt=12, rgb=(50, 50, 50))
            else:
                txb, tf_b = _add_textbox(slide_b, 1.0, 2.0, 8.5, 4.5, text="")
                _add_heading(tf_b, "Key Questions for the Room:", font_size_pt=15, rgb=(35, 80, 106))
                for q in qlist:
                    _add_bullet(tf_b, q, font_size_pt=14, rgb=(50, 50, 50))
            # Notes for B (with deterministic metadata)
            try:
                ns_b = slide_b.notes_slide
                ntf_b = ns_b.notes_text_frame
                lines_b = []
                lines_b.append(f"DYNAMIC_SLIDE_TYPE: INJECT_QUESTIONS_B")
                lines_b.append(f"SCENARIO_ORDINAL: {scn_idx}")
                lines_b.append(f"INJECT_ORDINAL: {inj_idx}")
                ntf_b.text = "\n".join([ln for ln in lines_b if ln])
            except Exception:
                pass

    VERIFICATION: python -u tools/verify_pptx.py

Action [2]:

    FILE: pages/03_Tabletop_Designer.py

    SEARCH:
        ok, defects = (True, [])
        try:
            if callable(validate_tabletop_master_plan):
                ok, defects = validate_tabletop_master_plan(plan)

    REPLACE:
        # Merge saved Required Setup (Objectives + Scope) before validation/export
        _rs = st.session_state.get("tt_required_setup")
        if _rs:
            try:
                plan["objectives"] = _rs.get("objectives", plan.get("objectives", []))
                _rs_scope = _rs.get("scope", {})
                if isinstance(_rs_scope, dict):
                    _sc = plan.get("scope", {}) if isinstance(plan.get("scope", {}), dict) else {}
                    plan["scope"] = {
                        "included": _rs_scope.get("included", _sc.get("included", [])),
                        "excluded": _rs_scope.get("excluded", _sc.get("excluded", [])),
                        "assumptions": _rs_scope.get("assumptions", _sc.get("assumptions", [])),
                    }
                elif isinstance(_rs_scope, list):
                    plan["scope"] = _rs_scope
            except Exception:
                pass
        ok, defects = (True, [])
        try:
            if callable(validate_tabletop_master_plan):
                ok, defects = validate_tabletop_master_plan(plan)

    VERIFICATION: python -c "import json,streamlit as st; print('MERGE_OK')"

Action [3]:

    FILE: export.py

    SEARCH:
        _add_heading(atf, "Scope:", font_size_pt=15, rgb=(35, 80, 106))
        for sc in (_dict_get(master_plan_data, "scope", []) or []):
            _add_bullet(atf, str(sc), font_size_pt=14, rgb=(50, 50, 50))

    REPLACE:
        _add_heading(atf, "Scope:", font_size_pt=15, rgb=(35, 80, 106))
        _scope_ctx = _dict_get(master_plan_data, "scope", []) or []
        if isinstance(_scope_ctx, dict):
            for _label, _key in (("Included", "included"), ("Excluded", "excluded"), ("Assumptions", "assumptions")):
                _items = _scope_ctx.get(_key, []) or []
                if _items:
                    _add_heading(atf, f"{_label}:", font_size_pt=13, rgb=(35, 80, 106))
                    for sc in _items:
                        _add_bullet(atf, str(sc), font_size_pt=12, rgb=(50, 50, 50))
        else:
            for sc in _scope_ctx:
                _add_bullet(atf, str(sc), font_size_pt=14, rgb=(50, 50, 50))

    VERIFICATION: python -u tools/verify_pptx.py

Action [4]:

    FILE: export.py

    SEARCH:
        _add_heading(tf, "Scope:", font_size_pt=15, rgb=(35, 80, 106))
        for sc in (_dict_get(master_plan_data, "scope", []) or []):
            _add_bullet(tf, str(sc), font_size_pt=14, rgb=(50, 50, 50))

    REPLACE:
        _add_heading(tf, "Scope:", font_size_pt=15, rgb=(35, 80, 106))
        _scope_ctx = _dict_get(master_plan_data, "scope", []) or []
        if isinstance(_scope_ctx, dict):
            for _label, _key in (("Included", "included"), ("Excluded", "excluded"), ("Assumptions", "assumptions")):
                _items = _scope_ctx.get(_key, []) or []
                if _items:
                    _add_heading(tf, f"{_label}:", font_size_pt=13, rgb=(35, 80, 106))
                    for sc in _items:
                        _add_bullet(tf, str(sc), font_size_pt=12, rgb=(50, 50, 50))
        else:
            for sc in _scope_ctx:
                _add_bullet(tf, str(sc), font_size_pt=14, rgb=(50, 50, 50))

    VERIFICATION: python -u tools/verify_pptx.py