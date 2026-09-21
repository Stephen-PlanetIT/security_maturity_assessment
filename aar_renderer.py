"""
AAR Renderer — transforms internal Tabletop AAR objects and session notes
into clean, client-facing context for docxtpl. Provides sanitisation, validation,
template schema detection and a DOCX QA scan.
British English; consultative tone; evidence-led.
"""
from __future__ import annotations

import io
import re
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Optional

# Patterns
ISO_PAT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
RAW_JSONISH = re.compile(r"^\s*[\{\[].*[\}\]]\s*$")
PLACEHOLDER_ARTIFACTS = re.compile(r"\[(?:AM NAME|Customer|CLIENT|INSERT[^\]]*)\]")

# Supported keys for the flattened AAR template
SUPPORTED_KEYS = {
    # Core scalars
    "customer_name",
    "exercise_title",
    "exercise_id",
    "exercise_date",
    "start_time",
    "end_time",
    "exercise_location",
    "delivery_mode",
    "audience_profile",
    "report_status",
    "report_version",
    "information_classification",
    "facilitator_review_display",
    "overall_maturity_observed",
    "maturity_rationale",
    "executive_summary",
    "facilitator_observations",
    "delta_notes_for_profile",
    # Lists
    "scenarios",
    "red_flags",
    "strengths_render",
    "gaps_render",
    "actions_render",
    "exercise_limitations",
    "approved_distribution",
    "profile_changes",
    # Display/text blocks
    "session_notes_render",
    "capability_heatmap_text",
    # Appendix/governance extras
    "consultant_name",
    "account_manager_name",
    "generated_at",
    "approval_date_display",
    "report_approver_display",
    # Always-on marketing (values only; sections stay in template)
    "marketing_why_planet",
    "marketing_pedigree",
    "marketing_contacts",
    "marketing_assumptions_text",
    "marketing_tcs_text",
}


# ---------- Sanitisation helpers ----------

def _is_empty(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        return len(v.strip()) == 0
    if isinstance(v, (list, tuple, set, dict)):
        return len(v) == 0
    return False


def sanitize_text(s: Any) -> str:
    if s is None:
        return ""
    txt = str(s)
    if txt.strip() in ("None", "null", "[]", "{}"):
        return ""
    # If the entire field is an ISO timestamp, convert to UK-friendly
    if ISO_PAT.match(txt.strip()):
        try:
            dt = datetime.fromisoformat(txt.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc).strftime("%-d %B %Y, %H:%M")
        except Exception:
            pass
    txt = PLACEHOLDER_ARTIFACTS.sub("", txt)
    # Collapse excessive whitespace
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def sanitize_list(vals: Any) -> List[str]:
    out: List[str] = []
    if isinstance(vals, (list, tuple, set)):
        for v in vals:
            t = sanitize_text(v)
            if t:
                out.append(t)
    elif not _is_empty(vals):
        t = sanitize_text(vals)
        if t:
            out.append(t)
    return out


def format_date_uk(d: Any) -> str:
    try:
        # datetime instance
        if isinstance(d, datetime):
            return d.astimezone(timezone.utc).strftime("%-d %B %Y")
        # date-like object with strftime but not a plain string
        if hasattr(d, "strftime") and not isinstance(d, str):
            try:
                return d.strftime("%-d %B %Y")
            except Exception:
                pass
        # ISO string (handle trailing Z)
        if isinstance(d, str) and d.strip():
            s = d.strip()
            if s.endswith("Z"):
                s = s.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            return dt.astimezone(timezone.utc).strftime("%-d %B %Y")
    except Exception:
        pass
    return sanitize_text(d)


def format_time_short(t: Any) -> str:
    try:
        s = str(t).strip()
        if ISO_PAT.match(s):
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt.strftime("%H:%M")
        if re.match(r"^\d{1,2}:\d{2}$", s):
            return s
    except Exception:
        pass
    return sanitize_text(t)


# ---------- Accessors ----------

def _get(o: Any, key: str, default: Any = "") -> Any:
    if isinstance(o, dict):
        return o.get(key, default)
    return getattr(o, key, default)


# ---------- Section renderers ----------

def render_executive_summary(aar_obj: Any) -> str:
    return sanitize_text(_get(aar_obj, "executive_summary"))


def render_session_notes(session_notes: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for n in session_notes or []:
        scenario = sanitize_text(n.get("scenario", ""))
        phase = sanitize_text(n.get("phase", ""))
        decision = sanitize_text(n.get("decision", ""))
        notes = sanitize_text(n.get("notes", ""))
        tm = format_time_short(n.get("simulated_timestamp", ""))
        parts = [
            p
            for p in [
                f"Scenario: {scenario}" if scenario else "",
                f"Inject: {phase}" if phase else "",
                f"Decision: {decision}" if decision else "",
                f"Notes: {notes}" if notes else "",
                f"Time: {tm}" if tm else "",
            ]
            if p
        ]
        if parts:
            lines.append("- " + " | ".join(parts))
    return "\n".join(lines)


def render_strength(obs: Any) -> str:
    summary = sanitize_text(_get(obs, "summary"))
    if not summary:
        return ""
    return f"{summary}. This demonstrated practical, evidence-led response during the exercise."


def render_gap(obs: Any) -> str:
    summary = sanitize_text(_get(obs, "summary"))
    rationale = sanitize_text(_get(obs, "rationale"))
    if not summary:
        return ""
    implication = rationale or "This may delay decisions and containment during a live incident."
    return f"{summary}. {implication}"


def render_action(a: Any) -> str:
    pr = sanitize_text(_get(a, "priority"))
    rec = sanitize_text(_get(a, "recommendation"))
    rat = sanitize_text(_get(a, "rationale"))
    owner = sanitize_text(_get(a, "accountable_owner"))
    evidence = sanitize_text(_get(a, "closure_evidence"))
    parts: List[str] = []
    if rec:
        parts.append(f"{pr + ' priority — ' if pr else ''}{rec}.")
    if rat:
        parts.append(rat if rat.endswith(".") else rat + ".")
    if owner:
        parts.append(f"Suggested owner: {owner}.")
    if evidence:
        parts.append(f"Evidence of completion: {evidence}.")
    return " ".join(parts).strip()


def render_capability_heatmap(items: List[Any]) -> str:
    if not items:
        return ""
    lines = ["Capability\tMaturity"]
    for ca in items:
        cap = sanitize_text(_get(ca, "capability"))
        mat = sanitize_text(_get(ca, "maturity"))
        if cap or mat:
            lines.append(f"{cap}\t{mat}")
    return "\n".join(lines)


def render_facilitator_observations(txt: Any) -> str:
    return sanitize_text(txt)


def render_red_flag(issue: Dict[str, Any], idx: int, scenarios: List[Any]) -> Dict[str, str]:
    """
    Returns dict with keys: issue_id, discovered_scenario, issue, proposed_resolution, owner
    """
    disc = sanitize_text(issue.get("discovered_scenario", "")) or "Session-wide"
    scn_ref = sanitize_text(issue.get("scenario") or issue.get("scenario_reference") or "")
    if scn_ref.isdigit():
        disc = f"Scenario {scn_ref}"
    elif scn_ref:
        m = re.search(r"(\d+)", scn_ref)
        if m:
            disc = f"Scenario {int(m.group(1))}"
    return {
        "issue_id": str(idx),
        "discovered_scenario": disc,
        "issue": sanitize_text(issue.get("issue") or issue.get("summary") or ""),
        "proposed_resolution": sanitize_text(issue.get("proposed_resolution") or issue.get("recommendation") or ""),
        "owner": sanitize_text(issue.get("owner") or "Client / Planet IT"),
    }


# ---------- Scenario/inject sanitisation ----------

def sanitize_scenario(scn: Any, seq: int) -> Dict[str, Any]:
    get = (lambda k: (scn.get(k) if isinstance(scn, dict) else getattr(scn, k, "")))
    title = sanitize_text(get("title") or get("scenario_title") or f"Scenario {seq}")
    summary = sanitize_text(get("summary") or get("scenario_theme") or get("initial_vector"))
    objectives = sanitize_list(get("objectives"))
    capabilities = sanitize_list(get("capabilities_exercised"))
    expected_outcomes = sanitize_list(get("expected_outcomes"))
    outcome_summary = sanitize_text(get("outcome_summary"))
    inj_list = []
    raw_injs = get("injects") or []
    for idx, inj in enumerate(raw_injs, 1):
        inj_get = (lambda k: (inj.get(k) if isinstance(inj, dict) else getattr(inj, k, "")))
        resp = sanitize_text(inj_get("response_observed") or inj_get("expected_mature_response"))
        inj_list.append({
            "sequence": idx,
            "simulated_time": format_time_short(inj_get("simulated_time") or inj_get("simulated_timestamp")),
            "information_presented": sanitize_text(inj_get("information_presented") or inj_get("scenario_narrative")),
            "intended_capability": sanitize_text(inj_get("intended_capability") or inj_get("phase_title")),
            "response_observed": resp or "No specific response was recorded during the session.",
            "decision_owner": sanitize_text(inj_get("decision_owner")),
            "outcome": sanitize_text(inj_get("outcome")),
        })
    return {
        "sequence": seq,
        "title": title,
        "summary": summary,
        "objectives": objectives,
        "capabilities_exercised": capabilities,
        "expected_outcomes": expected_outcomes,
        "outcome_summary": outcome_summary,
        "injects": inj_list,
    }


# ---------- Context builder, validation, QA, schema ----------

def build_aar_context(master_plan: Dict[str, Any], session_notes: List[Dict[str, Any]], aar_obj: Any, flags: Dict[str, Any]) -> Dict[str, Any]:
    g = lambda k: _get(aar_obj, k)
    ctx: Dict[str, Any] = {
        "customer_name": sanitize_text(g("customer_name")),
        "exercise_title": sanitize_text(g("exercise_title")),
        "exercise_id": sanitize_text(g("exercise_id")),
        "exercise_date": format_date_uk(g("exercise_date")),
        "start_time": format_time_short(g("start_time")),
        "end_time": format_time_short(g("end_time")),
        "exercise_location": sanitize_text(g("exercise_location")),
        "delivery_mode": sanitize_text(g("delivery_mode")),
        "audience_profile": sanitize_text(g("audience_profile")),
        "report_status": sanitize_text(g("report_status")),
        "report_version": sanitize_text(g("report_version")),
        "information_classification": sanitize_text(g("information_classification")),
        "overall_maturity_observed": sanitize_text(g("overall_maturity_observed")),
        "maturity_rationale": sanitize_text(g("maturity_rationale")),
        # Appendix/governance
        "consultant_name": sanitize_text(_get(aar_obj, "consultant_name") or _get(master_plan, "consultant_name")),
        "account_manager_name": sanitize_text(_get(aar_obj, "account_manager_name") or _get(master_plan, "account_manager_name")),
        "generated_at": format_date_uk(_get(aar_obj, "generated_at") or datetime.now(timezone.utc).isoformat(timespec="seconds")),
        "approval_date_display": format_date_uk(_get(aar_obj, "approval_date_display")),
        "report_approver_display": sanitize_text(_get(aar_obj, "report_approver_display")),
    }
    # Narrative
    ctx["executive_summary"] = render_executive_summary(aar_obj)
    ctx["session_notes_render"] = render_session_notes(session_notes or [])
    # Scenarios
    scenarios = []
    for i, scn in enumerate(_get(aar_obj, "scenarios", []) or [], 1):
        scenarios.append(sanitize_scenario(scn, i))
    ctx["scenarios"] = scenarios

    # Evidence gating for strengths/gaps
    def strong_enough(o) -> bool:
        src = str(_get(o, "evidence_source", "")).strip().lower()
        conf = str(_get(o, "confidence", "")).strip().lower()
        if "observ" in src or "demonstr" in src:
            return True
        if conf in ("high", "med", "medium"):
            return True
        return False

    fac_obs_lines: List[str] = []
    strengths = _get(aar_obj, "key_strengths", []) or []
    gaps = _get(aar_obj, "critical_gaps_identified", []) or []
    actions = _get(aar_obj, "improvement_actions", []) or []

    strengths_render = []
    for o in strengths:
        s = render_strength(o)
        if not s:
            continue
        if strong_enough(o):
            strengths_render.append(s)
        else:
            fac_obs_lines.append(s + " (for validation)")
    gaps_render = []
    for o in gaps:
        s = render_gap(o)
        if not s:
            continue
        if strong_enough(o):
            gaps_render.append(s)
        else:
            fac_obs_lines.append(s + " (for validation)")

    ctx["strengths_render"] = strengths_render
    ctx["gaps_render"] = gaps_render
    ctx["actions_render"] = [s for s in (render_action(a) for a in actions) if s]
    ctx["capability_heatmap_text"] = render_capability_heatmap(_get(aar_obj, "capability_assessments", []) or [])
    ctx["exercise_limitations"] = sanitize_list(_get(aar_obj, "exercise_limitations", []) or [])
    ctx["approved_distribution"] = sanitize_list(_get(aar_obj, "approved_distribution", []) or [])
    ctx["profile_changes"] = [pc for pc in (_get(aar_obj, "profile_changes", []) or []) if pc]

    # Red Flags: ensure fields present and sanitised
    rf_src = _get(aar_obj, "red_flags", []) or []
    red_flags: List[Dict[str, str]] = []
    if isinstance(rf_src, list) and rf_src:
        for i, rf in enumerate(rf_src, 1):
            red_flags.append(render_red_flag(rf, i, scenarios))
    ctx["red_flags"] = red_flags

    # Facilitator observations (weak/inferred)
    existing_obs = sanitize_text(_get(aar_obj, "facilitator_observations"))
    combined = ("\n".join(fac_obs_lines)).strip()
    ctx["facilitator_observations"] = (existing_obs + ("\n" if existing_obs and combined else "") + combined).strip()

    # Drop empty scalars/lists (template should gate empty blocks)
    for k in list(ctx.keys()):
        v = ctx[k]
        if isinstance(v, str) and not v.strip():
            ctx[k] = ""
        elif isinstance(v, list) and len(v) == 0:
            ctx[k] = []

    return ctx


def validate_aar_context(ctx: Dict[str, Any], allowed_keys: Optional[set] = None, strict: bool = True) -> Tuple[bool, List[str]]:
    allowed = set(allowed_keys) if allowed_keys else SUPPORTED_KEYS
    defects: List[str] = []

    # Key whitelist
    unknown = [k for k in ctx.keys() if k not in allowed]
    if unknown:
        defects.append(f"AAR-KEY-001: Unknown keys present: {', '.join(sorted(unknown))}")

    # Scan strings for forbidden content
    def _scan(s: str, field: str):
        if s is None:
            return
        if RAW_JSONISH.match(s or ""):
            defects.append(f"AAR-TXT-201: Raw JSON-like text in '{field}'")
        if s in ("None", "null"):
            defects.append(f"AAR-TXT-202: Literal None/null in '{field}'")
        if ISO_PAT.match((s or "").strip()):
            defects.append(f"AAR-TXT-203: ISO timestamp leaked in '{field}'")
        if PLACEHOLDER_ARTIFACTS.search(s or ""):
            defects.append(f"AAR-TXT-204: Placeholder artefact leaked in '{field}'")
        if "AI-assisted" in (s or "") or "LLM" in (s or "") or "generated by AI" in (s or ""):
            defects.append(f"AAR-TXT-205: AI wording leaked in '{field}'")

    for k, v in ctx.items():
        if isinstance(v, str):
            _scan(v, k)
        elif isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, str):
                    _scan(item, f"{k}[{i}]")
                elif isinstance(item, dict):
                    for sub_k, sub_v in item.items():
                        if isinstance(sub_v, str):
                            _scan(sub_v, f"{k}.{sub_k}[{i}]")

    # Red flag completeness
    for i, rf in enumerate(ctx.get("red_flags", []) or []):
        for req in ("issue", "proposed_resolution", "discovered_scenario", "owner"):
            if not sanitize_text(rf.get(req, "")):
                defects.append(f"AAR-RF-401: red_flags[{i}].{req} missing")

    ok = (not defects) if strict else (len([d for d in defects if not d.startswith("AAR-KEY-")]) == 0)
    return ok, defects


def qa_scan_docx_bytes(docx_bytes: bytes) -> Tuple[bool, List[str]]:
    """
    Scan the generated DOCX XML for obvious client-visible defects.
    """
    issues: List[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(docx_bytes), 'r') as z:
            texts = []
            for name in z.namelist():
                if name.endswith(".xml"):
                    try:
                        data = z.read(name).decode("utf-8", errors="ignore")
                        texts.append(data)
                    except Exception:
                        continue
            blob = "\n".join(texts)
            for tok, code in [
                ("None", "QA-001"),
                ("null", "QA-002"),
                ("[AM NAME]", "QA-003"),
                ("AI-assisted", "QA-004"),
                ("{{", "QA-005"),
                ("}}", "QA-005"),
            ]:
                if tok in blob:
                    issues.append(f"{code}: Found '{tok}' in document xml")
            if re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", blob):
                issues.append("QA-006: ISO timestamp pattern found")
    except Exception:
        issues.append("QA-999: Could not open DOCX for QA scan")
    return (len(issues) == 0), issues


def _detect_template_schema_version(docx_path: str) -> str:
    """
    Extract a simple schema marker from the DOCX XML:
      template_schema_version: SOMETHING
    Returns the value or "" if not found.
    """
    try:
        with zipfile.ZipFile(docx_path, 'r') as z:
            for name in z.namelist():
                if name.endswith(".xml"):
                    try:
                        data = z.read(name).decode("utf-8", errors="ignore")
                        m = re.search(r"template_schema_version\s*:\s*([A-Za-z0-9_\-\.]+)", data)
                        if m:
                            return m.group(1).strip()
                    except Exception:
                        continue
    except Exception:
        return ""
    return ""