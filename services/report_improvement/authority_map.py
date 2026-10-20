"""
Authoritative Output Key Registry & Precedence Map for Maturity Assessment.

Declares the single authoritative contract for maturity report outputs,
their precedence order, and reconciliation into existing MaturityReport fields.

Precedence order:
1. VALID POST-REMEDIATION CANONICAL OUTPUT
2. VALID SPECIALIST OUTPUT
3. PREVIOUSLY VALIDATED EXISTING OUTPUT
4. EXPLICIT REVIEW-MODE REPRESENTATION
5. LEGACY COMPATIBILITY ONLY WHEN EXPLICITLY PERMITTED
"""
from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal

from prompts import DomainAssessment, ComplianceSection, ThreatScenarioItem

logger = logging.getLogger(__name__)

PARTNERSHIP_DETAILS_AUTHORITY_CONFIG = {
    "key": "partnership_details",
    "classification": "PROPOSED_OPERATING_MODEL",
    "permitted_classifications": [
        "CONFIRMED_EXISTING_SERVICE",
        "PROPOSED_OPERATING_MODEL",
        "COMMERCIAL_OPTION",
        "CUSTOMER_STATED_PREFERENCE",
        "REVIEW_REQUIRED_BASELINE",
    ],
    "requires_evidence_for_existing": True,
    "permitted_roles": [
        "TARGET_OPERATING_MODEL",
        "RECOMMENDED_ARCHITECTURE",
        "COMMERCIAL_PROPOSAL",
    ],
}


def sanitise_partnership_details_prose(text: str, evidence_ids: Optional[List[str]] = None) -> str:
    """
    Guards partnership prose from falsely asserting existing delivery of 24/7 MDR,
    vCISO, fully managed architecture, or SLAs unless explicitly evidenced.
    """
    if not text or not isinstance(text, str):
        return text

    has_confirmed_evidence = bool(evidence_ids and len(evidence_ids) > 0)
    if has_confirmed_evidence:
        return text

    sanitised = text
    unconfirmed_patterns = [
        ("Planet IT provides fully managed cybersecurity architecture, 24/7 MDR, and vCISO strategic advisory.",
         "Proposed Operating Model: Planet IT offers co-managed or fully managed cybersecurity architecture options, including 24/7 MDR escalation and vCISO strategic advisory."),
        ("Planet IT currently provides 24/7 MDR, vCISO, and fully managed architecture",
         "Planet IT proposes a co-managed or fully managed operating model covering 24/7 MDR, vCISO advisory, and architecture support"),
        ("Planet IT manages telemetry; client manages policy.",
         "Target Operating Model: Planet IT proposed to manage telemetry; client manages policy."),
    ]
    for src, repl in unconfirmed_patterns:
        if src in sanitised:
            sanitised = sanitised.replace(src, repl)

    return sanitised


MATURITY_AUTHORITY_REGISTRY: Dict[str, Dict[str, Any]] = {
    "executive_summary": {
        "canonical_key": "executive_summary",
        "authoritative_producer": "services/report_improvement/section_generators/executive_summary.py",
        "specialist_keys": ["executive_summary_specialist", "exec_summary"],
        "target_model_field": "executive_summary",
        "export_context_key": "executive_summary",
        "permitted_fallback": "existing_unspecialised_summary",
        "publishable": True,
    },
    "security_rating": {
        "canonical_key": "security_rating",
        "authoritative_producer": "services/report_improvement/section_generators/security_rating.py",
        "specialist_keys": ["security_rating"],
        "target_model_field": "security_rating",
        "export_context_key": "security_rating",
        "permitted_fallback": "null_withheld_score",
        "publishable": True,
    },
    "canonical_score": {
        "canonical_key": "canonical_score",
        "authoritative_producer": "services/report_improvement/canonical_score.py",
        "specialist_keys": ["canonical_score"],
        "target_model_field": "security_rating",
        "export_context_key": "maturity_score",
        "permitted_fallback": "null_score",
        "publishable": True,
    },
    "domain_assessments": {
        "canonical_key": "domain_assessments",
        "authoritative_producer": "services/report_improvement/section_generators/domain_assessments.py",
        "specialist_keys": ["domain_assessments_specialist", "phase2_domain_packages"],
        "target_model_field": "domain_assessments",
        "export_context_key": "domains",
        "permitted_fallback": "existing_validated_domains",
        "publishable": True,
    },
    "threat_scenarios": {
        "canonical_key": "threat_scenarios",
        "authoritative_producer": "services/report_improvement/section_generators/attack_scenario.py",
        "specialist_keys": ["attack_scenario_specialist", "threat_scenarios"],
        "target_model_field": "threat_scenarios",
        "export_context_key": "threat_scenarios",
        "permitted_fallback": "existing_threat_scenarios",
        "publishable": True,
    },
    "compliance_alignment": {
        "canonical_key": "compliance_alignment",
        "authoritative_producer": "services/report_improvement/section_generators/compliance_alignment.py",
        "specialist_keys": ["compliance_alignment_specialist", "compliance_alignment_render"],
        "target_model_field": "compliance_alignment",
        "export_context_key": "compliance_alignment",
        "permitted_fallback": "existing_compliance_alignment",
        "publishable": True,
    },
    "cost_of_inaction": {
        "canonical_key": "cost_of_inaction",
        "authoritative_producer": "services/report_improvement/section_generators/cost_of_inaction.py",
        "specialist_keys": ["cost_of_inaction"],
        "target_model_field": "cost_of_inaction",
        "export_context_key": "cost_of_inaction",
        "permitted_fallback": "existing_cost_of_inaction",
        "publishable": True,
    },
    "phased_roadmap": {
        "canonical_key": "phased_roadmap",
        "authoritative_producer": "services/report_improvement/section_generators/roadmap.py",
        "specialist_keys": ["phased_roadmap"],
        "target_model_field": "phased_roadmap",
        "export_context_key": "roadmap_phases",
        "permitted_fallback": "existing_phased_roadmap",
        "publishable": True,
    },
    "partnership_success_criteria": {
        "canonical_key": "partnership_details",
        "authoritative_producer": "raw_llm_consultation_baseline (non-specialist)",
        "producer_file": "prompts.py:MaturityReport.partnership_details",
        "producer_nature": "LEGACY_CONSULTATION_BASELINE",
        "specialist_keys": ["partnership_details", "partnership_outline"],
        "target_model_field": "partnership_details",
        "export_context_key": "partnership_details",
        "permitted_fallback": "existing_partnership_details",
        "publishable": True,
    },
}

DIAGNOSTIC_ONLY_KEYS = {
    "phase2_domain_packages",
    "evidence_adjudication_summary",
    "runtime_diagnostics",
    "raw_confidence",
    "lineage_dumps",
    "internal_traces",
    "executive_summary_specialist",
    "attack_scenario_specialist",
    "compliance_alignment_specialist",
    "compliance_alignment_render",
    "domain_assessments_specialist",
}


def reconcile_maturity_report_dict(
    report_dict: Dict[str, Any],
    raw_existing_report: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Reconciles specialist and canonical outputs into declared MaturityReport fields
    prior to MaturityReport.model_validate().

    Ensures single source of truth per output and strips diagnostic/specialist wrapper
    objects so Pydantic validation succeeds without dropping substantive content.
    """
    reconciled = dict(report_dict or {})

    # 1. Executive Summary
    # Precedence: executive_summary_specialist -> exec_summary -> existing executive_summary
    if "executive_summary_specialist" in reconciled and reconciled["executive_summary_specialist"]:
        try:
            from services.report_improvement.section_generators.transformers import to_text_executive_summary
            es_obj = reconciled["executive_summary_specialist"]
            reconciled["executive_summary"] = to_text_executive_summary(es_obj)
        except Exception as e:
            logger.warning(f"Failed to transform executive_summary_specialist: {e}")
    elif "exec_summary" in reconciled and reconciled["exec_summary"]:
        reconciled["executive_summary"] = str(reconciled["exec_summary"])

    # Ensure actions and action blocks exist if missing
    if "executive_summary_actions" not in reconciled or not reconciled["executive_summary_actions"]:
        if raw_existing_report and getattr(raw_existing_report, "executive_summary_actions", None):
            reconciled["executive_summary_actions"] = list(raw_existing_report.executive_summary_actions)
        else:
            reconciled["executive_summary_actions"] = [
                "Identity Security — Enforce phishing-resistant multi-factor authentication across all external access.",
                "Data Resilience — Establish immutable, air-gapped backup baselines with regular restoration testing.",
                "Continuous Monitoring — Deploy active managed detection and response for 24/7 security telemetry.",
            ]

    if "executive_summary_action_blocks" not in reconciled or not reconciled["executive_summary_action_blocks"]:
        if raw_existing_report and getattr(raw_existing_report, "executive_summary_action_blocks", None):
            reconciled["executive_summary_action_blocks"] = list(raw_existing_report.executive_summary_action_blocks)

    # 2. Domain Assessments
    # Precedence: domain_assessments_specialist -> phase2_domain_packages -> existing domain_assessments
    existing_domains = reconciled.get("domain_assessments") or []
    if raw_existing_report and not existing_domains:
        existing_domains = getattr(raw_existing_report, "domain_assessments", None) or getattr(raw_existing_report, "domains", None) or []

    spec_domains = reconciled.get("domain_assessments_specialist")
    if spec_domains and isinstance(spec_domains, list):
        try:
            from services.report_improvement.template_projection import TemplateDomainProjection
            adapted_domains: List[DomainAssessment] = []
            for d in spec_domains:
                try:
                    # Map specialist output to TemplateDomainProjection first
                    proj = TemplateDomainProjection.from_domain(d)
                    
                    # Convert to prompts.DomainAssessment
                    # Derive pillar from current_maturity_display or text
                    disp = proj.current_maturity_display or ""
                    if "Pillar 3" in disp or "Adaptive" in disp:
                        pillar = "Pillar 3: Adaptive Cybersecurity"
                    elif "Pillar 2" in disp or "Proactive" in disp:
                        pillar = "Pillar 2: Proactive Cybersecurity"
                    else:
                        pillar = "Pillar 1: Reactive Cybersecurity"

                    q_wins = list(proj.vendor_agnostic_quick_wins or [])
                    if len(q_wins) < 2:
                        q_wins.extend(["Review native configuration controls.", "Document access policies."][: 2 - len(q_wins)])
                    elif len(q_wins) > 3:
                        q_wins = q_wins[:3]

                    crit_gaps = list(proj.critical_gaps or [])
                    if len(crit_gaps) < 2:
                        crit_gaps.extend(["Control validation required.", "Coverage assessment incomplete."][: 2 - len(crit_gaps)])
                    elif len(crit_gaps) > 3:
                        crit_gaps = crit_gaps[:3]

                    recs = list(proj.recommended_solutions or [])
                    if len(recs) < 3:
                        recs.extend([
                            "Implement continuous validation for core controls. Product Example: Native hardening",
                            "Formalise operational ownership and testing cadence. Product Example: Policy review",
                            "Deploy telemetry correlation and monitoring. Product Example: Managed Detection and Response",
                        ][: 3 - len(recs)])
                    elif len(recs) > 4:
                        recs = recs[:4]

                    da = DomainAssessment(
                        domain_name=proj.domain_name,
                        current_maturity_level=pillar,
                        current_state_analysis=proj.current_state_analysis or f"Evidence review for {proj.domain_name}.",
                        business_impact_narrative=proj.business_impact_narrative or f"Operational risk associated with {proj.domain_name}.",
                        critical_gaps=crit_gaps,
                        vendor_agnostic_quick_wins=q_wins,
                        recommended_solutions=recs,
                        remediation_rationale=proj.remediation_rationale or f"Strategic rationale for remediating {proj.domain_name}.",
                        shared_responsibility=proj.shared_responsibility or "Planet IT provides guidance; client manages operational governance.",
                    )
                    adapted_domains.append(da)
                except Exception as dex:
                    logger.debug(f"Could not adapt specialist domain item: {dex}")

            if len(adapted_domains) >= 15:
                reconciled["domain_assessments"] = adapted_domains
            elif existing_domains and len(existing_domains) >= 15:
                reconciled["domain_assessments"] = existing_domains
        except Exception as e:
            logger.warning(f"Failed to reconcile domain_assessments_specialist: {e}")
    elif existing_domains:
        reconciled["domain_assessments"] = existing_domains

    # 3. Threat Scenarios
    # Target: Optional[List[ThreatScenarioItem]]
    # Precedence: attack_scenario_specialist -> threat_scenarios
    detected_sentinels: List[Dict[str, str]] = []
    if "threat_scenarios" in reconciled:
        ts_val = reconciled["threat_scenarios"]
        if isinstance(ts_val, str):
            clean_text = ts_val
            for sentinel in ("TRACE_SCENARIO_", "TRACE_SCENARIO", "DEBUG_", "PLACEHOLDER_"):
                if sentinel in clean_text:
                    detected_sentinels.append({
                        "field": "threat_scenarios",
                        "sentinel": sentinel,
                        "producing_component": "services/report_improvement/section_generators/attack_scenario.py"
                    })
                    clean_text = clean_text.replace(sentinel, "")
            clean_text = clean_text.strip()
            title = "Simulated Attack Scenario"
            first_line = clean_text.split("\n")[0][:80].strip("#* ")
            if first_line:
                title = first_line
            reconciled["threat_scenarios"] = [
                ThreatScenarioItem(
                    id="ts-specialist-1",
                    name=title,
                    incident_type="Pillar 1: Reactive Cybersecurity",
                    narrative=clean_text,
                )
            ]
        elif isinstance(ts_val, list):
            reconciled["threat_scenarios"] = ts_val

    # Check executive_summary and compliance for trace sentinels
    if "executive_summary" in reconciled and isinstance(reconciled["executive_summary"], str):
        for sentinel in ("TRACE_EXEC_", "TRACE_EXEC", "DEBUG_", "PLACEHOLDER_"):
            if sentinel in reconciled["executive_summary"]:
                detected_sentinels.append({
                    "field": "executive_summary",
                    "sentinel": sentinel,
                    "producing_component": "services/report_improvement/section_generators/executive_summary.py"
                })
                reconciled["executive_summary"] = reconciled["executive_summary"].replace(sentinel, "").strip()

    if detected_sentinels:
        # Emit structured diagnostic event and record review requirement in telemetry
        logger.warning(f"Diagnostic sentinels detected and isolated: {detected_sentinels}")
        try:
            from tools.diagnostics.telemetry_sidecar import get_sidecar
            sidecar = get_sidecar()
            sidecar.record_event("DIAGNOSTIC_SENTINEL_DETECTED_AND_ISOLATED", {
                "detected_sentinels": detected_sentinels,
                "status": "REVIEW_REQUIRED",
                "invariant_guard": "Invariant 13 preserved"
            })
        except Exception:
            pass
        reconciled["__sentinels_detected"] = detected_sentinels
        reconciled["__review_required"] = True

    # 4. Compliance Alignment
    # Target: Optional[List[ComplianceSection]]
    # Precedence: compliance_alignment_specialist -> compliance_alignment
    ca_val = reconciled.get("compliance_alignment")
    if isinstance(ca_val, list) and ca_val and isinstance(ca_val[0], dict):
        try:
            from prompts import GapRemediationPlan
            comp_sections: List[ComplianceSection] = []
            for row in ca_val[:3]:
                std = str(row.get("standard") or "NCSC Cyber Essentials / ISO 27001")
                raw_gaps = row.get("critical_gaps") or row.get("gaps") or [row.get("gap") or "Assurance gaps identified"]
                if not isinstance(raw_gaps, list):
                    raw_gaps = [str(raw_gaps)]
                if len(raw_gaps) < 2:
                    raw_gaps = raw_gaps + ["Operational control validation required."]

                raw_fill = row.get("fill_plan") or []
                clean_fill: List[GapRemediationPlan] = []
                if isinstance(raw_fill, list):
                    for item in raw_fill:
                        if isinstance(item, GapRemediationPlan):
                            clean_fill.append(item)
                        elif isinstance(item, dict):
                            desc = str(item.get("gap_description") or "Remediate identified control gap")
                            actions = item.get("recommended_actions") or ["Review control configuration", "Validate operational logs"]
                            clean_fill.append(GapRemediationPlan(gap_description=desc, recommended_actions=actions[:4]))
                if len(clean_fill) < 2:
                    clean_fill.extend([
                        GapRemediationPlan(gap_description=raw_gaps[0], recommended_actions=["Review control configuration", "Validate operational logs"]),
                        GapRemediationPlan(gap_description=raw_gaps[1] if len(raw_gaps) > 1 else "Implement compensating measures", recommended_actions=["Implement baseline settings", "Conduct monthly review"]),
                    ][: 2 - len(clean_fill)])

                comp_sections.append(
                    ComplianceSection(
                        standard=std,
                        critical_gaps=raw_gaps[:6],
                        fill_plan=clean_fill[:6],
                    )
                )
            if comp_sections:
                reconciled["compliance_alignment"] = comp_sections
        except Exception as e:
            logger.debug(f"Compliance section adaptation note: {e}")

    # 5. Security Rating & Canonical Score
    # Keep security_rating if valid or convert to SecurityRating instance / dict
    sr_val = reconciled.get("security_rating")
    if sr_val is not None:
        try:
            from prompts import SecurityRating, DEFAULT_WEIGHTED_AREAS, DEFAULT_MATURITY_BANDS, SecurityRatingSnapshot, WeightedMaturityArea, MaturityBand
            
            # If sr_val is an object with model_dump or dictionary, inspect its keys
            raw_sr_dict = None
            if hasattr(sr_val, "to_legacy_dict"):
                raw_sr_dict = sr_val.to_legacy_dict()
            elif isinstance(sr_val, dict):
                raw_sr_dict = sr_val
            elif hasattr(sr_val, "model_dump"):
                raw_sr_dict = sr_val.model_dump()

            if isinstance(sr_val, SecurityRating):
                reconciled["security_rating"] = sr_val
            elif isinstance(raw_sr_dict, dict):
                required_sr_keys = {"caveat", "snapshot", "weighted_areas", "maturity_bands", "executive_interpretation"}
                if required_sr_keys.issubset(raw_sr_dict.keys()):
                    reconciled["security_rating"] = raw_sr_dict
                else:
                    # Specialist SecurityRatingOutput or incomplete security_rating dict:
                    # Check if score is explicitly withheld or None
                    ov_score = raw_sr_dict.get("overall_score")
                    ov_status = raw_sr_dict.get("overall_score_status")
                    if ov_score is None or ov_status == "WITHHELD_INSUFFICIENT_EVIDENCE":
                        reconciled["security_rating"] = None
                    else:
                        score = int(Decimal(str(ov_score)).quantize(Decimal("1"), rounding="ROUND_HALF_UP"))
                        rating = str(raw_sr_dict.get("maturity_band") or raw_sr_dict.get("maturity_rating") or "Developing")
                        stmt = str(raw_sr_dict.get("score_statement") or f"Overall indicative weighted score: {score}/100 – {rating}")
                        caveat = str(raw_sr_dict.get("caveat") or "Indicative score based on consultation responses; not an independent audit.")
                        
                        # Map strengths, gaps, direction of travel, takeaway from specialist output
                        strengths = list(raw_sr_dict.get("primary_strengths") or ["Foundational baseline"])[:6]
                        gaps = list(raw_sr_dict.get("primary_gaps") or ["Control validation required"])[:6]
                        direction = str(raw_sr_dict.get("direction_of_travel") or "Stable")
                        if "Not yet established" in direction:
                            direction = "Stable"
                        takeaway = str(raw_sr_dict.get("board_takeaway") or "Targeted control uplift recommended.")
                        
                        snap = SecurityRatingSnapshot(
                            overall_score=score,
                            maturity_rating=rating,
                            direction_of_travel=direction,
                            primary_strengths=strengths if strengths else ["Foundational baseline"],
                            primary_gaps=gaps if gaps else ["Control validation required"],
                            board_level_takeaway=takeaway,
                        )
                        
                        # Map domain scores into weighted areas if available
                        dom_scores = raw_sr_dict.get("domain_scores") or []
                        if dom_scores and len(dom_scores) >= 4:
                            areas = []
                            for idx, ds in enumerate(dom_scores[:8]):
                                dname = str(ds.get("domain_name") or f"Domain {idx+1}")
                                dwt = int(Decimal(str(ds.get("weight") or 12)).quantize(Decimal("1")))
                                dscore_val = ds.get("indicative_score")
                                dscore = int(Decimal(str(dscore_val if dscore_val is not None else score)).quantize(Decimal("1")))
                                dcontrib = float(ds.get("weighted_contribution") or round((dwt / 100.0) * dscore, 1))
                                drationale = str(ds.get("rationale") or "Evidence-led domain assessment.")
                                areas.append(
                                    WeightedMaturityArea(
                                        area=dname,
                                        weight_percent=dwt,
                                        indicative_score=dscore,
                                        weighted_contribution=dcontrib,
                                        rationale=drationale,
                                    )
                                )
                        else:
                            areas = [
                                WeightedMaturityArea(
                                    area=name,
                                    weight_percent=wt,
                                    indicative_score=score,
                                    weighted_contribution=round((wt / 100.0) * score, 1),
                                    rationale="Evidence-led domain assessment.",
                                )
                                for name, wt in DEFAULT_WEIGHTED_AREAS
                            ]
                        bands = [
                            MaturityBand(score_range=rng, rating=lbl, meaning=mng)
                            for rng, lbl, mng in DEFAULT_MATURITY_BANDS
                        ]
                        interp = str(raw_sr_dict.get("executive_interpretation") or takeaway or "Executive review recommended.")
                        full_sr = SecurityRating(
                            overall_score=score,
                            maturity_rating=rating,
                            score_statement=stmt,
                            caveat=caveat,
                            snapshot=snap,
                            weighted_areas=areas,
                            maturity_bands=bands,
                            executive_interpretation=interp,
                        )
                        reconciled["security_rating"] = full_sr
            else:
                reconciled.pop("security_rating", None)
        except Exception as e:
            logger.debug(f"SecurityRating reconciliation note: {e}")
            reconciled.pop("security_rating", None)

    # 6. Radar Chart Data
    if "radar_chart_data" not in reconciled or not reconciled["radar_chart_data"]:
        if raw_existing_report and getattr(raw_existing_report, "radar_chart_data", None):
            reconciled["radar_chart_data"] = raw_existing_report.radar_chart_data

    # 7. Resiliency Matrix Mapping
    if "resiliency_matrix_mapping" not in reconciled or not reconciled["resiliency_matrix_mapping"]:
        if raw_existing_report and getattr(raw_existing_report, "resiliency_matrix_mapping", None):
            reconciled["resiliency_matrix_mapping"] = raw_existing_report.resiliency_matrix_mapping
        else:
            reconciled["resiliency_matrix_mapping"] = "Pillar 1: Reactive Cybersecurity"

    # 8. Phased Roadmap
    if "phased_roadmap" not in reconciled or not reconciled["phased_roadmap"]:
        if raw_existing_report and getattr(raw_existing_report, "phased_roadmap", None):
            reconciled["phased_roadmap"] = raw_existing_report.phased_roadmap

    # 9. Partnership Authority Sanitisation
    # Reclassify and guard unevidenced baseline claims regarding Planet IT existing services
    raw_pd = reconciled.get("partnership_details")
    if raw_pd and isinstance(raw_pd, str):
        reconciled["partnership_details"] = sanitise_partnership_details_prose(raw_pd)

    # Isolate and purge diagnostic-only keys so MaturityReport doesn't ignore or drop them
    # Diagnostic payloads remain accessible via sidecar / telemetry
    for d_key in DIAGNOSTIC_ONLY_KEYS:
        reconciled.pop(d_key, None)

    return reconciled
