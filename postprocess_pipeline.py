from __future__ import annotations
from typing import Tuple, Dict, Any, List
import json
import os
from datetime import datetime
from pydantic import BaseModel  # noqa: F401 (placeholder for potential future use)
from config import get_config, ConfigKey
from evidence_extraction import extract_evidence_once, AssessmentEvidence, TranscriptInsight, CombinedExtraction
from section_improvers.shared_rules import ReportImprovementRules, ReviewerChange
from section_improvers import improve_all_sections
from consistency_validator import validate_all, ConsistencyIssue
from services.report_improvement.evidence_adjudicator import (
    adjudicate_evidence, EvidenceAdjudicationResult, save_adjudication_log
)

def _to_dict(obj: Any) -> Dict[str, Any]:
    try:
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "dict"):
            return obj.dict()
    except Exception:
        pass
    return obj if isinstance(obj, dict) else {}

def _log_bundle(customer: str, bundle: Dict[str, Any]) -> None:
    try:
        base_dir = get_config(ConfigKey.LOG_STORAGE_DIR, os.path.join(os.path.dirname(__file__), "exports", "logs"))
        cust = (customer or "Client").replace(" ", "_")
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        out_dir = os.path.join(base_dir, cust, ts)
        os.makedirs(out_dir, exist_ok=True)
        for name, payload in bundle.items():
            path = os.path.join(out_dir, f"{name}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        # Fail closed on logging
        pass

def run_postprocessing(
    assessment_profile: Dict[str, Any],
    meeting_transcript: str,
    meeting_summary: str,
    raw_report_obj: Any
) -> Tuple[Any, Dict[str, Any]]:
    """
    Orchestrate evidence extraction, section improvement, consistency validation.
    Returns (improved_report_obj, logs_dict). On failure, returns (raw_report_obj, logs_dict).
    """
    # Diagnostics: initialise run_id and capture effective runtime configuration (env‑gated)
    try:
        from services.report_improvement.lineage import is_diagnostics_enabled, ensure_run_id, write_runtime_configuration  # type: ignore
        if is_diagnostics_enabled():
            rid = ensure_run_id()
            try:
                # Optional feature toggles (safe fallbacks)
                from config import is_specialist_enabled as _is_sgen  # type: ignore
            except Exception:
                def _is_sgen():  # type: ignore
                    return True
            try:
                from config import is_specialist_strict_lineage as _is_strict  # type: ignore
            except Exception:
                def _is_strict():  # type: ignore
                    return False
            cfg = {
                "specialist_generators_enabled": bool(_is_sgen()),
                "remediation_enabled": str(get_config('REMEDIATION_ENABLED', 'true')).strip().lower() in ('1', 'true', 'yes', 'on'),
                "strict_lineage": bool(_is_strict()),
                "template_version": get_config(ConfigKey.APP_VERSION, "unknown"),
                "template_path": None,
                "export_mode": None,
                "compatibility_mode": None,
                "model_deployment": get_config(ConfigKey.AZURE_DEPLOYMENT, ""),
                "prompt_versions": {},
                "generator_versions": {},
            }
            write_runtime_configuration(cfg)
    except Exception:
        pass
    # 1) Evidence extraction (single pass over transcript)
    extraction = extract_evidence_once(meeting_transcript or "", meeting_summary or "", assessment_profile or {})
    if extraction is None:
        # Return original unchanged
        return raw_report_obj, {"error": "evidence_extraction_failed"}

    evidence: AssessmentEvidence = extraction.evidence
    insights: List[TranscriptInsight] = extraction.insights or []

    # 1b) Evidence adjudication (authoritative source of truth)
    adjudication: EvidenceAdjudicationResult = adjudicate_evidence(evidence, insights, meeting_summary or "")
    try:
        save_adjudication_log(evidence.customer_name or assessment_profile.get("customer_name") or "Client", adjudication)
    except Exception:
        pass

    # 2) Run section improvers with default global rules (adjudication-first)
    rules = ReportImprovementRules.default()
    raw_report_dict = _to_dict(raw_report_obj)
    improved_dict, reviewer_changes = improve_all_sections(raw_report_dict, evidence, insights, adjudication, rules)

    # 2b) Deterministic Evidence Enforcement (fail closed, bounded retries)
    from services.report_improvement.orchestrator import enforce_report
    enforced_dict, report_validation = enforce_report(raw_report_dict, improved_dict, adjudication)
    # Diagnostics: per-section stored-stage lineage (env-gated)
    try:
        # SectionLineageTrace utilities imported lazily to avoid hard dependency at runtime
        from services.report_improvement.lineage import SectionLineageTrace, record_stage_hash, write_lineage_trace  # type: ignore
        if is_diagnostics_enabled():
            rid = ensure_run_id()
            def _safe_get(d, k):
                try:
                    return d.get(k)
                except Exception:
                    return None
            for _sec in ["executive_summary", "security_rating", "threat_scenarios", "compliance_alignment", "cost_of_inaction", "domain_assessments"]:
                try:
                    val = _safe_get(enforced_dict, _sec)
                    tr = SectionLineageTrace(
                        run_id=rid,
                        section_name=_sec,
                        stored_field_path=f"report.{_sec}",
                        export_context_key=_sec,
                    )
                    record_stage_hash(
                        tr,
                        "stored",
                        val,
                        validation_status=str(getattr(report_validation, "status", "")),
                    )
                    write_lineage_trace(tr)
                except Exception:
                    pass
    except Exception:
        pass

    # 3) Cross-Section Consistency validation (after deterministic enforcement)
    issues = validate_all(enforced_dict, evidence, insights)

    # 4) Choose enforced or fallback (VALIDATE_BEFORE_REPLACE semantics)
    improved_obj = raw_report_obj
    try:
        from prompts import MaturityReport
        # Attempt to validate via Pydantic; fallback to original on failure
        improved_obj = MaturityReport(**enforced_dict)
    except Exception:
        improved_obj = raw_report_obj

    # 5) Publication readiness gate (authoritative)
    publication_allowed = bool(getattr(report_validation, "automatic_publication_allowed", False))
    human_review_required = bool(getattr(report_validation, "human_review_required", True))
    status_str = str(getattr(report_validation, "status", "") or "").lower()
    # Accept enum string "ValidationStatus.PASS" or raw "pass"
    final_export_allowed = publication_allowed and (not human_review_required) and (status_str.endswith("pass"))
    review_export_required = (not final_export_allowed)
    
    # 6) Logging bundle
    logs = {
        "AssessmentEvidence": _to_dict(evidence),
        "TranscriptInsights": [_to_dict(i) for i in insights],
        "AdjudicationResult": adjudication.model_dump() if hasattr(adjudication, "model_dump") else _to_dict(adjudication),
        "EvidenceEnforcement": report_validation.model_dump() if hasattr(report_validation, "model_dump") else _to_dict(report_validation),
        "ReviewerChanges": [rc.model_dump() if hasattr(rc, "model_dump") else _to_dict(rc) for rc in reviewer_changes],
        "ConsistencyIssues": [ci.model_dump() if hasattr(ci, "model_dump") else _to_dict(ci) for ci in issues],
        "Meta": {
            "customer_name": evidence.customer_name or assessment_profile.get("customer_name") or "Client",
            "timestamp_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "version": get_config(ConfigKey.APP_VERSION, "unknown"),
            "publication_allowed": final_export_allowed,
            "human_review_required": human_review_required
        }
    }
    # Populate remediation manifest with run metadata and hashes (conservative; no transcripts)
    try:
        import hashlib as _hashlib
        from services.report_improvement.lineage import ensure_run_id  # type: ignore
        _orig_hash = _hashlib.sha256(json.dumps(raw_report_dict, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        _rem_hash = _hashlib.sha256(json.dumps(enforced_dict, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        _run_id = ensure_run_id()
    except Exception:
        _orig_hash = ""
        _rem_hash = ""
        _run_id = ""
    logs["RemediationManifest"] = {
        "run_id": _run_id,
        "original_report_hash": _orig_hash,
        "remediated_report_hash": _rem_hash,
        "automatic_fixes": [],
        "evidence_grounded_rewrites": [],
        "section_rebuilds": [],
        "unresolved_consultant_decisions": [],
        "final_validation_status": str(getattr(report_validation, "status", "")),
        "final_export_allowed": bool(final_export_allowed)
    }
    # Persist a dedicated remediation manifest alongside logs (best-effort, non-fatal)
    try:
        from services.report_improvement.auto_remediation.audit import write_remediation_manifest  # type: ignore
        _rep_name = logs.get("Meta", {}).get("customer_name") or assessment_profile.get("customer_name") or "Client"
        write_remediation_manifest(_rep_name, logs.get("RemediationManifest", {}))
    except Exception:
        pass
    # Append unresolved template inputs as structured consultant decisions (no transcripts)
    try:
        from services.report_improvement.auto_remediation.document_fixes import TemplateResolutionContext, build_template_resolution  # type: ignore
        trc = TemplateResolutionContext(
            customer_name=evidence.customer_name or assessment_profile.get("customer_name") or "Client",
            report_month_year=None,
            consultant_name=None,
            account_manager_name=None,
            approver_name=None,
            customer_logo_path=None,
            planet_branding_enabled=True,
            revision_number=None,
        )
        _bundle = build_template_resolution(trc)
        _mi = list((_bundle or {}).get("missing_inputs") or [])
        try:
            logs["RemediationManifest"]["unresolved_consultant_decisions"].extend(_mi)
        except Exception:
            logs["RemediationManifest"]["unresolved_consultant_decisions"] = _mi
    except Exception:
        pass
    _log_bundle(logs["Meta"]["customer_name"], logs)
    
    # Structured result (keeps legacy return shape positionally compatible if ignored)
    try:
        from pydantic import BaseModel  # type: ignore
        class PostprocessingResult(BaseModel):  # lightweight inline to avoid module cycles
            report: Any
            validation: Any
            final_export_allowed: bool = False
            review_export_required: bool = True
            review_reasons: List[str] = []
    except Exception:  # pragma: no cover
        class PostprocessingResult:  # type: ignore
            def __init__(self, report, validation, final_export_allowed=False, review_export_required=True, review_reasons=None):
                self.report = report
                self.validation = validation
                self.final_export_allowed = final_export_allowed
                self.review_export_required = review_export_required
                self.review_reasons = review_reasons or []
    
    reasons = []
    if not final_export_allowed:
        reasons.append("Validation status not PASS or human review required")
    ppres = PostprocessingResult(
        report=improved_obj,
        validation=report_validation,
        final_export_allowed=final_export_allowed,
        review_export_required=review_export_required,
        review_reasons=reasons
    )
    return ppres, logs
