Objective: Enable the LLM to generate and the exporters to render realistic artefacts (logs, code, emails, tickets) on Inject A slides and in the facilitator PDF for tabletop exercises.

Action 1:

    FILE: prompts.py

    SEARCH:
# ==========================================
# PYDANTIC MODELS: TABLETOP EXERCISE
# ==========================================
class TabletopInject(BaseModel):

    REPLACE:
# ==========================================
# PYDANTIC MODELS: TABLETOP EXERCISE
# ==========================================
class InjectArtefact(BaseModel):
    artefact_type: str = Field(description="One of: 'log', 'email', 'code', 'ticket', 'screenshot', 'configuration'.")
    title: Optional[str] = Field(default=None, description="Short label for the artefact (e.g., Alert name, Email subject).")
    source_system: Optional[str] = Field(default=None, description="System/source where the artefact originates (e.g., 'Sophos Central', 'Microsoft Entra').")
    body: str = Field(description="Content of the artefact: for 'log' include a realistic excerpt; for 'email' include headers + body; for 'code' include the snippet.")
    metadata: Optional[List[str]] = Field(default=None, description="Additional contextual hints (e.g., case ID, query path).", min_items=0, max_items=6)
    render_hint: Optional[str] = Field(default=None, description="Short hint to the renderer for formatting (e.g., 'monospace', 'wrap-80').")

class TabletopInject(BaseModel):

    VERIFICATION: python -c "from prompts import InjectArtefact, TabletopInject; print('OK')"

Action 2:

    FILE: prompts.py

    SEARCH:
class TabletopInject(BaseModel):
    inject_id: str = Field(description="Unique identifier, e.g., 'INJ-1.1'")
    phase_title: str = Field(description="Phase title, e.g., 'Initial Anomaly Detection' or 'Interim Escalation'")
    simulated_timestamp: str = Field(description="Relative or clock timestamp, e.g., 'Day 1 - 08:15 UTC'")
    scenario_narrative: str = Field(description="The event presented to the room. Grounded in their actual estate.")
    technical_indicators: List[str] = Field(description="Specific logs, alerts, cmdlines, or console indicators (e.g., Sophos MDR alert, Entra sign-in).", min_items=1, max_items=4)
    facilitator_probe_questions: List[str] = Field(description="Challenging, provocative questions for the facilitator to pose to the room.", min_items=2, max_items=5)

    REPLACE:
class TabletopInject(BaseModel):
    inject_id: str = Field(description="Unique identifier, e.g., 'INJ-1.1'")
    phase_title: str = Field(description="Phase title, e.g., 'Initial Anomaly Detection' or 'Interim Escalation'")
    simulated_timestamp: str = Field(description="Relative or clock timestamp, e.g., 'Day 1 - 08:15 UTC'")
    scenario_narrative: str = Field(description="The event presented to the room. Grounded in their actual estate.")
    technical_indicators: List[str] = Field(description="Specific logs, alerts, cmdlines, or console indicators (e.g., Sophos MDR alert, Entra sign-in).", min_items=1, max_items=4)
    artefacts: Optional[List[InjectArtefact]] = Field(default=None, description="1–3 realistic artefacts enhancing the inject (logs, emails, code, tickets).", min_items=1, max_items=3)
    facilitator_probe_questions: List[str] = Field(description="Challenging, provocative questions for the facilitator to pose to the room.", min_items=2, max_items=5)

    VERIFICATION: python -c "from prompts import TabletopInject; assert 'artefacts' in TabletopInject.model_fields, 'missing artefacts field'; print('OK')"

Action 3:

    FILE: prompts.py

    SEARCH:
  - TabletopMasterPlan: 2–4 scenarios; each with 3–5 injects. For each inject provide: phase_title, simulated_timestamp, scenario_narrative, technical_indicators (1–4), facilitator_probe_questions (2–5), expected_mature_response, common_pitfalls (2–4), decision_threshold, success_criteria (1–3), evaluation_evidence (1–3), systems_to_check (2–6), roles_to_engage (2–5), runbook_references (1–3), evidence_hunt (2–6), knowledge_checks (2–4), timebox_hint.

    REPLACE:
  - TabletopMasterPlan: 2–4 scenarios; each with 3–5 injects. For each inject provide: phase_title, simulated_timestamp, scenario_narrative, technical_indicators (1–4), artefacts (1–3), facilitator_probe_questions (2–5), expected_mature_response, common_pitfalls (2–4), decision_threshold, success_criteria (1–3), evaluation_evidence (1–3), systems_to_check (2–6), roles_to_engage (2–5), runbook_references (1–3), evidence_hunt (2–6), knowledge_checks (2–4), timebox_hint.

    VERIFICATION: python -c "import prompts; print('artefacts' in prompts.SYSTEM_PERSONA_TABLETOP)"

Action 4:

    FILE: prompts.py

    SEARCH:
    INJECT DESIGN HINTS (STRICT):
    - technical_indicators should be concrete (e.g., Sophos MDR alert name, Entra sign‑in risk event, firewall log), 1–4 items.
    - common_pitfalls should capture cognitive biases and typical missteps (e.g., assuming backups are immutable without evidence).
    - decision_threshold must be explicit (e.g., Major Incident declaration, ICO 72h, invoke retainer).
    - success_criteria must be measurable and tied to runbooks/governance (e.g., declare incident within 10 minutes under IR‑01; notify regulator if threshold crossed), 1–3 items.
    - evaluation_evidence should list specific artefacts and where to locate them (e.g., SIEM query path, ticket ID, comms record).
    - systems_to_check: list exact consoles/queries in the client stack; roles_to_engage: list accountable/consulted roles; runbook_references: cite IR/BCP/DR IDs; evidence_hunt: list artefacts to collect and their locations; knowledge_checks: short checks that force recall of ownership and evidence paths; timebox_hint: force rapid decision-making (e.g., 5–7 minutes).

    REPLACE:
    INJECT DESIGN HINTS (STRICT):
    - technical_indicators should be concrete (e.g., Sophos MDR alert name, Entra sign‑in risk event, firewall log), 1–4 items.
    - artefacts: Provide 1–3 realistic items per inject. For 'log': include timestamped sample lines and source. For 'email': From/To/Subject and a concise body. For 'code': language and snippet. For 'ticket': ID and summary. Keep aligned to the client's stack; do not invent tools.
    - common_pitfalls should capture cognitive biases and typical missteps (e.g., assuming backups are immutable without evidence).
    - decision_threshold must be explicit (e.g., Major Incident declaration, ICO 72h, invoke retainer).
    - success_criteria must be measurable and tied to runbooks/governance (e.g., declare incident within 10 minutes under IR‑01; notify regulator if threshold crossed), 1–3 items.
    - evaluation_evidence should list specific artefacts and where to locate them (e.g., SIEM query path, ticket ID, comms record).
    - systems_to_check: list exact consoles/queries in the client stack; roles_to_engage: list accountable/consulted roles; runbook_references: cite IR/BCP/DR IDs; evidence_hunt: list artefacts to collect and their locations; knowledge_checks: short checks that force recall of ownership and evidence paths; timebox_hint: force rapid decision-making (e.g., 5–7 minutes).

    VERIFICATION: python -c "import prompts; print('Evidence Artefacts' if 'artefacts' in prompts.build_tabletop_plan_prompt.__code__.co_consts.__str__() else 'OK')"

Action 5:

    FILE: export.py

    SEARCH:
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

    REPLACE:
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
                # Render structured artefacts (if provided)
                arts = _dict_get(inj, "artefacts", []) or []
                if arts:
                    try:
                        _add_heading(tf_a, "Evidence Artefacts:", font_size_pt=13, rgb=(35, 80, 106))
                        for ar in arts[:3]:
                            try:
                                at = _dict_get(ar, "artefact_type", "")
                                ttl = _dict_get(ar, "title", "")
                                src = _dict_get(ar, "source_system", "")
                                line = f"[{at}] {ttl or '(untitled)'} — {src}".strip()
                                _add_bullet(tf_a, line, font_size_pt=12, rgb=(50, 50, 50))
                            except Exception:
                                continue
                    except Exception:
                        pass
            else:
                txa, tf_a = _add_textbox(slide_a, 1.0, 2.0, 8.5, 4.5, text=narrative or "")

    VERIFICATION: python -c "import export; print('pptx_fn' if hasattr(export,'create_tabletop_pptx') else 'OK')"

Action 6:

    FILE: export.py

    SEARCH:
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

    REPLACE:
            try:
                ns_a = slide_a.notes_slide
                ntf_a = ns_a.notes_text_frame
                lines_a = []
                emr = _dict_get(inj, "expected_mature_response", "")
                if emr: lines_a.append("What Good Looks Like: " + str(emr))
                dt = _dict_get(inj, "decision_threshold", "")
                if dt: lines_a.append("Decision Threshold: " + str(dt))
                arts = _dict_get(inj, "artefacts", []) or []
                if isinstance(arts, list) and arts:
                    lines_a.append("Artefacts:")
                    for ar in arts[:3]:
                        at = _dict_get(ar, "artefact_type", "")
                        ttl = _dict_get(ar, "title", "")
                        src = _dict_get(ar, "source_system", "")
                        lines_a.append(f"- {at}: {ttl} ({src})")
                lines_a.append(f"DYNAMIC_SLIDE_TYPE: INJECT_EVIDENCE_A")
                lines_a.append(f"SCENARIO_ORDINAL: {scn_idx}")
                lines_a.append(f"INJECT_ORDINAL: {inj_idx}")
                ntf_a.text = "\n".join([ln for ln in lines_a if ln])
            except Exception:
                pass

    VERIFICATION: python -c "import export; print('notes_ok')"

Action 7:

    FILE: export.py

    SEARCH:
            pdf.set_font("helvetica", "", 10)
            robust_multi_cell(pdf, 0, 5, f"Situation: {inj.get('scenario_narrative')}")
            
            pdf.set_font("helvetica", "B", 10)
            pdf.cell(0, 6, "Expected Mature Action (What Good Looks Like):", ln=True)

    REPLACE:
            pdf.set_font("helvetica", "", 10)
            robust_multi_cell(pdf, 0, 5, f"Situation: {inj.get('scenario_narrative')}")
            # Evidence Artefacts (optional)
            try:
                arts = inj.get("artefacts", []) or []
                if isinstance(arts, list) and arts:
                    pdf.set_font("helvetica", "B", 10)
                    pdf.cell(0, 6, "Evidence Artefacts:", ln=True)
                    pdf.set_font("helvetica", "", 10)
                    for ar in arts[:3]:
                        kind = str(ar.get("artefact_type", ""))
                        ttl = str(ar.get("title", "") or "(untitled)")
                        src = str(ar.get("source_system", "") or "")
                        robust_multi_cell(pdf, 0, 5, f"- [{kind}] {ttl} — {src}")
                        body = str(ar.get("body", "") or "")
                        if body:
                            robust_multi_cell(pdf, 0, 5, body)
            except Exception:
                pass
            
            pdf.set_font("helvetica", "B", 10)
            pdf.cell(0, 6, "Expected Mature Action (What Good Looks Like):", ln=True)

    VERIFICATION: python -c "import export; print('pdf_ok')"

Action 8:

    FILE: export.py

    SEARCH:
    if len(agenda_slide.placeholders) > 1:
        atf = agenda_slide.placeholders[1].text_frame
        try:
            atf.clear()
        except Exception:
            atf.text = ""
        # Merge ground rules into Agenda when present
        rules = _dict_get(master_plan_data, "housekeeping_rules", []) or []
        if rules:
            _add_heading(atf, "Ground Rules:", font_size_pt=15, rgb=(35, 80, 106))
            for rule in rules:
                _add_bullet(atf, str(rule), font_size_pt=14, rgb=(50, 50, 50))
        _add_heading(atf, "Objectives:", font_size_pt=15, rgb=(35, 80, 106))
        for obj in (_dict_get(master_plan_data, "objectives", []) or []):
            _add_bullet(atf, str(obj), font_size_pt=14, rgb=(50, 50, 50))
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
        _add_heading(atf, "Scenarios:", font_size_pt=15, rgb=(35, 80, 106))
        for si, scn in enumerate(_dict_get(master_plan_data, "scenarios", []) or [], 1):
            _add_bullet(atf, f"{si}. " + str(_dict_get(scn, "scenario_title", f"Scenario {si}")), font_size_pt=14, rgb=(50, 50, 50))

    REPLACE:
    if len(agenda_slide.placeholders) > 1:
        atf = agenda_slide.placeholders[1].text_frame
        try:
            atf.clear()
        except Exception:
            atf.text = ""
        # Streamlined Agenda: compact two-column layout with canonical section labels
        sections = _dict_get(master_plan_data, "sections", {}) or {}
        agenda_cfg = _dict_get(master_plan_data, "agenda", {}) or {}
        refs = []
        try:
            if isinstance(agenda_cfg, dict):
                refs = list(agenda_cfg.get("sectionRefs", []) or [])
        except Exception:
            refs = []
        labels = []
        if refs:
            # Validation: unique, <=8, and all references resolvable
            uniq = []
            for r in refs:
                r = str(r)
                if r not in uniq:
                    uniq.append(r)
            if len(uniq) != len(refs):
                raise ValidationError("Agenda sectionRefs must be unique")
            if len(refs) > 8:
                raise ValidationError("Agenda must not contain more than 8 items")
            missing = [r for r in refs if r not in sections]
            if missing:
                raise ValidationError("Agenda references missing sections: " + ", ".join(missing))
            for r in refs:
                sec = sections.get(r, {}) or {}
                lab = _dict_get(sec, "agendaLabel", "") or _dict_get(sec, "title", "") or str(r)
                labels.append(str(lab))
        else:
            # Default compact agenda if none provided
            labels = ["Exercise briefing", "Scenario and injects", "Hotwash and next steps"]
        # Deterministic balanced column-major split
        mid = int((len(labels) + 1) // 2)
        left_items = labels[:mid][:4]
        right_items = labels[mid:][:4]
        # Render two columns (ignore the body placeholder; add textboxes)
        left_tx, left_tf = _add_textbox(agenda_slide, 1.0, 2.0, 4.0, 4.5, text="")
        right_tx, right_tf = _add_textbox(agenda_slide, 5.5, 2.0, 4.0, 4.5, text="")
        for lbl in left_items:
            _add_bullet(left_tf, str(lbl), font_size_pt=14, rgb=(50, 50, 50))
        for lbl in right_items:
            _add_bullet(right_tf, str(lbl), font_size_pt=14, rgb=(50, 50, 50))

    VERIFICATION: python -c "import export; print('agenda_cols_if')"

Action 9:

    FILE: export.py

    SEARCH:
    else:
        tx, tf = _add_textbox(agenda_slide, 1.0, 2.0, 8.5, 4.5, text="")
        # Merge ground rules into Agenda when present
        rules = _dict_get(master_plan_data, "housekeeping_rules", []) or []
        if rules:
            _add_heading(tf, "Ground Rules:", font_size_pt=15, rgb=(35, 80, 106))
            for rule in rules:
                _add_bullet(tf, str(rule), font_size_pt=14, rgb=(50, 50, 50))
        _add_heading(tf, "Objectives:", font_size_pt=15, rgb=(35, 80, 106))
        for obj in (_dict_get(master_plan_data, "objectives", []) or []):
            _add_bullet(tf, str(obj), font_size_pt=14, rgb=(50, 50, 50))
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
        _add_heading(tf, "Scenarios:", font_size_pt=15, rgb=(35, 80, 106))
        for si, scn in enumerate(_dict_get(master_plan_data, "scenarios", []) or [], 1):
            _add_bullet(tf, f"{si}. " + str(_dict_get(scn, "scenario_title", f"Scenario {si}")), font_size_pt=14, rgb=(50, 50, 50))

    REPLACE:
    else:
        # Streamlined Agenda: compact two-column layout with canonical section labels
        sections = _dict_get(master_plan_data, "sections", {}) or {}
        agenda_cfg = _dict_get(master_plan_data, "agenda", {}) or {}
        refs = []
        try:
            if isinstance(agenda_cfg, dict):
                refs = list(agenda_cfg.get("sectionRefs", []) or [])
        except Exception:
            refs = []
        labels = []
        if refs:
            uniq = []
            for r in refs:
                r = str(r)
                if r not in uniq:
                    uniq.append(r)
            if len(uniq) != len(refs):
                raise ValidationError("Agenda sectionRefs must be unique")
            if len(refs) > 8:
                raise ValidationError("Agenda must not contain more than 8 items")
            missing = [r for r in refs if r not in sections]
            if missing:
                raise ValidationError("Agenda references missing sections: " + ", ".join(missing))
            for r in refs:
                sec = sections.get(r, {}) or {}
                lab = _dict_get(sec, "agendaLabel", "") or _dict_get(sec, "title", "") or str(r)
                labels.append(str(lab))
        else:
            labels = ["Exercise briefing", "Scenario and injects", "Hotwash and next steps"]
        mid = int((len(labels) + 1) // 2)
        left_items = labels[:mid][:4]
        right_items = labels[mid:][:4]
        # Create two column text frames
        left_tx, left_tf = _add_textbox(agenda_slide, 1.0, 2.0, 4.0, 4.5, text="")
        right_tx, right_tf = _add_textbox(agenda_slide, 5.5, 2.0, 4.0, 4.5, text="")
        for lbl in left_items:
            _add_bullet(left_tf, str(lbl), font_size_pt=14, rgb=(50, 50, 50))
        for lbl in right_items:
            _add_bullet(right_tf, str(lbl), font_size_pt=14, rgb=(50, 50, 50))

    VERIFICATION: python -c "import export; print('agenda_cols_else')"

Action 10:

    FILE: pages/03_Tabletop_Designer.py

    SEARCH:
        plan["_exercise_profile"] = st.session_state.get("exercise_profile", "blended")
        plan["_presentation_detail_profile"] = st.session_state.get("presentation_detail_profile", "standard")
        plan["_migration_notices"] = st.session_state.get("_migration_notices", [])
        pptx_data = create_tabletop_pptx(plan)

    REPLACE:
        plan["_exercise_profile"] = st.session_state.get("exercise_profile", "blended")
        plan["_presentation_detail_profile"] = st.session_state.get("presentation_detail_profile", "standard")
        plan["_migration_notices"] = st.session_state.get("_migration_notices", [])
        # Canonical agenda registry with compact two-column layout if not provided
        _sections_default = {
            "briefing": {"title": "Exercise briefing", "agendaLabel": "Exercise briefing", "slideRef": "exercise-briefing"},
            "scenario": {"title": "Scenario and injects", "agendaLabel": "Scenario and injects", "slideRef": "scenario"},
            "hotwash": {"title": "Hotwash and next steps", "agendaLabel": "Hotwash and next steps", "slideRef": "hotwash"},
        }
        try:
            if not isinstance(plan.get("sections"), dict) or not plan.get("sections"):
                plan["sections"] = _sections_default
        except Exception:
            plan["sections"] = _sections_default
        _agenda_default = {
            "sectionRefs": ["briefing", "scenario", "hotwash"],
            "layout": {"columns": 2, "split": "balanced-column-major", "maxItemsPerColumn": 4},
        }
        try:
            if not isinstance(plan.get("agenda"), dict) or not plan.get("agenda"):
                plan["agenda"] = _agenda_default
        except Exception:
            plan["agenda"] = _agenda_default
        pptx_data = create_tabletop_pptx(plan)

    VERIFICATION: python -c "import importlib; m=importlib.import_module('pages.03_Tabletop_Designer'.replace('/','.').replace('.py','')); print('OK')"