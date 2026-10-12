from __future__ import annotations

"""
lineage.py — Specialist Output Lineage Utilities

Non-invasive lineage hashing and trace writer for specialist sections:
  generator → validation → remediation → final object → export context → rendered
Hashes are canonical SHA256 of stable serialisations.
"""

import json
import os
import hashlib
import unicodedata
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional, Dict, Any

try:
    # Optional config integration; avoid hard dependency
    from config import get_config  # type: ignore
except Exception:
    def get_config(key: str, default: Optional[str] = None) -> Optional[str]:  # type: ignore
        return default


class SectionSource:
    SPECIALIST = "specialist"
    REMEDIATED_SPECIALIST = "remediated_specialist"
    VALIDATED_ORIGINAL = "validated_original"
    BLOCKED_REVIEW = "blocked_review"


@dataclass
class SectionLineageTrace:
    run_id: str
    section_name: str

    generator_executed: bool = False
    generator_hash: Optional[str] = None

    validation_hash: Optional[str] = None
    validation_status: Optional[str] = None

    remediation_executed: bool = False
    remediation_hash: Optional[str] = None

    stored_field_path: str = ""
    stored_hash: Optional[str] = None

    export_context_key: str = ""
    export_hash: Optional[str] = None

    rendered_hash: Optional[str] = None

    source: str = SectionSource.SPECIALIST
    fallback_reason: Optional[str] = None

    lineage_match: bool = False


def _normalize_text(s: str) -> str:
    """
    Canonicalise text for stable hashing:
      - NFKC unicode normalisation
      - normalise CRLF to LF
      - strip trailing spaces per line
    """
    try:
        s_norm = unicodedata.normalize("NFKC", s)
    except Exception:
        s_norm = s
    try:
        s_norm = s_norm.replace("\r\n", "\n").replace("\r", "\n")
    except Exception:
        pass
    try:
        s_norm = "\n".join([ln.rstrip() for ln in s_norm.split("\n")])
    except Exception:
        pass
    return s_norm


def hash_canonical(obj_or_text: Any) -> str:
    """
    Compute SHA256 of a canonicalised serialisation:
      - dict/list: JSON with sorted keys
      - other: normalised string
    """
    try:
        if isinstance(obj_or_text, (dict, list)):
            payload = json.dumps(obj_or_text, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        else:
            payload = str(obj_or_text if obj_or_text is not None else "")
        payload = _normalize_text(payload)
    except Exception:
        payload = ""
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _ensure_dir(p: str) -> None:
    try:
        os.makedirs(p, exist_ok=True)
    except Exception:
        pass


def _default_logs_dir() -> str:
    try:
        return get_config("LOGS_DIR", "exports/logs") or "exports/logs"
    except Exception:
        return "exports/logs"


def write_lineage_trace(trace: SectionLineageTrace, out_dir: Optional[str] = None) -> Optional[str]:
    """
    Append/merge the given trace into per-run lineage log files:
      exports/logs/<run_id>/specialist_lineage.json                (legacy path)
      exports/logs/<run_id>/specialist_runtime_lineage.json        (diagnostic path)
    Returns the primary path written or None on failure.
    """
    try:
        base_dir = out_dir or _default_logs_dir()
        run_dir = os.path.join(base_dir, trace.run_id)
        _ensure_dir(run_dir)
        out_path_primary = os.path.join(run_dir, "specialist_lineage.json")
        out_path_runtime = os.path.join(run_dir, "specialist_runtime_lineage.json")

        # Load existing map [section_name -> latest trace] from primary path
        existing: Dict[str, Dict[str, Any]] = {}
        if os.path.exists(out_path_primary):
            try:
                with open(out_path_primary, "r", encoding="utf-8") as f:
                    existing = json.load(f) if f.readable() else {}
                    if not isinstance(existing, dict):
                        existing = {}
            except Exception:
                existing = {}

        # Upsert latest trace
        existing[str(trace.section_name)] = asdict(trace)

        # Write atomically to both files (best-effort)
        try:
            tmp_primary = out_path_primary + ".tmp"
            with open(tmp_primary, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2, sort_keys=True)
            os.replace(tmp_primary, out_path_primary)
        except Exception:
            # Continue; attempt runtime file even if primary fails
            pass

        try:
            tmp_runtime = out_path_runtime + ".tmp"
            with open(tmp_runtime, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2, sort_keys=True)
            os.replace(tmp_runtime, out_path_runtime)
        except Exception:
            # Ignore runtime write failures silently (diagnostic optional)
            pass

        return out_path_primary
    except Exception:
        return None


def new_run_id() -> str:
    """
    Generate a simple UTC timestamp-based run id suitable for file names.
    """
    try:
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    except Exception:
        return "unknown_run"


def record_stage_hash(
    trace: SectionLineageTrace,
    stage: str,
    payload: Any,
    validation_status: Optional[str] = None,
    source: Optional[str] = None,
    fallback_reason: Optional[str] = None,
) -> SectionLineageTrace:
    """
    Convenience: set the appropriate hash on the trace for a given stage.
    stage ∈ {generator, validation, remediation, stored, export, rendered}
    """
    h = hash_canonical(payload)
    if stage == "generator":
        trace.generator_executed = True
        trace.generator_hash = h
    elif stage == "validation":
        trace.validation_hash = h
        if validation_status is not None:
            trace.validation_status = validation_status
    elif stage == "remediation":
        trace.remediation_executed = True
        trace.remediation_hash = h
    elif stage == "stored":
        trace.stored_hash = h
    elif stage == "export":
        trace.export_hash = h
    elif stage == "rendered":
        trace.rendered_hash = h
    if source:
        trace.source = source
    if fallback_reason is not None:
        trace.fallback_reason = fallback_reason
    return trace


def finalise_lineage_match(trace: SectionLineageTrace) -> SectionLineageTrace:
    """
    Set lineage_match flag based on export vs rendered hash equality
    (only for sections where rendered hash has been captured).
    """
    try:
        if trace.export_hash and trace.rendered_hash:
            trace.lineage_match = (trace.export_hash == trace.rendered_hash)
        else:
            trace.lineage_match = False
    except Exception:
        trace.lineage_match = False
    return trace


# Convenience helpers for simpler call-sites
def write_section_event(
    trace_or_name: SectionLineageTrace | str,
    stage: str,
    payload: Any,
    validation_status: Optional[str] = None,
    source: Optional[str] = None,
    fallback_reason: Optional[str] = None,
    stored_field_path: str = "",
    export_context_key: str = ""
) -> Optional[str]:
    """
    Write a lineage event in one call.
    - If trace_or_name is a SectionLineageTrace, it will be used directly.
    - If it's a string, a new trace will be created for that section.
    Stage ∈ {"generator","validation","remediation","stored","export","rendered"}.
    """
    try:
        if isinstance(trace_or_name, SectionLineageTrace):
            trace = trace_or_name
        else:
            # Build a minimal trace for this section
            rid = ensure_run_id()
            sec_name = str(trace_or_name)
            trace = SectionLineageTrace(
                run_id=rid,
                section_name=sec_name,
                stored_field_path=stored_field_path or f"report.{sec_name}",
                export_context_key=export_context_key or sec_name,
                source=source or SectionSource.SPECIALIST,
            )
        record_stage_hash(
            trace,
            stage,
            payload,
            validation_status=validation_status,
            source=source,
            fallback_reason=fallback_reason,
        )
        return write_lineage_trace(trace)
    except Exception:
        return None

# ============================
# Diagnostic extensions (env‑gated)
# ============================

# Run ID state (propagated via env when available)
_RUN_ID: Optional[str] = None

def is_diagnostics_enabled() -> bool:
    """
    Diagnostics enabled only when:
      - RUNTIME_LINEAGE_TRACE_ENABLED=true
      AND (ENVIRONMENT != 'production' OR DIAGNOSTIC_SANDBOX=true)
    """
    try:
        enabled = str(get_config("RUNTIME_LINEAGE_TRACE_ENABLED", "false")).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        enabled = False
    try:
        env = (os.getenv("ENVIRONMENT") or str(get_config("ENVIRONMENT", "dev")) or "").strip().lower()
    except Exception:
        env = "dev"
    try:
        sandbox = str(get_config("DIAGNOSTIC_SANDBOX", "false")).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        sandbox = False
    return bool(enabled and (env != "production" or sandbox))


def set_run_id(run_id: str) -> None:
    global _RUN_ID
    _RUN_ID = run_id or _RUN_ID
    try:
        if run_id:
            os.environ["RUNTIME_LINEAGE_RUN_ID"] = run_id
    except Exception:
        pass


def get_run_id() -> Optional[str]:
    rid = os.getenv("RUNTIME_LINEAGE_RUN_ID")
    return rid or _RUN_ID


def ensure_run_id() -> str:
    rid = get_run_id()
    if not rid:
        rid = new_run_id()
        set_run_id(rid)
    return rid


def _run_dir() -> Optional[str]:
    rid = get_run_id()
    if not rid:
        return None
    base_dir = _default_logs_dir()
    p = os.path.join(base_dir, rid)
    _ensure_dir(p)
    return p


# Canonical hashing API requested by diagnostics spec

def canonical_json_hash(value: Any) -> str:
    """
    Canonical JSON hash for structured values (dict/list, pydantic models).
    - Uses model_dump()/dict() when available
    - Sorted keys, UTF-8, NFC/LF normalised via hash_canonical()
    """
    try:
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        elif hasattr(value, "dict"):
            value = value.dict()
    except Exception:
        pass
    return hash_canonical(value if isinstance(value, (dict, list)) else {})


def canonical_text_hash(value: str) -> str:
    """
    Canonical text hash with Unicode normalisation and LF line endings.
    """
    return hashlib.sha256(_normalize_text(str(value or "")).encode("utf-8")).hexdigest()


def canonical_section_hash(section_name: str, value: Any) -> str:
    """
    Canonical hash incorporating section name and canonicalised payload.
    """
    try:
        payload = f"{section_name}::{_normalize_text(json.dumps(value, ensure_ascii=False, sort_keys=True))}" if isinstance(value, (dict, list)) else f"{section_name}::{_normalize_text(str(value))}"
    except Exception:
        payload = f"{section_name}::"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# Runtime configuration writer

def write_runtime_configuration(cfg: Dict[str, Any]) -> Optional[str]:
    """
    Write effective runtime configuration under exports/logs/<run_id>/runtime_configuration.json
    """
    if not is_diagnostics_enabled():
        return None
    rid = ensure_run_id()
    run_dir = _run_dir()
    if not run_dir:
        return None
    out_path = os.path.join(run_dir, "runtime_configuration.json")
    try:
        tmp = out_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"runtime_configuration": cfg}, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp, out_path)
        return out_path
    except Exception:
        return None


# Assignment trace (JSONL)

def trace_assignment(field_path: str, prior_value: Any, new_value: Any, source: str, caller_hint: Optional[str] = None) -> Optional[str]:
    """
    Append a runtime assignment record with canonical hashes and caller metadata.
    File: exports/logs/<run_id>/runtime_assignment_trace.jsonl
    """
    if not is_diagnostics_enabled():
        return None
    rid = ensure_run_id()
    run_dir = _run_dir()
    if not run_dir:
        return None
    try:
        import inspect  # local import to avoid baseline impact
        frm = inspect.stack()[1] if not caller_hint else None
        fn = (frm.filename if frm else None)
        ln = (frm.lineno if frm else None)
        func = caller_hint or (frm.function if frm else None)
    except Exception:
        fn = ln = func = None
    record = {
        "run_id": rid,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "field_path": field_path,
        "source": source,
        "prior_hash": hash_canonical(prior_value),
        "new_hash": hash_canonical(new_value),
        "prior_len": len(str(prior_value)) if prior_value is not None else 0,
        "new_len": len(str(new_value)) if new_value is not None else 0,
        "caller_file": fn,
        "caller_line": ln,
        "caller_func": func,
    }
    out_path = os.path.join(run_dir, "runtime_assignment_trace.jsonl")
    try:
        with open(out_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            f.write("\n")
        return out_path
    except Exception:
        return None


# Persist a diagnostic review copy (.docx)

def persist_review_copy(doc_bytes: bytes) -> Optional[str]:
    """
    Write diagnostic_review_copy.docx under the current run directory.
    """
    if not is_diagnostics_enabled():
        return None
    rid = ensure_run_id()
    run_dir = _run_dir()
    if not run_dir:
        return None
    out_path = os.path.join(run_dir, "diagnostic_review_copy.docx")
    try:
        with open(out_path, "wb") as f:
            f.write(doc_bytes or b"")
        return out_path
    except Exception:
        return None


# Rendered section extracts

def write_rendered_section_extracts(doc_bytes: bytes) -> Optional[str]:
    """
    Extract rendered text for key sections and write rendered_section_extracts.json.
    Uses python-docx; best-effort extraction, tolerant to template variance.
    """
    if not is_diagnostics_enabled():
        return None
    rid = ensure_run_id()
    run_dir = _run_dir()
    if not run_dir:
        return None
    try:
        from docx import Document  # type: ignore
    except Exception:
        return None
    sections = {
        "Executive Summary": [],
        "Security Rating": [],
        "Simulated Attack Scenario": [],
        "Compliance and Framework Alignment": [],
        "Cost of Inaction": [],
        "Domain Assessments": [],
    }
    try:
        import io as _io
        doc = Document(_io.BytesIO(doc_bytes))
        # Heuristic: collect text lines, then segment by headings (exact or contains)
        current = None
        for p in doc.paragraphs:
            txt = (p.text or "").strip()
            if not txt:
                continue
            # Heading detection (case-insensitive, tolerant)
            low = txt.lower()
            if "executive summary" in low:
                current = "Executive Summary"; continue
            if "security rating" in low or "security snapshot" in low:
                current = "Security Rating"; continue
            if "attack scenario" in low or "threat scenario" in low:
                current = "Simulated Attack Scenario"; continue
            if "compliance" in low and ("alignment" in low or "framework" in low):
                current = "Compliance and Framework Alignment"; continue
            if "cost of inaction" in low:
                current = "Cost of Inaction"; continue
            if "domain assessment" in low or "security domain" in low:
                current = "Domain Assessments"; continue
            if current:
                sections[current].append(txt)
    except Exception:
        pass
    # Hashes
    out = {}
    for k, lines in sections.items():
        joined = "\n".join(lines)
        out[k] = {
            "text": joined,
            "canonical_text_hash": canonical_text_hash(joined),
            "length": len(joined),
        }
    out_path = os.path.join(run_dir, "rendered_section_extracts.json")
    try:
        tmp = out_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp, out_path)
        return out_path
    except Exception:
        return None
