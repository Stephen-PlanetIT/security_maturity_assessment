from __future__ import annotations

import os
import io
import json
import hashlib
import importlib
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, List

# Soft deps from existing lineage utilities (do not fail import at module import-time)
try:
    from services.report_improvement import lineage as _lin
except Exception:  # pragma: no cover
    _lin = None  # type: ignore

try:
    from config import get_config as _get_cfg  # type: ignore
except Exception:  # pragma: no cover
    def _get_cfg(key: str, default: Optional[str] = None) -> Optional[str]:
        return default

# Diagnostics gating (env + non-production)
def _diag_enabled() -> bool:
    try:
        enabled = str(_get_cfg("RUNTIME_LINEAGE_TRACE_ENABLED", "false")).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        enabled = False
    try:
        env = (os.getenv("ENVIRONMENT") or str(_get_cfg("ENVIRONMENT", "dev")) or "").strip().lower()
    except Exception:
        env = "dev"
    try:
        sandbox = str(_get_cfg("DIAGNOSTIC_SANDBOX", "false")).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        sandbox = False
    return bool(enabled and (env != "production" or sandbox))


def _ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)


def _logs_base() -> str:
    try:
        return _get_cfg("LOGS_DIR", "exports/logs") or "exports/logs"
    except Exception:
        return "exports/logs"


def _rid() -> str:
    if _lin is None:
        raise RuntimeError("lineage utilities not available")
    return _lin.ensure_run_id()  # type: ignore


def _run_dir() -> str:
    rid = _rid()
    base = _logs_base()
    p = os.path.join(base, rid)
    _ensure_dir(p)
    return p


class RuntimeLineageDiagnosticError(RuntimeError):
    pass

# Module-level diagnostics: capture real context shapes and specialist objects used for export projection
_LATEST_REPORT_DATA = None
_LATEST_CLIENT_INPUTS = None

def _truncate_text(s, max_len=2000):
    try:
        s = str(s or "")
        return s if len(s) <= max_len else (s[:max_len] + "…")
    except Exception:
        return ""

def _shape_summary(name, value):
    from typing import Mapping, Sequence
    out = {"name": name, "type": type(value).__name__, "keys": None, "len": None, "non_empty_fields": [], "hash": None}
    try:
        if isinstance(value, Mapping):
            out["keys"] = sorted(list(value.keys()))
            out["len"] = len(value)
            for k, v in value.items():
                try:
                    if v not in (None, "", [], {}):
                        out["non_empty_fields"].append(k)
                except Exception:
                    continue
        elif isinstance(value, (list, tuple)):
            out["len"] = len(value)
            if value and isinstance(value[0], Mapping):
                out["keys"] = sorted(list(value[0].keys()))
                for k, v in value[0].items():
                    try:
                        if v not in (None, "", [], {}):
                            out["non_empty_fields"].append(k)
                    except Exception:
                        continue
        elif isinstance(value, str):
            out["len"] = len(value)
        else:
            try:
                out["len"] = len(value)  # type: ignore
            except Exception:
                out["len"] = None
        out["hash"] = canonical_value_hash(value)
    except Exception:
        out["hash"] = canonical_value_hash(str(value))
    return out

def write_context_shapes(context_dict):
    if not _diag_enabled():
        return None
    try:
        rd = _run_dir()
        path = os.path.join(rd, "context_shapes.json")
        data = {
            "run_id": _rid(),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "context": {},
            "specialist": {},
        }
        ctx = context_dict if isinstance(context_dict, dict) else {}
        # Capture requested context keys
        for key in ("exec_summary","ExecutiveSummary","ComplianceAlignment","compliance_alignment","compliance_alignment_render","domains","security_rating"):
            try:
                val = ctx.get(key)
            except Exception:
                val = None
            # domains[0] special handling
            if key == "domains" and isinstance(val, list) and val:
                data["context"]["domains[0]"] = _shape_summary("domains[0]", val[0])
            else:
                data["context"][key] = _shape_summary(key, val)
        # Specialist objects (best-effort from last report_data)
        try:
            rep = globals().get("_LATEST_REPORT_DATA", None)
            if rep is not None:
                spec = {}
                for attr in ("executive_summary_specialist","compliance_alignment_specialist","domain_assessments_specialist","security_rating"):
                    try:
                        spec[attr] = _shape_summary(attr, getattr(rep, attr, None))
                    except Exception:
                        spec[attr] = _shape_summary(attr, None)
                data["specialist"] = spec
        except Exception:
            pass
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp, path)
        return path
    except Exception as exc:
        write_diagnostic_error({"where": "context_shapes.write", "error": repr(exc)})
        return None


def write_diagnostic_error(event: Dict[str, Any]) -> Optional[str]:
    if not _diag_enabled():
        return None
    try:
        rd = _run_dir()
        path = os.path.join(rd, "diagnostic_errors.jsonl")
        rec = {"run_id": _rid(), "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        rec.update(event or {})
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
        return path
    except Exception:
        return None


def _normalize_text(s: str) -> str:
    try:
        import unicodedata
        s_norm = unicodedata.normalize("NFKC", str(s))
    except Exception:
        s_norm = str(s)
    try:
        s_norm = s_norm.replace("\r\n", "\n").replace("\r", "\n")
    except Exception:
        pass
    try:
        s_norm = "\n".join([ln.rstrip() for ln in s_norm.split("\n")])
    except Exception:
        pass
    return s_norm


def canonical_text_hash(value: str) -> str:
    return hashlib.sha256(_normalize_text(str(value or "")).encode("utf-8")).hexdigest()


def _as_supported(value: Any) -> Any:
    # Canonical adapter: pydantic, dataclass, dict/list/tuple, scalars; else stringify
    try:
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        from dataclasses import is_dataclass, asdict as _asdict
        if is_dataclass(value):
            return _asdict(value)
    except Exception:
        pass
    if isinstance(value, (dict, list, tuple)):
        return value
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    # unsupported custom object — use safe string
    return str(value)


def canonical_value_hash(value: Any) -> str:
    v = _as_supported(value)
    if isinstance(v, (dict, list, tuple)):
        try:
            payload = json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            return hashlib.sha256(_normalize_text(payload).encode("utf-8")).hexdigest()
        except Exception as exc:
            write_diagnostic_error({"where": "canonical_value_hash.json", "error": repr(exc)})
            raise RuntimeLineageDiagnosticError from exc
    if isinstance(v, str):
        return canonical_text_hash(v)
    if isinstance(v, (int, float, bool)) or v is None:
        return hashlib.sha256(str(v).encode("utf-8")).hexdigest()
    return hashlib.sha256(str(v).encode("utf-8")).hexdigest()


def write_call_event(stage: str, caller: str, callee: str, input_obj: Any = None, output_obj: Any = None, exception: str | None = None) -> Optional[str]:
    if not _diag_enabled():
        return None
    rd = _run_dir()
    rec = {
        "run_id": _rid(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stage": stage,   # "enter" | "exit" | "exception"
        "caller": caller,
        "callee": callee,
        "input_type": type(input_obj).__name__ if input_obj is not None else None,
        "input_hash": canonical_value_hash(input_obj) if input_obj is not None else None,
        "output_type": type(output_obj).__name__ if output_obj is not None else None,
        "output_hash": canonical_value_hash(output_obj) if output_obj is not None else None,
        "exception": exception,
    }
    path = os.path.join(rd, "runtime_call_graph.jsonl")
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
        return path
    except Exception as exc:
        write_diagnostic_error({"where": "call_graph.write", "error": repr(exc)})
        raise RuntimeLineageDiagnosticError from exc


def write_overwrite_event(section: str, stage: str, before_value: Any, after_value: Any, handler: str | None = None) -> Optional[str]:
    if not _diag_enabled():
        return None
    rd = _run_dir()
    rec = {
        "run_id": _rid(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "section": section,
        "stage": stage,
        "before_hash": canonical_value_hash(before_value),
        "after_hash": canonical_value_hash(after_value),
        "changed": canonical_value_hash(before_value) != canonical_value_hash(after_value),
        "handler": handler or "",
    }
    path = os.path.join(rd, "runtime_overwrites.jsonl")
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
        return path
    except Exception as exc:
        write_diagnostic_error({"where": "overwrite.write", "error": repr(exc)})
        raise RuntimeLineageDiagnosticError from exc


def _rc_path() -> str:
    return os.path.join(_run_dir(), "runtime_configuration.json")


def merge_runtime_configuration(checkpoint_name: str, cfg: Dict[str, Any], effective: Optional[Dict[str, Any]] = None) -> Optional[str]:
    if not _diag_enabled():
        return None
    try:
        path = _rc_path()
        data = {
            "run_id": _rid(),
            "checkpoints": {},
            "effective_configuration": {},
        }
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {"run_id": _rid(), "checkpoints": {}, "effective_configuration": {}}
        cps = data.get("checkpoints") or {}
        cps[checkpoint_name] = cfg or {}
        data["checkpoints"] = cps
        if effective:
            data["effective_configuration"] = effective
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp, path)
        return path
    except Exception as exc:
        write_diagnostic_error({"where": "runtime_configuration.merge", "error": repr(exc)})
        raise RuntimeLineageDiagnosticError from exc


_SPECIALIST_SECTIONS = {
    "executive_summary",
    "security_rating",
    "threat_scenarios",
    "compliance_alignment",
    "cost_of_inaction",
    "domain_assessments",
}


def specialist_expected_for(section: str) -> bool:
    try:
        enabled = str(_get_cfg("SPECIALIST_GENERATORS_ENABLED", "false")).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        enabled = False
    return bool(enabled and section in _SPECIALIST_SECTIONS)


def assert_single_run_id(fn_name: str) -> None:
    if _lin is None:
        return
    rid = _lin.get_run_id()  # type: ignore
    if not rid:
        raise RuntimeLineageDiagnosticError(f"Missing run_id at {fn_name}")


def make_token(prefix: str, run_id: str, section: str) -> str:
    return f"{prefix}_{section.upper()}_{run_id}"


def add_export_token_to_context(ctx: dict, run_id: str) -> dict:
    if not isinstance(ctx, dict):
        return ctx

    mapping = {
        "executive_summary": "exec_summary",
        "security_rating": "security_rating",  # nested board takeaway handled separately
        "threat_scenarios": "threat_scenarios",
        "compliance_alignment": "compliance_alignment_render",
        "cost_of_inaction": "cost_of_inaction",
        # domain_assessments table skipped for token injection
    }
    for sec, key in mapping.items():
        if not key:
            continue
        tok = make_token("EXPORT", _rid(), sec)
        if sec == "security_rating":
            try:
                sr = ctx.get("security_rating")
                if isinstance(sr, dict):
                    # Try snapshot.board_level_takeaway or board_level_takeaway direct
                    if isinstance(sr.get("snapshot", {}).get("board_level_takeaway"), str):
                        sr["snapshot"]["board_level_takeaway"] = (sr["snapshot"]["board_level_takeaway"] or "") + " " + tok
                    elif isinstance(sr.get("board_level_takeaway"), str):
                        sr["board_level_takeaway"] = (sr["board_level_takeaway"] or "") + " " + tok
                    ctx["security_rating"] = sr
            except Exception as exc:
                write_diagnostic_error({"where": "export_token.security_rating", "error": repr(exc)})
                raise RuntimeLineageDiagnosticError from exc
        else:
            try:
                if isinstance(ctx.get(key), str):
                    sep = "\n" if key != "security_rating" else " "
                    ctx[key] = (ctx.get(key) or "") + sep + tok if ctx.get(key) else tok
            except Exception as exc:
                write_diagnostic_error({"where": "export_token", "section": sec, "error": repr(exc)})
                raise RuntimeLineageDiagnosticError from exc
    return ctx


def _deepcopy_pydantic(obj: Any) -> Any:
    try:
        if hasattr(obj, "model_copy"):
            return obj.model_copy(deep=True)
        if hasattr(obj, "copy"):
            return obj.copy()
    except Exception:
        pass
    try:
        return deepcopy(obj)
    except Exception:
        return obj


def add_gen_token_pydantic(out: Any, section: str) -> Any:
    # Inject GEN token into a safe text field on a deep copy of the Pydantic output
    if not _diag_enabled():
        return out
    rid = _rid()
    tok = make_token("GEN", rid, section)
    obj = _deepcopy_pydantic(out)
    try:
        if section == "executive_summary":
            # ExecutiveSummaryOutput: board_level_takeaway or assessment_context
            if hasattr(obj, "board_level_takeaway") and isinstance(getattr(obj, "board_level_takeaway"), str):
                obj.board_level_takeaway = f"{getattr(obj, 'board_level_takeaway') or ''} {tok}".strip()
            elif hasattr(obj, "assessment_context") and isinstance(getattr(obj, "assessment_context"), str):
                obj.assessment_context = f"{getattr(obj, 'assessment_context') or ''} {tok}".strip()
        elif section == "security_rating":
            # SecurityRatingOutput: board_takeaway
            if hasattr(obj, "board_takeaway") and isinstance(getattr(obj, "board_takeaway"), str):
                obj.board_takeaway = f"{getattr(obj, 'board_takeaway') or ''} {tok}".strip()
        elif section == "threat_scenarios":
            # AttackScenarioOutput: scenario_title
            if hasattr(obj, "scenario_title") and isinstance(getattr(obj, "scenario_title"), str):
                obj.scenario_title = f"{getattr(obj, 'scenario_title') or ''} {tok}".strip()
        elif section == "compliance_alignment":
            # ComplianceAlignmentOutput: add one diagnostic FrameworkAlignmentRow
            try:
                if hasattr(obj, "rows") and isinstance(obj.rows, list):
                    obj.rows.append(type(obj.rows[0])(
                        framework_name=f"TRACE_COMPLIANCE_{rid}",
                        framework_area="diagnostic",
                        current_position="n/a",
                        assurance_gap_or_consideration="diagnostic",
                        recommended_focus="diagnostic",
                    ))
            except Exception:
                pass
        elif section == "cost_of_inaction":
            # CostOfInactionOutput: qualitative_narrative
            if hasattr(obj, "qualitative_narrative") and isinstance(getattr(obj, "qualitative_narrative"), str):
                obj.qualitative_narrative = f"{getattr(obj, 'qualitative_narrative') or ''}\n{tok}".strip()
        elif section == "domain_assessments":
            # DomainAssessmentOutput list: inject into the first item's business_impact_and_risk
            try:
                if isinstance(obj, list) and obj:
                    d0 = obj[0]
                    if hasattr(d0, "business_impact_narrative"):
                        d0.business_impact_narrative = f"{getattr(d0, 'business_impact_narrative') or ''}\n{tok}".strip()
            except Exception:
                pass
        return obj
    except Exception as exc:
        write_diagnostic_error({"where": "gen_token.inject", "section": section, "error": repr(exc)})
        raise RuntimeLineageDiagnosticError from exc


def enable_runtime_tracing() -> None:
    if not _diag_enabled():
        return
    # Patch orchestrator and generators at the actual call sites
    try:
        # Orchestrator
        try:
            orch = importlib.import_module("services.report_improvement.orchestrator")
            if hasattr(orch, "enforce_report"):
                _orig_enforce = getattr(orch, "enforce_report")

                def _wrap_enforce_report(*args, **kwargs):
                    write_call_event("enter", "ui", "orchestrator.enforce_report", input_obj={"args": len(args)})
                    # Pre-call probe: record composite callable signature and identity
                    # (informational only; final fault attribution will use traceback frame matching)
                    try:
                        import inspect, json, os
                        from core import LLMEngine as _LE  # type: ignore
                        comp = getattr(_LE, "generate_maturity_report_composite", None)
                        meta = {
                            "run_id": _rid(),
                            "stage": "precall",
                            "callable_present": bool(comp is not None),
                            "callable_repr": repr(comp) if comp else None,
                            "module": getattr(comp, "__module__", None) if comp else None,
                            "qualname": getattr(comp, "__qualname__", None) if comp else None,
                            "callable_id": id(comp) if comp else None,
                            "signature": str(inspect.signature(comp)) if comp else None,
                        }
                        rd = _run_dir()
                        if rd:
                            with open(os.path.join(rd, "orchestrator_exception_trace.jsonl"), "a", encoding="utf-8") as f:
                                f.write(json.dumps(meta, ensure_ascii=False, sort_keys=True) + "\n")
                    except Exception as _exc_meta:
                        # Diagnostics must not silently drop this; log a diagnostic error line and continue
                        write_diagnostic_error({"where": "orchestrator_trace.pre", "error": repr(_exc_meta)})

                    try:
                        out = _orig_enforce(*args, **kwargs)
                        write_call_event("exit", "ui", "orchestrator.enforce_report", output_obj={"tuple_len": len(out) if isinstance(out, tuple) else 1})
                        return out
                    except Exception as exc:
                        write_call_event("exception", "ui", "orchestrator.enforce_report", exception=repr(exc))
                        # Detailed traceback capture using traceback.TracebackException and extract_tb
                        try:
                            import traceback, inspect, json, os, linecache
                            rid = _rid()
                            rd = _run_dir()
                            if not rd:
                                raise RuntimeLineageDiagnosticError("Missing run_dir for traceback logging")

                            # Build structured traceback records
                            tb_exc = traceback.TracebackException.from_exception(exc)
                            tb_list = traceback.extract_tb(exc.__traceback__) or []
                            frames_json = []
                            for fr in tb_list:
                                frames_json.append({
                                    "file": fr.filename,
                                    "line": fr.lineno,
                                    "function": fr.name,
                                    "source": fr.line
                                })

                            # Identify the exact frame that invoked LLMEngine.generate_maturity_report_composite
                            invoker_record = None
                            # Walk concrete frames to inspect locals for alias/callable and source line explicitly
                            for frame_info in inspect.getinnerframes(exc.__traceback__):
                                try:
                                    fn = frame_info.function
                                    filename = frame_info.filename
                                    lineno = frame_info.lineno
                                    # Explicit source retrieval
                                    source_line = None
                                    try:
                                        source_line = linecache.getline(filename, lineno)
                                        if source_line:
                                            source_line = source_line.rstrip()
                                    except Exception:
                                        source_line = None
                                    if source_line is None and frame_info.code_context:
                                        source_line = frame_info.code_context[0].strip()

                                    # Resolve target callable to compare identities/signatures
                                    from core import LLMEngine as _LE  # type: ignore
                                    target = getattr(_LE, "generate_maturity_report_composite", None)
                                    expected_signature = None
                                    if target:
                                        try:
                                            expected_signature = str(inspect.signature(target))
                                        except Exception:
                                            expected_signature = None

                                    # If this frame line shows a call to the composite by name, record it
                                    if fn and source_line and "generate_maturity_report_composite" in source_line:
                                        invoker_record = {
                                            "module": frame_info.frame.f_globals.get("__name__", None),
                                            "file": filename,
                                            "line": lineno,
                                            "function": fn,
                                            "source": source_line,
                                            "local_callable_name": None,
                                            "callable_id": None,
                                            "callable_repr": None,
                                            "supplied_positional_count": None,
                                            "supplied_keyword_names": None,
                                            "expected_signature": expected_signature
                                        }
                                        break
                                except Exception:
                                    continue

                            rec = {
                                "run_id": rid,
                                "stage": "exception",
                                "callee": "orchestrator.enforce_report",
                                "exception_type": type(exc).__name__,
                                "exception_message": str(exc),
                                "traceback_message": "".join(tb_exc.format()) if tb_exc else None,
                                "frames": frames_json,
                                "invoker": invoker_record
                            }
                            with open(os.path.join(rd, "orchestrator_exception_trace.jsonl"), "a", encoding="utf-8") as f:
                                f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
                        except Exception as capture_exc:
                            # Fail the diagnostic run if we cannot record the primary traceback
                            write_diagnostic_error({"where": "orchestrator_trace.capture", "error": repr(capture_exc)})
                            raise RuntimeLineageDiagnosticError("Failed to capture orchestrator traceback") from capture_exc
                        raise
                setattr(orch, "enforce_report", _wrap_enforce_report)
        except Exception as exc:
            write_diagnostic_error({"where": "enable_trace.orchestrator", "error": repr(exc)})

        # Generator wrappers
        def _wrap_source_and_callsite(mod_path: str, fn_name: str, section: str) -> None:
            src = None
            # Patch source module
            try:
                src = importlib.import_module(mod_path)
                if hasattr(src, fn_name):
                    _origf = getattr(src, fn_name)

                    def _wrapped(*args, **kwargs):
                        write_call_event("enter", "ui", f"{mod_path}.{fn_name}", input_obj={"args": len(args)})
                        try:
                            out = _origf(*args, **kwargs)
                            # inject GEN token for text or pydantic
                            if isinstance(out, str):
                                out2 = (out or "") + "\n" + make_token("GEN", _rid(), section)
                            else:
                                out2 = add_gen_token_pydantic(out, section)
                            write_call_event("exit", "ui", f"{mod_path}.{fn_name}", output_obj={"type": type(out2).__name__})
                            return out2
                        except Exception as exc:
                            write_call_event("exception", "ui", f"{mod_path}.{fn_name}", exception=repr(exc))
                            raise
                    setattr(src, fn_name, _wrapped)
                    write_diagnostic_error({
                        "where": "enable_trace.wrap.source",
                        "source_module_reference": f"{mod_path}.{fn_name}",
                        "source_callable_id": str(id(_origf)),
                        "wrapper_callable_id": str(id(getattr(src, fn_name))),
                        "patch_target": "source",
                    })
            except Exception as exc:
                write_diagnostic_error({"where": "enable_trace.wrap.source_error", "fn": f"{mod_path}.{fn_name}", "error": repr(exc)})

            # Patch orchestrator call site if it imports the symbol directly
            try:
                orch = importlib.import_module("services.report_improvement.orchestrator")
                if hasattr(orch, fn_name):
                    _orig_call = getattr(orch, fn_name)

                    def _wrapped_call(*args, **kwargs):
                        write_call_event("enter", "ui", f"orchestrator.{fn_name}", input_obj={"args": len(args)})
                        try:
                            out = _orig_call(*args, **kwargs)
                            if isinstance(out, str):
                                out2 = (out or "") + "\n" + make_token("GEN", _rid(), section)
                            else:
                                out2 = add_gen_token_pydantic(out, section)
                            write_call_event("exit", "ui", f"orchestrator.{fn_name}", output_obj={"type": type(out2).__name__})
                            return out2
                        except Exception as exc:
                            write_call_event("exception", "ui", f"orchestrator.{fn_name}", exception=repr(exc))
                            raise
                    setattr(orch, fn_name, _wrapped_call)
                    write_diagnostic_error({
                        "where": "enable_trace.wrap.callsite",
                        "calling_module_reference": f"orchestrator.{fn_name}",
                        "caller_callable_id": str(id(_orig_call)),
                        "wrapper_callable_id": str(id(getattr(orch, fn_name))),
                        "patch_target": "caller",
                    })
            except Exception as exc:
                write_diagnostic_error({"where": "enable_trace.wrap.callsite_error", "fn": f"orchestrator.{fn_name}", "error": repr(exc)})

        _wrap_source_and_callsite("services.report_improvement.section_generators.executive_summary", "generate_executive_summary", "executive_summary")
        _wrap_source_and_callsite("services.report_improvement.section_generators.security_rating", "calculate_security_rating", "security_rating")
        _wrap_source_and_callsite("services.report_improvement.section_generators.attack_scenario", "generate_attack_scenario", "threat_scenarios")
        _wrap_source_and_callsite("services.report_improvement.section_generators.compliance_alignment", "generate_compliance_alignment", "compliance_alignment")
        _wrap_source_and_callsite("services.report_improvement.section_generators.cost_of_inaction", "generate_cost_of_inaction", "cost_of_inaction")
        _wrap_source_and_callsite("services.report_improvement.section_generators.domain_assessments", "generate_domain_assessment", "domain_assessments")

        # Wrap quality_pipeline.process_maturity_report for before/after diffs and call graph
        try:
            qp = importlib.import_module("quality_pipeline")
            if hasattr(qp, "process_maturity_report"):
                _orig_qp = getattr(qp, "process_maturity_report")

                def _wrap_qp(client_inputs, report_data, *args, **kwargs):
                    write_call_event("enter", "export", "quality_pipeline.process_maturity_report", input_obj={"client_inputs_hash": canonical_value_hash(client_inputs)})
                    try:
                        before = {
                            "executive_summary": getattr(report_data, "executive_summary", None),
                            "security_rating": getattr(report_data, "security_rating", None),
                            "threat_scenarios": getattr(report_data, "threat_scenarios", None),
                            "compliance_alignment": getattr(report_data, "compliance_alignment", None),
                            "cost_of_inaction": getattr(report_data, "cost_of_inaction", None),
                            "domain_assessments": getattr(report_data, "domain_assessments", None),
                        }
                    except Exception:
                        before = {}
                    out = _orig_qp(client_inputs, report_data, *args, **kwargs)
                    try:
                        rd_after = out[0] if isinstance(out, tuple) else out
                        after = {
                            "executive_summary": getattr(rd_after, "executive_summary", None),
                            "security_rating": getattr(rd_after, "security_rating", None),
                            "threat_scenarios": getattr(rd_after, "threat_scenarios", None),
                            "compliance_alignment": getattr(rd_after, "compliance_alignment", None),
                            "cost_of_inaction": getattr(rd_after, "cost_of_inaction", None),
                            "domain_assessments": getattr(rd_after, "domain_assessments", None),
                        }
                        for _k in before.keys():
                            write_overwrite_event(_k, "quality_pipeline", before.get(_k), after.get(_k), handler="quality_pipeline.process_maturity_report")
                    except Exception as exc:
                        write_diagnostic_error({"where": "quality_pipeline.diff", "error": repr(exc)})
                    write_call_event("exit", "export", "quality_pipeline.process_maturity_report", output_obj={"type": type(out).__name__})
                    return out
                setattr(qp, "process_maturity_report", _wrap_qp)
        except Exception as exc:
            write_diagnostic_error({"where": "enable_trace.quality_pipeline", "error": repr(exc)})

        # Wrap docxtpl.DocxTemplate.render to inject MODEL/EXPORT tokens at export-context time
        try:
            docxtpl = importlib.import_module("docxtpl")
            if hasattr(docxtpl, "DocxTemplate") and hasattr(docxtpl.DocxTemplate, "render"):
                _orig_render = getattr(docxtpl.DocxTemplate, "render")

                def _render_wrapper(self, context, *args, **kwargs):
                    rid = _rid()
                    ctx_copy = context
                    try:
                        if isinstance(context, dict):
                            ctx_copy = dict(context)
                            # MODEL tokens for six sections (diagnostic only, env gated in downstream helpers)
                            try:
                                tok = make_token
                                if isinstance(ctx_copy.get("exec_summary"), str) and ctx_copy["exec_summary"]:
                                    ctx_copy["exec_summary"] = ctx_copy["exec_summary"] + "\n" + tok("MODEL", rid, "executive_summary")
                                sr = ctx_copy.get("security_rating")
                                if isinstance(sr, dict) and isinstance(sr.get("snapshot", {}).get("board_level_takeaway"), str):
                                    sr["snapshot"]["board_level_takeaway"] = sr["snapshot"]["board_level_takeaway"] + " " + tok("MODEL", rid, "security_rating")
                                    ctx_copy["security_rating"] = sr
                                if isinstance(ctx_copy.get("threat_scenarios"), str) and ctx_copy["threat_scenarios"]:
                                    ctx_copy["threat_scenarios"] = ctx_copy["threat_scenarios"] + "\n" + tok("MODEL", rid, "threat_scenarios")
                                if isinstance(ctx_copy.get("compliance_alignment_render"), str) and ctx_copy["compliance_alignment_render"]:
                                    ctx_copy["compliance_alignment_render"] = ctx_copy["compliance_alignment_render"] + "\n" + tok("MODEL", rid, "compliance_alignment")
                                if isinstance(ctx_copy.get("cost_of_inaction"), str) and ctx_copy["cost_of_inaction"]:
                                    ctx_copy["cost_of_inaction"] = ctx_copy["cost_of_inaction"] + "\n" + tok("MODEL", rid, "cost_of_inaction")
                                if isinstance(ctx_copy.get("domains"), list) and ctx_copy["domains"]:
                                    d0 = ctx_copy["domains"][0]
                                    if isinstance(d0, dict):
                                        for _k in ("business_impact_narrative", "remediation_rationale", "current_state_analysis"):
                                            if _k in d0 and isinstance(d0.get(_k), str) and d0[_k]:
                                                d0[_k] = d0[_k] + "\n" + tok("MODEL", rid, "domain_assessments")
                                                break
                                    ctx_copy["domains"][0] = d0
                            except Exception:
                                pass
                            # EXPORT tokens
                            try:
                                ctx_copy = add_export_token_to_context(ctx_copy, rid)
                            except Exception:
                                pass
                    except Exception:
                        ctx_copy = context
                    # Avoid hashing full context (may include non‑serialisable InlineImage, file handles, etc.)
                    safe_meta = {
                        "context_keys": sorted(list(ctx_copy.keys())) if isinstance(ctx_copy, dict) else None,
                        "context_size": (len(ctx_copy) if isinstance(ctx_copy, dict) else None),
                    }
                    try:
                        write_context_shapes(ctx_copy)
                    except Exception:
                        pass
                    write_call_event("enter", "export", "DocxTemplate.render", input_obj=safe_meta)
                    try:
                        return _orig_render(self, ctx_copy, *args, **kwargs)
                    finally:
                        write_call_event("exit", "export", "DocxTemplate.render")
                setattr(docxtpl.DocxTemplate, "render", _render_wrapper)
        except Exception as exc:
            write_diagnostic_error({"where": "enable_trace.docxtpl_render", "error": repr(exc)})

        # Wrap export.create_maturity_docx to capture bytes and persist rendered extracts
        try:
            exp_mod = importlib.import_module("export")
            if hasattr(exp_mod, "create_maturity_docx"):
                _orig_export = getattr(exp_mod, "create_maturity_docx")

                def _wrap_export(*args, **kwargs):
                    write_call_event("enter", "ui", "export.create_maturity_docx", input_obj={"args": len(args)})
                    try:
                        globals()["_LATEST_CLIENT_INPUTS"] = args[0] if len(args) >= 1 else None
                        globals()["_LATEST_REPORT_DATA"] = args[1] if len(args) >= 2 else None
                    except Exception:
                        pass
                    out = _orig_export(*args, **kwargs)
                    try:
                        extract_rendered_sections(out)
                        persist_diagnostic_docx(out)
                        merge_runtime_configuration("render", {"rendered_bytes": len(out)}, None)
                        write_call_event("exit", "ui", "export.create_maturity_docx", output_obj={"bytes": len(out)})
                    except Exception as exc:
                        write_diagnostic_error({"where": "export.wrapper.post", "error": repr(exc)})
                    return out
                setattr(exp_mod, "create_maturity_docx", _wrap_export)
        except Exception as exc:
            write_diagnostic_error({"where": "enable_trace.export_wrapper", "error": repr(exc)})

        # Wrap LLMEngine generators to identify raw report creation (best-effort)
        try:
            core = importlib.import_module("core")
            for _name in ("generate_maturity_report_staged_v3", "generate_maturity_report_composite"):
                if hasattr(core.LLMEngine, _name):
                    _orig = getattr(core.LLMEngine, _name)

                    def _make_wrap(name, orig):
                        def _wrap_llm(*args, **kwargs):
                            write_call_event("enter", "ui", f"LLMEngine.{name}", input_obj={"args": len(args)})
                            out = orig(*args, **kwargs)
                            # Record initial report snapshot hashes best-effort
                            try:
                                rd = {
                                    "executive_summary": getattr(out, "executive_summary", None),
                                    "security_rating": getattr(out, "security_rating", None),
                                    "threat_scenarios": getattr(out, "threat_scenarios", None),
                                    "compliance_alignment": getattr(out, "compliance_alignment", None),
                                    "cost_of_inaction": getattr(out, "cost_of_inaction", None),
                                    "domain_assessments": getattr(out, "domain_assessments", None),
                                    "current_environment": getattr(out, "current_environment", None),
                                    "critical_findings": getattr(out, "critical_findings", None),
                                    "roadmap": getattr(out, "phased_roadmap", getattr(out, "roadmap", None)),
                                }
                                # Token origin scan
                                tokens = [
                                    "Professional Services", "60 servers", "CRM", "ERP", "Payroll", "HR systems",
                                    "£455,000", "£280,000", "£630,000", "CVE-", "Adlumin",
                                    "Gap: Missing policies or controls",
                                    "Planet IT configures and guides best practice",
                                ]
                                origins = []
                                for t in tokens:
                                    try:
                                        for k, v in rd.items():
                                            s = str(v) if not isinstance(v, (dict, list, tuple)) else json.dumps(_as_supported(v), ensure_ascii=False)
                                            if t in s:
                                                origins.append({
                                                    "token": t, "first_stage": "raw_report_generation",
                                                    "function": f"LLMEngine.{name}", "field_path": k,
                                                    "source_hash": canonical_value_hash(v),
                                                    "later_stages": []
                                                })
                                                break
                                    except Exception:
                                        continue
                                if origins:
                                    path = os.path.join(_run_dir(), "canonical_environment_trace.json")
                                    try:
                                        prior = []
                                        if os.path.exists(path):
                                            with open(path, "r", encoding="utf-8") as f:
                                                prior = json.load(f)
                                        with open(path + ".tmp", "w", encoding="utf-8") as f:
                                            json.dump(prior + origins, f, ensure_ascii=False, indent=2, sort_keys=True)
                                        os.replace(path + ".tmp", path)
                                    except Exception:
                                        write_diagnostic_error({"where": "token_origins.write", "error": "write_failed"})
                            except Exception:
                                pass
                            write_call_event("exit", "ui", f"LLMEngine.{name}", output_obj={"type": type(out).__name__})
                            return out
                        return _wrap_llm

                    setattr(core.LLMEngine, _name, _make_wrap(_name, _orig))
        except Exception as exc:
            write_diagnostic_error({"where": "enable_trace.llmengine", "error": repr(exc)})

    except Exception as exc:
        write_diagnostic_error({"where": "enable_trace", "error": repr(exc)})
        raise RuntimeLineageDiagnosticError from exc


def extract_rendered_sections(doc_bytes: bytes) -> Optional[str]:
    """Extract paragraph and table content in document order with explicit start/stop boundaries."""
    if not _diag_enabled():
        return None
    try:
        from docx import Document  # type: ignore
        from docx.oxml.text.paragraph import CT_P  # type: ignore
        from docx.oxml.table import CT_Tbl  # type: ignore
        from docx.text.paragraph import Paragraph  # type: ignore
        from docx.table import _Cell, Table  # type: ignore
    except Exception as exc:
        write_diagnostic_error({"where": "render_extracts.import", "error": repr(exc)})
        raise RuntimeLineageDiagnosticError from exc

    try:
        doc = Document(io.BytesIO(doc_bytes))
    except Exception as exc:
        write_diagnostic_error({"where": "render_extracts.open", "error": repr(exc)})
        raise RuntimeLineageDiagnosticError from exc

    # Boundaries (aliases can be extended via env later)
    start_aliases = {
        "Executive Summary": ["executive summary"],
        "Security Rating": ["security rating", "security snapshot"],
        "Simulated Attack Scenario": ["simulated attack scenario", "simulated attack of current infrastructure", "attack scenario", "threat scenario"],
        "Compliance and Framework Alignment": ["compliance and framework alignment", "compliance alignment"],
        "Cost of Inaction": ["cost of inaction"],
        "Domain Assessments": ["detailed assessment", "domain assessment", "security domain"],
    }
    stop_aliases = {
        "Executive Summary": ["identified known issues", "security rating", "security snapshot"],
        "Security Rating": ["findings", "critical findings"],
        "Simulated Attack Scenario": ["current domain alignment", "executive commentary", "compliance"],
        "Compliance and Framework Alignment": ["cost of inaction"],
        "Cost of Inaction": ["overview of current environment"],
        "Domain Assessments": ["security testing and planning"],
    }

    def iter_block_items(parent):
        # Iterate paragraphs and tables in document order
        for child in parent.element.body.iterchildren():
            if isinstance(child, CT_P):
                yield Paragraph(child, parent)
            elif isinstance(child, CT_Tbl):
                yield Table(child, parent)

    sections: Dict[str, Dict[str, Any]] = {
        "Executive Summary": {"lines": [], "reliable": True, "found_start": False, "found_stop": False},
        "Security Rating": {"lines": [], "reliable": True, "found_start": False, "found_stop": False},
        "Simulated Attack Scenario": {"lines": [], "reliable": True, "found_start": False, "found_stop": False},
        "Compliance and Framework Alignment": {"lines": [], "reliable": True, "found_start": False, "found_stop": False},
        "Cost of Inaction": {"lines": [], "reliable": True, "found_start": False, "found_stop": False},
        "Domain Assessments": {"lines": [], "reliable": True, "found_start": False, "found_stop": False},
    }
    active: Optional[str] = None

    def _is_heading(text_lower: str, aliases: List[str]) -> bool:
        return any(a in text_lower for a in aliases)

    try:
        for blk in iter_block_items(doc):
            if isinstance(blk, Paragraph):
                txt = (blk.text or "").strip()
                tlo = txt.lower()
                # Start headings
                for sec, aliases in start_aliases.items():
                    if _is_heading(tlo, aliases):
                        active = sec
                        sections[sec]["found_start"] = True
                        continue
                # Heuristic: domain table rows often start with "Domain:" even when heading context is ambiguous
                if "domain:" in tlo:
                    active = "Domain Assessments"
                    sections["Domain Assessments"]["found_start"] = True
                # Stop headings
                for sec, aliases in stop_aliases.items():
                    if active == sec and _is_heading(tlo, aliases):
                        sections[sec]["found_stop"] = True
                        active = None
                        break
                if active and txt:
                    sections[active]["lines"].append({"type": "paragraph", "text": txt})
            elif isinstance(blk, Table):
                # Table — also detect headings within table cells
                tbl: Table = blk
                for r_idx, row in enumerate(tbl.rows):
                    for c_idx, cell in enumerate(row.cells):
                        # Extract cell text
                        text = (cell.text or "").strip()
                        if not text:
                            continue
                        tll = text.lower()
                        # Start headings inside tables (allow switching even if another section is active)
                        for sec, aliases in start_aliases.items():
                            if _is_heading(tll, aliases):
                                active = sec
                                sections[sec]["found_start"] = True
                                # Do not record this heading cell as content line
                                break
                        # Stop headings inside tables
                        if active:
                            for sec, aliases in stop_aliases.items():
                                if active == sec and _is_heading(tll, aliases):
                                    sections[sec]["found_stop"] = True
                                    active = None
                                    break
                        # Heuristic: switch to Domain Assessments when encountering domain row markers in tables
                        if "domain:" in tll and active != "Domain Assessments":
                            active = "Domain Assessments"
                            sections["Domain Assessments"]["found_start"] = True
                        if active:
                            sections[active]["lines"].append({"type": "table_cell", "row": r_idx, "col": c_idx, "text": text})
    except Exception as exc:
        write_diagnostic_error({"where": "render_extracts.iter", "error": repr(exc)})
        raise RuntimeLineageDiagnosticError from exc

    out = {}
    for sec, rec in sections.items():
        if not rec["found_start"] or not rec["found_stop"]:
            rec["reliable"] = False
        joined = "\n".join([l.get("text", "") for l in rec["lines"] if l.get("text")])
        out[sec] = {
            "lines": rec["lines"],
            "canonical_text_hash": canonical_text_hash(joined),
            "length": len(joined),
            "found_start": rec["found_start"],
            "found_stop": rec["found_stop"],
            "reliable": rec["reliable"],
        }
    path = os.path.join(_run_dir(), "rendered_section_extracts.json")
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp, path)
        return path
    except Exception as exc:
        write_diagnostic_error({"where": "render_extracts.write", "error": repr(exc)})
        raise RuntimeLineageDiagnosticError from exc


def persist_diagnostic_docx(doc_bytes: bytes) -> Optional[str]:
    if not _diag_enabled():
        return None
    try:
        path = os.path.join(_run_dir(), f"diagnostic_review_copy_{_rid()}.docx")
        with open(path, "wb") as f:
            f.write(doc_bytes or b"")
        return path
    except Exception as exc:
        write_diagnostic_error({"where": "persist_diagnostic_docx", "error": repr(exc)})
        raise RuntimeLineageDiagnosticError from exc