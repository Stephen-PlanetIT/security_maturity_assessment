from __future__ import annotations

from typing import Any, Optional, Tuple

try:
    from pydantic import BaseModel  # type: ignore
except Exception:  # pragma: no cover
    BaseModel = object  # type: ignore

# Lineage utilities (run-id propagation)
try:
    from services.report_improvement.lineage import ensure_run_id  # type: ignore
except Exception:  # pragma: no cover
    def ensure_run_id() -> str:
        return "unknown_run"

# Evidence extraction and adjudication
try:
    from evidence_extraction import extract_evidence_once, AssessmentEvidence, TranscriptInsight  # type: ignore
    from services.report_improvement.evidence_adjudicator import (  # type: ignore
        adjudicate_evidence,
        EvidenceAdjudicationResult,
        save_adjudication_log,
    )
except Exception:  # pragma: no cover
    extract_evidence_once = None  # type: ignore
    adjudicate_evidence = None  # type: ignore
    class EvidenceAdjudicationResult:  # type: ignore
        pass
    def save_adjudication_log(customer: str, result: Any) -> Optional[str]:  # type: ignore
        return None

# Orchestrator
try:
    from services.report_improvement.orchestrator import enforce_report  # type: ignore
except Exception:  # pragma: no cover
    enforce_report = None  # type: ignore

# Report model
try:
    from prompts import MaturityReport  # type: ignore
except Exception:  # pragma: no cover
    MaturityReport = None  # type: ignore


def _to_dict(obj: Any) -> dict:
    """
    Best-effort conversion of a Pydantic/dict-like report object into a plain dict.
    """
    try:
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "dict"):
            return obj.dict()
    except Exception:
        pass
    try:
        return dict(obj)
    except Exception:
        return {}


class ReportImprovementIntegrationResult(BaseModel):  # type: ignore
    raw_report: Any
    improved_report: Any | None = None
    validation_result: Any | None = None
    adjudication: Any | None = None
    orchestration_executed: bool = False
    publication_allowed: bool = False
    review_required: bool = True
    run_id: str
    failure_stage: str | None = None
    failure_reason: str | None = None


def improve_generated_maturity_report(
    *,
    raw_report: Any,
    client_inputs: dict,
    transcript: str | None,
    meeting_summary: str | None,
    run_id: str | None,
) -> ReportImprovementIntegrationResult:
    """
    Improve an already-generated maturity report using evidence-led enforcement:
      1) Preserve the raw report (Pydantic object)
      2) Extract assessment evidence and insights (best-effort)
      3) Adjudicate evidence into EvidenceAdjudicationResult
      4) Invoke orchestrator.enforce_report exactly once
      5) Reconstruct a MaturityReport for export
      6) Return validation and publication flags (fail-closed on errors)
    """
    rid = run_id or ensure_run_id()
    result = ReportImprovementIntegrationResult(
        raw_report=raw_report,
        improved_report=None,
        validation_result=None,
        orchestration_executed=False,
        publication_allowed=False,
        review_required=True,
        run_id=rid,
        failure_stage=None,
        failure_reason=None,
    )

    # Defensive copies of inputs
    ci = dict(client_inputs or {})
    tx = str(transcript or "")
    summ = str(meeting_summary or "")

    # Structured source authority metadata (portable examples detection)
    from pathlib import Path as _Path
    def _is_examples_path(p: str) -> bool:
        try:
            return "examples" in _Path(str(p)).parts
        except Exception:
            return False
    try:
        sample_flag = bool(ci.get("sample_demo_mode", False))
        profile_path = str(ci.get("_profile_path") or ci.get("profile_path") or ci.get("assessment_profile_path") or "")
        ci["__source_authority"] = {
            "source_id": profile_path or "unknown_profile",
            "source_type": "sample_fixture" if _is_examples_path(profile_path) else "customer_profile",
            "authoritative": bool(sample_flag) and _is_examples_path(profile_path),
            "authority_reason": ("Fixture used outside explicit demo mode" if (not sample_flag and _is_examples_path(profile_path)) else "Customer profile in current session"),
            "sample_demo_mode": bool(sample_flag),
        }
        # Fixture quarantine flag for downstream prompt advisory
        if (not sample_flag) and _is_examples_path(profile_path):
            ci["__sample_non_authoritative"] = True
        # Persist computed authoritativeness (generic)
        ci["__SAMPLE_PROFILE_AUTHORITATIVE"] = bool(ci["__source_authority"]["authoritative"])
        # Propagate parent normalised evidence path if available for adjudication precedence (portable)
        parent_norm_path = str(ci.get("_parent_normalised_path") or "")
        if parent_norm_path:
            ci["__baseline_normalised_path"] = parent_norm_path
    except Exception as _authority_exc:
        # Diagnostic: do not fail silently
        ci["__authority_error"] = repr(_authority_exc)

    # Step 1: Convert raw report to dict snapshots
    try:
        orig_dict = _to_dict(raw_report)
        imp_dict = _to_dict(raw_report)
    except Exception as exc:
        result.failure_stage = "to_dict"
        result.failure_reason = repr(exc)
        return result

    # Step 2–3: Build adjudication (best-effort)
    try:
        if extract_evidence_once is not None and (tx or summ):
            comb = extract_evidence_once(transcript=tx, summary=summ, assessment_profile=ci)  # type: ignore
        else:
            comb = None
        if adjudicate_evidence is not None:
            # Pass baseline normalised evidence when available
            baseline_payload = None
            try:
                bl_path = str(ci.get("__baseline_normalised_path") or "")
                if bl_path:
                    import json as _json
                    with open(bl_path, "r", encoding="utf-8") as _bf:
                        baseline_payload = _json.load(_bf)
            except Exception as _baseline_exc:
                ci["__baseline_error"] = repr(_baseline_exc)
            # Prefer extracted evidence; fallback to baseline-only adjudication with empty evidence/insights
            if comb is not None:
                adj = adjudicate_evidence(comb.evidence, comb.insights, summ, baseline=baseline_payload)  # type: ignore
            else:
                try:
                    empty_ev = AssessmentEvidence()  # type: ignore
                except Exception:
                    empty_ev = None  # type: ignore
                empty_ins: list[TranscriptInsight] = []  # type: ignore
                adj = adjudicate_evidence(empty_ev, empty_ins, summ, baseline=baseline_payload)  # type: ignore
            # Persist adjudication log best-effort
            try:
                save_adjudication_log(str(ci.get("customer_name", "Client")), adj)  # type: ignore
            except Exception:
                pass
            # Expose adjudication payload to caller to avoid hard dependency on log discovery
            try:
                result.adjudication = getattr(adj, "model_dump", lambda: adj)()
            except Exception:
                result.adjudication = adj  # type: ignore
        else:
            # Fail-closed when adjudication is unavailable (no silent fallback)
            result.failure_stage = "evidence_adjudication"
            result.failure_reason = "Evidence adjudication was not available"
            result.orchestration_executed = False
            result.publication_allowed = False
            result.review_required = True
            return result
    except Exception as exc:
        # Fail-closed and do not proceed without adjudication
        result.failure_stage = "evidence_adjudication"
        result.failure_reason = repr(exc)
        result.orchestration_executed = False
        result.publication_allowed = False
        result.review_required = True
        return result

    # Step 4: Invoke orchestrator once
    try:
        if enforce_report is None:
            result.failure_stage = "orchestrator_import"
            result.failure_reason = "enforce_report not importable"
            return result
        final_report_dict, validation = enforce_report(orig_dict, imp_dict, adj)  # type: ignore
        result.validation_result = validation
        result.orchestration_executed = True
        pub_allowed = bool(getattr(validation, "automatic_publication_allowed", False))
        result.publication_allowed = pub_allowed
        result.review_required = not pub_allowed
    except Exception as exc:
        result.failure_stage = "enforce_report"
        result.failure_reason = repr(exc)
        return result

    # Step 5: Reconstruct improved MaturityReport (best-effort)
    # Checkpoint B2: Reconcile authoritative specialist outputs into declared model fields
    from services.report_improvement.authority_map import reconcile_maturity_report_dict
    reconciled_report_dict = reconcile_maturity_report_dict(final_report_dict, raw_report)
    improved_model: Any = None
    try:
        if MaturityReport is not None:
            if hasattr(MaturityReport, "model_validate"):
                improved_model = MaturityReport.model_validate(reconciled_report_dict)  # type: ignore
            else:
                improved_model = MaturityReport(**reconciled_report_dict)  # type: ignore
        else:
            improved_model = raw_report
            try:
                for k, v in (reconciled_report_dict or {}).items():
                    try:
                        setattr(improved_model, k, v)
                    except Exception:
                        try:
                            improved_model[k] = v  # type: ignore
                        except Exception:
                            pass
            except Exception:
                pass
        # Mark specialist content validated to protect against subsequent regeneration
        try:
            setattr(improved_model, "_specialist_content_validated", True)
        except Exception:
            pass
        result.improved_report = improved_model
    except Exception as exc:
        # Fallback: mutate the original report object in-place if reconstruction fails
        result.failure_stage = "reconstruct_model"
        result.failure_reason = repr(exc)
        try:
            improved_model = raw_report
            for k, v in (reconciled_report_dict or final_report_dict or {}).items():
                try:
                    setattr(improved_model, k, v)
                except Exception:
                    try:
                        improved_model[k] = v  # type: ignore
                    except Exception:
                        pass
            try:
                setattr(improved_model, "_specialist_content_validated", True)
            except Exception:
                pass
            result.improved_report = improved_model
        except Exception:
            result.improved_report = None

    return result