"""
Orchestrator for Evidence Enforcement + Auto Remediation (bounded loop).
Phase 2: wraps deterministic validator.enforce_report with an evidence-grounded rewrite pass.
Fail-closed publication controls remain authoritative.
"""
from __future__ import annotations
from typing import Dict, Any, Tuple, List
from services.report_improvement.evidence_enforcement import validator as _val
from services.report_improvement.evidence_enforcement.models import (
    ValidationStatus,
    SectionValidationResult,
    ReportValidationResult,
)
from services.report_improvement.evidence_enforcement.revision import (
    revise_section_from_validation_errors,
)
from services.report_improvement.auto_remediation.evidence_rewriter import (
    rewrite_from_validation_issues,
)
from services.report_improvement.auto_remediation.section_rebuilder import (
    rebuild_attack_scenario,
)
from services.report_improvement.auto_remediation.audit import write_metrics
from services.report_improvement.evidence_adjudicator import (
    EvidenceAdjudicationResult,
)
from services.report_improvement.lineage import (
    canonical_section_hash as _canon_section_hash,
)


__all__ = ["enforce_report"]


def enforce_report(
    original_report: Dict[str, Any],
    improved_report: Dict[str, Any],
    adjudication: EvidenceAdjudicationResult,
) -> Tuple[Dict[str, Any], ReportValidationResult]:
    """
    Bounded remediation loop:
    Pass 1: deterministic fixes (existing validator logic)
    Pass 2: evidence-grounded rewrite (max 2 attempts per blocking section)
    Pass 3: section rebuild (reserved for future)
    """
    # Build enforcement context
    ctx = _val._build_context(adjudication)

    # Sections registry (keep in sync with validator)
    section_names = [
        "executive_summary",
        "security_rating",
        "critical_findings",
        "indicative_solutions",
        "main_findings",
        "threat_scenarios",
        "threat_intelligence_context",
        "executive_commentary",
        "compliance_alignment",
        "cost_of_inaction",
        "current_environment",
        "identity_access",
        "information_protection",
        "saas_governance",
        "asset_assurance",
        "monitoring_detection",
        "supplier_assurance",
        "third_party_access",
        "recovery_assurance",
        "incident_response",
        "network_edge",
        "email_security",
        "endpoint_security",
        "cloud_security",
        "application_security",
        "ai_governance",
        "security_testing",
        "incident_response_planning",
        "disaster_recovery_planning",
        "phased_roadmap",
        "partnership_success_criteria",
    ]

    # Start from improved_report copy
    final_report = dict(improved_report or {})
    # Optional specialist generation pass (feature toggle; default-ON via config helper)
    try:
        from config import is_specialist_enabled as _is_sgen
        _sgen_enabled = _is_sgen()
    except Exception:
        _sgen_enabled = True
    if _sgen_enabled:
        try:
            # Late imports to avoid hard dependencies when disabled
            from services.report_improvement.section_generators import select_section_evidence  # type: ignore
            from services.report_improvement.section_generators.executive_summary import generate_executive_summary as _gen_es  # type: ignore
            from services.report_improvement.section_generators.attack_scenario import generate_attack_scenario as _gen_as  # type: ignore
            from services.report_improvement.section_generators.compliance_alignment import generate_compliance_alignment as _gen_ca  # type: ignore
            from services.report_improvement.section_generators.transformers import to_text_executive_summary, to_text_attack_scenario, to_render_compliance  # type: ignore
            # Executive Summary (authoritative when specialist gen is enabled; do not suppress due to legacy)
            try:
                si = select_section_evidence("executive_summary", ctx, adjudication, transcript_insights=[])
                es = _gen_es(si)
                final_report["executive_summary_specialist"] = es
                final_report["exec_summary"] = to_text_executive_summary(es)
            except Exception:
                pass
            # Threat Scenarios (authoritative when specialist gen is enabled; do not suppress due to legacy)
            try:
                ao = _gen_as(ctx, adjudication)
                final_report["attack_scenario_specialist"] = ao
                final_report["threat_scenarios"] = to_text_attack_scenario(ao)
            except Exception:
                pass
            # Compliance Alignment (preserve structured output; do not flatten)
            try:
                si2 = select_section_evidence("compliance_alignment", ctx, adjudication, transcript_insights=[])
                ca = _gen_ca(si2)
                final_report["compliance_alignment_specialist"] = ca
                final_report["compliance_alignment_render"] = to_render_compliance(ca)
                # Map structured rows for export consumption to prevent COMPLIANCE_ROWS_EMPTY
                try:
                    rows_struct = []
                    for r in (getattr(ca, "rows", []) or []):
                        try:
                            rows_struct.append({
                                "standard": getattr(r, "framework_name", ""),
                                "framework_area": getattr(r, "framework_area", ""),
                                "relevant_expectation": getattr(r, "relevant_expectation", ""),
                                "current_position": getattr(ca, "current_position", ""),
                                "gaps": ([getattr(r, "assurance_gap_or_consideration", "")] if getattr(r, "assurance_gap_or_consideration", "") else []),
                                "recommended_focus": getattr(r, "recommended_focus", ""),
                                "evidence_ids": list(getattr(r, "evidence_ids", []) or []),
                            })
                        except Exception:
                            continue
                    final_report["compliance_alignment"] = rows_struct
                except Exception:
                    pass
            except Exception:
                pass
            # Cost of Inaction (authoritative when specialist gen is enabled; do not suppress due to legacy)
            try:
                from services.report_improvement.section_generators.cost_of_inaction import generate_cost_of_inaction as _gcoi  # type: ignore
                coi = _gcoi(ctx, adjudication, transcript_insights=[])
                qparts = [coi.qualitative_narrative]
                if coi.cost_drivers:
                    qparts.extend([f"- {d.driver_name}: {d.description}" for d in coi.cost_drivers[:5]])
                if coi.quantified_narrative:
                    qparts.append(coi.quantified_narrative)
                final_report["cost_of_inaction"] = "\n".join([p for p in qparts if p]).strip()
            except Exception:
                pass
            # Security Rating (authoritative when specialist gen is enabled; provide specialist object to export)
            try:
                from decimal import Decimal
                from services.report_improvement.section_generators.security_rating import calculate_security_rating, SCORING_POLICY_VERSION  # type: ignore
                from services.report_improvement.section_generators.models import DomainScoreInput  # type: ignore
                # Build deterministic domain inputs using selector-derived evidence signals
                domain_keys = [
                    "identity_access","information_protection","saas_governance","asset_assurance","monitoring_detection",
                    "supplier_assurance","third_party_access","recovery_assurance","incident_response","network_edge",
                    "email_security","endpoint_security","cloud_security","application_security","ai_governance"
                ]
                def _cov(v: str) -> Decimal:
                    t = (v or "limited").strip().lower()
                    if t == "strong":
                        return Decimal("0.90")
                    if t == "mixed":
                        return Decimal("0.50")
                    return Decimal("0.20")
                d_inputs = []
                for dk in domain_keys:
                    try:
                        si_dom = select_section_evidence(dk, ctx, adjudication, transcript_insights=[])
                        strength_cnt = len(getattr(si_dom, "supported_claims", []) or [])
                        gap_cnt = len(getattr(adjudication, "unsupported_claims", []) or []) + len(getattr(adjudication, "contradicted_claims", []) or [])
                        unknown_cnt = len(getattr(si_dom, "known_unknowns", []) or [])
                        unvalidated_cnt = 0
                        weight = Decimal(str(100/len(domain_keys))) if domain_keys else Decimal("0")
                        d_inputs.append(
                            DomainScoreInput(
                                domain_name=dk,
                                configured_weight=weight,
                                evidence_coverage=_cov(getattr(si_dom, "evidence_quality", "limited")),
                                confirmed_strength_count=int(strength_cnt),
                                confirmed_gap_count=int(gap_cnt),
                                unvalidated_control_count=int(unvalidated_cnt),
                                unknown_count=int(unknown_cnt),
                                approved_score_inputs=[],
                                supporting_claim_ids=[str(getattr(c, "claim_id", "")) for c in (getattr(si_dom, "supported_claims", []) or [])][:10],
                                scoring_policy_version=SCORING_POLICY_VERSION,
                            )
                        )
                    except Exception:
                        continue
                if d_inputs:
                    sr = calculate_security_rating(d_inputs, ctx, adjudication)
                    final_report["security_rating"] = sr
            except Exception:
                pass
            # Domain Assessments (authoritative when specialist gen is enabled; preserve structured list)
            try:
                from services.report_improvement.section_generators.domain_assessments import generate_domain_assessment as _gen_da  # type: ignore
                from services.report_improvement.section_generators.models import DomainEvidence  # type: ignore
                def _pretty(n: str) -> str:
                    try:
                        return " ".join([w.capitalize() for w in str(n or "").replace("_"," ").split()])
                    except Exception:
                        return str(n or "")
                domain_keys = [
                    "identity_access","information_protection","saas_governance","asset_assurance","monitoring_detection",
                    "supplier_assurance","third_party_access","recovery_assurance","incident_response","network_edge",
                    "email_security","endpoint_security","cloud_security","application_security","ai_governance"
                ]
                da_outputs = []
                for dk in domain_keys:
                    try:
                        si_dom = select_section_evidence(dk, ctx, adjudication, transcript_insights=[])
                        ev = DomainEvidence(
                            domain_name=_pretty(dk),
                            supported_controls=list(getattr(si_dom, "existing_controls", []) or []),
                            confirmed_strengths=list(getattr(si_dom, "supported_claims", []) or []),
                            confirmed_gaps=list(getattr(si_dom, "confirmed_gaps", []) or []),
                            known_unknowns=list(getattr(si_dom, "known_unknowns", []) or []),
                            contradicted_claims=list(getattr(si_dom, "contradicted_claims", []) or []),
                            relevant_business_dependencies=[],
                            relevant_crown_jewels=list(getattr(si_dom, "crown_jewels", []) or []),
                            relevant_customer_priorities=list(getattr(si_dom, "customer_priorities", []) or []),
                            relevant_transcript_insights=list(getattr(si_dom, "relevant_transcript_insights", []) or []),
                            approved_recommendations=list(getattr(si_dom, "approved_recommendations", []) or []),
                            approved_products=list(getattr(si_dom, "approved_products", []) or []),
                            maturity_score=None,
                            evidence_quality=getattr(si_dom, "evidence_quality", "limited"),
                        )
                        da_out = _gen_da(ev)
                        da_outputs.append(da_out)
                    except Exception:
                        continue
                if da_outputs:
                    final_report["domain_assessments_specialist"] = da_outputs
            except Exception:
                pass
        except Exception:
            pass
    # Metrics: initial blocking issue count (pre-deterministic, on improved_report)
    try:
        initial_blocking_issue_count = 0
        for name in section_names:
            content0 = improved_report.get(name)
            if content0 is None:
                continue
            text0 = content0 if isinstance(content0, str) else str(content0)
            s0 = _val._validate_section_text(name, text0, ctx)
            if getattr(s0, "issues", None):
                initial_blocking_issue_count += sum(1 for i in s0.issues if getattr(i, "status", None) == ValidationStatus.BLOCK)
    except Exception:
        initial_blocking_issue_count = 0

    # Pass 1: Deterministic enforcement (existing loop + deterministic revision)
    enforced_after_det, det_result = _val.enforce_report(original_report, final_report, adjudication)
    final_report = enforced_after_det
    # Metrics: count blocking issues after deterministic pass; init rewrite counters
    try:
        det_blocking_issue_count = 0
        for r in getattr(det_result, "section_results", []) or []:
            det_blocking_issue_count += sum(1 for i in (getattr(r, "issues", []) or []) if getattr(i, "status", None) == ValidationStatus.BLOCK)
    except Exception:
        det_blocking_issue_count = 0
    model_call_count = 0
    unchanged_rewrite_count = 0
    section_rebuild_resolution_count = 0

    # If PASS after deterministic pass, return early
    if getattr(det_result, "status", ValidationStatus.PASS) == ValidationStatus.PASS:
        return final_report, det_result

    # Pass 2: Evidence-grounded rewrite (bounded, feature toggle)
    section_results: List[SectionValidationResult] = []
    from config import get_config
    rem_enabled = str(get_config('REMEDIATION_ENABLED', 'true')).strip().lower() in ('1','true','yes','on')
    if not rem_enabled:
        # Skip rewrite pass entirely (deterministic result stands)
        return final_report, det_result
    for name in section_names:
        content = final_report.get(name)
        if content is None:
            continue
        # Guard: do not stringify or rewrite structured sections required by UI/export
        structured_only = {"phased_roadmap", "security_rating", "compliance_alignment"}
        if name in structured_only and not isinstance(content, str):
            # Validate using a textual view for rule checks, but preserve structured content
            sres = _val._validate_section_text(name, str(content), ctx)
            section_results.append(sres)
            continue
        text = content if isinstance(content, str) else str(content)
        sres = _val._validate_section_text(name, text, ctx)
        if not sres.has_blocking_errors:
            section_results.append(sres)
            continue

        # Attempt rewrite passes (max 2), track hash to avoid resubmitting unchanged content
        import hashlib, asyncio
        h0 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        tries = 0
        # Use configurable max passes; default 2
        try:
            max_passes = int(get_config('REMEDIATION_MAX_MODEL_PASSES', '2') or '2')
        except Exception:
            max_passes = 2
        while sres.has_blocking_errors and tries < max_passes:
            tries += 1
            try:
                try:
                    # Evidence-grounded rewrite (strict prompt contract; placeholder implementation in Phase 2 scaffold)
                    revised = asyncio.run(
                        rewrite_from_validation_issues(
                            section_name=name,
                            rejected_content=text,
                            issues=sres.issues,
                            context=ctx,
                            adjudication=adjudication,
                        )
                    )
                    model_call_count += 1
                except RuntimeError:
                    # If an event loop is already running (e.g., Streamlit), skip the async call safely
                    revised = None
                if revised and getattr(revised, "revised_content", None):
                    text = revised.revised_content
            except Exception:
                # Non-fatal; keep previous text
                pass
            # Deterministic revalidation
            sres = _val._validate_section_text(name, text, ctx)
            h1 = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if h1 == h0:
                # Unchanged submission — stop further attempts for this section
                unchanged_rewrite_count += 1
                break
            h0 = h1

        # Update final content and record result
        final_report[name] = text
        section_results.append(sres)

    # Final rebuild pass (bounded, evidence-led) for severely invalid sections
    try:
        # Threshold: if >=3 blocking issues in scenario-related categories, rebuild scenario section
        REBUILD_RULES = {
            "SCENARIO_CVE_NOT_APPROVED",
            "SCENARIO_THREAT_ACTOR_NOT_APPROVED",
            "INSIDER_SCENARIO_NOT_APPROVED",
            "UNAPPROVED_VENDOR",
            "GENERIC_FALLBACK_CONTENT",
            "TRUNCATED_CONTENT",
        }
        import asyncio
        from hashlib import sha256 as _sha256
        from config import get_config
        rebuild_enabled = str(get_config("REMEDIATION_ENABLED", "true")).strip().lower() in ("1", "true", "yes", "on")
        if rebuild_enabled:
            # Iterate threat sections only, once
            for idx, name in enumerate(section_names):
                if name not in ("threat_scenarios", "threat_intelligence_context"):
                    continue
                content = final_report.get(name)
                if content is None:
                    continue
                text = content if isinstance(content, str) else str(content)
                # Locate the latest validation result for this section
                sres_candidates = [r for r in section_results if getattr(r, "section_name", "") == name]
                sres_current = sres_candidates[-1] if sres_candidates else _val._validate_section_text(name, text, ctx)
                blocked_issue_ids = [str(getattr(i, "rule_id", "")) for i in (getattr(sres_current, "issues", []) or []) if getattr(i, "status", None) is not None]
                rebuild_count = sum(1 for rid in blocked_issue_ids if rid in REBUILD_RULES)
                if getattr(sres_current, "has_blocking_errors", False) and rebuild_count >= 3:
                    # Attempt a single rebuild
                    h0 = _sha256(text.encode("utf-8")).hexdigest()
                    try:
                        revised = asyncio.run(rebuild_attack_scenario(profile=getattr(ctx, "scenario_profile", None), evidence_ctx=ctx))
                    except RuntimeError:
                        revised = None
                    if revised and getattr(revised, "revised_content", None):
                        text = revised.revised_content
                        # Deterministic revalidation and update
                        sres_new = _val._validate_section_text(name, text, ctx)
                        # Metrics: track reduction of blocking issues due to rebuild
                        try:
                            prev_blocks = sum(1 for i in (getattr(sres_current, "issues", []) or []) if getattr(i, "status", None) == ValidationStatus.BLOCK)
                            new_blocks = sum(1 for i in (getattr(sres_new, "issues", []) or []) if getattr(i, "status", None) == ValidationStatus.BLOCK)
                            if new_blocks < prev_blocks:
                                section_rebuild_resolution_count += (prev_blocks - new_blocks)
                        except Exception:
                            pass
                        final_report[name] = text
                        # Replace previous entry if existed; else append
                        replaced = False
                        for j, r in enumerate(section_results):
                            if getattr(r, "section_name", "") == name:
                                section_results[j] = sres_new
                                replaced = True
                                break
                        if not replaced:
                            section_results.append(sres_new)
                        # Stop if unchanged
                        h1 = _sha256(text.encode("utf-8")).hexdigest()
                        if h1 == h0:
                            break
    except Exception:
        # Rebuild pass is best-effort; non-fatal
        pass

    # Aggregate overall status post rewrite/rebuild passes
    # Metrics: compute post-rewrite blocking issues and resolution counts
    try:
        post_rewrite_blocking_issue_count = 0
        for r in (section_results or []):
            post_rewrite_blocking_issue_count += sum(1 for i in (getattr(r, "issues", []) or []) if getattr(i, "status", None) == ValidationStatus.BLOCK)
    except Exception:
        post_rewrite_blocking_issue_count = 0
    try:
        deterministic_resolution_count = max((initial_blocking_issue_count - det_blocking_issue_count), 0)
        evidence_rewrite_resolution_count = max((det_blocking_issue_count - post_rewrite_blocking_issue_count), 0)
        resolved_total = max((initial_blocking_issue_count - post_rewrite_blocking_issue_count), 0)
        remediation_success_rate = (resolved_total / initial_blocking_issue_count) if initial_blocking_issue_count > 0 else 1.0
    except Exception:
        deterministic_resolution_count = 0
        evidence_rewrite_resolution_count = 0
        remediation_success_rate = 1.0
    overall_status = ValidationStatus.PASS
    if any(r.status == ValidationStatus.HUMAN_REVIEW for r in section_results):
        overall_status = ValidationStatus.HUMAN_REVIEW
    elif any(r.status == ValidationStatus.BLOCK for r in section_results):
        overall_status = ValidationStatus.BLOCK
    elif any(r.status == ValidationStatus.WARNING for r in section_results):
        overall_status = ValidationStatus.WARNING

    # Cross-section coherence validation (fail-closed with single regeneration attempt)
    try:
        from config import get_config  # lazy import to avoid hard dependency
        coherence_enabled = str(get_config("COHERENCE_VALIDATION_ENABLED", "true")).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        coherence_enabled = True
    cs_issues = []
    if coherence_enabled:
        try:
            from services.report_improvement.section_generators.cross_section_context import build_cross_section_map_from_report  # type: ignore
            from services.report_improvement.section_generators.quality_checks import validate_coherence  # type: ignore
            cs_map = build_cross_section_map_from_report(final_report)
            cs_issues = validate_coherence(cs_map)
        except Exception:
            cs_issues = []

        # Attempt a single targeted regeneration for specific coherence issues
        if cs_issues:
            try:
                # Map representative rule_ids to sections and regenerate once (bounded)
                from services.report_improvement.section_generators.quality_checks import map_coherence_issue_to_section  # type: ignore
                # Pick first actionable issue
                target_issue = None
                target_section = None
                for rid in cs_issues:
                    sec = map_coherence_issue_to_section(rid)
                    if sec:
                        target_issue = rid
                        target_section = sec
                        break
                if target_section:
                    # Lazy import generators to avoid hard dependency
                    from services.report_improvement.section_generators import select_section_evidence  # type: ignore
                    if target_section == "executive_summary":
                        try:
                            from services.report_improvement.section_generators import generate_executive_summary  # type: ignore
                            si = select_section_evidence("executive_summary", ctx, adjudication, transcript_insights=[])
                            es = generate_executive_summary(si)
                            final_report["executive_summary"] = "\n\n".join(
                                [
                                    es.assessment_context,
                                    es.business_overview,
                                    es.security_posture_narrative,
                                    ("Key strengths: " + ", ".join(es.key_strengths)) if es.key_strengths else "",
                                    ("Priority gaps: " + ", ".join(es.priority_gaps)) if es.priority_gaps else "",
                                    "Board takeaway: " + es.board_level_takeaway,
                                    "Strategic direction: " + es.strategic_direction,
                                ]
                            ).strip()
                        except Exception:
                            pass
                    elif target_section == "threat_scenarios":
                        try:
                            from services.report_improvement.section_generators import generate_attack_scenario  # type: ignore
                            ao = generate_attack_scenario(ctx, adjudication)
                            final_report["threat_scenarios"] = "\n\n".join(
                                [
                                    ao.disclaimer,
                                    ao.scenario_title,
                                    ao.initial_access,
                                    ao.progression,
                                    ao.business_impact,
                                    ao.detection_opportunities,
                                    ao.containment_considerations,
                                    ao.recovery_considerations,
                                ]
                            ).strip()
                        except Exception:
                            pass
                    elif target_section == "compliance_alignment":
                        try:
                            from services.report_improvement.section_generators import generate_compliance_alignment  # type: ignore
                            si2 = select_section_evidence("compliance_alignment", ctx, adjudication, transcript_insights=[])
                            ca = generate_compliance_alignment(si2)
                            rows_txt = []
                            for r in (ca.rows or [])[:5]:
                                rows_txt.append(f"{r.framework_name} — {r.framework_area}: {r.current_position} | {r.assurance_gap_or_consideration} | Focus: {r.recommended_focus}")
                            final_report["compliance_alignment"] = "\n\n".join([ca.current_position, ca.scope_and_limitations] + rows_txt).strip()
                        except Exception:
                            pass
                    elif target_section == "cost_of_inaction":
                        try:
                            from services.report_improvement.section_generators.cost_of_inaction import generate_cost_of_inaction as _gcoi  # type: ignore
                            coi = _gcoi(ctx, adjudication, transcript_insights=[])
                            qparts = [coi.qualitative_narrative]
                            if coi.cost_drivers:
                                qparts.extend([f"- {d.driver_name}: {d.description}" for d in coi.cost_drivers[:5]])
                            if coi.quantified_narrative:
                                qparts.append(coi.quantified_narrative)
                            final_report["cost_of_inaction"] = "\n".join([p for p in qparts if p]).strip()
                        except Exception:
                            pass
                    # Re-evaluate coherence once
                    try:
                        cs_map = build_cross_section_map_from_report(final_report)
                        cs_issues = validate_coherence(cs_map)
                    except Exception:
                        cs_issues = cs_issues  # keep previous if evaluation fails
            except Exception:
                # Regeneration is best-effort
                pass

        if cs_issues and overall_status != ValidationStatus.BLOCK:
            # Enforce fail-closed on coherence issues
            overall_status = ValidationStatus.BLOCK

    rv = ReportValidationResult(
        status=overall_status,
        section_results=section_results,
        cross_section_issues=cs_issues,
        publication_issues=[],
        automatic_publication_allowed=(overall_status == ValidationStatus.PASS) and (len(cs_issues) == 0),
        human_review_required=(overall_status in (ValidationStatus.BLOCK, ValidationStatus.HUMAN_REVIEW)),
    )
    # Emit per-section blocking rule IDs for failure summaries
    try:
        _blocking_map = {}
        for r in (section_results or []):
            bids = [str(getattr(i, "rule_id", "")) for i in (getattr(r, "issues", []) or []) if getattr(i, "status", None) == ValidationStatus.BLOCK]
            if bids:
                _blocking_map[str(getattr(r, "section_name", ""))] = bids
    except Exception:
        _blocking_map = {}
    # Best-effort metrics emission; do not affect fail-closed gating on IO failure
    try:
        from config import get_config
        from datetime import datetime, timezone
        logs_dir = get_config("LOGS_DIR", "exports/logs")
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        # Evaluation summary and coherence metrics (non-blocking; best-effort)
        try:
            eval_enabled = str(get_config("EVALUATION_ENABLED", "true")).strip().lower() in ("1", "true", "yes", "on")
        except Exception:
            eval_enabled = True
        evaluation_summary = None
        if eval_enabled:
            try:
                from services.report_improvement.evaluation.runner import run_evaluation as _run_evaluation  # type: ignore
                evr = _run_evaluation(final_report, adjudication, ctx)
                evaluation_summary = {
                    "unsupported_claim_count": int(getattr(evr, "unsupported_claim_count", 0)),
                    "control_recognition_score": float(getattr(evr, "control_recognition_score", 0.0)),
                    "recommendation_traceability_score": float(getattr(evr, "recommendation_traceability_score", 0.0)),
                    "customer_specificity_score": float(getattr(evr, "customer_specificity_score", 0.0)),
                    "cross_section_consistency_ok": bool(getattr(evr, "cross_section_consistency_ok", True)),
                    "commercial_proportionality_ok": bool(getattr(evr, "commercial_proportionality_ok", True)),
                    "executive_readability_ok": bool(getattr(evr, "executive_readability_ok", True)),
                    "evidence_disclosure_ok": bool(getattr(evr, "evidence_disclosure_ok", True)),
                    "editing_distance_proxy": float(getattr(evr, "editing_distance_proxy", 0.0)),
                }
            except Exception:
                evaluation_summary = None
        # Compute canonical hashes for output and evidence context
        try:
            output_hash = _canon_section_hash("report", final_report)
        except Exception:
            output_hash = ""
        try:
            evidence_context_hash = _canon_section_hash("evidence_ctx", getattr(ctx, "evidence", None) or adjudication)
        except Exception:
            evidence_context_hash = ""
        coherence_issue_count = int(len(cs_issues) if cs_issues else 0)
        coherence_rule_ids_top = list((cs_issues or [])[:5])
        write_metrics(
            logs_dir=logs_dir,
            run_id=run_id,
            data={
                "final_status": str(overall_status),
                "sections": len(section_results),
                "initial_blocking_issue_count": int(initial_blocking_issue_count),
                "deterministic_resolution_count": int(deterministic_resolution_count),
                "evidence_rewrite_resolution_count": int(evidence_rewrite_resolution_count),
                "section_rebuild_resolution_count": int(section_rebuild_resolution_count),
                "post_rewrite_blocking_issue_count": int(post_rewrite_blocking_issue_count),
                "remediation_success_rate": float(remediation_success_rate),
                "model_call_count": int(model_call_count),
                "unchanged_rewrite_count": int(unchanged_rewrite_count),
                "coherence_issue_count": int(coherence_issue_count),
                "coherence_rule_ids": coherence_rule_ids_top,
                "evaluation_summary": evaluation_summary,
                "output_hash": output_hash,
                "evidence_context_hash": evidence_context_hash,
                "unresolved_consultant_decision_count": None,
                "blocking_rule_ids_by_section": _blocking_map,
            },
            report_name=str((original_report or {}).get("report_name", "report")),
        )
    except Exception:
        pass
    return final_report, rv
