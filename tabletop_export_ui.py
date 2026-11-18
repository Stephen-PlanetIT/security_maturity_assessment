# -*- coding: utf-8 -*-
"""
UI adapter for presenting transactional export results in Streamlit.

This module is intentionally independent of pages/03_Tabletop_Designer.py so it can be
unit-tested without importing the Streamlit page. It provides:

- TabletopExportView: a simple, testable view-model describing the derived UI state
- build_tabletop_export_view(export_state, export_result, expected_fingerprint=None):
    Builds a strict-verified view from state and result dict
- render_tabletop_export_status(st_api, view) -> bool:
    Renders the view onto the provided st-like API surface.
    Returns True if a Retry action was invoked (only in failed/unverified states).
"""

from __future__ import annotations

import dataclasses
import hashlib
import hmac
import json
import os
from typing import Optional, Tuple
from config import get_config
try:
    # Use shared production functions for provenance (do not compute fingerprint here)
    from production_export import get_tabletop_template_lineage
except Exception:
    get_tabletop_template_lineage = None


@dataclasses.dataclass
class TabletopExportView:
    # Raw state/result
    export_state: str
    export_result: dict

    # Derived verification flags and safe display fields
    verified: bool = False
    participant_basename: str = ""
    facilitator_basename: str = ""
    export_timestamp_utc: str = ""
    reused_existing_pack: bool = False
    verification_error: Optional[str] = None

    # Absolute paths are retained only for internal file reads (not exposed)
    _participant_path: Optional[str] = None
    _facilitator_path: Optional[str] = None
    _acceptance_meta_path: Optional[str] = None

    # Reported hashes (must be present and match)
    _reported_pptx_sha: Optional[str] = None
    _reported_docx_sha: Optional[str] = None


def _const_eq(a: str, b: str) -> bool:
    try:
        return hmac.compare_digest(str(a), str(b))
    except Exception:
        # Fallback to equality if compare_digest not available for environment
        return str(a) == str(b)


def _sha256(path: str) -> str:
    hh = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hh.update(chunk)
    return hh.hexdigest()


def _load_acceptance_meta(path: str) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _verify_success_contract(
    result: dict,
    expected_fingerprint: Optional[str],
) -> Tuple[bool, Optional[str]]:
    """
    Strict success verification contract:
      - result['succeeded'] is True
      - participant_pptx_path, facilitator_guide_path, acceptance_metadata_path exist
      - participant_pptx_sha256 present and matches file
      - facilitator_guide_sha256 present and matches file
      - acceptance metadata exists and, if expected_fingerprint is provided, matches
      - acceptance metadata records both published hashes equal to files' hashes (accepted)
    """
    # Basic shape
    if not bool(result.get("succeeded") is True):
        return False, "Result not succeeded"
    pptx_path = result.get("participant_pptx_path")
    docx_path = result.get("facilitator_guide_path")
    meta_path = result.get("acceptance_metadata_path")
    if not (pptx_path and docx_path and meta_path):
        return False, "Missing published artefact paths"
    if not (os.path.exists(pptx_path) and os.path.exists(docx_path) and os.path.exists(meta_path)):
        return False, "Published artefacts missing on filesystem"

    # Reported hashes must be present
    rep_pptx = result.get("participant_pptx_sha256")
    rep_docx = result.get("facilitator_guide_sha256")
    if not (rep_pptx and rep_docx):
        return False, "Reported hashes missing"

    # Compute hashes and constant-time compare (no permissive fallback)
    try:
        act_pptx = _sha256(pptx_path)
        act_docx = _sha256(docx_path)
    except Exception as e:
        return False, f"Hash computation failed: {e}"
    if not _const_eq(rep_pptx, act_pptx):
        return False, "PPTX hash mismatch"
    if not _const_eq(rep_docx, act_docx):
        return False, "DOCX hash mismatch"

    # Acceptance metadata
    meta = _load_acceptance_meta(meta_path)
    if not isinstance(meta, dict):
        return False, "Acceptance metadata unreadable"

    # Optional fingerprint check (must match both result and metadata fingerprints)
    if expected_fingerprint is not None:
        res_fp = str(result.get("export_fingerprint") or "")
        meta_fp = str(meta.get("FINGERPRINT") or "")
        if not (res_fp and meta_fp):
            return False, "Result or metadata fingerprint missing"
        if not (_const_eq(meta_fp, expected_fingerprint) and _const_eq(res_fp, expected_fingerprint)):
            return False, "Fingerprint mismatch"

    # Metadata must reflect accepted published hashes matching files
    meta_pub_pptx = meta.get("published_pptx_sha256")
    meta_pub_docx = meta.get("published_docx_sha256")
    if not (meta_pub_pptx and meta_pub_docx):
        return False, "Acceptance metadata missing published hashes"
    if not (_const_eq(meta_pub_pptx, act_pptx) and _const_eq(meta_pub_docx, act_docx)):
        return False, "Acceptance metadata published hashes mismatch"

    # Independent master hash verification
    try:
        persisted_master_path = str(meta.get("master_path") or "")
        if not persisted_master_path:
            persisted_master_path = os.path.join(get_config("REPORTS_DIR", "reports") or "reports", "northstar_terra_master_quality_review.json")
        if not os.path.exists(persisted_master_path):
            return False, "Current persisted master missing"
        hh = hashlib.sha256()
        with open(persisted_master_path, "rb") as _mf:
            for chunk in iter(lambda: _mf.read(1024 * 1024), b""):
                hh.update(chunk)
        cur_master_sha = hh.hexdigest()
        res_master_sha = str(result.get("source_master_sha256") or "")
        meta_master_sha = str(meta.get("master_sha256") or "")
        if not (cur_master_sha and res_master_sha and meta_master_sha and _const_eq(cur_master_sha, res_master_sha) and _const_eq(cur_master_sha, meta_master_sha)):
            return False, "Master hash mismatch"
    except Exception as e:
        return False, f"Master hash verification failed: {e}"

    # Independent template provenance verification
    try:
        tpl_ver_meta = str(meta.get("template_version") or "")
        tpl_sha_meta = str(meta.get("template_sha256") or "")
        if callable(get_tabletop_template_lineage):
            _tpl_path_sys, tpl_ver_sys, tpl_sha_sys = get_tabletop_template_lineage()
            tpl_ver_sys = str(tpl_ver_sys or "")
            tpl_sha_sys = str(tpl_sha_sys or "")
            if not (tpl_ver_meta and tpl_sha_meta and tpl_ver_sys and tpl_sha_sys and _const_eq(tpl_ver_meta, tpl_ver_sys) and _const_eq(tpl_sha_meta, tpl_sha_sys)):
                return False, "Template provenance mismatch"
        else:
            return False, "Template provenance unavailable"
    except Exception as e:
        return False, f"Template provenance verification failed: {e}"

    return True, None


def build_tabletop_export_view(
    export_state: str,
    export_result: dict,
    expected_fingerprint: Optional[str] = None,
) -> TabletopExportView:
    """
    Build a TabletopExportView by strictly verifying success or documenting a safe reason.
    This is presentation-only; no state transitions are made here.
    """
    state = str(export_state or "").strip()
    res = export_result or {}
    view = TabletopExportView(
        export_state=state,
        export_result=res,
        reused_existing_pack=bool(res.get("reused_existing_pack", False)),
        _participant_path=res.get("participant_pptx_path"),
        _facilitator_path=res.get("facilitator_guide_path"),
        _acceptance_meta_path=res.get("acceptance_metadata_path"),
        _reported_pptx_sha=res.get("participant_pptx_sha256"),
        _reported_docx_sha=res.get("facilitator_guide_sha256"),
    )

    # Fill safe filenames
    try:
        view.participant_basename = os.path.basename(view._participant_path or "") if view._participant_path else ""
        view.facilitator_basename = os.path.basename(view._facilitator_path or "") if view._facilitator_path else ""
    except Exception:
        view.participant_basename = ""
        view.facilitator_basename = ""

    # Timestamp from metadata (safe)
    try:
        meta = _load_acceptance_meta(view._acceptance_meta_path) if view._acceptance_meta_path else None
        if isinstance(meta, dict):
            view.export_timestamp_utc = str(meta.get("validation_timestamp_utc", "") or "")
    except Exception:
        view.export_timestamp_utc = ""

    # Verify only when state claims success
    if state == "succeeded":
        ok, err = _verify_success_contract(res, expected_fingerprint)
        view.verified = bool(ok)
        view.verification_error = err
    else:
        view.verified = False
        view.verification_error = None

    return view


def render_tabletop_export_status(st_api, view: TabletopExportView) -> bool:
    """
    Render the export status using a provided st-like API surface.
    Returns True if a Retry action was invoked (only relevant in failed/unverified states).
    """
    # Generating
    if view.export_state == "generating":
        st_api.info("Generating exercise pack...")
        return False

    # Failed
    if view.export_state == "failed":
        safe_stage = str(view.export_result.get("failed_stage") or "unknown")
        safe_msg = str(view.export_result.get("safe_error_message") or "")
        st_api.error(f"Exercise-pack export failed at: {safe_stage}")
        if safe_msg:
            st_api.caption("The validated tabletop plan has been retained. Correct the export issue and retry.")
        # Retry in failed only
        if st_api.button("Retry Export"):
            return True
        return False

    # Succeeded (verified)
    if view.export_state == "succeeded" and view.verified:
        st_api.success("Exercise pack ready")
        if view.participant_basename:
            st_api.markdown(f"- Participant PowerPoint: {view.participant_basename}")
        if view.facilitator_basename:
            st_api.markdown(f"- Facilitator Guide: {view.facilitator_basename}")
        if view.export_timestamp_utc:
            st_api.markdown(f"- Export timestamp (UTC): {view.export_timestamp_utc}")
        st_api.markdown(f"- Accepted pack: {'reused' if view.reused_existing_pack else 'generated'}")
        # Participant download (public)
        try:
            with open(view._participant_path, "rb") as pf:
                st_api.download_button(
                    "📊 Download Participant PowerPoint (.pptx)",
                    data=pf.read(),
                    file_name=view.participant_basename,
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )
        except Exception:
            st_api.error("Participant PowerPoint download unavailable.")
        # Facilitator download is rendered in a clearly private section by the caller (page).
        return False

    # Succeeded but failed verification (show safe message, allow retry)
    if view.export_state == "succeeded" and not view.verified:
        st_api.error("Acceptance verification failed; downloads unavailable.")
        # Offer retry action
        if st_api.button("Retry Export"):
            return True
        return False

    # Idle/unexpected — no downloads and no messages
    return False