Objective: Restore Monte Carlo section rendering in the Maturity DOCX and ensure the humanisation pass performs inline edits without suggestion blocks.

Action [1]:

    FILE: export.py

    SEARCH: def _inject_monte_carlo_section_after_render(doc, mc, mc_text: str = ""):
        """
        Insert a formatted Monte Carlo section at the {{ monte_carlo_section }} anchor, if present; otherwise append at end.
        Renders:
          - Heading: "Monte Carlo Risk Analysis"
          - Summary line with breach probability, AAL, P50/P90/P95/CVaR95
          - Consultant’s interpretation (LLM narrative) if provided
          - Deterministic interpretation paragraph (fallback)
          - Top Exposure Drivers as bullet points (if provided)
          - Assumptions as bullet points (if provided)
        """
        from docx.shared import Pt
        from docx.oxml import OxmlElement
        from docx.text.paragraph import Paragraph

        # Do not return early; we may still need to remove the placeholder even if MC is unavailable
        mc_valid = isinstance(mc, dict) and bool(mc)

        def _new_para_after(prev_el, body_parent, style=None):
            new_p = OxmlElement('w:p')
            prev_el.addnext(new_p)
            para = Paragraph(new_p, body_parent)
            if style:
                try:
                    para.style = style
                except Exception:
                    pass
            return para, new_p

        def _append_para(doc_obj, style=None):
            para = doc_obj.add_paragraph()
            if style:
                try:
                    para.style = style
                except Exception:
                    pass
            return para

        # Locate anchor using tolerant regex (supports NBSP and underscores), scanning body and table cells
        placeholder_element = None
        body_parent = None
        try:
            import re as _re_norm
        except Exception:
            _re_norm = re

        ANCHOR_PATTERNS = [
            _re_norm.compile("\\{\\{\\s*monte[\\s_\\u00A0]*carlo[\\s_\\u00A0]*section\\s*\\}\}", _re_norm.IGNORECASE),
            _re_norm.compile("\\{\\{\\s*mc[\\s_\\u00A0]*section\\s*\\}\}", _re_norm.IGNORECASE),
        ]

        def _iter_all_paragraphs(doc_obj):
            for p in doc_obj.paragraphs:
                yield p
            for tbl in getattr(doc_obj, 'tables', []) or []:
                for row in tbl.rows:
                    for cell in row.cells:
                        for cp in cell.paragraphs:
                            yield cp

        for paragraph in _iter_all_paragraphs(doc):
            txt = (paragraph.text or '').replace('\u00A0', ' ')
            if any(pat.search(txt) for pat in ANCHOR_PATTERNS):
                placeholder_element = paragraph._element
                body_parent = paragraph._parent
                break

        # If MC data is unavailable, remove the placeholder if found and stop
        if not mc_valid:
            if placeholder_element is not None and body_parent is not None:
                placeholder_element.getparent().remove(placeholder_element)
            return

        def _render(after_el=None, body_parent_ref=None):
            # Heading
            if after_el is not None and body_parent_ref is not None:
                h_para, new_el = _new_para_after(after_el, body_parent_ref)
            else:
                h_para = _append_para(doc)
                new_el = None
            run = h_para.add_run("Monte Carlo Risk Analysis")
            run.bold = True
            run.font.size = Pt(13)

            # Summary line
            br = float(mc.get('breach_probability_pct', 0.0))
            aal = float(mc.get('aal_gbp', 0.0))
            p50 = float(mc.get('p50_gbp', 0.0))
            p90 = float(mc.get('p90_gbp', 0.0))
            p95 = float(mc.get('p95_gbp', 0.0))
            cvar95 = float(mc.get('cvar95_gbp', 0.0))
            summary_text = (
                f"Estimated annual breach probability: {br:.1f}% | AAL: £{aal:,.0f} | "
                f"P50: £{p50:,.0f} | P90: £{p90:,.0f} | P95: £{p95:,.0f} | CVaR95: £{cvar95:,.0f}"
            )
            if after_el is not None and body_parent_ref is not None:
                s_para, new_el = _new_para_after(new_el or after_el, body_parent_ref)
            else:
                s_para = _append_para(doc)
            s_para.add_run(summary_text)

        # Consultant’s interpretation (LLM) and deterministic fallback
        if isinstance(mc_text, str) and mc_text.strip():
            if after_el is not None and body_parent_ref is not None:
                ci_head, new_el = _new_para_after(new_el, body_parent_ref)
            else:
                ci_head = _append_para(doc)
            ci_run = ci_head.add_run("Consultant’s interpretation")
            ci_run.bold = True
            ci_run.font.size = Pt(11)
            if after_el is not None and body_parent_ref is not None:
                ci_para, new_el = _new_para_after(new_el, body_parent_ref)
            else:
                ci_para = _append_para(doc)
            ci_para.add_run(str(mc_text))

        expl = mc.get('explanation')
        if expl:
            if after_el is not None and body_parent_ref is not None:
                i_head, new_el = _new_para_after(new_el, body_parent_ref)
            else:
                i_head = _append_para(doc)
            i_run = i_head.add_run("What these numbers mean")
            i_run.bold = True
            i_run.font.size = Pt(11)
            if after_el is not None and body_parent_ref is not None:
                i_para, new_el = _new_para_after(new_el, body_parent_ref)
            else:
                i_para = _append_para(doc)
            i_para.add_run(str(expl))

        # Top Exposure Drivers (if any)
        drivers = mc.get('drivers') or []
        if drivers:
            if after_el is not None and body_parent_ref is not None:
                d_head, new_el = _new_para_after(new_el, body_parent_ref)
            else:
                d_head = _append_para(doc)
            d_run = d_head.add_run("Top Exposure Drivers")
            d_run.bold = True
            d_run.font.size = Pt(11)
            for d in drivers[:3]:
                if after_el is not None and body_parent_ref is not None:
                    d_para, new_el = _new_para_after(new_el, body_parent_ref, style='List Bullet')
                else:
                    d_para = _append_para(doc, style='List Bullet')
                d_para.add_run(str(d))

        # Optional assumptions
        assumptions = mc.get('assumptions', []) or []
        if assumptions:
            if after_el is not None and body_parent_ref is not None:
                a_head, new_el = _new_para_after(new_el, body_parent_ref)
            else:
                a_head = _append_para(doc)
            a_run = a_head.add_run("Assumptions")
            a_run.bold = True
            a_run.font.size = Pt(11)
            for a in assumptions:
                if after_el is not None and body_parent_ref is not None:
                    b_para, new_el = _new_para_after(new_el, body_parent_ref, style='List Bullet')
                else:
                    b_para = _append_para(doc, style='List Bullet')
                b_para.add_run(str(a))

        if placeholder_element is not None and body_parent is not None:
            _render(after_el=placeholder_element, body_parent_ref=body_parent)
            placeholder_element.getparent().remove(placeholder_element)
        else:
            _render(after_el=None, body_parent_ref=None)

    REPLACE: def _inject_monte_carlo_section_after_render(doc, mc, mc_text: str = ""):
        """
        Insert a formatted Monte Carlo section at the {{ monte_carlo_section }} anchor, if present; otherwise append at end.
        Renders:
          - Heading: "Monte Carlo Risk Analysis"
          - Summary line with breach probability, AAL, P50/P90/P95/CVaR95
          - Consultant’s interpretation (LLM narrative) if provided
          - Deterministic interpretation paragraph (fallback)
          - Top Exposure Drivers as bullet points (if provided)
          - Assumptions as bullet points (if provided)
        """
        from docx.shared import Pt
        from docx.oxml import OxmlElement
        from docx.text.paragraph import Paragraph

        # Do not return early; we may still need to remove the placeholder even if MC is unavailable
        mc_valid = isinstance(mc, dict) and bool(mc)

        def _new_para_after(prev_el, body_parent, style=None):
            new_p = OxmlElement('w:p')
            prev_el.addnext(new_p)
            para = Paragraph(new_p, body_parent)
            if style:
                try:
                    para.style = style
                except Exception:
                    pass
            return para, new_p

        def _append_para(doc_obj, style=None):
            para = doc_obj.add_paragraph()
            if style:
                try:
                    para.style = style
                except Exception:
                    pass
            return para

        # Locate anchor using tolerant regex (supports NBSP and underscores), scanning body and table cells
        placeholder_element = None
        body_parent = None
        try:
            import re as _re_norm
        except Exception:
            _re_norm = re

        ANCHOR_PATTERNS = [
            _re_norm.compile("\\{\\{\\s*monte[\\s_\\u00A0]*carlo[\\s_\\u00A0]*section\\s*\\}\}", _re_norm.IGNORECASE),
            _re_norm.compile("\\{\\{\\s*mc[\\s_\\u00A0]*section\\s*\\}\}", _re_norm.IGNORECASE),
        ]

        def _iter_all_paragraphs(doc_obj):
            for p in doc_obj.paragraphs:
                yield p
            for tbl in getattr(doc_obj, 'tables', []) or []:
                for row in tbl.rows:
                    for cell in row.cells:
                        for cp in cell.paragraphs:
                            yield cp

        for paragraph in _iter_all_paragraphs(doc):
            txt = (paragraph.text or '').replace('\u00A0', ' ')
            if any(pat.search(txt) for pat in ANCHOR_PATTERNS):
                placeholder_element = paragraph._element
                body_parent = paragraph._parent
                break

        # If MC data is unavailable, remove the placeholder if found and stop
        if not mc_valid:
            if placeholder_element is not None and body_parent is not None:
                placeholder_element.getparent().remove(placeholder_element)
            return

        def _render(after_el=None, body_parent_ref=None):
            # Heading
            if after_el is not None and body_parent_ref is not None:
                h_para, new_el = _new_para_after(after_el, body_parent_ref)
            else:
                h_para = _append_para(doc)
                new_el = None
            run = h_para.add_run("Monte Carlo Risk Analysis")
            run.bold = True
            run.font.size = Pt(13)

            # Summary line
            br = float(mc.get('breach_probability_pct', 0.0))
            aal = float(mc.get('aal_gbp', 0.0))
            p50 = float(mc.get('p50_gbp', 0.0))
            p90 = float(mc.get('p90_gbp', 0.0))
            p95 = float(mc.get('p95_gbp', 0.0))
            cvar95 = float(mc.get('cvar95_gbp', 0.0))
            summary_text = (
                f"Estimated annual breach probability: {br:.1f}% | AAL: £{aal:,.0f} | "
                f"P50: £{p50:,.0f} | P90: £{p90:,.0f} | P95: £{p95:,.0f} | CVaR95: £{cvar95:,.0f}"
            )
            if after_el is not None and body_parent_ref is not None:
                s_para, new_el = _new_para_after(new_el or after_el, body_parent_ref)
            else:
                s_para = _append_para(doc)
            s_para.add_run(summary_text)

            # Consultant’s interpretation (LLM) and deterministic fallback
            if isinstance(mc_text, str) and mc_text.strip():
                if after_el is not None and body_parent_ref is not None:
                    ci_head, new_el = _new_para_after(new_el, body_parent_ref)
                else:
                    ci_head = _append_para(doc)
                ci_run = ci_head.add_run("Consultant’s interpretation")
                ci_run.bold = True
                ci_run.font.size = Pt(11)
                if after_el is not None and body_parent_ref is not None:
                    ci_para, new_el = _new_para_after(new_el, body_parent_ref)
                else:
                    ci_para = _append_para(doc)
                ci_para.add_run(str(mc_text))

            expl = mc.get('explanation')
            if expl:
                if after_el is not None and body_parent_ref is not None:
                    i_head, new_el = _new_para_after(new_el, body_parent_ref)
                else:
                    i_head = _append_para(doc)
                i_run = i_head.add_run("What these numbers mean")
                i_run.bold = True
                i_run.font.size = Pt(11)
                if after_el is not None and body_parent_ref is not None:
                    i_para, new_el = _new_para_after(new_el, body_parent_ref)
                else:
                    i_para = _append_para(doc)
                i_para.add_run(str(expl))

            # Top Exposure Drivers (if any)
            drivers = mc.get('drivers') or []
            if drivers:
                if after_el is not None and body_parent_ref is not None:
                    d_head, new_el = _new_para_after(new_el, body_parent_ref)
                else:
                    d_head = _append_para(doc)
                d_run = d_head.add_run("Top Exposure Drivers")
                d_run.bold = True
                d_run.font.size = Pt(11)
                for d in drivers[:3]:
                    if after_el is not None and body_parent_ref is not None:
                        d_para, new_el = _new_para_after(new_el, body_parent_ref, style='List Bullet')
                    else:
                        d_para = _append_para(doc, style='List Bullet')
                    d_para.add_run(str(d))

            # Optional assumptions
            assumptions = mc.get('assumptions', []) or []
            if assumptions:
                if after_el is not None and body_parent_ref is not None:
                    a_head, new_el = _new_para_after(new_el, body_parent_ref)
                else:
                    a_head = _append_para(doc)
                a_run = a_head.add_run("Assumptions")
                a_run.bold = True
                a_run.font.size = Pt(11)
                for a in assumptions:
                    if after_el is not None and body_parent_ref is not None:
                        b_para, new_el = _new_para_after(new_el, body_parent_ref, style='List Bullet')
                    else:
                        b_para = _append_para(doc, style='List Bullet')
                    b_para.add_run(str(a))

        if placeholder_element is not None and body_parent is not None:
            _render(after_el=placeholder_element, body_parent_ref=body_parent)
            placeholder_element.getparent().remove(placeholder_element)
        else:
            _render(after_el=None, body_parent_ref=None)

    VERIFICATION: python -c "import export; print('OK')"

Action [2]:

    FILE: quality_pipeline.py

    SEARCH: def humanise_text_with_llm(section_text: str) -> str:
        if not stage_enabled("HUMANISATION_ENABLED", "0") or not section_text:
            return section_text
        try:
            # Import inside function to avoid hard dependency/cycles
            from core import LLMEngine
            from config import get_config, ConfigKey  # type: ignore
            from prompts import SYSTEM_PERSONA  # type: ignore
            client = LLMEngine.get_client()
            deployment = get_config("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
            prompt = (
                "Review this report as a senior cybersecurity consultant. "
                "Identify: - repetitive wording - AI phrasing - overclaiming - excessive vendor references - generic observations. "
                "Rewrite affected sections only. Preserve technical meaning.\n\n" + section_text
            )
            improved = LLMEngine.generate_text_report(client, deployment, SYSTEM_PERSONA, prompt, temperature=0.2)
            return improved or section_text
        except Exception:
            # Fail closed to original text if LLM unavailable
            return section_text

    REPLACE: def humanise_text_with_llm(section_text: str) -> str:
        if not stage_enabled("HUMANISATION_ENABLED", "0") or not section_text:
            return section_text
        try:
            # Import inside function to avoid hard dependency/cycles
            from core import LLMEngine
            from config import get_config, ConfigKey  # type: ignore
            from prompts import SYSTEM_PERSONA  # type: ignore
            client = LLMEngine.get_client()
            deployment = get_config("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
            prompt = (
                "Rewrite the following text directly, applying light human edits to tone, clarity, and repetition. "
                "Do not add headings, labels, or commentary. Return only the revised text — no ‘Suggestion’, ‘Before/After’, bullets of edits, or code blocks. "
                "Preserve technical meaning and use British English.\n\nTEXT START\n" + section_text + "\nTEXT END"
            )
            improved = LLMEngine.generate_text_report(client, deployment, SYSTEM_PERSONA, prompt, temperature=0.2)
            if not improved:
                return section_text
            # Defensive sanitiser: strip any suggestion-style artefacts if the model ignores instructions
            cleaned = re.sub(r"(?im)^(?:suggest(?:ion|ed)\s*(?:edits?)?|before|after|change|replace)\s*[:：].*$", "", improved)
            cleaned = re.sub(r"(?s)```.*?```", "", cleaned)
            cleaned = re.sub(r"(?im)^\s*\*\s*(?:suggestion|edit|note)\s*[:：].*$", "", cleaned)
            cleaned = cleaned.strip()
            return cleaned if cleaned else section_text
        except Exception:
            # Fail closed to original text if LLM unavailable
            return section_text

    VERIFICATION: python -c "import quality_pipeline, sys; print(quality_pipeline.humanise_text_with_llm('Suggestion: Replace this sentence with clearer prose.'))"

[PLAN_COMPLETE: AWAITING EXECUTION]