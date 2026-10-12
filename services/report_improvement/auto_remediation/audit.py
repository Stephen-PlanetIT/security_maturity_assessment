from __future__ import annotations
from typing import Dict, Any
import os
import json
from datetime import datetime, timezone
from config import get_config

# Minimal audit/metrics helpers.
# - Metrics dictionary keys are free-form strings; values are integers or small scalars.
# - Manifest writer avoids transcripts; stores evidence IDs and short excerpts only (provided by caller).
# - Writers are best-effort; IO failures are swallowed to preserve fail-closed gating.


def record_metric(metrics: Dict[str, Any], key: str, inc: int = 1) -> None:
    try:
        metrics[key] = int(metrics.get(key, 0)) + inc
    except Exception:
        pass


def record_action(manifest: Dict[str, Any], action: Dict[str, Any]) -> None:
    """
    Append a remediation action to the manifest under 'automatic_fixes' (default bucket).
    Callers may pre-arrange the manifest structure as needed (e.g., evidence_grounded_rewrites).
    """
    try:
        bucket = manifest.setdefault("automatic_fixes", [])
        if isinstance(bucket, list):
            bucket.append(dict(action or {}))
    except Exception:
        pass


def _sanitize_name(name: str) -> str:
    """Allow only safe characters for filenames/paths."""
    try:
        return "".join(ch for ch in str(name or "report") if ch.isalnum() or ch in ("-", "_")).strip() or "report"
    except Exception:
        return "report"


def write_remediation_manifest(report_name: str, manifest: Dict[str, Any], logs_dir: str | None = None) -> str:
    """
    Write the remediation manifest JSON:
      exports/logs/<safe_report>/<run_id>/<safe_report>_remediation.json

    Returns the full file path on success (or intended path on failure).
    """
    try:
        safe_report = _sanitize_name(report_name or "report")
        base_dir = str(logs_dir or get_config("LOGS_DIR", "exports/logs"))
        run_id = str(manifest.get("run_id") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        out_dir = os.path.join(base_dir, safe_report, run_id)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"{safe_report}_remediation.json")

        # Ensure minimal sensitive content: strip raw transcripts if present
        to_write: Dict[str, Any] = dict(manifest or {})
        for k in list(to_write.keys()):
            if "transcript" in str(k).lower():
                to_write.pop(k, None)

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(to_write, f, ensure_ascii=False, indent=2)
        return out_path
    except Exception:
        # Best-effort; return the intended path if we can compute it
        try:
            safe_report = _sanitize_name(report_name or "report")
            base_dir = str(logs_dir or get_config("LOGS_DIR", "exports/logs"))
            run_id = str(manifest.get("run_id") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
            return os.path.join(base_dir, safe_report, run_id, f"{safe_report}_remediation.json")
        except Exception:
            return ""


def write_metrics(logs_dir: str, run_id: str, data: Dict[str, Any], report_name: str = "report") -> str:
    """
    Write a minimal metrics.json alongside the remediation manifest directory structure.
    """
    try:
        safe_report = _sanitize_name(report_name or "report")
        base_dir = str(logs_dir or get_config("LOGS_DIR", "exports/logs"))
        out_dir = os.path.join(base_dir, safe_report, str(run_id or "latest"))
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "metrics.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(dict(data or {}), f, ensure_ascii=False, indent=2)
        return out_path
    except Exception:
        return ""
