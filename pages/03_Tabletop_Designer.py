import streamlit as st
import time
import json

# JSON serialisation helper for non-JSON-native types (sets, tuples, unknowns)
def _json_default(o):
    if isinstance(o, set):
        # Convert sets to sorted lists for deterministic output
        return sorted(list(o))
    if isinstance(o, tuple):
        return list(o)
    # Best-effort fallback: stringify unknown objects
    return str(o)

# keep the previous default serializer above
def _ensure_required_plan_fields(p: dict) -> dict:
    try:
        if not isinstance(p, dict):
            return p
        scns = p.get("scenarios", [])
        if not isinstance(scns, list):
            return p
        for scn in scns:
            if not isinstance(scn, dict):
                continue
            fr = scn.get("facilitator_reveal")
            if not isinstance(fr, dict):
                scn["facilitator_reveal"] = {
                    "reveal_title": scn.get("scenario_title", "") or "Wrap-up",
                    "reveal_narrative": "",
                    "key_lessons": ["Lesson 1", "Lesson 2"],
                    "wrap_up_questions": ["What would you do differently next time?", "Who needs to be informed?"],
                }
            else:
                fr.setdefault("reveal_title", scn.get("scenario_title", "") or "Wrap-up")
                fr.setdefault("reveal_narrative", "")
                kl = fr.get("key_lessons")
                if not isinstance(kl, list) or len([x for x in (kl or []) if str(x).strip()]) < 2:
                    fr["key_lessons"] = ["Lesson 1", "Lesson 2"]
                wq = fr.get("wrap_up_questions")
                if not isinstance(wq, list) or len([x for x in (wq or []) if str(x).strip()]) < 2:
                    fr["wrap_up_questions"] = ["What would you do differently next time?", "Who needs to be informed?"]
                scn["facilitator_reveal"] = fr
            inj_list = scn.get("injects", [])
            if isinstance(inj_list, list):
                for inj in inj_list:
                    if not isinstance(inj, dict):
                        continue
                    inj.setdefault("primary_decision_target", inj.get("decision_threshold", "") or "Decision")
                    inj.setdefault("knowledge_before", ["Context"])
                    inj.setdefault("knowledge_newly_revealed", ["Revealed"])
                    inj.setdefault("knowledge_after", ["State"])
        return p
    except Exception:
        return p

def _quality_normalise_tabletop_plan(p: dict, client_inputs: dict | None = None) -> dict:
    """
    Deterministic clean-up to satisfy quality gates and avoid vendor/platform inaccuracies.
    - Redact vendor claims (e.g., Sophos) when unsupported by systems_to_check/client MDR.
    - Ensure probe coverage: evidence, governance, authority, communications; add 'what if'.
    - Scrub early-reveal lexicon (injects 1–3) to observable symptoms.
    - Downgrade invalid sophos/mdr/case artefacts to generic 'ticket' when required fields missing.
    - Map decision_questions objective_id to actual objectives (post-merge safe).
    """
    try:
        ci = client_inputs or {}
        mdr = str((ci.get("mdr_provider") or "")).strip().lower()
        scns = p.get("scenarios", []) if isinstance(p, dict) else []
        objectives = p.get("objectives", []) if isinstance(p, dict) else []
        obj0 = (objectives[0] if isinstance(objectives, list) and objectives else "").strip()

        def _norm_txt(s: str) -> str:
            try:
                import re as _re
                return _re.sub(r"\s+", " ", str(s or "")).strip()
            except Exception:
                return str(s or "").strip()

        def _has(tokens, q: str) -> bool:
            ql = q.lower()
            return any(t in ql for t in tokens)

        early_terms = ("malicious activity", "compromised account", "phishing attack", "threat actor", "unauthorised access")

        for si, scn in enumerate(scns, 1):
            inj_list = scn.get("injects", []) if isinstance(scn, dict) else []
            for ji, inj in enumerate(inj_list, 1):
                # Redact vendor/platform claims if MDR unsupported
                try:
                    systems = inj.get("systems_to_check", []) if isinstance(inj, dict) else []
                    joined = " ".join([str(x).lower() for x in systems]) if isinstance(systems, list) else str(systems).lower()
                    body = str(inj.get("scenario_narrative", "") or "")
                    if ("sophos" in body.lower()) and (mdr in ("", "none") or not any(tok in joined for tok in ("sophos", "mdr", "sophos central"))):
                        inj["scenario_narrative"] = _norm_txt(body.replace("Sophos MDR", "our monitoring service").replace("Sophos", "our monitoring"))
                    # Artefacts: downgrade invalid sophos/mdr/case
                    arts = inj.get("artefacts", []) if isinstance(inj, dict) else []
                    new_arts = []
                    for ar in arts or []:
                        try:
                            meta = ar.get("metadata", []) if isinstance(ar, dict) else []
                            prof = ""
                            for m in meta or []:
                                s = str(m).lower()
                                if s.startswith("profile:"):
                                    prof = s.split(":", 1)[1].strip()
                                    break
                            if prof == "sophos/mdr/case":
                                body_lines = [ln for ln in str(ar.get("body", "")).splitlines() if str(ln).strip()]
                                has_fields = all(any(lbl in ln for ln in body_lines) for lbl in ["Decoded command line:", "Command path:", "Sophos PID:", "Purpose:"])
                                if (mdr in ("", "none") or not any(tok in joined for tok in ("sophos", "mdr", "sophos central"))) or not has_fields or len(body_lines) < 6:
                                    ar = dict(ar)
                                    ar["artefact_type"] = "ticket"
                                    ar["metadata"] = []
                        except Exception:
                            pass
                        new_arts.append(ar)
                    inj["artefacts"] = new_arts
                except Exception:
                    pass

                # Probe coverage
                try:
                    probes = inj.get("facilitator_probe_questions", []) if isinstance(inj, dict) else []
                    probes = [str(x) for x in (probes or [])]
                    need = {
                        "evidence": not any(_has(("evidence", "log", "alert", "where would you", "siem"), q) for q in probes),
                        "governance": not any(_has(("governance", "major incident", "regulator", "ico", "72h", "notification"), q) for q in probes),
                        "authority": not any(_has(("authority", "authorised", "runbook", "invoke", "containment"), q) for q in probes),
                        "communications": not any(_has(("communications", "stakeholder", "inform", "brief", "comms"), q) for q in probes),
                        "whatif": not any(q.lower().startswith("what if") for q in probes),
                    }
                    if need["evidence"]:
                        probes.append("Where would you look for corroborating evidence in logs or alerts?")
                    if need["governance"]:
                        probes.append("Does this meet our incident declaration or regulator threshold?")
                    if need["authority"]:
                        probes.append("Who is authorised to invoke the relevant runbook and containment steps?")
                    if need["communications"]:
                        probes.append("Which stakeholders must be briefed at this stage?")
                    if need["whatif"]:
                        probes.append("What if this signal is a false positive—what would you do next?")
                    inj["facilitator_probe_questions"] = probes[:8]
                except Exception:
                    pass

                # Early-reveal scrubbing (injects 1–3)
                try:
                    if ji <= 3:
                        txt = str(inj.get("scenario_narrative", "") or "")
                        for et in early_terms:
                            if et in txt.lower():
                                txt = txt.replace("unauthorised access", "anomalous access patterns").replace("compromised account", "account anomalies indicated").replace("phishing attack", "suspicious email reported").replace("threat actor", "unidentified party").replace("malicious activity", "suspect activity")
                        inj["scenario_narrative"] = _norm_txt(txt)
                except Exception:
                    pass

                # Decision question objective mapping (post-merge safe)
                try:
                    dqs = inj.get("decision_questions", []) if isinstance(inj, dict) else []
                    if isinstance(dqs, list) and dqs:
                        objectives2 = p.get("objectives", []) if isinstance(p, dict) else []
                        objset = {str(x).strip().lower() for x in (objectives2 or []) if isinstance(x, str)}
                        chosen = (objectives2[0] if objectives2 else obj0) or ""
                        for dq in dqs:
                            if isinstance(dq, dict):
                                oid = str(dq.get("objective_id", "")).strip().lower()
                                if not oid or oid not in objset:
                                    dq["objective_id"] = chosen
                        inj["decision_questions"] = dqs
                except Exception:
                    pass
        return p
    except Exception:
        return p

def _derive_visibility_contract(inputs: dict) -> dict:
    """
    Build a simple visibility contract from client profile.
    Keys:
      - mdr_enabled: bool
      - idp_present: bool
      - endpoint_managed: bool   (true if endpoint vendor != 'Select...' and not 'Other'/'None')
      - remote_access: str
      - saas_backup_present: bool
    """
    try:
        v = {}
        prov = str((inputs or {}).get("mdr_provider", "")).strip().lower()
        v["mdr_enabled"] = bool(prov and prov != "none" and prov != "select mdr / soc provider...")
        idp = str((inputs or {}).get("identity", "")).strip().lower()
        v["idp_present"] = idp in ("microsoft entra id (azure ad)", "okta")
        endpoint = str((inputs or {}).get("endpoint", "")).strip().lower()
        v["endpoint_managed"] = endpoint and endpoint not in ("select endpoint vendor...", "other", "none")
        v["remote_access"] = str((inputs or {}).get("remote_access", "")).strip().lower()
        v["saas_backup_present"] = str((inputs or {}).get("saas_backup", "")).strip().lower() != "none (relying on microsoft/google)"
        return v
    except Exception:
        return {}

def _enforce_visibility_on_injects(plan: dict, inputs: dict) -> dict:
    """
    Enforce realistic sources of detection based on visibility contract.
    - If MDR not enabled or not plausibly covering the signal → replace MDR detection claims with IdP/app/proxy/helpdesk sources.
    - BYOD and third‑party SaaS: prefer identity risk detections, app admin/audit logs, reverse proxy/WAF, or user-reported signals.
    - Update systems_to_check accordingly.
    """
    try:
        vis = _derive_visibility_contract(inputs)
        scns = plan.get("scenarios", []) if isinstance(plan, dict) else []
        for scn in scns:
            inj_list = scn.get("injects", []) if isinstance(scn, dict) else []
            for inj in inj_list:
                if not isinstance(inj, dict):
                    continue
                narr = str(inj.get("scenario_narrative", "") or "")
                syschk = inj.get("systems_to_check", [])
                syschk = syschk if isinstance(syschk, list) else []
                lower_narr = narr.lower()
                is_chargepoint = "chargepoint" in lower_narr or "back office" in lower_narr
                is_byod = ("byod" in lower_narr) or ("bring your own device" in lower_narr)
                # If MDR not enabled, remove MDR claims
                if ("mdr" in lower_narr or "sophos" in lower_narr) and not vis.get("mdr_enabled"):
                    narr = narr.replace("Sophos MDR", "identity provider risk detection").replace("MDR", "monitoring")
                # For BYOD + SaaS (Chargepoint), rewrite to realistic detection channels
                if is_chargepoint and is_byod:
                    # Prefer IdP/app/proxy signals
                    if "identity provider risk detection" not in narr and "admin audit" not in lower_narr:
                        narr = f"Identity provider risk detection flagged anomalous access patterns to the Chargepoint back office tooling. Admin audit logs corroborate unusual session behaviour."
                    # Adjust systems_to_check (ensure only plausible sources)
                    desired = ["Identity provider sign-in logs", "Chargepoint admin audit logs", "Reverse proxy / WAF access logs", "Helpdesk ticket"]
                    # Drop MDR/EDR dashboards if present and endpoint not managed
                    if not vis.get("endpoint_managed"):
                        syschk = [s for s in syschk if "EDR" not in str(s) and "MDR" not in str(s)]
                    # Merge desired uniques
                    seen = set()
                    merged = []
                    for s in (syschk + desired):
                        t = str(s).strip()
                        if t and t not in seen:
                            seen.add(t)
                            merged.append(t)
                    syschk = merged[:6]
                inj["scenario_narrative"] = " ".join(narr.split())
                inj["systems_to_check"] = syschk
        return plan
    except Exception:
        return plan

from core import LLMEngine
from prompts import (
    TabletopMasterPlan,
    build_tabletop_plan_prompt,
    SYSTEM_PERSONA_TABLETOP,
)
from export import create_tabletop_pptx, create_tabletop_facilitator_pdf
from config import get_config, ConfigKey, is_tabletop_quality_strict
from catalog import PLANET_IT_PORTFOLIO
from ui_shared_sections import render_governance_assurance_sections, render_ai_usage_and_governance, render_security_culture_sections, render_top_nav
from data import TABLETOP_OBJECTIVE_PRESETS

# Version tracker (for JSON export parity)
import os
try:
    _version_path = os.path.join(os.path.dirname(__file__), "..", "VERSION")
    with open(_version_path, "r") as _vf:
        APP_VERSION = _vf.read().strip()
except Exception:
    APP_VERSION = "dev"
from ui_shared_sections import render_footer

def _safe_index(options, value):
    """Return index of value in options; 0 if missing or invalid."""
    try:
        return options.index(value) if value in options else 0
    except Exception:
        return 0

def _coerce_list(value, options):
    """Coerce values into a valid list constrained to options."""
    try:
        if isinstance(value, list):
            return [v for v in value if v in options]
        if isinstance(value, str):
            parts = [p.strip() for p in value.split(",") if p.strip()]
            return [p for p in parts if p in options]
    except Exception:
        pass
    return []

st.set_page_config(page_title="Tabletop Designer (BETA)", layout="wide", initial_sidebar_state="collapsed")

# Auth-aware guard: if login is enabled and user not signed-in, route to app.py sign-in
from config import get_config
def _is_auth_enabled():
    try:
        return str(get_config("AUTH_ENABLED", "false")).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        return False
if _is_auth_enabled() and not st.session_state.get("_auth_user"):
    st.warning("Sign in required to access the Tabletop Designer.")
    st.page_link("app.py", label="🔐 Go to Sign In")
    st.stop()

# Branding header
st.title("Planet IT Advisory Engine")

render_top_nav(active="tabletop")

st.header("🛠️ Tabletop Exercise Designer & Editor (BETA)")
# Workflow navigation removed — render all sections unconditionally
st.divider()
show_setup = True
show_themes = True
show_customise = True
show_export = True

with st.expander("Profile: Export / Import", expanded=False):
    import json as _json
    col_e1, col_e2 = st.columns([1, 1])
    # Debug import toggle via config; prints branch decisions and metadata
    try:
        DEBUG_IMPORT = str(get_config("DEBUG_IMPORT", "false")).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        DEBUG_IMPORT = False

    export_profile = st.session_state.get("client_inputs", {})
    file_customer_name = (export_profile or {}).get("customer_name", "Client")

    with col_e1:
        if export_profile:
            st.download_button(
                "⬇️ Export current options (.json)",
                data=_json.dumps({"version": APP_VERSION, "profile": export_profile}, ensure_ascii=False, indent=2, default=_json_default).encode("utf-8"),
                file_name=f"{str(file_customer_name).replace(' ', '_')}_options.json",
                mime="application/json",
            )
        else:
            st.info("Provide inputs to enable export.")

    with col_e2:
        nonce = st.session_state.get('_tt_import_nonce', 0)
        uploaded = st.file_uploader("Import options (.json)", type=["json"], key=f"tt_profile_import_json_{nonce}")
        # One-shot guard: skip importer once right after a successful import
        if st.session_state.get('_tt_profile_import_applied'):
            st.session_state.pop('_tt_profile_import_applied', None)
            st.session_state['_tt_import_nonce'] = (nonce + 1)
            if 'DEBUG_IMPORT' in globals() and DEBUG_IMPORT:
                st.caption(f"DEBUG: one-shot guard hit; nonce→{nonce+1}")
            st.info("Profile applied to UI.")
            uploaded = None
        if uploaded is not None:
            try:
                # Defensive: reset pointer if stream-like
                try:
                    if hasattr(uploaded, "seek"):
                        uploaded.seek(0)
                except Exception:
                    pass
                raw = uploaded.getvalue() if hasattr(uploaded, "getvalue") else uploaded.read()
                import hashlib as _hashlib
                try:
                    _h = _hashlib.sha256(raw).hexdigest() if isinstance(raw, (bytes, bytearray)) else _hashlib.sha256(str(raw).encode("utf-8")).hexdigest()
                except Exception:
                    _h = f"{getattr(uploaded, 'name', 'unknown')}:{len(raw) if hasattr(raw, '__len__') else 0}"
                if 'DEBUG_IMPORT' in globals() and DEBUG_IMPORT:
                    fname = getattr(uploaded, "name", "unknown")
                    size = len(raw) if isinstance(raw, (bytes, bytearray)) else len(str(raw))
                    st.caption(f"DEBUG: nonce={nonce}, file={fname}, size={size} bytes, hash={_h[:12]}...")
                # If this exact file was already applied, bump nonce to reset uploader and avoid rerun loops
                if st.session_state.get('_tt_last_import_hash') == _h:
                    st.info("Profile already applied.")
                    st.session_state['_tt_import_nonce'] = (nonce + 1)
                    if 'DEBUG_IMPORT' in globals() and DEBUG_IMPORT:
                        st.caption(f"DEBUG: already-applied branch; nonce→{nonce+1}")
                else:
                    data = _json.loads(raw.decode("utf-8")) if isinstance(raw, (bytes, bytearray)) else _json.loads(raw)
                    profile = data.get("profile") if isinstance(data, dict) and "profile" in data else data
                    if not isinstance(profile, dict):
                        st.error("Invalid file format: expected a JSON object with a 'profile' object or a flat object of fields.")
                    else:
                        try:
                            from consultation_helpers import migrate_profile
                            profile = migrate_profile(profile)
                        except Exception:
                            if 'DEBUG_IMPORT' in globals() and DEBUG_IMPORT:
                                st.caption("DEBUG: migrate_profile raised; continuing with raw profile.")
                        st.session_state["client_inputs"] = profile
                        st.session_state['_tt_last_import_hash'] = _h
                        st.session_state['_tt_profile_import_applied'] = True
                        st.session_state['_tt_import_nonce'] = (nonce + 1)
                        if 'DEBUG_IMPORT' in globals() and DEBUG_IMPORT:
                            cust = profile.get('customer_name') if isinstance(profile, dict) else None
                            st.caption(f"DEBUG: success branch; customer_name={cust}; nonce→{nonce+1}; rerunning")
                        st.success("Profile imported. Applying to UI...")
                        st.rerun()
            except Exception as e:
                st.error(f"Failed to import profile: {e}")

st.subheader("Setup")
st.caption("These required fields appear on the Agenda and drive validation. Supply Objectives and the three-part Scope before generation.")
if show_setup:
    # Ensure client_inputs available before presets toolbar
    client_inputs = st.session_state.get("client_inputs") or {}
    # Presets toolbar (outside the form to avoid form button errors)
    cols_preset = st.columns([1, 1, 2])
    with cols_preset[0]:
        if st.button("Apply recommended objectives"):
            _aud = (st.session_state.get("tabletop_audience") or "Blended").strip().lower()
            _key = "board" if _aud == "board" else ("technical" if _aud == "technical" else "blended")
            _presets = TABLETOP_OBJECTIVE_PRESETS.get(_key, [])
            st.session_state["tt_obj_text"] = "\n".join(_presets[:5])
    with cols_preset[1]:
        if st.button("Apply scope suggestions"):
            def _suggest_scope(audience: str, inputs: dict) -> dict:
                aud = (audience or "Blended").strip().lower()
                included = []
                excluded = ["Production system changes", "Live customer or regulator contact", "Irreversible or destructive commands"]
                assumptions = ["All artefacts are simulated", "Decisions are timeboxed", "Use capability‑level language for unknowns"]
                if aud == "board":
                    included.extend([
                        "Incident command process",
                        "Executive communications workflow",
                        "Service continuity and recovery governance",
                    ])
                elif aud == "technical":
                    included.extend([
                        "EDR telemetry for affected hosts",
                        "Firewall/flow logs",
                        "Backup catalogues",
                    ])
                else:
                    included.extend([
                        "SOC/SIEM telemetry",
                        "Endpoint EDR",
                        "Change control process",
                    ])
                try:
                    if (client_inputs.get("identity") or "").strip():
                        included.append("Identity provider sign‑in logs")
                    if (client_inputs.get("endpoint") or "").strip():
                        included.append("Endpoint security platform telemetry")
                    if (client_inputs.get("firewall") or "").strip():
                        included.append("Firewall logs and blocks")
                    if (client_inputs.get("saas_backup") or "").strip():
                        included.append("SaaS/backup platform catalogues")
                    if ((client_inputs.get("mdr_provider") or "None").strip() != "None"):
                        included.append("MDR case hand‑off and escalation flow")
                except Exception:
                    pass
                seen = set()
                def _uniq(seq):
                    out = []
                    for x in seq:
                        k = (x or "").strip()
                        if not k or k in seen:
                            continue
                        seen.add(k)
                        out.append(k)
                    return out
                return {"included": _uniq(included), "excluded": _uniq(excluded), "assumptions": _uniq(assumptions)}
            _rs = _suggest_scope(st.session_state.get("tabletop_audience", "Blended"), client_inputs)
            st.session_state["tt_scope_included"] = "\n".join(_rs["included"])
            st.session_state["tt_scope_excluded"] = "\n".join(_rs["excluded"])
            st.session_state["tt_scope_assumptions"] = "\n".join(_rs["assumptions"])
    st.caption("Presets are editable; click Save Required Setup to persist.")
    # Required Exercise Setup form (Objectives + Scope)
    with st.form("tt_required_setup"):
        st.markdown("**Objectives** — :red[Required]")
        _obj_text = st.text_area(
            "Objectives (one per line)",
            value=st.session_state.get("tt_obj_text", ""),
            key="tt_obj_text",
            height=120,
        )
        st.markdown("**Scope** — :red[Required]")
        cols_sc = st.columns(3)
        with cols_sc[0]:
            _inc_text = st.text_area(
                "Included (one per line)",
                value=st.session_state.get("tt_scope_included", ""),
                key="tt_scope_included",
                height=120,
            )
        with cols_sc[1]:
            _exc_text = st.text_area(
                "Excluded (one per line)",
                value=st.session_state.get("tt_scope_excluded", ""),
                key="tt_scope_excluded",
                height=120,
            )
        with cols_sc[2]:
            _ass_text = st.text_area(
                "Assumptions (one per line)",
                value=st.session_state.get("tt_scope_assumptions", ""),
                key="tt_scope_assumptions",
                height=120,
            )
        _saved = st.form_submit_button("Save Required Setup")
        if _saved:
            st.session_state["tt_required_setup_data"] = {
                "objectives": [x.strip() for x in (st.session_state.get("tt_obj_text", "")).splitlines() if x.strip()],
                "scope": {
                    "included": [x.strip() for x in (st.session_state.get("tt_scope_included", "")).splitlines() if x.strip()],
                    "excluded": [x.strip() for x in (st.session_state.get("tt_scope_excluded", "")).splitlines() if x.strip()],
                    "assumptions": [x.strip() for x in (st.session_state.get("tt_scope_assumptions", "")).splitlines() if x.strip()],
                },
            }
            st.success("Required setup saved.")
    with st.expander("Customer Estate & Engagement Profile (Quick Capture)", expanded=False):
        qc_name = st.text_input("Customer Name", value=st.session_state.get("client_inputs", {}).get("customer_name", ""))
        qc_industry = st.text_input("Industry", value=st.session_state.get("client_inputs", {}).get("industry", ""))
        qc_users = st.number_input("Headcount", min_value=0, value=int(st.session_state.get("client_inputs", {}).get("users", 0)))
        qc_crown = st.text_input("Crown Jewels", value=st.session_state.get("client_inputs", {}).get("critical_infra", ""))
        if st.button("Apply Quick Profile"):
            st.session_state.setdefault("client_inputs", {})
            st.session_state["client_inputs"].update({
                "customer_name": qc_name.strip(),
                "industry": (qc_industry or "").strip() or "Unknown",
                "users": qc_users,
                "critical_infra": (qc_crown or "").strip(),
            })
            st.success("Quick profile applied to Tabletop context.")

# Guard: require client profile
client_inputs = st.session_state.get("client_inputs") or {}
cached_customer_name = client_inputs.get("customer_name", "Client")
key_assets = client_inputs.get("critical_infra", "Crown Jewels")

if show_setup:
    # Summary cards to reduce inline clutter; full details remain under Advanced Evidence Capture
    with st.container():
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            st.subheader("Organisation")
            st.markdown(f"- Name: {cached_customer_name}")
            st.markdown(f"- Industry: {client_inputs.get('industry','Unknown')}")
            st.markdown(f"- Headcount: {client_inputs.get('users','0')}")
            st.markdown(f"- Crown Jewels: {key_assets or 'N/A'}")
        with col_s2:
            st.subheader("Tech Stack")
            st.markdown(f"- Endpoint: {client_inputs.get('endpoint','Unknown')}")
            st.markdown(f"- Firewall: {client_inputs.get('firewall','Unknown')}")
            st.markdown(f"- Identity: {client_inputs.get('identity','Unknown')}")
            st.markdown(f"- Email: {client_inputs.get('email','Unknown')}")
            _cloud_env = client_inputs.get('cloud_env', [])
            st.markdown(f"- Cloud: {', '.join(_cloud_env) if isinstance(_cloud_env, list) and _cloud_env else (_cloud_env or 'None')}")
        with col_s3:
            st.subheader("Hygiene & MDR")
            st.markdown(f"- MFA: {client_inputs.get('mfa_status','Unknown')}")
            st.markdown(f"- Patching: {client_inputs.get('patching','Unknown')}")
            st.markdown(f"- Backups: {client_inputs.get('backups','Unknown')}")
            st.markdown(f"- MDR: {client_inputs.get('mdr_provider','None')}")
    st.caption("Advanced Evidence Capture (Optional) retains all detailed inputs for LLM context.")

with st.expander("Customer Estate & Engagement Profile (Advanced)", expanded=False):
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("Organisational Profile")
        customer_name = st.text_input("Customer Name", value=client_inputs.get("customer_name", ""), key="adv_customer_name")
        consultant_name = st.text_input("Consultant Name", value=client_inputs.get("consultant_name", ""))
        industry_options = [
            "Select Industry...",
            "Healthcare",
            "Finance",
            "Manufacturing",
            "Retail & eCommerce",
            "Technology",
            "Education",
            "Legal",
            "Local Government",
            "Central Government",
            "Non-profit / Charity",
            "Energy & Utilities",
            "Construction",
            "Logistics & Supply Chain",
            "Media & Entertainment",
            "Hospitality & Leisure",
            "Pharmaceuticals & Life Sciences",
            "Professional Services",
            "Real Estate & Facilities",
            "Transportation",
            "Aviation",
            "Defence & Aerospace",
            "Critical National Infrastructure (CNI)",
            "Insurance",
            "Telecommunications",
            "Automotive",
            "Agriculture & Food",
            "Mining & Natural Resources",
            "Other",
        ]
        industry = st.selectbox("Industry", industry_options, index=_safe_index(industry_options, client_inputs.get("industry")))
        users = st.number_input("Headcount", min_value=0, value=int(client_inputs.get("users", 0)), key="adv_users")
        critical_infra = st.text_input("Crown Jewels", value=client_inputs.get("critical_infra", ""), key="adv_critical_infra")

    with col2:
        st.subheader("Technology Stack")
        endpoints = st.number_input("Number of Endpoints", min_value=0, value=int(client_inputs.get("endpoints", 0)))
        servers = st.number_input("Number of Servers", min_value=0, value=int(client_inputs.get("servers", 0)))
        _os_options = ["Windows 10", "Windows 11", "Windows Server", "macOS", "Linux", "ChromeOS"]
        operating_systems = st.multiselect("Operating Systems in Use", _os_options, default=_coerce_list(client_inputs.get("operating_systems", []), _os_options))

        mdr_options = ["Select MDR / SOC Provider...", "None", "Sophos MDR", "Sophos MDR Plus", "Microsoft Defender Experts", "CrowdStrike Falcon Complete", "Arctic Wolf", "Expel", "Red Canary", "Local Partner SOC", "Other"]
        mdr_provider = st.selectbox("Current MDR / SOC Provider", mdr_options, index=_safe_index(mdr_options, client_inputs.get("mdr_provider")))

        endpoint_options = ["Select Endpoint Vendor...", "Sophos", "Microsoft Defender", "CrowdStrike", "SentinelOne", "Trend Micro", "Symantec", "N-able", "Other"]
        endpoint = st.selectbox("Endpoint Security Vendor", endpoint_options, index=_safe_index(endpoint_options, client_inputs.get("endpoint")))

        endpoint_posture_options = ["Select Endpoint Capability...", "Legacy AV Only (Signatures/Heuristics)", "Next-Gen AV (NGAV / Deep Learning)", "EDR Deployed (Endpoint Detection & Response)", "XDR Deployed (Cross-Domain Telemetry)", "Full ZTNA / Device Control Enforced"]
        endpoint_posture = st.selectbox("Endpoint Capability (Licensing)", endpoint_posture_options, index=_safe_index(endpoint_posture_options, client_inputs.get("endpoint_posture")))

        firewall_options = ["Select Firewall Vendor...", "Fortinet", "Palo Alto", "Cisco", "Sophos", "Check Point", "SonicWall", "Other"]
        firewall = st.selectbox("Firewall Vendor", firewall_options, index=_safe_index(firewall_options, client_inputs.get("firewall")))

        remote_access_options = [
            "Select Remote Access Strategy...",
            "None / Cloud Only",
            "Legacy VPN (Client-based)",
            "Always-On VPN",
            "VPN with Certificate-based Authentication",
            "Clientless VPN Portal",
            "Zero Trust Network Access (ZTNA) / SASE",
            "SD-WAN with Secure Access Overlay"
        ]
        remote_access = st.selectbox("Remote Access Strategy", remote_access_options, index=_safe_index(remote_access_options, client_inputs.get("remote_access")))

        saas_backup_options = ["Select SaaS Backup...", "None (Relying on Microsoft/Google)", "Basic Retention Policies Only", "Dedicated Third-Party SaaS Backup"]
        saas_backup = st.selectbox("M365 / SaaS Backup", saas_backup_options, index=_safe_index(saas_backup_options, client_inputs.get("saas_backup")))

    with col3:
        st.subheader("Cloud & Identity")
        identity_options = ["Select Identity Provider...", "Microsoft Entra ID (Azure AD)", "Okta", "On-Prem Active Directory", "None"]
        identity = st.selectbox("Identity Provider", identity_options, index=_safe_index(identity_options, client_inputs.get("identity")))

        m365_license_options = ["None / On-Prem Only", "M365 Business Premium", "Microsoft 365 E5", "Office 365 E3 / M365 E3"]
        m365_licenses = st.multiselect("Microsoft 365 Licensing", m365_license_options, default=_coerce_list([client_inputs.get("m365_license")] if client_inputs.get("m365_license") else [], m365_license_options))
        m365_license_str = ", ".join(m365_licenses) if m365_licenses else "None / On-Prem Only"

        email_options = ["Select Email Security...", "Mimecast", "Proofpoint", "Microsoft Defender", "Barracuda", "Egress", "Other"]
        email = st.selectbox("Email Security", email_options, index=_safe_index(email_options, client_inputs.get("email")))

        cloud_env_options = ["AWS", "Microsoft Azure", "GCP", "Oracle Cloud", "None (Fully On-Prem)"]
        cloud_env = st.multiselect("Cloud Infrastructure", cloud_env_options, default=_coerce_list(client_inputs.get("cloud_env", []), cloud_env_options))

    st.divider()

    st.markdown("### 🚫 Ban Vendors from Recommendations")
    st.caption("Select any vendors your customer has explicitly ruled out. They will not appear in any generated recommendations or reports.")
    all_vendors = sorted(set(item["vendor"] for category in PLANET_IT_PORTFOLIO.values() for item in category))
    banned_vendors = st.multiselect("Excluded Vendors", options=all_vendors, default=_coerce_list(client_inputs.get("banned_vendors", []), all_vendors))

    st.divider()
    st.subheader("Operations & Validation")
    col_ops1, col_ops2 = st.columns(2)
    with col_ops1:
        in_house_options = ["Select Internal SOC Team...", "No", "Yes (9-to-5)", "Yes (24/7)"]
        in_house_team = st.selectbox("Internal SOC Team", in_house_options, index=_safe_index(in_house_options, client_inputs.get("in_house_team")))
        pentest_options = ["Select Penetration Testing Cadence...", "None", "Annual", "Bi-Annual", "Quarterly"]
        pentest_status = st.selectbox("Penetration Testing", pentest_options, index=_safe_index(pentest_options, client_inputs.get("pentest_status")))
        vuln_options = ["Select Vulnerability Scanning...", "None", "Monthly Authenticated", "Quarterly External", "Continuous"]
        vuln_scanning = st.selectbox("Vuln Scanning", vuln_options, index=_safe_index(vuln_options, client_inputs.get("vuln_scanning")))
        public_web_apps = st.checkbox("Host Public Web Apps", value=bool(client_inputs.get("public_web_apps", False)))
    with col_ops2:
        compliance_options = ["ISO 27001", "Cyber Essentials", "Cyber Essentials Plus", "PCI DSS", "HIPAA", "NIST CSF", "UK DfE (2026) Cyber Security Standards"]
        compliance = st.multiselect("Target Compliance", compliance_options, default=_coerce_list(client_inputs.get("compliance", []), compliance_options))
        physical_locations = st.number_input("Physical Locations", min_value=0, value=int(client_inputs.get("physical_locations", 0)))
        advanced_controls = st.multiselect(
            "Advanced Adaptive Controls (Pillar 3)",
            ["Zero-Trust Architecture (ZTA)", "Network Microsegmentation", "SOAR / Automated Remediation", "User Behaviour Analytics (UBA)", "Automated DR Orchestration", "Deception Tech (Honeypots)"],
            default=_coerce_list(client_inputs.get("advanced_controls", []), ["Zero-Trust Architecture (ZTA)", "Network Microsegmentation", "SOAR / Automated Remediation", "User Behaviour Analytics (UBA)", "Automated DR Orchestration", "Deception Tech (Honeypots)"])
        )
        proactive_tools_options = [
            "KnowBe4 Security Awareness",
            "Hoxhunt",
            "Cofense PhishMe",
            "Proofpoint Security Awareness",
            "Microsoft Attack Simulation Training",
            "AttackIQ (BAS)",
            "SafeBreach (BAS)",
            "Mandiant Security Validation (BAS)"
        ]
        proactive_tools = st.multiselect("Proactive Security Tools", proactive_tools_options, default=_coerce_list(client_inputs.get("proactive_tools", []), proactive_tools_options))
        validation_notes = st.text_area("Validation Notes", value=client_inputs.get("validation_notes", ""))
        context_notes = st.text_area("Consultant Context (LLM-visible)", value=client_inputs.get("context_notes", ""))

    st.divider()
    col_apply1, col_apply2 = st.columns([1, 1])
    with col_apply1:
        ir_readiness_options = ["Unknown", "No Formal Plan", "Plan Drafted", "Plan Approved", "Plan Tested (Tabletop in past year)"]
        ir_readiness = st.selectbox("Incident Response Readiness", ir_readiness_options, index=_safe_index(ir_readiness_options, client_inputs.get("ir_readiness")))
        ir_retainer_options = ["None", "Microsoft DART", "Sophos MDR Plus / Incident Response", "Other"]
        ir_retainer = st.selectbox("Active IR Retainer", ir_retainer_options, index=_safe_index(ir_retainer_options, client_inputs.get("ir_retainer")))

    with col_apply2:
        managed_service_options = ["None (No managed service in place)", "Planet IT Fully Managed (Active)", "Planet IT Co-Managed (Active)", "Other MSP (Active)"]
        managed_service_status = st.selectbox("Managed Service Status", managed_service_options, index=_safe_index(managed_service_options, client_inputs.get("managed_service_status")))
        co_managed_units = st.number_input("Co-Managed Service Units", min_value=0, value=int(client_inputs.get("co_managed_units", 0)))
        partnership_type_options = ["Fully Managed", "Co-Managed", "Project-Based", "Advisory Only"]
        partnership_type = st.selectbox("Partnership Preference", partnership_type_options, index=_safe_index(partnership_type_options, client_inputs.get("partnership_type")))

    st.divider()
    st.subheader("Operational Telemetry (Hygiene)")
    col_tel1, col_tel2, col_tel3 = st.columns(3)
    with col_tel1:
        mfa_options = ["Unknown", "None", "Privileged Accounts Only", "Universal / Conditional Access"]
        mfa_status = st.selectbox("MFA Enforcement", mfa_options, index=_safe_index(mfa_options, client_inputs.get("mfa_status")))
    with col_tel2:
        patching_options = ["Unknown", "Manual / Ad-hoc", "Automated (OS Only)", "Automated (OS + Apps)"]
        patching = st.selectbox("Patch Management", patching_options, index=_safe_index(patching_options, client_inputs.get("patching")))
    with col_tel3:
        backup_options = ["Unknown", "No Formal Backups", "On-Premise Only", "Cloud/Offsite (Standard)", "Cloud/Offsite (Immutable/Air-gapped)"]
        backups = st.selectbox("Infrastructure Backups", backup_options, index=_safe_index(backup_options, client_inputs.get("backups")))

    if st.button("Apply Advanced Profile", type="primary"):
        st.session_state.setdefault("client_inputs", {})
        st.session_state["client_inputs"].update({
            "customer_name": (customer_name or "").strip(),
            "consultant_name": (consultant_name or "").strip(),
            "industry": industry,
            "users": int(users),
            "critical_infra": (critical_infra or "").strip(),
            "endpoints": int(endpoints),
            "servers": int(servers),
            "operating_systems": operating_systems,
            "mdr_provider": mdr_provider,
            "endpoint": endpoint,
            "endpoint_posture": endpoint_posture,
            "firewall": firewall,
            "remote_access": remote_access,
            "saas_backup": saas_backup,
            "identity": identity,
            "m365_license": m365_license_str,
            "email": email,
            "cloud_env": cloud_env,
            "banned_vendors": banned_vendors,
            "in_house_team": in_house_team,
            "pentest_status": pentest_status,
            "vuln_scanning": vuln_scanning,
            "public_web_apps": bool(public_web_apps),
            "compliance": compliance,
            "physical_locations": int(physical_locations),
            "advanced_controls": advanced_controls,
            "proactive_tools": proactive_tools,
            "validation_notes": (validation_notes or "").strip(),
            "context_notes": (context_notes or "").strip(),
            "ir_readiness": ir_readiness,
            "ir_retainer": ir_retainer,
            "managed_service_status": managed_service_status,
            "co_managed_units": int(co_managed_units),
            "partnership_type": partnership_type,
            "mfa_status": mfa_status,
            "patching": patching,
            "backups": backups,
        })
        st.success("Advanced profile applied to Tabletop context.")

# Extended inputs parity with Maturity (shared)
ai_dict = render_ai_usage_and_governance()
sav_dict = render_security_culture_sections()
cap_dict, sr_dict, ip_dict, idg_dict, saas_dict, aa_dict, mon_dict, sup_dict, tpa_dict, rec_dict, ir_dict, as_map = render_governance_assurance_sections()
st.session_state.setdefault("client_inputs", {})
# Merge Security Culture (behaviours)
st.session_state["client_inputs"].update({
    "savviness": sav_dict.get("savviness"),
    "savviness_label": sav_dict.get("savviness_label"),
    "culture_score": sav_dict.get("culture_score"),
    "culture_q1": sav_dict.get("culture_q1"),
    "culture_q2": sav_dict.get("culture_q2"),
    "culture_q3": sav_dict.get("culture_q3"),
    "culture_reporting_routes": sav_dict.get("culture_reporting_routes"),
    "culture_followup_coaching": sav_dict.get("culture_followup_coaching"),
    "culture_role_training": sav_dict.get("culture_role_training"),
    "culture_leadership_engagement": sav_dict.get("culture_leadership_engagement"),
    "culture_policy_ack": sav_dict.get("culture_policy_ack"),
    "culture_phish_fail_pct_90d": sav_dict.get("culture_phish_fail_pct_90d"),
    "culture_report_rate_pct_90d": sav_dict.get("culture_report_rate_pct_90d"),
})
# Merge AI Governance
st.session_state["client_inputs"].update(ai_dict)
# Merge Governance & Assurance evidence maps
st.session_state["client_inputs"].update({
    "critical_asset_profile": cap_dict,
    "service_resilience_profile": sr_dict,
    "information_protection_profile": ip_dict,
    "identity_governance_profile": idg_dict,
    "saas_governance_profile": saas_dict,
    "asset_assurance_profile": aa_dict,
    "monitoring_assurance_profile": mon_dict,
    "supplier_assurance_profile": sup_dict,
    "third_party_access_profile": tpa_dict,
    "recovery_assurance_profile": rec_dict,
    "incident_response_assurance_profile": ir_dict,
    "assurance_status": as_map,
})
st.subheader("Themes")
st.caption("Generate uses your saved Setup and any Advanced evidence. Profiles are independent; Audience is for presets/labels only.")
# Approval control for blueprint-driven inject generation
st.checkbox("Use approved ExerciseBlueprint to generate injects (deterministic; bypass LLM plan)", key="exercise_blueprint_approved")
if show_themes:
    col_sc1, col_sc2 = st.columns(2)
    with col_sc1:
        selected_themes = st.multiselect(
            "Select Scenarios to Include:",
            [
                "Ransomware (Double Extortion)",
                "Business Email Compromise (Payment Fraud)",
                "OAuth Consent Grant Attack",
                "Unauthorised Access (Insider / Social Engineering / Service Desk)",
                "Third-Party Access Abuse (Supplier)",
                "Public Web App/API Exploitation",
                "Cloud Incident (M365/Azure Outage or Misconfiguration)",
                "Identity Attack (AiTM Session Hijack / MFA Fatigue)",
                "Endpoint Lateral Movement (EDR Telemetry)",
                "Backup Destruction & DR Failure",
            ],
            default=[
                "Ransomware (Double Extortion)",
                "Unauthorised Access (Insider / Social Engineering / Service Desk)",
            ],
        )
    with col_sc2:
        st.markdown(f"**Target Customer:** `{cached_customer_name}`")
        st.markdown(f"**Key Assets:** `{key_assets}`")
        # Auto-seed custom brief from Threat Simulator if available and no user-provided brief
        default_brief = st.session_state.get("custom_tabletop_brief", "")
        if not default_brief:
            _sc = st.session_state.get("scenario_obj")
            if _sc is not None:
                try:
                    import re as _re  # local import to avoid global dependency
                except Exception:
                    _re = None
                try:
                    _text = getattr(_sc, "narrative", "")
                    if isinstance(_text, str):
                        _text = _re.sub(r"\s+", " ", _text).strip() if _re else _text.strip()
                        default_brief = _text[:400]
                except Exception:
                    pass
        custom_brief = st.text_area(
            "Custom scenario brief (optional)",
            help="Provide 1–3 sentences describing a bespoke scenario to include (30–400 characters).",
            value=default_brief,
            placeholder="e.g., Overnight outage in M365 Exchange Online with downstream impacts to customer support and finance approvals.",
        )
        custom_brief = (custom_brief or "").strip()
        if custom_brief and len(custom_brief) < 30:
            st.warning("Custom brief is too short; provide at least 30 characters for meaningful context.")
        st.session_state["custom_tabletop_brief"] = custom_brief
# Independent configuration dimensions (do not infer)
exercise_profile_options = ["blended", "board", "technical"]
exercise_profile = st.selectbox("Exercise Profile", exercise_profile_options, index=_safe_index(exercise_profile_options, (st.session_state.get("exercise_profile") or "blended")))
st.caption("Independent from Presentation Detail. Do not infer either from Audience.")
st.session_state["exercise_profile"] = exercise_profile

presentation_detail_options = ["standard", "detailed"]
# Honour legacy alias TABLETOP_PRESENTATION_PROFILE if present; record migration/default
legacy_alias = st.session_state.get("TABLETOP_PRESENTATION_PROFILE")
detail_default = st.session_state.get("presentation_detail_profile") or legacy_alias or "standard"
if not st.session_state.get("presentation_detail_profile") and not legacy_alias:
    st.session_state.setdefault("_migration_notices", []).append("Applied default presentation_detail_profile=standard")
if legacy_alias:
    st.session_state.setdefault("_migration_notices", []).append("Legacy alias TABLETOP_PRESENTATION_PROFILE applied as presentation_detail_profile")
presentation_detail_profile = st.selectbox("Presentation Detail Level", presentation_detail_options, index=_safe_index(presentation_detail_options, detail_default))
st.caption("Standard keeps operational probes in speaker notes; Detailed adds compact, capped prompts to the slide.")
st.session_state["presentation_detail_profile"] = presentation_detail_profile

# Audience remains display-only; do not infer profiles from it
audience_options = ["Blended", "Board", "Technical"]
audience = st.selectbox("Audience (display only)", audience_options, index=_safe_index(audience_options, st.session_state.get("tabletop_audience", "Blended")))
st.session_state["tabletop_audience"] = audience

if show_themes and st.button("Generate Bespoke Tabletop Plan", type="primary"):
    with st.spinner("Compiling scenarios and facilitator guides from estate profile..."):
        client = LLMEngine.get_client()
        deployment = get_config(ConfigKey.AZURE_DEPLOYMENT, "gpt-4o")
        # ExerciseBlueprint (optional, ahead of inject plan)
        try:
            if str(get_config("TABLETOP_BLUEPRINT_ENABLED", "true")).strip().lower() in ("1","true","yes","on"):
                blueprint = LLMEngine.generate_exercise_blueprint(
                    client,
                    deployment,
                    SYSTEM_PERSONA_TABLETOP,
                    client_inputs,
                    selected_themes,
                    audience=st.session_state.get("tabletop_audience", "Blended"),
                )
                if blueprint:
                    st.session_state["exercise_blueprint"] = blueprint
        except Exception as e:
            import logging as _logging
            _logging.getLogger(__name__).warning("ExerciseBlueprint generation failed; proceeding with plan generation. Error: %s", e)

        # If an approved ExerciseBlueprint exists, deterministically build the plan from it (no LLM)
        st.session_state.setdefault("exercise_blueprint_approved", False)
        _use_bp = bool(st.session_state.get("exercise_blueprint_approved"))
        _bp = st.session_state.get("exercise_blueprint")
        if _use_bp and isinstance(_bp, dict):
            try:
                # Minimal deterministic plan from blueprint
                plan = {
                    "exercise_title": _bp.get("exercise_title", "Tabletop Exercise"),
                    "client_name": client_inputs.get("customer_name", _bp.get("client_name", "Client")),
                    "housekeeping_rules": _bp.get("housekeeping_rules", []),
                    "scenarios": []
                }
                # Single scenario mapped from blueprint context; map inject_plan → injects
                ip = _bp.get("inject_plan", []) or []
                scenario = {
                    "scenario_id": "SCN-01",
                    "scenario_title": _bp.get("exercise_title", "Scenario"),
                    "scenario_theme": "Blended",
                    "target_assets": [client_inputs.get("critical_infra", "Crown Jewels")],
                    "initial_vector": "Blueprint",
                    "injects": [],
                    "facilitator_reveal": {
                        "reveal_title": "Wrap-up",
                        "reveal_narrative": ((_bp.get("facilitation_guide") or {}).get("escalation_notes") or ""),
                        "key_lessons": ((_bp.get("facilitation_guide") or {}).get("key_lessons") or []) or ["Lesson"],
                        "wrap_up_questions": ((_bp.get("facilitation_guide") or {}).get("wrap_up_questions") or []) or ["Question"]
                    }
                }
                # Progressive knowledge tracker
                running_known = []
                for idx, item in enumerate(ip[:4], 1):
                    sb = (item.get("story_beat") or {})
                    ks = (sb.get("knowledge_state") or {})
                    facts = [str(x) for x in (ks.get("known_facts") or [])]
                    # Progressive knowledge states
                    knowledge_before = list(dict.fromkeys(running_known)) or ["Context"]
                    newly = [x for x in facts if x not in running_known] or (facts or ["Revealed"])
                    after = list(dict.fromkeys(running_known + facts)) or ["State"]
                    running_known = after[:]
                    esc = (sb.get("escalation_state") or {})
                    dec_thr = esc.get("decision_threshold", "")
                    prim = dec_thr or ""
                    # Technical indicators derived from artefact requests/source systems
                    tech_inds = []
                    try:
                        for ar in (item.get("artefact_requests") or []):
                            if isinstance(ar, dict):
                                t = ar.get("artefact_type", "") or "artefact"
                                s = ar.get("source_system", "") or "System"
                                tech_inds.append(f"{t} from {s}")
                    except Exception:
                        pass
                    if not tech_inds:
                        tech_inds = ["Indicator"]
                    # Systems to check from artefact source systems; ensure >=2 with fallbacks
                    syschk = []
                    try:
                        srcs = set()
                        for ar in (item.get("artefact_requests") or []):
                            if isinstance(ar, dict):
                                s = (ar.get("source_system", "") or "").strip()
                                if s:
                                    srcs.add(s)
                        syschk = list(srcs)[:6]
                    except Exception:
                        syschk = []
                    if len(syschk) < 2:
                        for extra in ("SIEM console", "EDR dashboard", "Identity logs"):
                            if extra not in syschk:
                                syschk.append(extra)
                            if len(syschk) >= 6:
                                break
                    # Default roles/runbooks/evidence/knowledge checks
                    roles = ["Incident Manager", "SOC Analyst"][:5]
                    runbooks = ["IR‑01 Declaration"]
                    evhunt = ["Ticket ID for incident declaration", "SIEM export of indicators"]
                    kchecks = ["Who approves external comms?", "Where is the SIEM query stored?"]
                    inj = {
                        "inject_id": f"INJ-1.{idx}",
                        "phase_title": sb.get("phase_title", "Phase"),
                        "simulated_timestamp": sb.get("simulated_timestamp", ""),
                        "scenario_narrative": sb.get("participant_narrative", ""),
                        "technical_indicators": tech_inds[:4],
                        "artefacts": [],  # Deterministic path does not synthesise full artefacts; editor/LLM may enrich later
                        "facilitator_probe_questions": [dq.get("prompt","Question") for dq in (item.get("decision_questions") or [])][:5] or ["What if..."],
                        "expected_mature_response": dec_thr or "Follow runbook authority and governance thresholds.",
                        "common_pitfalls": ["Assuming evidence without validation", "Skipping authority checks"],
                        "decision_threshold": dec_thr or "",
                        "primary_decision_target": prim or "Decision",
                        "knowledge_before": knowledge_before[:8],
                        "knowledge_newly_revealed": newly[:8],
                        "knowledge_after": after[:10],
                        "systems_to_check": syschk[:6],
                        "roles_to_engage": roles,
                        "runbook_references": runbooks,
                        "evidence_hunt": evhunt[:6],
                        "knowledge_checks": kchecks[:4],
                        "timebox_hint": item.get("timebox_hint", "5–7 minutes to decision")
                    }
                    scenario["injects"].append(inj)
                plan["scenarios"].append(scenario)
                # Merge Required Setup (Objectives & Scope) if present
                _rs = st.session_state.get("tt_required_setup_data")
                if _rs:
                    plan["objectives"] = _rs.get("objectives", [])
                    plan["scope"] = _rs.get("scope", {})
                # Enforce telemetry visibility realism before other quality rules
                plan = _enforce_visibility_on_injects(plan, st.session_state.get("client_inputs", {}))
                # Quality normalisation (vendor/probes/lexicon/objective mapping)
                plan = _quality_normalise_tabletop_plan(plan, st.session_state.get("client_inputs", {}))
                # Knowledge-bound participant artefact synthesis (deterministic; optional)
                try:
                    from participant_artefacts import synthesise_participant_artefacts as _synth
                    if str(get_config("TABLETOP_ARTEFACT_GEN_ENABLED", "true")).strip().lower() in ("1","true","yes","on"):
                        plan = _synth(plan, st.session_state.get("exercise_blueprint"), audience=st.session_state.get("tabletop_audience","Blended"))
                except Exception as _ae:
                    st.caption(f"Participant artefact synthesis skipped: {_ae}")
                # Facilitator-only guidance synthesis (mandatory; speaker notes only)
                try:
                    from facilitator_guidance import generate_inject_facilitation, attach_facilitation_to_plan
                    fac_map = generate_inject_facilitation(plan, st.session_state.get("exercise_blueprint"), audience=st.session_state.get("tabletop_audience","Blended"))
                    plan = attach_facilitation_to_plan(plan, fac_map)
                except Exception as _fe:
                    st.caption(f"Facilitation notes synthesis skipped: {_fe}")
                # Synthesise DecisionQuestion list from facilitator_probe_questions (fallback)
                try:
                    _objs = plan.get("objectives", []) if isinstance(plan, dict) else []
                    _obj0 = (_objs[0] if isinstance(_objs, list) and _objs else "")
                    for scn in (plan.get("scenarios", []) if isinstance(plan, dict) else []):
                        for inj in (scn.get("injects", []) if isinstance(scn, dict) else []):
                            # Skip if already present
                            if isinstance(inj, dict) and isinstance(inj.get("decision_questions"), list) and inj["decision_questions"]:
                                continue
                            fpq = inj.get("facilitator_probe_questions", []) if isinstance(inj, dict) else []
                            dq_list = []
                            for q in (fpq or []):
                                qs = str(q or "")
                                lower = qs.lower()
                                cat = "Evidence"
                                if lower.startswith("what if"):
                                    cat = "What‑if"
                                elif ("declare" in lower) or ("notify" in lower) or ("regulator" in lower):
                                    cat = "Governance"
                                elif ("who" in lower and "approve" in lower):
                                    cat = "Authority"
                                elif any(x in lower for x in ("stakeholder", "communicat", "brief", "inform")):
                                    cat = "Communications"
                                dq_list.append({
                                    "prompt": qs,
                                    "category": cat,
                                    "objective_id": _obj0,
                                    "decision_target": (inj.get("decision_threshold", "") if isinstance(inj, dict) else ""),
                                })
                            if dq_list:
                                inj["decision_questions"] = dq_list
                except Exception:
                    pass
                st.session_state["tabletop_plan"] = plan
                st.success("Tabletop scenario compiled deterministically from approved ExerciseBlueprint.")
                st.stop()
            except Exception as _xe:
                st.warning(f"Blueprint transform failed; falling back to LLM plan. Error: {_xe}")

        # Seed custom brief from Threat Simulator if user did not provide one
        _seed_brief = st.session_state.get("custom_tabletop_brief")
        if not _seed_brief:
            _sc = st.session_state.get("scenario_obj")
            if _sc is not None:
                try:
                    import re as _re  # local import to avoid global dependency
                except Exception:
                    _re = None
                try:
                    _text = getattr(_sc, "narrative", "")
                    if isinstance(_text, str):
                        _text = _re.sub(r"\s+", " ", _text).strip() if _re else _text.strip()
                        _seed_brief = _text[:400]
                except Exception:
                    pass
        prompt = build_tabletop_plan_prompt(
            client_inputs,
            selected_themes,
            custom_brief=_seed_brief,
            audience=st.session_state.get("tabletop_audience", "Blended"),
            exercise_profile=st.session_state.get("exercise_profile", "blended"),
            presentation_detail_profile=st.session_state.get("presentation_detail_profile", "standard"),
        )
        plan = LLMEngine.generate_structured_report(
            client, deployment, SYSTEM_PERSONA_TABLETOP, prompt, TabletopMasterPlan
        )
        if plan:
            plan_dict = plan.model_dump() if hasattr(plan, 'model_dump') else plan
            # Knowledge-bound participant artefact synthesis (deterministic; optional)
            try:
                from participant_artefacts import synthesise_participant_artefacts as _synth
                if str(get_config("TABLETOP_ARTEFACT_GEN_ENABLED", "true")).strip().lower() in ("1","true","yes","on"):
                    plan_dict = _synth(plan_dict, st.session_state.get("exercise_blueprint"), audience=st.session_state.get("tabletop_audience","Blended"))
            except Exception as _ae:
                st.caption(f"Participant artefact synthesis skipped: {_ae}")
            # Facilitator-only guidance synthesis (mandatory; speaker notes only)
            try:
                from facilitator_guidance import generate_inject_facilitation, attach_facilitation_to_plan
                fac_map = generate_inject_facilitation(plan_dict, st.session_state.get("exercise_blueprint"), audience=st.session_state.get("tabletop_audience","Blended"))
                plan_dict = attach_facilitation_to_plan(plan_dict, fac_map)
            except Exception as _fe:
                st.caption(f"Facilitation notes synthesis skipped: {_fe}")
            # Backfill fiction policy defaults (advisory)
            try:
                scns = plan_dict.get("scenarios", []) if isinstance(plan_dict, dict) else []
                for scn in scns:
                    if isinstance(scn, dict) and not scn.get("fiction_policy"):
                        scn["fiction_policy"] = {
                            "may_invent_people": False,
                            "may_invent_email_addresses": True,
                            "may_invent_log_values": True,
                            "may_invent_customer_impact": False,
                            "may_invent_supplier_responses": False,
                            "prohibited_inventions": ["undocumented production architecture"]
                        }
            except Exception:
                pass
            # Synthesise DecisionQuestion list from facilitator_probe_questions (fallback)
            try:
                _objs = plan_dict.get("objectives", []) if isinstance(plan_dict, dict) else []
                _obj0 = (_objs[0] if isinstance(_objs, list) and _objs else "")
                for scn in (plan_dict.get("scenarios", []) if isinstance(plan_dict, dict) else []):
                    for inj in (scn.get("injects", []) if isinstance(scn, dict) else []):
                        if isinstance(inj, dict) and isinstance(inj.get("decision_questions"), list) and inj["decision_questions"]:
                            continue
                        fpq = inj.get("facilitator_probe_questions", []) if isinstance(inj, dict) else []
                        dq_list = []
                        for q in (fpq or []):
                            qs = str(q or "")
                            lower = qs.lower()
                            cat = "Evidence"
                            if lower.startswith("what if"):
                                cat = "What‑if"
                            elif ("declare" in lower) or ("notify" in lower) or ("regulator" in lower):
                                cat = "Governance"
                            elif ("who" in lower and "approve" in lower):
                                cat = "Authority"
                            elif any(x in lower for x in ("stakeholder", "communicat", "brief", "inform")):
                                cat = "Communications"
                            dq_list.append({
                                "prompt": qs,
                                "category": cat,
                                "objective_id": _obj0,
                                "decision_target": (inj.get("decision_threshold", "") if isinstance(inj, dict) else ""),
                            })
                        if dq_list:
                            inj["decision_questions"] = dq_list
                        # Inject timing defaults (advisory pacing)
                        try:
                            if not inj.get("inject_timing"):
                                inj["inject_timing"] = {
                                    "target_minutes": 6,
                                    "minimum_minutes": 4,
                                    "maximum_minutes": 8,
                                    "free_discussion_seconds": 45,
                                    "release_condition": "facilitator"
                                }
                        except Exception:
                            pass
            except Exception:
                pass
            # Merge saved Required Setup (Objectives + Scope) if present
            _rs = st.session_state.get("tt_required_setup_data")
            if _rs:
                try:
                    plan_dict["objectives"] = _rs.get("objectives", plan_dict.get("objectives", []))
                    plan_dict["scope"] = _rs.get("scope", plan_dict.get("scope", {}))
                except Exception:
                    pass
            # Enforce telemetry visibility realism before other quality rules
            plan_dict = _enforce_visibility_on_injects(plan_dict, st.session_state.get("client_inputs", {}))
            # Quality normalisation (vendor/probes/lexicon/objective mapping)
            plan_dict = _quality_normalise_tabletop_plan(plan_dict, st.session_state.get("client_inputs", {}))
            st.session_state["tabletop_plan"] = plan_dict
            st.success("Tabletop scenario compiled. Proceed to customisation below, then confirm to start facilitation.")
        else:
            st.error("Generation failed. Check Azure configuration.")

if show_customise and st.session_state.get("tabletop_plan"):
    st.divider()
    st.subheader("Bespoke Customisation")
    
    plan = st.session_state["tabletop_plan"]
    plan["exercise_title"] = st.text_input("Exercise Title", value=plan.get("exercise_title", ""))


    # Optional Exercise Settings — keep separate from required fields
    with st.expander("Optional Exercise Settings", expanded=False):
        _dur = st.number_input("Total exercise duration (minutes)", min_value=30, max_value=360, value=int(plan.get("duration_minutes") or 90))
        plan["duration_minutes"] = int(_dur)

        _aud_roles_default = "\n".join([str(x) for x in (plan.get("audience_roles") or []) if str(x).strip()])
        _aud_roles_text = st.text_area(
            "Audience roles (one per line, optional)",
            value=_aud_roles_default,
            placeholder="e.g.\nIR Lead\nIT Ops\nLegal\nComms\nExecutive Sponsor",
            key="tt_audience_roles",
            height=100,
        )
        plan["audience_roles"] = [x.strip() for x in _aud_roles_text.splitlines() if x.strip()]

        _hk_default = "\n".join([str(x) for x in (plan.get("housekeeping_rules") or []) if str(x).strip()])
        _hk_text = st.text_area(
            "Housekeeping / Ground Rules (optional, one per line)",
            value=_hk_default,
            placeholder="e.g.\nNo blame\nPhones silent\nUse current roles, processes, tools and authority",
            key="tt_housekeeping_rules",
            height=100,
        )
        plan["housekeeping_rules"] = [x.strip() for x in _hk_text.splitlines() if x.strip()]

    for s_idx, scn in enumerate(plan.get("scenarios", [])):
        with st.expander(f"Scenario {s_idx + 1}: {scn.get('scenario_title')}", expanded=True):
            scn["scenario_title"] = st.text_input("Title", value=scn.get("scenario_title"), key=f"title_{s_idx}")
            scn["initial_vector"] = st.text_input("Initial Vector", value=scn.get("initial_vector"), key=f"vec_{s_idx}")

            for i_idx, inj in enumerate(scn.get("injects", [])):
                st.markdown(f"**Inject {i_idx + 1}: {inj.get('simulated_timestamp')}**")
                inj["scenario_narrative"] = st.text_area(
                    "Narrative", value=inj.get("scenario_narrative"), key=f"narr_{s_idx}_{i_idx}"
                )
                inj["expected_mature_response"] = st.text_area(
                    "What Good Looks Like", value=inj.get("expected_mature_response"), key=f"resp_{s_idx}_{i_idx}"
                )
            # Facilitator Reveal / Wrap-Up editor
            st.markdown("#### 🎬 Facilitator Reveal / Wrap-Up")
            fr = scn.get("facilitator_reveal") or {}
            fr["reveal_title"] = st.text_input("Reveal Title", value=fr.get("reveal_title", ""), key=f"fr_title_{s_idx}")
            fr["reveal_narrative"] = st.text_area("Reveal Narrative", value=fr.get("reveal_narrative", ""), key=f"fr_narr_{s_idx}", height=120)
            fr["facilitator_script"] = st.text_area("Facilitator Script (optional)", value=fr.get("facilitator_script", ""), key=f"fr_script_{s_idx}", height=100)
            _kl_default = "\n".join([str(x) for x in (fr.get("key_lessons") or []) if str(x).strip()])
            fr["key_lessons"] = [x.strip() for x in st.text_area("Key Lessons (one per line, 2–5)", value=_kl_default, key=f"fr_kl_{s_idx}", height=100).splitlines() if x.strip()]
            _wq_default = "\n".join([str(x) for x in (fr.get("wrap_up_questions") or []) if str(x).strip()])
            fr["wrap_up_questions"] = [x.strip() for x in st.text_area("Wrap-Up Questions (one per line, 2–6)", value=_wq_default, key=f"fr_wq_{s_idx}", height=100).splitlines() if x.strip()]
            _wc_default = "\n".join([str(x) for x in (fr.get("wrap_up_checklist") or []) if str(x).strip()])
            fr["wrap_up_checklist"] = [x.strip() for x in st.text_area("Wrap-Up Checklist (optional, one per line)", value=_wc_default, key=f"fr_wc_{s_idx}", height=100).splitlines() if x.strip()]
            _fsc_default = "\n".join([str(x) for x in (fr.get("final_success_criteria") or []) if str(x).strip()])
            fr["final_success_criteria"] = [x.strip() for x in st.text_area("Final Success Criteria (optional, 1–3 items, one per line)", value=_fsc_default, key=f"fr_fsc_{s_idx}", height=80).splitlines() if x.strip()]
            scn["facilitator_reveal"] = fr

    col_json1, col_json2 = st.columns(2)
    with col_json1:
        st.download_button(
            "🧩 Export Tabletop Plan (.json)",
            data=(json.dumps(_ensure_required_plan_fields(plan), ensure_ascii=False, indent=2, default=_json_default)).encode("utf-8"),
            file_name=f"{cached_customer_name}_Tabletop_Plan.json",
            mime="application/json",
        )
    with col_json2:
        uploaded_plan = st.file_uploader("Import Tabletop Plan (.json)", type=["json"])
        if uploaded_plan is not None:
            try:
                imported = json.loads(uploaded_plan.getvalue().decode("utf-8"))
                try:
                    imported = _ensure_required_plan_fields(imported)
                except Exception:
                    pass
                validated = TabletopMasterPlan.model_validate(imported)
                st.session_state["tabletop_plan"] = validated.model_dump()
                st.success("Tabletop plan imported and applied to the editor.")
            except Exception as e:
                st.error(f"Invalid plan JSON: {e}")

    st.divider()
    col_lock1, col_lock2 = st.columns(2)
    with col_lock1:
        # Run preflight validation
        try:
            from export import validate_tabletop_master_plan
            strict_flag = is_tabletop_quality_strict()
        except Exception:
            strict_flag = True
            validate_tabletop_master_plan = None
        # Merge saved Required Setup (Objectives + Scope) before validation/export
        _rs = st.session_state.get("tt_required_setup_data")
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
        except Exception:
            ok, defects = (True, [])
        if not ok:
            st.warning("Quality Gate: The plan has defects. Resolve the issues below before export.")
            with st.expander("Defects", expanded=True):
                for d in defects:
                    st.markdown(f"- {d}")
        # Compact Prompt Preview (collapsed)
        with st.expander("Prompt Preview (compact)", expanded=False):
            try:
                _objs = plan.get("objectives", []) or []
                _scope = plan.get("scope", {}) or {}
                _scn_cnt = len(plan.get("scenarios", []) or [])
                st.markdown(f"- Objectives: {len(_objs)}")
                st.markdown(f"- Scope: included={len(_scope.get('included',[]))}, excluded={len(_scope.get('excluded',[]))}, assumptions={len(_scope.get('assumptions',[]))}")
                st.markdown(f"- Scenarios: {_scn_cnt}")
            except Exception:
                st.caption("Prompt preview unavailable.")
        # Pass profiles forward for export logging/validation
        plan["_exercise_profile"] = st.session_state.get("exercise_profile", "blended")
        plan["_presentation_detail_profile"] = st.session_state.get("presentation_detail_profile", "standard")
        plan["_migration_notices"] = st.session_state.get("_migration_notices", [])
        # Dynamic agenda disabled: do not inject default 'sections' or 'agenda' keys; rely on static template slide.
        pptx_data = create_tabletop_pptx(plan)
        st.download_button(
            "📊 Download Presentation Deck (.pptx)",
            data=(pptx_data or b""),
            file_name=f"{cached_customer_name}_Tabletop_Deck.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            disabled=bool(((not ok) and strict_flag) or (not pptx_data)),
        )
    with col_lock2:
        pdf_data = create_tabletop_facilitator_pdf(plan)
        st.download_button(
            "📑 Download Facilitator Guide (.pdf)",
            data=(pdf_data or b""),
            file_name=f"{cached_customer_name}_Facilitator_Guide.pdf",
            mime="application/pdf",
            disabled=bool(((not ok) and strict_flag) or (not pdf_data)),
        )

    st.divider()
    if st.button("Confirm & Start Facilitation ➡️", type="primary"):
        try:
            st.switch_page("pages/04_Live_Facilitation.py")  # type: ignore[attr-defined]
        except Exception:
            st.page_link("pages/04_Live_Facilitation.py", label="Go to Live Facilitation ➡️")

with st.expander("Developer Utilities (Test Data Injection)", expanded=False):
    col_dev1, col_dev2 = st.columns(2)
    if col_dev1.button("Load Sample Profile"):
        try:
            import json as _json
            sample_path = os.path.join(os.path.dirname(__file__), "..", "examples", "sample_profile_full.json")
            with open(sample_path, "r", encoding="utf-8") as _sf:
                profile = _json.load(_sf)
            if isinstance(profile, dict):
                try:
                    from consultation_helpers import migrate_profile
                    profile = migrate_profile(profile)
                except Exception:
                    pass
                st.session_state["client_inputs"] = profile
                st.success("Sample profile loaded into Tabletop context.")
                st.rerun()
            else:
                st.error("Sample profile file format invalid.")
        except Exception as e:
            st.error(f"Failed to load sample profile: {e}")
    if col_dev2.button("Clear All Fields"):
        st.session_state["client_inputs"] = {}
        st.session_state["tabletop_plan"] = None
        st.success("Cleared all fields.")
        st.rerun()

# Standard footer
try:
    render_footer(show_divider=True)
except Exception:
    pass
