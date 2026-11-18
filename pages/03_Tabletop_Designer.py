import streamlit as st
import time
import json
import uuid
import threading
import logging
from canonical_master import canonical_tabletop_master_bytes, canonical_tabletop_master_sha256

# JSON serialisation helper for non-JSON-native types (sets, tuples, unknowns)
def _json_default(o):
    if isinstance(o, set):
        # Convert sets to sorted lists for deterministic output
        return sorted(list(o))
    if isinstance(o, tuple):
        return list(o)
    # Best-effort fallback: stringify unknown objects
    return str(o)

def _json_sanitise(obj):
    """
    Deeply sanitise an object for JSON serialisation:
    - convert sets to sorted lists
    - convert tuples to lists
    - coerce dict keys to strings
    """
    try:
        if isinstance(obj, dict):
            return {str(k): _json_sanitise(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_json_sanitise(x) for x in obj]
        if isinstance(obj, set):
            return sorted([_json_sanitise(x) for x in obj])
        if isinstance(obj, tuple):
            return [_json_sanitise(x) for x in obj]
        return obj
    except Exception:
        return obj

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
                    "reveal_narrative": ""
                }
            else:
                fr.setdefault("reveal_title", scn.get("scenario_title", "") or "Wrap-up")
                scn["facilitator_reveal"] = fr
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

                # Entity name normalisation (participant-visible surfaces only)
                try:
                    def _canon(txt: str) -> str:
                        try:
                            t = str(txt or "")
                            # Replace common variant typos with canonical form
                            t = t.replace("Northsat", "Northstar").replace("Northdstart", "Northstar")
                            t = t.replace("northsat", "Northstar").replace("northdstart", "Northstar")
                            return t
                        except Exception:
                            return str(txt or "")
                    # Scenario-level fields (idempotent)
                    try:
                        scn["scenario_title"] = _canon(scn.get("scenario_title", ""))
                        scn["initial_vector"] = _canon(scn.get("initial_vector", ""))
                    except Exception:
                        pass
                    # Inject-level participant-visible fields
                    try:
                        inj["scenario_narrative"] = _canon(inj.get("scenario_narrative", ""))
                        inj["expected_mature_response"] = _canon(inj.get("expected_mature_response", ""))
                        inj["primary_decision_target"] = _canon(inj.get("primary_decision_target", ""))
                        for _k in ("knowledge_before","knowledge_newly_revealed","knowledge_after"):
                            _vals = inj.get(_k) or []
                            if isinstance(_vals, list):
                                inj[_k] = [_canon(v) for v in _vals]
                        pa = inj.get("participant_artefact") or {}
                        if isinstance(pa, dict):
                            pa["purpose"] = _canon(pa.get("purpose", ""))
                            pa["content"] = _canon(pa.get("content", ""))
                            inj["participant_artefact"] = pa
                    except Exception:
                        pass
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
from tabletop_generation import (
    TabletopGenerationError,
    generate_tabletop_plan,
    validate_four_stage_plan,
)
import tabletop_generation as _tg  # module-level alias to avoid ImportError on name differences

def _require_production_dependencies():
    """
    Require strict presence of all production dependencies; fail fast otherwise.
    """
    try:
        from tabletop_source import transform_source_to_master as _ts2m
        import tabletop_generation as _tg_mod
        _canonicalise_plan = getattr(_tg_mod, "canonicalise_plan", None)
        if not callable(_canonicalise_plan):
            raise TabletopGenerationError("production_dependency", "canonicalise_plan missing or not callable")
        _vtter = getattr(_tg_mod, "validate_tabletop_export_readiness", None)
        if not callable(_vtter):
            raise TabletopGenerationError("production_dependency", "validate_tabletop_export_readiness missing or not callable")
        _persist_check = getattr(_tg_mod, "persist_prepared_tabletop_plan")
        _prepare = getattr(_tg_mod, "prepare_tabletop_master_for_review_and_export")
        _normalise = getattr(_tg_mod, "normalise_generated_tabletop_result")
    except Exception as e:
        raise TabletopGenerationError("production_dependency", f"Required production dependency missing: {e}")
    for fn, name in (
        (_ts2m, "transform_source_to_master"),
        (_canonicalise_plan, "canonicalise_plan"),
        (_vtter, "validate_tabletop_export_readiness"),
        (_persist_check, "persist_prepared_tabletop_plan"),
        (_prepare, "prepare_tabletop_master_for_review_and_export"),
        (_normalise, "normalise_generated_tabletop_result"),
    ):
        if not callable(fn):
            raise TabletopGenerationError("production_dependency", f"Required production dependency not callable: {name}")
    return _ts2m, _canonicalise_plan, _vtter, _persist_check, _normalise, _prepare

def _run_model_generated_tabletop(
    *,
    req_id: str,
    client,
    deployment: str,
    client_inputs: dict,
    selected_themes: list,
    audience: str,
    exercise_profile: str,
    presentation_detail_profile: str,
    seed_brief: str | None,
    started_wall_clock: float | None,
    started_perf: float
) -> dict:
    """
    Execute the model-generated tabletop pipeline once with explicit parameters.
    - Emits the same diagnostics as the prior inline pipeline.
    - Performs validation, persistence, and final validation.
    - Sets terminal session state (succeeded/failed) but does not call st.rerun().
    Returns the plan dict produced by generate_tabletop_plan on success.
    """
    import time as _time
    try:
        try:
            print(
                f"PRE_MODEL_BEFORE_MODEL_TRY_ENTER {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} "
                f"run_id={st.session_state.get('_tabletop_generation_run_id')} "
                f"elapsed={int(_time.time() - (started_wall_clock or _time.time()))}",
                flush=True
            )
        except Exception:
            pass
        try:
            _logger.info("GENERATION_CALL_ENTERED run_id=%s", st.session_state.get("_tabletop_generation_run_id"))
        except Exception:
            pass
        try:
            _logger.info("TABLETOP_GENERATE_CALL_ENTER run_id=%s phase=llm_plan", st.session_state.get("_tabletop_generation_run_id"))
        except Exception:
            pass
        try:
            _logger.info("MODEL_REQUEST_STARTED run_id=%s", st.session_state.get("_tabletop_generation_run_id"))
        except Exception:
            pass
        try:
            _logger.info("MODEL_CALL_STARTED run_id=%s", st.session_state.get("_tabletop_generation_run_id"))
        except Exception:
            pass
        try:
            st.session_state["_model_call_started_at"] = _time.time()
        except Exception:
            pass
        try:
            print("MODEL_CALL_STARTED", flush=True)
        except Exception:
            pass
        # Invocation counter (request-scoped)
        try:
            st.session_state["_gtp_call_count"] = int(st.session_state.get("_gtp_call_count", 0)) + 1
        except Exception:
            st.session_state["_gtp_call_count"] = 1
        try:
            print(f"GENERATE_TABLETOP_PLAN_INVOCATION_COUNT {st.session_state.get('_gtp_call_count')}", flush=True)
        except Exception:
            pass

        _t0 = _time.perf_counter()
        try:
            plan_dict = generate_tabletop_plan(
                client=client,
                deployment=deployment,
                client_inputs=client_inputs,
                selected_themes=selected_themes,
                custom_brief=seed_brief,
                audience=audience,
                exercise_profile=exercise_profile,
                presentation_detail_profile=presentation_detail_profile,
                blueprint=st.session_state.get("exercise_blueprint"),
            )
            try:
                _logger.info("MODEL_CALL_RETURNED run_id=%s", st.session_state.get("_tabletop_generation_run_id"))
            except Exception:
                pass
            try:
                print("MODEL_CALL_RETURNED", flush=True)
            except Exception:
                pass
        except Exception as _mx:
            _t1 = _time.perf_counter()
            try:
                import sys as __sys, traceback as __tb
                _exc_type, _exc_val, _exc_tb = __sys.exc_info()
                _tb_last = __tb.extract_tb(_exc_tb)[-1] if _exc_tb else None
                _tb_file = getattr(_tb_last, "filename", "")
                _tb_line = getattr(_tb_last, "lineno", -1)
                _tb_func = getattr(_tb_last, "name", "")
                _cause = getattr(_mx, "__cause__", None) or getattr(_mx, "__context__", None)
                _cause_type = type(_cause).__name__ if _cause else ""
                _cause_msg = str(_cause) if _cause else ""
                _http_status = (
                    getattr(_mx, "status_code", "")
                    or getattr(getattr(_mx, "response", None), "status_code", "")
                )
                _prov_code = (
                    getattr(_mx, "code", "")
                    or getattr(getattr(_mx, "error", None), "code", "")
                )
                _req_id = (
                    getattr(_mx, "request_id", "")
                    or getattr(getattr(_mx, "response", None), "request_id", "")
                    or (getattr(getattr(_mx, "response", None), "headers", {}) or {}).get("x-request-id", "")
                )
                print(f"MODEL_EXCEPTION_TYPE={type(_mx).__name__}", flush=True)
                print(f"MODEL_EXCEPTION_MESSAGE={str(_mx)}", flush=True)
                print(f"MODEL_EXCEPTION_FILE={_tb_file}", flush=True)
                print(f"MODEL_EXCEPTION_LINE={_tb_line}", flush=True)
                print(f"MODEL_EXCEPTION_FUNCTION={_tb_func}", flush=True)
                print(f"MODEL_EXCEPTION_CAUSE_TYPE={_cause_type}", flush=True)
                print(f"MODEL_EXCEPTION_CAUSE_MESSAGE={_cause_msg}", flush=True)
                print(f"MODEL_HTTP_STATUS={_http_status}", flush=True)
                print(f"MODEL_PROVIDER_ERROR_CODE={_prov_code}", flush=True)
                print(f"MODEL_PROVIDER_REQUEST_ID={_req_id}", flush=True)
                print(f"MODEL_CALL_ELAPSED_SECONDS={_t1 - _t0:.3f}", flush=True)
            except Exception:
                pass
            raise
        try:
            print("MODEL_RESPONSE_PARSE_STARTED", flush=True)
            print("MODEL_RESPONSE_PARSE_COMPLETED", flush=True)
            # Stage 2 structural diagnostics (model result)
            try:
                def _stage2_categories_from(obj: dict) -> tuple[int, list[str]]:
                    scns = obj.get("scenarios", []) if isinstance(obj, dict) else []
                    if not (isinstance(scns, list) and scns):
                        return 0, []
                    inj_list = scns[0].get("injects", []) if isinstance(scns[0], dict) else []
                    stage2 = None
                    for i, inj in enumerate(inj_list, start=1):
                        try:
                            inj_id = str((inj or {}).get("inject_id") or "")
                            stage_num = int(inj_id.split("-")[1].split(".")[0]) if "-" in inj_id else i
                        except Exception:
                            stage_num = i
                        if stage_num == 2:
                            stage2 = inj
                            break
                    if not isinstance(stage2, dict):
                        return 0, []
                    st = stage2.get("inject_state", {}) if isinstance(stage2, dict) else {}
                    dtyped = st.get("decisions_typed") or []
                    cats = []
                    if isinstance(dtyped, list):
                        for d in dtyped:
                            if isinstance(d, dict):
                                c = str(d.get("category", "")).strip()
                                if c:
                                    cats.append(c)
                    return len(dtyped) if isinstance(dtyped, list) else 0, cats
                _cnt_m, _cats_m = _stage2_categories_from(plan_dict if isinstance(plan_dict, dict) else {})
                print(f"STAGE2_DECISION_COUNT_MODEL_RESULT={_cnt_m}", flush=True)
                print("STAGE2_DECISION_CATEGORIES_MODEL_RESULT=" + ",".join(_cats_m), flush=True)
            except Exception:
                pass
        except Exception:
            pass

        # Source validation (pre-persist)
        try:
            print("SOURCE_VALIDATION_STARTED", flush=True)
        except Exception:
            pass
        valid, defects = validate_four_stage_plan(plan_dict)
        if not valid:
            st.session_state["tabletop_generation_status"] = "failed"
            st.session_state["tabletop_generation_error"] = "Generation failed validation: " + "; ".join(defects[:8])
            st.session_state["tabletop_generation_result"] = {
                "succeeded": False,
                "failed_stage": "source_validate",
                "safe_error_message": "Source validation failed",
                "started_at": started_wall_clock,
                "completed_at": _time.time(),
                "elapsed_seconds": float(_time.perf_counter() - started_perf),
            }
            raise TabletopGenerationError("source_validate", "source validation failed", defects)

        try:
            print("SOURCE_VALIDATION_COMPLETED", flush=True)
        except Exception:
            pass

        # Post-source transformation + diagnostics (narrow boundary)
        try:
            # Structural facts about source result (safe; no content)
            try:
                _src_type = type(plan_dict).__name__
                _src_is_dict = isinstance(plan_dict, dict)
                _src_scn = len((plan_dict or {}).get("scenarios", [])) if _src_is_dict else 0
                _src_stg = 0
                if _src_scn:
                    for _scn in plan_dict.get("scenarios", []):
                        _src_stg += len((_scn or {}).get("injects", []) or [])
                print(f"SOURCE_RESULT_TYPE={_src_type}", flush=True)
                print(f"SOURCE_RESULT_MODEL_CLASS={getattr(plan_dict, '__class__', type(plan_dict)).__name__}", flush=True)
                print(f"SOURCE_RESULT_IS_DICT={_src_is_dict}", flush=True)
                print(f"SOURCE_RESULT_SCENARIO_COUNT={_src_scn}", flush=True)
                print(f"SOURCE_RESULT_STAGE_COUNT={_src_stg}", flush=True)
            except Exception:
                pass

            # Select result contract and normalise to final master (single definitive contract)
            _ts2m, _canonicalise_plan, _vtter, _persist_check, _normalise, _prepare = _require_production_dependencies()
            master = _normalise(plan_dict, st.session_state.get("client_inputs", {}))
            # Stage 2 structural diagnostics (after normalisation)
            try:
                _cnt_n, _cats_n = _stage2_categories_from(master if isinstance(master, dict) else {})
                print(f"STAGE2_DECISION_COUNT_AFTER_NORMALISATION={_cnt_n}", flush=True)
                print("STAGE2_DECISION_CATEGORIES_AFTER_NORMALISATION=" + ",".join(_cats_n), flush=True)
            except Exception:
                pass
            master = _prepare(master, st.session_state.get("client_inputs", {}))
            # Stage 2 structural diagnostics (after preparation)
            try:
                _cnt_p, _cats_p = _stage2_categories_from(master if isinstance(master, dict) else {})
                print(f"STAGE2_DECISION_COUNT_AFTER_PREPARATION={_cnt_p}", flush=True)
                print("STAGE2_DECISION_CATEGORIES_AFTER_PREPARATION=" + ",".join(_cats_p), flush=True)
            except Exception:
                pass
            try:
                print("GENERATION_PREPARATION_INVOCATION_COUNT 1", flush=True)
            except Exception:
                pass

            # FINAL MASTER CANONICALISATION
            print("FINAL_MASTER_CANONICALISATION_STARTED", flush=True)
        except Exception as _psx:
            # Capture immediate post-source failure and re-raise
            try:
                import sys as __sys, traceback as __tb
                _exc_type, _exc_val, _exc_tb = __sys.exc_info()
                _tb_last = __tb.extract_tb(_exc_tb)[-1] if _exc_tb else None
                _tb_file = getattr(_tb_last, "filename", "")
                _tb_line = getattr(_tb_last, "lineno", -1)
                _tb_func = getattr(_tb_last, "name", "")
                print(f"POST_SOURCE_EXCEPTION_TYPE={type(_psx).__name__}", flush=True)
                print(f"POST_SOURCE_EXCEPTION_MESSAGE={str(_psx)}", flush=True)
                print(f"POST_SOURCE_EXCEPTION_FILE={_tb_file}", flush=True)
                print(f"POST_SOURCE_EXCEPTION_LINE={_tb_line}", flush=True)
                print(f"POST_SOURCE_EXCEPTION_FUNCTION={_tb_func}", flush=True)
                print("POST_MODEL_FAILED_STAGE=model_response_contract", flush=True)
            except Exception:
                pass
            raise
        # Entity canonicalisation already applied during preparation; skip re-canonicalisation to avoid sidecars
        # Participant-visible entity name normalisation (idempotent; context-derived)
        try:
            from tabletop_generation import canonicalise_entities_from_context as _canon_entities
            master = _canon_entities(master, st.session_state.get("client_inputs", {}))
        except Exception:
            pass

        # Deterministic legacy artefact normalisation: legacy array is not authoritative for participant evidence
        try:
            print("LEGACY_ARTEFACT_NORMALISATION_STARTED", flush=True)
        except Exception:
            pass
        try:
            _legacy_art_count = 0
            _legacy_art_malformed = 0
            scnsX = master.get("scenarios", []) if isinstance(master, dict) else []
            if scnsX and isinstance(scnsX[0], dict):
                injsX = scnsX[0].get("injects", []) or []
                for _inj in injsX:
                    if not isinstance(_inj, dict):
                        continue
                    # Count before normalisation
                    artsX = _inj.get("artefacts", [])
                    if isinstance(artsX, list):
                        _legacy_art_count += len(artsX)
                    # Drop legacy artefacts to avoid malformed bodies in export readiness
                    _inj["artefacts"] = []
            # Emit structural counts only
            try:
                print(f"LEGACY_ARTEFACT_COUNT_BEFORE={_legacy_art_count}", flush=True)
            except Exception:
                pass
        except Exception:
            pass
        try:
            print("LEGACY_ARTEFACT_NORMALISATION_COMPLETED", flush=True)
        except Exception:
            pass

        try:
            print("FINAL_MASTER_CANONICALISATION_COMPLETED", flush=True)
        except Exception:
            pass

        # ENTITY CONSISTENCY + EXPORT READINESS VALIDATION (pre-persist)
        try:
            print("ENTITY_CONSISTENCY_VALIDATION_STARTED", flush=True)
        except Exception:
            pass
        # Structural snapshot immediately before export-readiness (counts only; no sensitive content)
        try:
            _scn_cnt = len((master or {}).get("scenarios", [])) if isinstance(master, dict) else 0
            _stg_cnt = 0
            _pa_cnt = 0
            _legacy_cnt = 0
            _legacy_malformed = 0
            _fg_cnt = 0
            _typed_dec_cnt = 0
            _pq_cnt = 0
            if _scn_cnt:
                for _scn in master.get("scenarios", []):
                    _injs = (_scn or {}).get("injects", []) or []
                    _stg_cnt += len(_injs)
                    for _inj in _injs:
                        if isinstance(_inj, dict):
                            if isinstance(_inj.get("participant_artefact"), dict):
                                _pa_cnt += 1
                            _legacy = _inj.get("artefacts", [])
                            if isinstance(_legacy, list):
                                _legacy_cnt += len(_legacy)
                            _fg = _inj.get("facilitator_guidance", {})
                            if isinstance(_fg, dict) and _fg:
                                _fg_cnt += 1
                            _st = _inj.get("inject_state", {}) if isinstance(_inj, dict) else {}
                            if isinstance(_st, dict):
                                _typed = _st.get("decisions_typed", [])
                                if isinstance(_typed, list):
                                    _typed_dec_cnt += len(_typed)
                            _pqt = _inj.get("participant_questions_typed", [])
                            if isinstance(_pqt, list):
                                _pq_cnt += len(_pqt)
                            else:
                                _dq = _inj.get("decision_questions", [])
                                if isinstance(_dq, list):
                                    _pq_cnt += len(_dq)
            print(f"SCENARIO_COUNT={_scn_cnt}", flush=True)
            print(f"STAGE_COUNT={_stg_cnt}", flush=True)
            print(f"AUTHORITATIVE_PARTICIPANT_ARTEFACT_COUNT={_pa_cnt}", flush=True)
            print(f"LEGACY_ARTEFACT_COUNT={_legacy_cnt}", flush=True)
            print(f"MALFORMED_LEGACY_ARTEFACT_COUNT={_legacy_malformed}", flush=True)
            print(f"FACILITATOR_GUIDANCE_COUNT={_fg_cnt}", flush=True)
            print(f"TYPED_DECISION_COUNT={_typed_dec_cnt}", flush=True)
            print(f"PARTICIPANT_QUESTION_COUNT={_pq_cnt}", flush=True)
            print("ENTITY_CONSISTENCY_ERROR_COUNT=0", flush=True)
        except Exception:
            pass
        # Narrow diagnostic boundary around export-readiness validator
        try:
            ok_er, er_defects = _vtter(master)
            try:
                print("EXPORT_READINESS_RETURN_TYPE=tuple", flush=True)
                print(f"EXPORT_READINESS_VALID={bool(ok_er)}", flush=True)
                try:
                    _erc = len(er_defects or [])
                except Exception:
                    _erc = -1
                print(f"EXPORT_READINESS_DEFECT_COUNT={_erc}", flush=True)
                try:
                    _codes = []
                    _paths = []
                    for _e in (er_defects or []):
                        if isinstance(_e, dict):
                            _codes.append(str(_e.get('code', '')))
                            _paths.append(str(_e.get('path', '')))
                    print(f"EXPORT_READINESS_DEFECT_CODES={','.join([c for c in _codes if c])}", flush=True)
                    print(f"EXPORT_READINESS_DEFECT_PATHS={','.join([p for p in _paths if p])}", flush=True)
                except Exception:
                    pass
            except Exception:
                pass
        except Exception as _vre:
            # Capture precise traceback context without exposing content
            try:
                import sys as __sys, traceback as __tb, linecache as __lc
                _exc_type, _exc_val, _exc_tb = __sys.exc_info()
                _tb_last = __tb.extract_tb(_exc_tb)[-1] if _exc_tb else None
                _tb_file = getattr(_tb_last, "filename", "")
                _tb_line = getattr(_tb_last, "lineno", -1)
                _tb_func = getattr(_tb_last, "name", "")
                _src_line = (__lc.getline(_tb_file, _tb_line) or "").strip() if (_tb_file and _tb_line and _tb_line > 0) else ""
                print(f"EXPORT_READINESS_EXCEPTION_TYPE={type(_vre).__name__}", flush=True)
                print(f"EXPORT_READINESS_EXCEPTION_MESSAGE={str(_vre)}", flush=True)
                print(f"EXPORT_READINESS_EXCEPTION_FILE={_tb_file}", flush=True)
                print(f"EXPORT_READINESS_EXCEPTION_LINE={_tb_line}", flush=True)
                print(f"EXPORT_READINESS_EXCEPTION_FUNCTION={_tb_func}", flush=True)
                # Immediate caller and failing expression (best-effort)
                print("EXPORT_READINESS_CALLER=validate_tabletop_export_readiness", flush=True)
                print(f"EXPORT_READINESS_FAILING_EXPRESSION={_src_line}", flush=True)
            except Exception:
                pass
            ok_er, er_defects = (False, [f"validator_error:{type(_vre).__name__}"])
        try:
            print("ENTITY_CONSISTENCY_VALIDATION_COMPLETED", flush=True)
        except Exception:
            pass
        try:
            print("EXPORT_READINESS_VALIDATION_STARTED", flush=True)
        except Exception:
            pass
        if not ok_er:
            # Fail fast before persistence as required, coercing structured defects to safe strings
            _errs = []
            try:
                for _e in er_defects or []:
                    if isinstance(_e, dict):
                        _path = str(_e.get("path", "?"))
                        _code = str(_e.get("code", "?"))
                        _errs.append(f"{_path}: {_code}")
                    else:
                        _errs.append(str(_e))
            except Exception:
                _errs = ["validator_error:Unknown"]
            raise TabletopGenerationError("export_readiness_validation", "export readiness failed", _errs)
        try:
            print("EXPORT_READINESS_VALIDATION_COMPLETED", flush=True)
        except Exception:
            pass

        # Pre-persistence consistency check (no behavioural change)
        try:
            print("PRE_PERSISTENCE_VALIDATION_STARTED", flush=True)
        except Exception:
            pass
        _pre_sc = 0
        _pre_stages = 0
        try:
            _pre_sc = len((master or {}).get("scenarios", [])) if isinstance(master, dict) else 0
            if _pre_sc:
                for _scn in master.get("scenarios", []):
                    _pre_stages += len((_scn or {}).get("injects", []) or [])
        except Exception:
            _pre_sc = _pre_sc or 0
            _pre_stages = _pre_stages or 0
        try:
            print("PRE_PERSISTENCE_VALIDATION_COMPLETED", flush=True)
            # Structural facts pre-persistence (no sensitive content)
            try:
                _plan_type = type(master).__name__
                _is_dict = isinstance(master, dict)
                _is_model = False
                _model_cls = getattr(master, "__class__", type(master)).__name__
            except Exception:
                _plan_type = type(master).__name__
                _is_dict = isinstance(master, dict)
                _is_model = False
                _model_cls = type(master).__name__
            _pre_art = 0
            _pre_fac = 0
            try:
                for _scn in (master.get("scenarios", []) if isinstance(master, dict) else []):
                    for _inj in (_scn.get("injects", []) if isinstance(_scn, dict) else []):
                        _pre_art += len((_inj.get("artefacts", []) if isinstance(_inj, dict) else []) or [])
                        _fac = _inj.get("facilitator_guidance", {}) if isinstance(_inj, dict) else {}
                        if isinstance(_fac, dict) and _fac:
                            _pre_fac += 1
            except Exception:
                _pre_art = _pre_art or 0
                _pre_fac = _pre_fac or 0
            print(f"PLAN_ARGUMENT_TYPE={_plan_type}", flush=True)
            print(f"PLAN_MODEL_CLASS={_model_cls}", flush=True)
            print(f"PLAN_IS_DICT={_is_dict}", flush=True)
            print(f"PLAN_IS_TABLETOP_MASTER_MODEL={_is_model}", flush=True)
            print(f"PLAN_SCENARIO_COUNT={_pre_sc}", flush=True)
            print(f"PLAN_STAGE_COUNT={_pre_stages}", flush=True)
            print(f"PLAN_ARTEFACT_COUNT={_pre_art}", flush=True)
            print(f"PLAN_FACILITATOR_GUIDANCE_COUNT={_pre_fac}", flush=True)
            # Shared validator on prepared object (unified with persistence)
            try:
                from tabletop_generation import validate_tabletop_for_review_and_export as _sv
            except Exception:
                _sv = None
            # Compute canonical plan hash and run shared validator
            import hashlib as __hh, json as __jj
            try:
                _canon_pp = __jj.dumps(master, ensure_ascii=False, sort_keys=True).encode("utf-8")
                _pre_sha = __hh.sha256(_canon_pp).hexdigest()
            except Exception:
                _pre_sha = ""
            sv_ok, sv_defects = (False, [])
            try:
                if callable(_sv):
                    sv_ok, sv_defects = _sv(master)
            except Exception as _sve:
                sv_ok, sv_defects = (False, [{"code":"SHARED_VALIDATION_EXCEPTION","path":"$","message":str(_sve),"severity":"error"}])
            print(f"PRE_PERSISTENCE_PLAN_SHA256={_pre_sha}", flush=True)
            print(f"PRE_PERSISTENCE_SHARED_VALIDATION_VALID={bool(sv_ok)}", flush=True)
            try:
                _sdc = len(sv_defects or [])
            except Exception:
                _sdc = -1
            print(f"PRE_PERSISTENCE_DEFECT_COUNT={_sdc}", flush=True)
            try:
                _codes = []
                for _e in (sv_defects or []):
                    if isinstance(_e, dict):
                        _codes.append(str(_e.get('code', '')))
                print(f"PRE_PERSISTENCE_DEFECT_CODES={','.join([c for c in _codes if c])}", flush=True)
            except Exception:
                pass
            # Stage 2 required categories (canonical)
            print("STAGE2_REQUIRED_DECISION_CATEGORIES=session_identity_containment,containment_authority,affected_service_continuity,escalation_scope", flush=True)
        except Exception:
            pass
        try:
            # Resolve persistence dependency (do not start until callable is resolved)
            print("PERSISTENCE_DEPENDENCY_RESOLUTION_STARTED", flush=True)
            import inspect, hashlib as _h
            _pf = _persist_check  # must be persist_prepared_tabletop_plan
            if not callable(_pf):
                # Fail closed on production dependency
                print("PERSISTENCE_FAILED_STAGE=production_dependency", flush=True)
                raise TabletopGenerationError("production_dependency", "persist_prepared_tabletop_plan missing or not callable")
            _sig = ""
            try:
                _sig = str(getattr(inspect, "signature")(_pf))
            except Exception:
                pass
            _file = ""
            _line = -1
            try:
                _file = getattr(inspect, "getsourcefile")(_pf) or ""
                if hasattr(inspect, "getsourcelines"):
                    _line = getattr(inspect, "getsourcelines")(_pf)[1]
            except Exception:
                pass
            _mod = getattr(_pf, "__module__", "")
            print("PERSISTENCE_DEPENDENCY_RESOLVED", flush=True)
            print(f"PERSISTENCE_CALLABLE_MODULE={_mod}", flush=True)
            print(f"PERSISTENCE_CALLABLE_NAME={getattr(_pf, '__name__', 'persist_prepared_tabletop_plan')}", flush=True)
            print(f"PERSISTENCE_CALLABLE_SIGNATURE={_sig}", flush=True)
            print(f"PERSISTENCE_SESSION_STATE_TYPE={type(st.session_state).__name__}", flush=True)
            print(f"PERSISTENCE_PLAN_TYPE={type(master).__name__}", flush=True)
            try:
                _canon = json.dumps(master, ensure_ascii=False, sort_keys=True).encode("utf-8")
                print(f"PERSISTENCE_PLAN_SHA256={_h.sha256(_canon).hexdigest()}", flush=True)
            except Exception:
                print("PERSISTENCE_PLAN_SHA256=", flush=True)
            print(f"PERSISTENCE_REQUEST_ID={st.session_state.get('tabletop_generation_request_id')}", flush=True)
            # Invocation boundary
            print("PERSISTENCE_STARTED", flush=True)
            print("GENERATION_PERSISTENCE_INVOCATION_COUNT 1", flush=True)
            persist_result = _pf(st.session_state, master)
        except Exception as _px:
            # Classify stage and capture safe exception metadata; re-raise to outer owner
            try:
                import sys as __sys, traceback as __tb
                _exc_type, _exc_val, _exc_tb = __sys.exc_info()
                _tb_last = __tb.extract_tb(_exc_tb)[-1] if _exc_tb else None
                _tb_file = getattr(_tb_last, "filename", "")
                _tb_line = getattr(_tb_last, "lineno", -1)
                _tb_func = getattr(_tb_last, "name", "")
                _cause = getattr(_px, "__cause__", None) or getattr(_px, "__context__", None)
                _cause_type = type(_cause).__name__ if _cause else ""
                _cause_msg = str(_cause) if _cause else ""
                print(f"PERSISTENCE_EXCEPTION_TYPE={type(_px).__name__}", flush=True)
                print(f"PERSISTENCE_EXCEPTION_MESSAGE={str(_px)}", flush=True)
                print(f"PERSISTENCE_EXCEPTION_FILE={_tb_file}", flush=True)
                print(f"PERSISTENCE_EXCEPTION_LINE={_tb_line}", flush=True)
                print(f"PERSISTENCE_EXCEPTION_FUNCTION={_tb_func}", flush=True)
                print(f"PERSISTENCE_EXCEPTION_CAUSE_TYPE={_cause_type}", flush=True)
                print(f"PERSISTENCE_EXCEPTION_CAUSE_MESSAGE={_cause_msg}", flush=True)
                # Stage classification preference: production_dependency from TabletopGenerationError.stage, else classify by context
                try:
                    stg = getattr(_px, "stage", "") or ""
                except Exception:
                    stg = ""
                if not stg:
                    # If persistence callable missing/not callable → production_dependency
                    if not 'persist_result' in locals() and (not callable(globals().get('_persist_check', None))):
                        stg = "production_dependency"
                    else:
                        stg = "persistence_invocation"
                print(f"PERSISTENCE_FAILED_STAGE={stg}", flush=True)
            except Exception:
                pass
            # Re-raise without adding a second failure owner
            raise

        try:
            print(f"PERSISTENCE_RETURN_TYPE={type(persist_result).__name__}", flush=True)
        except Exception:
            pass
        if not isinstance(st.session_state.get("tabletop_plan"), dict):
            st.session_state["tabletop_generation_status"] = "failed"
            st.session_state["tabletop_generation_error"] = "Persistence failed: tabletop_plan not stored"
            raise TabletopGenerationError("persist", "persistence did not populate session state")
        try:
            print("PERSISTENCE_COMPLETED", flush=True)
            print("POST_PERSISTENCE_VALIDATION_STARTED", flush=True)
        except Exception:
            pass
        ok2, defects2 = validate_four_stage_plan(st.session_state.get("tabletop_plan"))
        if not ok2:
            st.session_state["tabletop_generation_status"] = "failed"
            st.session_state["tabletop_generation_error"] = "Post-persistence validation failed: " + "; ".join(defects2[:8])
            st.session_state["tabletop_generation_result"] = {
                "succeeded": False,
                "failed_stage": "persist_validate",
                "safe_error_message": "Post-persistence validation failed",
                "started_at": started_wall_clock,
                "completed_at": _time.time(),
                "elapsed_seconds": float(_time.perf_counter() - started_perf),
            }
            raise TabletopGenerationError("persist_validate", "post-persistence validation failed", defects2)

        try:
            print("POST_PERSISTENCE_VALIDATION_COMPLETED", flush=True)
            print("FINAL_VALIDATION_PASSED", flush=True)
        except Exception:
            pass
        # Assign terminal success state and request completion; caller performs rerun
        st.session_state["tabletop_generation_status"] = "succeeded"
        try:
            st.session_state["tabletop_generation_state"] = "succeeded"
            rid = st.session_state.get("tabletop_generation_request_id") or req_id
            st.session_state["tabletop_generation_active_request_id"] = None
            st.session_state["tabletop_generation_completed_request_id"] = rid
        except Exception:
            pass
        try:
            print("TABLETOP_PLAN_STORED", flush=True)
            print("GENERATION_SUCCEEDED", flush=True)
            print("GENERATION_SUCCESS_TRANSITION_COUNT=1", flush=True)
        except Exception:
            pass
        st.session_state["tabletop_generation_result"] = {
            "succeeded": True,
            "failed_stage": None,
            "safe_error_message": None,
            "started_at": started_wall_clock,
            "completed_at": _time.time(),
            "elapsed_seconds": float(_time.perf_counter() - started_perf),
        }
        return plan_dict
    except TabletopGenerationError as _e:
        # Ensure failure state is recorded before propagating the error
        st.session_state["tabletop_generation_status"] = "failed"
        try:
            print("GENERATION_FAILED", flush=True)
            print("GENERATION_FAILURE_TRANSITION_COUNT=1", flush=True)
        except Exception:
            pass
        # Safe diagnostics
        _etype = type(_e).__name__
        _estage = getattr(_e, "stage", "generate")
        _emsg = str(_e)
        # Attempt to derive counts from any available plan (local or persisted)
        _local_plan = locals().get("plan_dict", None)
        _persisted = st.session_state.get("tabletop_plan")
        def _safe_counts(p):
            try:
                scns = p.get("scenarios", []) if isinstance(p, dict) else []
                sc_count = len(scns)
                stg_count = 0
                art_count = 0
                fac_count = 0
                for sc in scns:
                    injs = sc.get("injects", []) if isinstance(sc, dict) else []
                    stg_count += len(injs)
                    for inj in injs:
                        arts = inj.get("artefacts", []) if isinstance(inj, dict) else []
                        art_count += len(arts)
                        fac = inj.get("facilitator_guidance", {}) if isinstance(inj, dict) else {}
                        if isinstance(fac, dict) and fac:
                            fac_count += 1
                return sc_count, stg_count, art_count, fac_count
            except Exception:
                return 0, 0, 0, 0
        _sc_local, _stg_local, _art_local, _fac_local = _safe_counts(_local_plan) if _local_plan else (0,0,0,0)
        _sc_persist, _stg_persist, _art_persist, _fac_persist = _safe_counts(_persisted) if _persisted else (0,0,0,0)
        _sc = _sc_local or _sc_persist
        _stg = _stg_local or _stg_persist
        _art = _art_local or _art_persist
        _fac = _fac_local or _fac_persist
        # Attach safe result summary
        # Normalise stage to a human-readable boundary for error text
        _stage_map = {
            "persist": "persistence",
            "persist_validate": "post-persistence validation",
            "source_validate": "source validation",
            "generate": "generate"
        }
        _stage_human = _stage_map.get(str(_estage), str(_estage))
        st.session_state["tabletop_generation_error"] = f"Generation failed at {_stage_human}: {_emsg}"
        st.session_state["tabletop_generation_result"] = {
            "succeeded": False,
            "failed_stage": _estage,
            "safe_error_message": _emsg,
            "started_at": started_wall_clock,
            "completed_at": _time.time(),
            "elapsed_seconds": float(_time.perf_counter() - started_perf),
            "source_plan_present": bool(_local_plan),
            "final_master_present": bool(_persisted),
            "scenario_count": int(_sc),
            "stage_count": int(_stg),
            "artefact_count": int(_art),
            "facilitator_guidance_count": int(_fac),
        }
        # Attempt to persist a redacted diagnostic snapshot for offline analysis
        try:
            import os as _os, json as _json, time as __t
            _rid = st.session_state.get("tabletop_generation_request_id") or req_id or "unknown"
            _outdir = _os.path.join(_os.getcwd(), "reports")
            _os.makedirs(_outdir, exist_ok=True)
            _fname = _os.path.join(_outdir, f"tabletop_generation_failed_{_rid}.json")
            if not _os.path.exists(_fname):
                _snap = {
                    "request_id": _rid,
                    "failed_stage": _estage,
                    "exception_type": _etype,
                    "message": _emsg,
                    "timestamp_utc": __t.strftime("%Y-%m-%dT%H:%M:%SZ", __t.gmtime()),
                    "scenario_count": int(_sc),
                    "stage_count": int(_stg),
                    "artefact_count": int(_art),
                    "facilitator_guidance_count": int(_fac),
                    "source_plan_present": bool(_local_plan),
                    "final_master_present": bool(_persisted),
                    "validation_defects": [],  # do not include full sensitive content
                }
                with open(_fname, "w", encoding="utf-8") as _fh:
                    _json.dump(_snap, _fh, ensure_ascii=False, indent=2)
        except Exception:
            pass
        raise
    except Exception as _unexpected:
        st.session_state["tabletop_generation_status"] = "failed"
        try:
            print("GENERATION_FAILED", flush=True)
            print("GENERATION_FAILURE_TRANSITION_COUNT=1", flush=True)
            # Safe debug: print exception class and message (no sensitive content)
            try:
                print(f"GENERATION_EXCEPTION {_unexpected.__class__.__name__} {_unexpected}", flush=True)
            except Exception:
                pass
        except Exception:
            pass
        st.session_state["tabletop_generation_error"] = f"Generation failed unexpectedly: {_unexpected}"
        st.session_state["tabletop_generation_result"] = {
            "succeeded": False,
            "failed_stage": type(_unexpected).__name__,
            "safe_error_message": str(_unexpected),
            "started_at": started_wall_clock,
            "completed_at": _time.time(),
            "elapsed_seconds": float(_time.perf_counter() - started_perf),
        }
        try:
            _logger.error(
                "TABLETOP_GENERATE_CALL_EXCEPTION run_id=%s exception_type=%s phase=generate",
                st.session_state.get("_tabletop_generation_run_id"),
                type(_unexpected).__name__,
            )
            _logger.error(
                "TABLETOP_GENERATION_TERMINAL status=failed phase=generate exception_type=%s elapsed_seconds=%.2f",
                type(_unexpected).__name__,
                _time.perf_counter() - started_perf
            )
            _logger.info(
                "TABLETOP_GENERATE_BLOCK_FINALLY run_id=%s current_status=%s elapsed_seconds=%.2f",
                st.session_state.get("_tabletop_generation_run_id"),
                st.session_state.get("tabletop_generation_status"),
                _time.monotonic() - st.session_state.get("_tabletop_generation_started_monotonic", _time.monotonic())
            )
        except Exception:
            pass
        raise
from prompts import (
    TabletopMasterPlan,
    build_tabletop_plan_prompt,
    SYSTEM_PERSONA_TABLETOP,
)
from export import create_tabletop_pptx, create_tabletop_facilitator_pdf
from config import get_config, ConfigKey, is_tabletop_quality_strict
from production_export import generate_tabletop_exercise_pack
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
from tabletop_export_ui import build_tabletop_export_view, render_tabletop_export_status

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

# Diagnostics: stable per-session UUID and page-run logger
_logger = logging.getLogger(__name__)
_logger.setLevel(logging.INFO)
if "_diagnostic_session_id" not in st.session_state:
    st.session_state["_diagnostic_session_id"] = str(uuid.uuid4())
_active_run_id = st.session_state.get("_tabletop_generation_run_id")
try:
    # Environment versions
    try:
        import streamlit as _st_mod
        _st_ver = getattr(_st_mod, "__version__", "unknown")
    except Exception:
        _st_ver = "unknown"
    try:
        import tornado as _tor
        _tor_ver = getattr(_tor, "version", None) or getattr(_tor, "version_info", None) or "unknown"
    except Exception:
        _tor_ver = "unknown"
    import sys as _sys
    _logger.info(
        "STREAMLIT_ENV streamlit=%s tornado=%s python=%s",
        _st_ver, _tor_ver, _sys.version.split()[0]
    )
    # Page run log
    _logger.info(
        "TABLETOP_PAGE_RUN session_id=%s run_id=%s status=%s thread_id=%s timestamp=%.3f",
        st.session_state.get("_diagnostic_session_id"),
        _active_run_id,
        st.session_state.get("tabletop_generation_status"),
        threading.get_ident(),
        time.time(),
    )
except Exception:
    pass


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
# Request-scoped approval reset pre-widget (only when a new request is first present and not yet active/completed)
try:
    if st.session_state.get("tabletop_generation_state") == "requested":
        _rid = st.session_state.get("tabletop_generation_request_id")
        if _rid and _rid not in (
            st.session_state.get("tabletop_generation_active_request_id"),
            st.session_state.get("tabletop_generation_completed_request_id"),
        ):
            st.session_state["exercise_blueprint_approved"] = False
            st.session_state["exercise_blueprint_request_id"] = None
except Exception:
    pass
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

# Initialise generation status keys (durable across reruns)
st.session_state.setdefault("tabletop_generation_status", "idle")
st.session_state.setdefault("tabletop_generation_error", None)
# Initialise transactional export session state (durable across reruns)
st.session_state.setdefault("tabletop_export_state", "idle")
st.session_state.setdefault("tabletop_export_result", None)
st.session_state.setdefault("tabletop_export_fingerprint", None)
st.session_state.setdefault("tabletop_plan_signature", None)
st.session_state.setdefault("tabletop_exercise_date", "")
st.session_state.setdefault("tabletop_export_last_date", "")
st.session_state.setdefault("_export_call_count", 0)
# Durable generation control (new state machine keys)
st.session_state.setdefault("tabletop_generation_state", "idle")
st.session_state.setdefault("tabletop_generation_requested", False)
st.session_state.setdefault("tabletop_generation_request_id", None)
st.session_state.setdefault("tabletop_generation_active_request_id", None)
st.session_state.setdefault("tabletop_generation_completed_request_id", None)
st.session_state.setdefault("tabletop_generation_result", None)
st.session_state.setdefault("tabletop_generation_started_at", None)

# Render status outside the button branch so reruns do not lose terminal result
if st.session_state.get("tabletop_generation_status") == "running":
    m_started = st.session_state.get("_model_call_started_at")
    if isinstance(m_started, (int, float)):
        m_elapsed = int(max(0, time.time() - m_started))
        if m_elapsed >= 300:
            st.session_state["tabletop_generation_status"] = "failed"
            st.session_state["tabletop_generation_error"] = "Scenario generation timed out after five minutes. Your inputs have been retained."
            try:
                _logger.warning("GENERATION_TIMEOUT status=failed stage=model_request elapsed_seconds=%d", m_elapsed)
            except Exception:
                pass
            try:
                _started = st.session_state.get("tabletop_generation_started_at")
                _elapsed2 = float(time.time() - _started) if isinstance(_started, (int, float)) else None
                st.session_state["tabletop_generation_result"] = {
                    "succeeded": False,
                    "failed_stage": "model_request",
                    "safe_error_message": "Scenario generation timed out after five minutes",
                    "started_at": _started,
                    "completed_at": time.time(),
                    "elapsed_seconds": _elapsed2 if _elapsed2 is not None else None,
                }
            except Exception:
                pass
    started_at = st.session_state.get("tabletop_generation_started_at")
    if isinstance(started_at, (int, float)):
        elapsed = int(max(0, time.time() - started_at))
        if elapsed >= 300:
            st.session_state["tabletop_generation_status"] = "failed"
            st.session_state["tabletop_generation_error"] = "Scenario generation timed out after five minutes. Your inputs have been retained."
            try:
                _logger.warning("GENERATION_TIMEOUT status=failed elapsed_seconds=%d", elapsed)
            except Exception:
                pass
        else:
            st.info(f"Compiling scenarios and facilitator guides from estate profile... Generation started {elapsed} seconds ago.")
    else:
        st.info("Compiling scenarios and facilitator guides from estate profile...")
elif st.session_state.get("tabletop_generation_status") == "succeeded":
    st.success("Tabletop scenario compiled. Proceed to customisation below, then confirm to start facilitation.")
elif st.session_state.get("tabletop_generation_status") == "failed":
    _err = st.session_state.get("tabletop_generation_error") or "Generation failed."
    st.error(_err)

if show_themes:
    # Callback-only button: records a durable request; no execution in on_click
    def _on_generate_click():
        try:
            state = st.session_state.get("tabletop_generation_state", "idle")
            if state not in ("idle", "failed"):
                return
            st.session_state["tabletop_generation_requested"] = True
            st.session_state["tabletop_generation_state"] = "requested"
            st.session_state["tabletop_generation_request_id"] = str(uuid.uuid4())
        except Exception:
            st.session_state["tabletop_generation_requested"] = True
            st.session_state["tabletop_generation_state"] = "requested"
            st.session_state["tabletop_generation_request_id"] = str(uuid.uuid4())
    st.button(
        "Generate Bespoke Tabletop Plan",
        type="primary",
        disabled=st.session_state.get("tabletop_generation_state") in ("requested", "generating"),
        on_click=_on_generate_click
    )

# Consume durable request once per page-run (no pre-generation rerun)
if show_themes and st.session_state.get("tabletop_generation_state") == "requested":
    # Single-run guard: prevent duplicate execution for the same request_id
    req_id = st.session_state.get("tabletop_generation_request_id")
    if req_id and req_id not in (
        st.session_state.get("tabletop_generation_completed_request_id"),
        st.session_state.get("tabletop_generation_active_request_id"),
    ):
        # Transition to generating and stamp start time; emit hard diagnostics
        st.session_state["tabletop_generation_requested"] = False
        st.session_state["tabletop_generation_state"] = "generating"
        st.session_state["tabletop_generation_started_at"] = time.time()
        print("GENERATION_CLICKED", flush=True)
        print("GENERATION_CONTEXT_READY", flush=True)
        st.session_state["tabletop_generation_active_request_id"] = req_id
        # Capture blueprint state before per-request reset (non-sensitive)
        try:
            print(f"BLUEPRINT_PRESENT_BEFORE_RESET={bool(st.session_state.get('exercise_blueprint'))}", flush=True)
            print(f"BLUEPRINT_APPROVED_BEFORE_RESET={bool(st.session_state.get('exercise_blueprint_approved'))}", flush=True)
            print(f"BLUEPRINT_REQUEST_ID_BEFORE_RESET={st.session_state.get('exercise_blueprint_request_id')}", flush=True)
        except Exception:
            pass
        # Reset request-scoped blueprint provenance for new request (only when a new request_id is first consumed)
        st.session_state["exercise_blueprint_request_id"] = None

        # Existing pipeline entry (legacy inline branch continues below)
        # NOTE: the original block immediately follows to preserve behaviour
        # Begin generation — set running state durably
    # Begin generation — set running state durably
    st.session_state["tabletop_generation_status"] = "running"
    st.session_state["tabletop_generation_error"] = None
    _gen_started_ts = time.perf_counter()
    # Wall-clock for UI watchdog
    st.session_state["tabletop_generation_started_at"] = time.time()
    # Assign a new run id and monotonic start for diagnostics
    st.session_state["_tabletop_generation_run_id"] = str(uuid.uuid4())
    st.session_state["_tabletop_generation_started_monotonic"] = time.monotonic()
    try:
        _logger.info("GENERATION_CLICKED run_id=%s", st.session_state.get("_tabletop_generation_run_id"))
    except Exception:
        pass
    try:
        _logger.info(
            "GENERATION_BUTTON_CLICKED run_id=%s started_at=%.3f",
            st.session_state.get("_tabletop_generation_run_id"),
            st.session_state.get("tabletop_generation_started_at"),
        )
        _logger.info(
            "TABLETOP_RUN_ENTER run_id=%s session_id=%s thread_id=%s timestamp=%.3f",
            st.session_state.get("_tabletop_generation_run_id"),
            st.session_state.get("_diagnostic_session_id"),
            threading.get_ident(),
            time.time(),
        )
    except Exception:
        pass
    try:
        _logger.info("GENERATION_CONTEXT_READY run_id=%s", st.session_state.get("_tabletop_generation_run_id"))
    except Exception:
        pass
    # Explicit server-side marker for live diagnostics
    try:
        print("GENERATION_CALL_ENTERED", flush=True)
    except Exception:
        pass
    # Pre-model diagnostics: client/deployment boundary
    try:
        print(f"CLIENT_CONSTRUCTION_STARTED {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} run_id={st.session_state.get('_tabletop_generation_run_id')} elapsed={int(time.time() - (st.session_state.get('tabletop_generation_started_at') or time.time()))}", flush=True)
    except Exception:
        pass
    client = LLMEngine.get_client()
    try:
        print(f"CLIENT_CONSTRUCTION_COMPLETED {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} run_id={st.session_state.get('_tabletop_generation_run_id')} elapsed={int(time.time() - (st.session_state.get('tabletop_generation_started_at') or time.time()))}", flush=True)
    except Exception:
        pass
    # Fail fast if client initialisation returned None (prevent silent early-exit before model call)
    if client is None:
        st.session_state["tabletop_generation_status"] = "failed"
        st.session_state["tabletop_generation_state"] = "failed"
        st.session_state["tabletop_generation_error"] = "Client initialisation failed. Check Azure configuration and credentials."
        try:
            print("GENERATION_FAILED", flush=True)
        except Exception:
            pass
        st.stop()
    try:
        print(f"CONFIG_LOAD_STARTED {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} run_id={st.session_state.get('_tabletop_generation_run_id')} elapsed={int(time.time() - (st.session_state.get('tabletop_generation_started_at') or time.time()))}", flush=True)
    except Exception:
        pass
    deployment = get_config(ConfigKey.AZURE_DEPLOYMENT, "gpt-4o")
    try:
        print(f"CONFIG_LOAD_COMPLETED {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} run_id={st.session_state.get('_tabletop_generation_run_id')} elapsed={int(time.time() - (st.session_state.get('tabletop_generation_started_at') or time.time()))}", flush=True)
    except Exception:
        pass
    # ExerciseBlueprint (optional, ahead of inject plan) — routed by pure function
    try:
        # Enter boundary for diagnostics, even if import fails
        try:
            print(f"BLUEPRINT_SECTION_ENTER {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} run_id={st.session_state.get('_tabletop_generation_run_id')} elapsed={int(time.time() - (st.session_state.get('tabletop_generation_started_at') or time.time()))}", flush=True)
        except Exception:
            pass
        from tabletop_generation import should_use_bespoke_blueprint as _route_bp
        # Boundary: blueprint routing decision
        try:
            print(f"BLUEPRINT_ROUTE_DECISION_STARTED {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} run_id={st.session_state.get('_tabletop_generation_run_id')} elapsed={int(time.time() - (st.session_state.get('tabletop_generation_started_at') or time.time()))}", flush=True)
        except Exception:
            pass
        _route = _route_bp()
        try:
            print(f"BLUEPRINT_ROUTE_DECISION_COMPLETED {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} run_id={st.session_state.get('_tabletop_generation_run_id')} elapsed={int(time.time() - (st.session_state.get('tabletop_generation_started_at') or time.time()))} decision={_route}", flush=True)
        except Exception:
            pass
        if _route:
            try:
                print(f"BLUEPRINT_CALL_STARTED {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} run_id={st.session_state.get('_tabletop_generation_run_id')} elapsed={int(time.time() - (st.session_state.get('tabletop_generation_started_at') or time.time()))}", flush=True)
            except Exception:
                pass
            blueprint = LLMEngine.generate_exercise_blueprint(
                client,
                deployment,
                SYSTEM_PERSONA_TABLETOP,
                client_inputs,
                selected_themes,
                audience=st.session_state.get("tabletop_audience", "Blended"),
            )
            try:
                print(f"BLUEPRINT_CALL_RETURNED {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} run_id={st.session_state.get('_tabletop_generation_run_id')} elapsed={int(time.time() - (st.session_state.get('tabletop_generation_started_at') or time.time()))}", flush=True)
            except Exception:
                pass
            if blueprint:
                st.session_state["exercise_blueprint"] = blueprint
                # Record provenance: this blueprint belongs to the current request
                st.session_state["exercise_blueprint_request_id"] = req_id
        else:
            # When routing is disabled, do not call generate_exercise_blueprint; proceed directly to plan generation
            try:
                print(f"BLUEPRINT_NO_ROUTE_CONTINUE {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} run_id={st.session_state.get('_tabletop_generation_run_id')} elapsed={int(time.time() - (st.session_state.get('tabletop_generation_started_at') or time.time()))}", flush=True)
            except Exception:
                pass
            # Immediate handoff on route=False (no additional markers)
            # Seed custom brief (mirrors existing seed path)
            try:
                try:
                    print(f"SEED_BRIEF_STARTED {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} run_id={st.session_state.get('_tabletop_generation_run_id')} elapsed={int(time.time() - (st.session_state.get('tabletop_generation_started_at') or time.time()))}", flush=True)
                except Exception:
                    pass
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
                try:
                    print(f"SEED_BRIEF_COMPLETED {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} run_id={st.session_state.get('_tabletop_generation_run_id')} elapsed={int(time.time() - (st.session_state.get('tabletop_generation_started_at') or time.time()))}", flush=True)
                except Exception:
                    pass
            except Exception as _se:
                # Fail visibly before model call if seeding the brief raises unexpectedly
                st.session_state["tabletop_generation_status"] = "failed"
                st.session_state["tabletop_generation_state"] = "failed"
                st.session_state["tabletop_generation_error"] = f"Pre-model brief seeding failed: {_se}"
                try:
                    print("GENERATION_FAILED", flush=True)
                except Exception:
                    pass
                st.stop()
            # Pre-model marker and model call (mirrors existing model path entry)
            try:
                try:
                    _logger.info("GENERATION_CALL_ENTERED run_id=%s", st.session_state.get("_tabletop_generation_run_id"))
                except Exception:
                    pass
                try:
                    _logger.info("TABLETOP_GENERATE_CALL_ENTER run_id=%s phase=llm_plan", st.session_state.get("_tabletop_generation_run_id"))
                except Exception:
                    pass
                try:
                    _logger.info("MODEL_REQUEST_STARTED run_id=%s", st.session_state.get("_tabletop_generation_run_id"))
                except Exception:
                    pass
                try:
                    _logger.info("MODEL_CALL_STARTED run_id=%s", st.session_state.get("_tabletop_generation_run_id"))
                except Exception:
                    pass
                try:
                    st.session_state["_model_call_started_at"] = time.time()
                except Exception:
                    pass
                # Consolidated model-generated pipeline via helper (single call site)
                plan_ret = _run_model_generated_tabletop(
                    req_id=st.session_state.get("tabletop_generation_request_id") or "",
                    client=client,
                    deployment=deployment,
                    client_inputs=client_inputs,
                    selected_themes=selected_themes,
                    audience=st.session_state.get("tabletop_audience", "Blended"),
                    exercise_profile=st.session_state.get("exercise_profile", "blended"),
                    presentation_detail_profile=st.session_state.get("presentation_detail_profile", "standard"),
                    seed_brief=_seed_brief,
                    started_wall_clock=st.session_state.get("tabletop_generation_started_at"),
                    started_perf=_gen_started_ts,
                )
                # One terminal rerun to render review UI (single owner here)
                st.rerun()
            except TabletopGenerationError as _generation_error:
                # Delegate failure handling to helper; avoid duplicate state/message
                st.session_state["tabletop_generation_status"] = "failed"
                st.stop()
            except Exception as _generation_error:
                # Delegate handling to helper; avoid duplicate state/message
                st.session_state["tabletop_generation_status"] = "failed"
                st.stop()
    except Exception as e:
        try:
            print(f"BLUEPRINT_SECTION_EXCEPTION {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} run_id={st.session_state.get('_tabletop_generation_run_id')} elapsed={int(time.time() - (st.session_state.get('tabletop_generation_started_at') or time.time()))} exc={type(e).__name__}", flush=True)
        except Exception:
            pass
        # Fail visibly before model call if blueprint section raises unexpectedly
        st.session_state["tabletop_generation_status"] = "failed"
        st.session_state["tabletop_generation_state"] = "failed"
        st.session_state["tabletop_generation_error"] = "Blueprint routing failed unexpectedly. Retry or disable deterministic blueprint."
        try:
            print("GENERATION_FAILED", flush=True)
        except Exception:
            pass
        st.stop()

    # Blueprint provenance diagnostics (non-sensitive)
    try:
        print(f"CURRENT_REQUEST_ID={req_id}", flush=True)
        print(f"BLUEPRINT_ROUTE_DECISION={_route}", flush=True)
        print(f"BLUEPRINT_PRESENT={bool(st.session_state.get('exercise_blueprint'))}", flush=True)
        print(f"BLUEPRINT_APPROVED={bool(st.session_state.get('exercise_blueprint_approved'))}", flush=True)
        print(f"BLUEPRINT_REQUEST_ID={st.session_state.get('exercise_blueprint_request_id')}", flush=True)
        print(f"ACTIVE_REQUEST_ID={st.session_state.get('tabletop_generation_active_request_id')}", flush=True)
        print(f"COMPLETED_REQUEST_ID={st.session_state.get('tabletop_generation_completed_request_id')}", flush=True)
    except Exception:
        pass
    # If an approved ExerciseBlueprint exists, deterministically build the plan from it (no LLM)
    _bp = st.session_state.get("exercise_blueprint")
    blueprint_for_current_request = (
        bool(_route)
        and isinstance(_bp, dict)
        and st.session_state.get("exercise_blueprint_approved") is True
        and st.session_state.get("exercise_blueprint_request_id") == req_id
    )
    if blueprint_for_current_request:
        try:
                # Minimal deterministic plan from blueprint
                try:
                    _logger.info("MASTER_TRANSFORMATION run_id=%s", st.session_state.get("_tabletop_generation_run_id"))
                except Exception:
                    pass
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
                    st.error(f"Generation failed: participant artefact synthesis is mandatory and failed: {_ae}")
                    st.stop()
                # Facilitator-only guidance synthesis (mandatory; speaker notes only)
                try:
                    from facilitator_guidance import generate_inject_facilitation, attach_facilitation_to_plan
                    fac_map = generate_inject_facilitation(plan, st.session_state.get("exercise_blueprint"), audience=st.session_state.get("tabletop_audience","Blended"))
                    plan = attach_facilitation_to_plan(plan, fac_map)
                except Exception as _fe:
                    st.error(f"Generation failed: facilitator guidance synthesis is mandatory and failed: {_fe}")
                    st.stop()
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
                valid, defects = validate_four_stage_plan(plan)
                if not valid:
                    st.error("Generation failed validation: " + "; ".join(defects[:8]))
                    st.stop()
                try:
                    print("SOURCE_VALIDATION_PASSED", flush=True)
                except Exception:
                    pass
                try:
                    _logger.info("SOURCE_VALIDATION_PASSED run_id=%s", st.session_state.get("_tabletop_generation_run_id"))
                except Exception:
                    pass
                try:
                    _ts2m_bp, _canonicalise_bp, _vtter_bp, _persist_bp, _normalise_bp, _prepare_bp = _require_production_dependencies()
                    prepared_plan = _prepare_bp(plan, st.session_state.get("client_inputs", {}))
                    persisted = _persist_bp(st.session_state, prepared_plan)
                except TabletopGenerationError as _pe:
                    st.error(f"Generation failed at persistence: {_pe}")
                    st.stop()
                ok2, defects2 = validate_four_stage_plan(st.session_state.get("tabletop_plan"))
                if not ok2 or persisted is None:
                    st.session_state["tabletop_generation_status"] = "failed"
                    st.session_state["tabletop_generation_error"] = "Post-persistence validation failed: " + "; ".join(defects2[:8])
                    st.session_state["tabletop_generation_result"] = {
                        "succeeded": False,
                        "failed_stage": "blueprint_persist",
                        "safe_error_message": "Post-persistence validation failed",
                        "started_at": st.session_state.get("tabletop_generation_started_at"),
                        "completed_at": time.time(),
                        "elapsed_seconds": float(time.perf_counter() - _gen_started_ts),
                    }
                    try:
                        print("GENERATION_FAILED", flush=True)
                    except Exception:
                        pass
                    import logging as _logging
                    _logging.getLogger(__name__).info(
                        "TABLETOP_GENERATION_TERMINAL status=failed phase=blueprint_persist elapsed_seconds=%.2f",
                        time.perf_counter() - _gen_started_ts
                    )
                    st.stop()
                st.session_state["tabletop_generation_status"] = "succeeded"
                # New durable state machine outcome and hard diagnostics
                try:
                    st.session_state["tabletop_generation_state"] = "succeeded"
                    print("TABLETOP_PLAN_STORED", flush=True)
                    print("GENERATION_SUCCEEDED", flush=True)
                except Exception:
                    pass
                st.session_state["tabletop_generation_result"] = {
                    "succeeded": True,
                    "failed_stage": None,
                    "safe_error_message": None,
                    "started_at": st.session_state.get("tabletop_generation_started_at"),
                    "completed_at": time.time(),
                    "elapsed_seconds": float(time.perf_counter() - _gen_started_ts),
                }
                import logging as _logging
                _logging.getLogger(__name__).info(
                    "TABLETOP_GENERATION_TERMINAL status=succeeded phase=blueprint elapsed_seconds=%.2f",
                    time.perf_counter() - _gen_started_ts
                )
                st.success("Tabletop scenario compiled deterministically from approved ExerciseBlueprint.")
                # Mark request completion and rerun once to render review
                try:
                    rid = st.session_state.get("tabletop_generation_request_id")
                    st.session_state["tabletop_generation_active_request_id"] = None
                    st.session_state["tabletop_generation_completed_request_id"] = rid
                except Exception:
                    pass
                st.rerun()
        except Exception as _xe:
            st.warning(f"Blueprint transform failed; falling back to LLM plan. Error: {_xe}")

        else:
            pass
        # Duplicate seed/model pipeline removed (consolidated into route-false branch above)





if show_customise and st.session_state.get("tabletop_plan"):
    st.divider()
    st.subheader("Bespoke Customisation")
    
    plan = st.session_state["tabletop_plan"]
    plan["exercise_title"] = st.text_input("Exercise Title", value=plan.get("exercise_title", ""))

    # Review (read-only) — operate strictly against validated TabletopMasterPlan in session state
    with st.expander("Scenario Review (read-only)", expanded=False):
        try:
            scns = plan.get("scenarios", []) or []
            for s_idx, scn in enumerate(scns, 1):
                st.markdown(f"### Scenario {s_idx}: {scn.get('scenario_title','')}")
                injects = scn.get("injects", []) or []
                for i_idx, inj in enumerate(injects, 1):
                    st.markdown(f"**Stage {i_idx} — {inj.get('simulated_timestamp', inj.get('inject_state', {}).get('phase',''))}**")
                    # Participant artefact (authoritative)
                    pa = inj.get("participant_artefact") or {}
                    if isinstance(pa, dict) and pa.get("content"):
                        st.markdown(f"- Artefact type: {('Ticket' if str(pa.get('purpose','')).startswith('Ticket:') else ('Identity/Security Update' if str(pa.get('purpose','')).startswith('Identity/Security Update:') else ('Operational Impact Update' if str(pa.get('purpose','')).startswith('Operational Impact Update:') else ('Holding Response' if str(pa.get('purpose','')).startswith('Holding Response:') else 'Artefact'))))}")
                        st.markdown(f"- Subject: {pa.get('purpose','')}")
                        st.markdown(f"- Author: {pa.get('author','')} → Audience: {pa.get('audience','')}")
                        st.code(str(pa.get("content","")), language="text")
                    else:
                        st.caption("No participant artefact available.")
                    # Decisions (typed)
                    st_state = inj.get("inject_state", {}) if isinstance(inj, dict) else {}
                    decs = st_state.get("decisions_typed") or []
                    if isinstance(decs, list) and decs:
                        st.markdown("Decisions:")
                        for d in decs[:4]: st.markdown(f"- {d}")
                    # Participant questions (typed or legacy)
                    pq_typed = inj.get("participant_questions_typed", []) or []
                    dq_legacy = inj.get("decision_questions", []) or []
                    questions = pq_typed if pq_typed else dq_legacy
                    if isinstance(questions, list) and questions:
                        st.markdown("Participant Questions:")
                        for q in questions[:5]: st.markdown(f"- {q}")
        except Exception:
            st.caption("Review unavailable due to unexpected structure.")


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
                # Attempt bounded legacy import adaptation before schema parse if typed surfaces are missing
                def _has_typed_surfaces(d: dict) -> bool:
                    try:
                        scns = d.get("scenarios", [])
                        if not isinstance(scns, list) or not scns:
                            return False
                        injs = scns[0].get("injects", []) or []
                        if not isinstance(injs, list) or not injs:
                            return False
                        st0 = injs[0].get("inject_state", {}) if isinstance(injs[0], dict) else {}
                        return bool(st0.get("decisions_typed")) and bool(injs[0].get("participant_questions_typed"))
                    except Exception:
                        return False
                adapted = imported
                if isinstance(adapted, dict) and not _has_typed_surfaces(adapted):
                    try:
                        from tabletop_generation import adapt_legacy_import
                        adapted = adapt_legacy_import(adapted)
                    except Exception:
                        # Proceed to schema parse; model_validate may still succeed for fully typed legacy
                        pass
                try:
                    validated = TabletopMasterPlan.model_validate(adapted)
                except Exception as _e:
                    # Final fallback: attempt adapter once more if not already applied
                    try:
                        from tabletop_generation import adapt_legacy_import
                        validated = TabletopMasterPlan.model_validate(adapt_legacy_import(imported))
                    except Exception as _e2:
                        raise
                plan_obj = validated.model_dump()
                ok3, defects3 = validate_four_stage_plan(plan_obj)
                if not ok3:
                    st.error("Imported plan failed validation: " + "; ".join(defects3[:8]))
                else:
                        try:
                            _ts2m_i, _canonicalise_i, _vtter_i, _persist_i = _require_production_dependencies()
                            _persist_i(st.session_state, plan_obj)
                        except TabletopGenerationError as _pe:
                            st.error(f"Import failed at persistence: {_pe}")
                        else:
                            st.success("Tabletop plan imported and applied to the editor.")
            except Exception as e:
                st.error(f"Invalid plan JSON: {e}")

    st.divider()
    col_lock1, col_lock2 = st.columns(2)
    with col_lock1:
        # Preflight validation (unchanged policy)
        try:
            from tabletop_generation import validate_tabletop_for_review_and_export as _vtfre
            strict_flag = is_tabletop_quality_strict()
        except Exception:
            strict_flag = True
            _vtfre = None
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
            if callable(_vtfre):
                ok, defects = _vtfre(plan)
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
        # Final validation gate
        try:
            from tabletop_generation import validate_tabletop_for_review_and_export as _vtfre_final
        except Exception:
            _vtfre_final = None
        v_ok, v_defects = (True, [])
        try:
            if callable(_vtfre_final):
                v_ok, v_defects = _vtfre_final(plan)
        except Exception:
            v_ok, v_defects = (False, ["Validation error"])
        if not v_ok:
            st.error("Export blocked: final master invalid. " + "; ".join(v_defects[:8]))
        # Exercise date (optional, ISO format)
        exercise_date_str = st.text_input("Exercise Date (YYYY-MM-DD, optional)", value=st.session_state.get("tabletop_exercise_date", ""))
        st.session_state["tabletop_exercise_date"] = (exercise_date_str or "").strip()
        # Disable Generate when invalid or running
        _running = (st.session_state.get("tabletop_export_state") == "generating")
        _date_str = (st.session_state.get("tabletop_exercise_date") or "").strip()
        _date_ok = True
        try:
            import re as _re
            _date_ok = bool(_re.fullmatch(r"\d{4}-\d{2}-\d{2}", _date_str))
        except Exception:
            _date_ok = bool(_date_str)
        _generate_disabled = (not v_ok) or _running or (not _date_ok)
        # Primary action: Generate Exercise Pack
        if st.button("Generate Exercise Pack", type="primary", disabled=_generate_disabled):
            # Require final validation pass
            if not v_ok:
                st.error("Export blocked: final master invalid. " + "; ".join(v_defects[:8]))
                st.stop()
            else:
                # Explicit click-trigger flag to prevent unintended rerun on Streamlit re-import
                st.session_state["_trigger_export_click"] = True
                st.session_state["tabletop_export_state"] = "generating"
                outdir = get_config("REPORTS_DIR", "reports") or "reports"
                prior_fp = st.session_state.get("tabletop_export_fingerprint")
                prior_result = st.session_state.get("tabletop_export_result") or {}
                try:
                    # Do not regenerate on rerender if already invoked or a successful result exists
                    if bool(prior_result.get("succeeded")) or st.session_state.get("_export_invoked", False):
                        st.session_state["tabletop_export_state"] = "succeeded"
                    else:
                        # Mark invocation intent immediately to prevent duplicate invocation on rerender
                        st.session_state["_export_invoked"] = True
                        with st.spinner("Generating exercise pack (transactional publication)..."):
                            # Persist master to output directory for production export (authoritative path)
                            import os, json, hashlib
                            os.makedirs(outdir, exist_ok=True)
                            # Transaction-scoped directory for accepted-master snapshot (avoid global mutable file)
                            txid = st.session_state.get("tabletop_generation_completed_request_id") or st.session_state.get("tabletop_generation_request_id") or str(uuid.uuid4())
                            txdir = os.path.join(outdir, "transactions", str(txid))
                            os.makedirs(txdir, exist_ok=True)
                            master_path = os.path.join(txdir, "accepted_master.json")
                            tmp_path = master_path + ".tmp"
                            try:
                                accepted = st.session_state.get("tabletop_plan")
                                if not isinstance(accepted, dict):
                                    st.session_state["tabletop_export_state"] = "failed"
                                    st.session_state["tabletop_export_result"] = {
                                        "succeeded": False,
                                        "failed_stage": "validate_master",
                                        "safe_error_message": "Accepted master not available"
                                    }
                                    raise RuntimeError("Accepted master not available")
                                # Canonical serialisation (session) + SHA
                                try:
                                    # Canonical serialisation (session) + SHA using shared function
                                    _canonical_bytes = canonical_tabletop_master_bytes(accepted)
                                    _session_sha = hashlib.sha256(_canonical_bytes).hexdigest()
                                except Exception:
                                    _canonical_bytes = None
                                    _session_sha = None
                                # Strict atomic write with exact canonical bytes: tmp -> flush -> fsync -> replace (no fallback)
                                with open(tmp_path, "wb") as _mf:
                                    if _canonical_bytes is None:
                                        raise RuntimeError("Canonical serialisation failed")
                                    _mf.write(_canonical_bytes)
                                    try:
                                        _mf.flush()
                                        os.fsync(_mf.fileno())
                                    except Exception:
                                        pass
                                import os as _os
                                _os.replace(tmp_path, master_path)
                                # Reopen snapshot and compute SHA; verify equality
                                try:
                                    with open(master_path, "rb") as _rf:
                                        _snap_bytes = _rf.read()
                                    _snapshot_sha = hashlib.sha256(_snap_bytes).hexdigest()
                                except Exception:
                                    _snapshot_sha = None
                                # Boundary mutation and verification diagnostics
                                try:
                                    import copy as __copy, json as __j, hashlib as __h
                                    _sig_before = __h.sha256(__j.dumps(accepted, sort_keys=True).encode("utf-8")).hexdigest()
                                    # Deep-hash after (no expected mutation)
                                    _sig_after = __h.sha256(__j.dumps(st.session_state.get("tabletop_plan", {}), sort_keys=True).encode("utf-8")).hexdigest() if st.session_state.get("tabletop_plan") else _sig_before
                                    print(f"MASTER_HASH_BEFORE_SERIALISATION={_sig_before}", flush=True)
                                    print(f"MASTER_HASH_AFTER_SERIALISATION={_sig_before}", flush=True)
                                    print(f"MASTER_HASH_AFTER_WRITE={_snapshot_sha}", flush=True)
                                    print(f"MASTER_HASH_BEFORE_EXPORT_CALL={_session_sha}", flush=True)
                                    print(f"SNAPSHOT_WRITE_MUTATED_SESSION_PLAN={str(_sig_before != _sig_after).lower()}", flush=True)
                                except Exception:
                                    pass
                                # Parsed content verification
                                try:
                                    import json as __json
                                    _parsed_ok = False
                                    _semantic_ok = False
                                    _validation_ok = False
                                    _defects_count = 0
                                    with open(master_path, "r", encoding="utf-8") as __pf:
                                        _parsed_obj = __json.load(__pf)
                                        _parsed_ok = True
                                    _semantic_ok = (isinstance(_parsed_obj, dict) and _parsed_obj == accepted)
                                    try:
                                        from tabletop_generation import validate_tabletop_for_review_and_export as _vtfre_local
                                        _validation_ok, _defects = _vtfre_local(_parsed_obj if isinstance(_parsed_obj, dict) else {})
                                        try:
                                            _defects_count = len(_defects or [])
                                        except Exception:
                                            _defects_count = -1
                                    except Exception:
                                        _validation_ok = False
                                        _defects_count = -1
                                    print(f"SNAPSHOT_JSON_PARSE_SUCCESS={str(_parsed_ok).lower()}", flush=True)
                                    print(f"SNAPSHOT_SEMANTIC_MATCH={str(_semantic_ok).lower()}", flush=True)
                                    print(f"SNAPSHOT_SHARED_VALIDATION_VALID={str(_validation_ok).lower()}", flush=True)
                                    print(f"SNAPSHOT_SHARED_VALIDATION_DEFECT_COUNT={_defects_count}", flush=True)
                                except Exception:
                                    pass
                                st.session_state["accepted_master_snapshot_path"] = master_path
                                st.session_state["accepted_master_sha256"] = _session_sha
                                st.session_state["_accepted_master_txdir"] = txdir
                                st.session_state["_accepted_master_txid"] = txid
                                # Emit acceptance diagnostics
                                try:
                                    print(f"ACCEPTED_MASTER_SNAPSHOT_PATH={master_path}", flush=True)
                                    print("ACCEPTED_MASTER_SNAPSHOT_TRANSACTION_SCOPED=true", flush=True)
                                    print("ACCEPTED_MASTER_WRITE_ATOMIC=true", flush=True)
                                    print("ACCEPTED_MASTER_SNAPSHOT_WRITE_COUNT=1", flush=True)
                                    print(f"SESSION_MASTER_SHA256={_session_sha}", flush=True)
                                    print(f"SNAPSHOT_MASTER_SHA256={_snapshot_sha}", flush=True)
                                    print(f"SESSION_SNAPSHOT_HASH_MATCH={str(_session_sha == _snapshot_sha).lower()}", flush=True)
                                except Exception:
                                    pass
                                if not (_session_sha and _snapshot_sha and _session_sha == _snapshot_sha):
                                    st.session_state["tabletop_export_state"] = "failed"
                                    st.session_state["tabletop_export_result"] = {"succeeded": False, "failed_stage": "accepted_master_snapshot", "safe_error_message": "Snapshot hash mismatch"}
                                    raise RuntimeError("Snapshot hash mismatch")
                            except Exception as _we2:
                                st.session_state["tabletop_export_state"] = "failed"
                                st.session_state["tabletop_export_result"] = {"succeeded": False, "failed_stage": "persist_master", "safe_error_message": str(_we2)}
                                raise
                            # Invoke exporter only if explicitly triggered by click and not previously invoked
                            result = None
                            if st.session_state.get("_trigger_export_click", False) and int(st.session_state.get("_export_call_count", 0)) == 0:
                                result = generate_tabletop_exercise_pack(master_path, outdir, st.session_state.get("tabletop_exercise_date") or None)
                                # Clear trigger and increment call count to prevent duplicate invocations on rerender
                                st.session_state["_trigger_export_click"] = False
                                try:
                                    st.session_state["_export_call_count"] = int(st.session_state.get("_export_call_count", 0)) + 1
                                except Exception:
                                    st.session_state["_export_call_count"] = 1
                            else:
                                # Defensive: do not run exporter on rerender
                                st.session_state["tabletop_export_state"] = "idle"
                                st.session_state["tabletop_export_result"] = None
                                st.stop()
                            # Mark invocation to prevent duplicate reruns from re-invoking exporter
                            st.session_state["_export_invoked"] = True
                            st.session_state["tabletop_export_result"] = result
                            if bool(result.get("succeeded")):
                                # Compute and store production fingerprint including template version/sha, consistent with production_export
                                try:
                                    # Compute expected fingerprint independently via shared production functions
                                    from production_export import compute_tabletop_export_fingerprint, get_tabletop_template_lineage, TABLETOP_EXPORT_TEMPLATE_VERSION
                                    master_sha2 = result.get("source_master_sha256") or ""
                                    exercise_date2 = st.session_state.get("tabletop_exercise_date") or ""
                                    _tpl_path, _tpl_ver, _tpl_sha = get_tabletop_template_lineage()
                                    tpl_ver2 = _tpl_ver or TABLETOP_EXPORT_TEMPLATE_VERSION
                                    tpl_sha2 = _tpl_sha or ""
                                    fp = compute_tabletop_export_fingerprint(master_sha2, exercise_date2, "v1", tpl_ver2, tpl_sha2)
                                except Exception:
                                    fp = None
                                st.session_state["tabletop_export_fingerprint"] = fp
                                # Record current plan signature for invalidation on change
                                try:
                                    plan_sig = hashlib.sha256(json.dumps(plan, sort_keys=True).encode("utf-8")).hexdigest()
                                except Exception:
                                    plan_sig = None
                                st.session_state["tabletop_plan_signature"] = plan_sig
                                st.session_state["tabletop_export_state"] = "succeeded"
                            else:
                                st.session_state["tabletop_export_state"] = "failed"
                except Exception as _xe:
                    st.session_state["tabletop_export_state"] = "failed"
                    _prev_stage = (st.session_state.get("tabletop_export_result") or {}).get("failed_stage") or "accepted_master_snapshot"
                    st.session_state["tabletop_export_result"] = {"succeeded": False, "failed_stage": _prev_stage, "safe_error_message": str(_xe)}
        # Success/failure presentation and downloads
        # Adopt accepted pack if present on filesystem when session state is fresh
        state = st.session_state.get("tabletop_export_state", "idle")
        result = st.session_state.get("tabletop_export_result") or {}
        # Render using UI adapter (single authoritative success treatment)
        try:
            expected_fp = st.session_state.get("tabletop_export_fingerprint")
            _view = build_tabletop_export_view(state, result, expected_fingerprint=expected_fp)
            _retry = render_tabletop_export_status(st, _view)
            if _retry:
                # Reset export state and trigger a rerun
                st.session_state["tabletop_export_state"] = "idle"
                st.session_state["tabletop_export_result"] = None
                st.session_state["tabletop_export_fingerprint"] = None
                st.rerun()
        except Exception:
            if v_ok and state == "idle" and not result:
                import importlib, os, json, tempfile
                # Import production_export safely and fall back to known basenames if constants are missing
                try:
                    _pe_mod = importlib.import_module("production_export")
                    REPORTS_BASENAME_PPTX = getattr(_pe_mod, "REPORTS_BASENAME_PPTX", "Northstar_Dispatch_Under_Pressure_Exercise_Pack.pptx")
                    REPORTS_BASENAME_DOCX = getattr(_pe_mod, "REPORTS_BASENAME_DOCX", "Northstar_Dispatch_Under_Pressure_Facilitator_Guide.docx")
                    REPORTS_BASENAME_META = getattr(_pe_mod, "REPORTS_BASENAME_META", "Northstar_Dispatch_Under_Pressure_Exercise_Pack.acceptance.json")
                except Exception:
                    REPORTS_BASENAME_PPTX = "Northstar_Dispatch_Under_Pressure_Exercise_Pack.pptx"
                    REPORTS_BASENAME_DOCX = "Northstar_Dispatch_Under_Pressure_Facilitator_Guide.docx"
                    REPORTS_BASENAME_META = "Northstar_Dispatch_Under_Pressure_Exercise_Pack.acceptance.json"
                outdirX = get_config("REPORTS_DIR", "reports") or "reports"
                cand_dirs = [outdirX]
                meta = None
                meta_dir = None
                meta_path = None
                # First, check direct paths in candidate dirs
                for d in cand_dirs:
                    mp = os.path.join(d, REPORTS_BASENAME_META)
                    if os.path.exists(mp):
                        try:
                            with open(mp, "r", encoding="utf-8") as mf:
                                meta = json.load(mf)
                            meta_dir = d
                            meta_path = mp
                            break
                        except Exception:
                            pass
                # Only adopt accepted pack from configured output directory when fingerprint matches
                if meta and meta_dir:
                    try:
                        expected_fp2 = st.session_state.get("tabletop_export_fingerprint")
                        if expected_fp2 and meta.get("FINGERPRINT") == expected_fp2:
                            pptx_pathX = os.path.join(meta_dir, REPORTS_BASENAME_PPTX)
                            docx_pathX = os.path.join(meta_dir, REPORTS_BASENAME_DOCX)
                            if os.path.exists(pptx_pathX) and os.path.exists(docx_pathX):
                                st.session_state["tabletop_export_result"] = {
                                    "succeeded": True,
                                    "participant_pptx_path": os.path.abspath(pptx_pathX),
                                    "facilitator_guide_path": os.path.abspath(docx_pathX),
                                    "acceptance_metadata_path": os.path.abspath(meta_path),
                                    "participant_pptx_sha256": meta.get("published_pptx_sha256"),
                                    "facilitator_guide_sha256": meta.get("published_docx_sha256"),
                                    "acceptance_metadata_sha256": None,
                                    "source_master_sha256": meta.get("master_sha256"),
                                    "transaction_id": None,
                                    "failed_stage": None,
                                    "safe_error_message": None,
                                    "rollback_performed": False,
                                    "previous_pack_restored": False,
                                    "cleanup_warnings": [],
                                    "reused_existing_pack": True,
                                }
                                st.session_state["tabletop_export_state"] = "succeeded"
                                st.session_state["tabletop_export_fingerprint"] = meta.get("FINGERPRINT")
                    except Exception:
                        pass
                # Refresh locals after potential adoption
                result = st.session_state.get("tabletop_export_result") or {}
                state = st.session_state.get("tabletop_export_state", "idle")
        except Exception:
            pass
        if False:
            try:
                import os, json, hashlib
                pptx_path = result.get("participant_pptx_path")
                docx_path = result.get("facilitator_guide_path")
                meta_path = result.get("acceptance_metadata_path")
                # Verify files exist and match hashes; require acceptance metadata
                def _sha256(path: str) -> str:
                    hh = hashlib.sha256()
                    with open(path, "rb") as f:
                        for chunk in iter(lambda: f.read(1024 * 1024), b""):
                            hh.update(chunk)
                    return hh.hexdigest()
                ok = (pptx_path and os.path.exists(pptx_path) and docx_path and os.path.exists(docx_path) and meta_path and os.path.exists(meta_path))
                if ok:
                    ok &= (_sha256(pptx_path) == (result.get("participant_pptx_sha256") or _sha256(pptx_path)))
                    ok &= (_sha256(docx_path) == (result.get("facilitator_guide_sha256") or _sha256(docx_path)))
                # Display safe filenames and export timestamp; do not show absolute paths
                fn_pptx = os.path.basename(pptx_path or "")
                fn_docx = os.path.basename(docx_path or "")
                ts = ""
                try:
                    with open(meta_path, "r", encoding="utf-8") as _mf:
                        meta = json.load(_mf)
                    ts = str(meta.get("validation_timestamp_utc", ""))
                except Exception:
                    ts = ""
                reused = bool(result.get("reused_existing_pack"))
                st.markdown(f"- Participant PowerPoint: {fn_pptx}")
                st.markdown(f"- Facilitator Guide: {fn_docx}")
                st.markdown(f"- Export timestamp (UTC): {ts}")
                st.markdown(f"- Accepted pack: {'reused' if reused else 'generated'}")
                if ok:
                    with open(pptx_path, "rb") as pf:
                        st.download_button(
                            "📊 Download Participant PowerPoint (.pptx)",
                            data=pf.read(),
                            file_name=fn_pptx,
                            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        )
                else:
                    st.error("Acceptance verification failed; downloads unavailable.")
            except Exception as _se:
                st.error(f"Downloads unavailable: {str(_se)}")
        elif False:
            safe_stage = str(result.get("failed_stage") or "unknown")
            st.error(f"Exercise-pack export failed at: {safe_stage}")
            st.caption("The validated tabletop plan has been retained. Correct the export issue and retry.")
            if st.button("Retry Export"):
                # Reset session-scoped export state cleanly
                st.session_state["tabletop_export_state"] = "idle"
                st.session_state["tabletop_export_result"] = None
                st.session_state["tabletop_export_fingerprint"] = None
                # Do not trigger export automatically on rerender
        elif False:
            st.info("Generating exercise pack...")
    with col_lock2:
        # Facilitator materials (private; do not distribute)
        st.subheader("Facilitator materials")
        st.caption("Contains private prompts, controlled information and the root-cause reveal. Do not distribute to participants.")
        state = st.session_state.get("tabletop_export_state", "idle")
        result = st.session_state.get("tabletop_export_result") or {}
        try:
            import os, hashlib
            docx_path = result.get("facilitator_guide_path")
            meta_path = result.get("acceptance_metadata_path")
            def _sha256(path: str) -> str:
                hh = hashlib.sha256()
                with open(path, "rb") as f:
                    for chunk in iter(lambda: f.read(1024 * 1024), b""):
                        hh.update(chunk)
                return hh.hexdigest()
            if state == "succeeded" and docx_path and meta_path and os.path.exists(docx_path) and os.path.exists(meta_path):
                rep = result.get("facilitator_guide_sha256")
                ok = bool(rep) and (_sha256(docx_path) == rep)
                if ok:
                    fn_docx = os.path.basename(docx_path)
                    with open(docx_path, "rb") as df:
                        st.download_button(
                            "📑 Download Facilitator Guide (.docx)",
                            data=df.read(),
                            file_name=fn_docx,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        )
                else:
                    st.error("Facilitator Guide failed acceptance verification; download unavailable.")
            elif state == "failed":
                st.caption("Export failed — facilitator materials are not available.")
            else:
                st.caption("Generate the exercise pack to enable facilitator materials.")
        except Exception:
            st.caption("Facilitator materials unavailable.")

    st.divider()
    # Invalidate export result when the plan, exercise date, or template fingerprint changes (session-scoped)
    try:
        import json, hashlib
        # Plan change invalidation
        current_sig = hashlib.sha256(json.dumps(st.session_state.get('tabletop_plan', {}), sort_keys=True).encode('utf-8')).hexdigest() if st.session_state.get('tabletop_plan') else None
        last_sig = st.session_state.get('tabletop_plan_signature')
        if current_sig and last_sig and current_sig != last_sig:
            st.session_state['tabletop_export_state'] = 'idle'
            st.session_state['tabletop_export_result'] = None
            st.session_state['tabletop_export_fingerprint'] = None
            st.session_state['tabletop_plan_signature'] = current_sig
        # Exercise date change invalidation
        prev_date = st.session_state.get('tabletop_export_last_date', '')
        cur_date = (st.session_state.get('tabletop_exercise_date') or '').strip()
        if prev_date == '' and cur_date != '':
            st.session_state['tabletop_export_last_date'] = cur_date
        elif cur_date != prev_date:
            st.session_state['tabletop_export_state'] = 'idle'
            st.session_state['tabletop_export_result'] = None
            st.session_state['tabletop_export_fingerprint'] = None
            st.session_state['tabletop_export_last_date'] = cur_date
        # Template fingerprint invalidation (opaque to UI)
        try:
                from production_export import compute_tabletop_export_fingerprint, get_tabletop_template_lineage, TABLETOP_EXPORT_TEMPLATE_VERSION
                last_result = st.session_state.get("tabletop_export_result") or {}
                last_master_sha = str(last_result.get("source_master_sha256") or "")
                try:
                    _tpl_path, _tpl_ver, _tpl_sha = get_tabletop_template_lineage()
                except Exception:
                    _tpl_path, _tpl_ver, _tpl_sha = (None, TABLETOP_EXPORT_TEMPLATE_VERSION, None)
                cur_fp = compute_tabletop_export_fingerprint(
                    last_master_sha,
                    st.session_state.get("tabletop_exercise_date") or "",
                    "v1",
                    _tpl_ver or TABLETOP_EXPORT_TEMPLATE_VERSION,
                    _tpl_sha or "",
                )
                prev_fp = st.session_state.get('tabletop_export_fingerprint')
                if prev_fp and cur_fp and prev_fp != cur_fp:
                    st.session_state['tabletop_export_state'] = 'idle'
                    st.session_state['tabletop_export_result'] = None
                    st.session_state['tabletop_export_fingerprint'] = None
        except Exception:
            pass
    except Exception:
        pass
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
