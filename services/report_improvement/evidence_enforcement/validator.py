from __future__ import annotations
from typing import Dict, Any, List, Tuple
from pydantic import BaseModel
from config import get_config, ConfigKey
from services.report_improvement.evidence_adjudicator import EvidenceAdjudicationResult
from .models import (
    EvidenceEnforcementContext,
    ApprovedEntity,
    ExistingControlRecord,
    ApprovedGapRecord,
    ApprovedRecommendationRecord,
    FinancialEvidenceProfile,
    ApprovedScenarioProfile,
    ValidationIssue,
    ValidationStatus,
    ValidationSeverity,
    SectionValidationResult,
    ReportValidationResult,
)
from .normalisation import normalise_text


def _build_context(adjudication: EvidenceAdjudicationResult) -> EvidenceEnforcementContext:
    """
    Build an enforcement context from adjudicated evidence.
    This uses only adjudicated facts; no inference.
    """
    # Entities: existing controls, crown jewels, technologies
    entities: List[ApprovedEntity] = []
    try:
        for c in getattr(adjudication, "existing_controls", []) or []:
            name = getattr(c, "control_name", None)
            if name:
                entities.append(ApprovedEntity(canonical_name=str(name), entity_type="product"))
    except Exception:
        pass
    try:
        aai = getattr(adjudication, "approved_attack_inputs", None)
        if aai:
            for cj in getattr(aai, "confirmed_crown_jewels", []) or []:
                entities.append(ApprovedEntity(canonical_name=str(cj), entity_type="crown_jewel"))
            for t in getattr(aai, "confirmed_technologies", []) or []:
                entities.append(ApprovedEntity(canonical_name=str(t), entity_type="technology"))
    except Exception:
        pass

    # Existing controls: mark implemented but effectiveness unvalidated by default (deterministic, conservative)
    controls: List[ExistingControlRecord] = []
    try:
        idx = 0
        for c in getattr(adjudication, "existing_controls", []) or []:
            name = getattr(c, "control_name", None)
            if name:
                controls.append(
                    ExistingControlRecord(
                        control_id=f"ctrl-{idx}",
                        canonical_name=str(name),
                        category="control",
                        implementation_status="implemented",
                        effectiveness_status="unvalidated",
                        products=[str(name)],
                        evidence_references=[],
                    )
                )
                idx += 1
    except Exception:
        pass

    # Gaps: use only unsupported/contradicted claims (unknown/unvalidated NOT used as gaps)
    gaps: List[ApprovedGapRecord] = []
    try:
        gi = 0
        for src in [
            getattr(adjudication, "unsupported_claims", []) or [],
            getattr(adjudication, "contradicted_claims", []) or [],
        ]:
            for cl in src:
                st = str(getattr(cl, "claim_text", "")).strip()
                if st:
                    gaps.append(
                        ApprovedGapRecord(
                            gap_id=f"gap-{gi}",
                            domain="general",
                            statement=st,
                            status="confirmed",
                            permitted_language=[],
                            prohibited_language=[],
                            evidence_references=[],
                        )
                    )
                    gi += 1
    except Exception:
        pass

    # Financial profile and scenario profile (explicit adapters; fail-closed)
    fp = getattr(adjudication, "cost_assumptions", None)
    scen = getattr(adjudication, "approved_attack_inputs", None)
    from .adapters import adapt_cost_profile, adapt_scenario_profile
    ctx = EvidenceEnforcementContext(
        approved_entities=entities,
        existing_controls=controls,
        approved_gaps=gaps,
        approved_recommendations=[],
        financial_profile=adapt_cost_profile(fp),
        scenario_profile=adapt_scenario_profile(scen),
    )
    return ctx


def _validate_section_text(section_name: str, text: str, ctx: EvidenceEnforcementContext) -> SectionValidationResult:
    """
    Deterministic validation rules against adjudicated context.
    Returns a SectionValidationResult carrying PASS/WARNING/BLOCK/HUMAN_REVIEW.
    """
    issues: List[ValidationIssue] = []

    tnorm = normalise_text(text or "")
    ltext = tnorm.lower()

    # Rule: Unknown is NOT a weakness — block absolute absence claims not grounded in adjudication
    banned_absence_phrases = ("no mdr", "no backups", "no patching", "no edr", "no endpoint", "no email security")
    try:
        if any(tok in ltext for tok in banned_absence_phrases):
            issues.append(
                ValidationIssue(
                    rule_id="UNKNOWN_NOT_WEAKNESS",
                    status=ValidationStatus.BLOCK,
                    severity=ValidationSeverity.MEDIUM,
                    section_name=section_name,
                    offending_text=tnorm[:200],
                    explanation="Language asserts control absence without adjudicated support; unknown must not be treated as a weakness.",
                    required_action="rewrite",
                )
            )
        # Identity/MFA contradiction: prevent 'unspecified identity' coexisting with universal MFA claims without exceptions
        if ("unspecified identity" in ltext) and ("universal / conditional access" in ltext or "universal mfa" in ltext or "conditional access" in ltext):
            issues.append(
                ValidationIssue(
                    rule_id="IDENTITY_MFA_CONTRADICTION",
                    status=ValidationStatus.BLOCK,
                    severity=ValidationSeverity.MEDIUM,
                    section_name=section_name,
                    offending_text=tnorm[:200],
                    explanation="Identity platform state contradicts universal MFA claims; exceptions must be reconciled explicitly (e.g., FTP).",
                    required_action="rewrite",
                )
            )
        # Primary strengths misclassification: block imperative recommendations inside strengths section markup
        import re as _re_imp
        if _re_imp.search(r"primary\s+strengths[:\-]\s*(enforce|adopt|automate|deploy)\b", ltext):
            issues.append(
                ValidationIssue(
                    rule_id="STRENGTHS_MISCLASSIFIED_AS_RECOMMENDATIONS",
                    status=ValidationStatus.BLOCK,
                    severity=ValidationSeverity.LOW,
                    section_name=section_name,
                    offending_text=tnorm[:200],
                    explanation="Primary strengths contain imperative recommendations; strengths must recognise existing controls only.",
                    required_action="rewrite",
                )
            )
    except Exception:
        pass

    # Rule: Prevent control replacement without justification — if existing control present and 'replace' is suggested
    try:
        known_controls = [str(c.canonical_name).lower() for c in (ctx.existing_controls or []) if str(c.canonical_name).strip()]
        if "replace" in ltext and known_controls:
            for kc in known_controls:
                if kc and kc in ltext:
                    issues.append(
                        ValidationIssue(
                            rule_id="NO_REPLACEMENT_WITHOUT_JUSTIFICATION",
                            status=ValidationStatus.BLOCK,
                            severity=ValidationSeverity.MEDIUM,
                            section_name=section_name,
                            offending_text=tnorm[:200],
                            explanation=f"Text appears to recommend replacing existing control '{kc}'. Replacement requires explicit, approved justification.",
                            required_action="rewrite",
                        )
                    )
                    break
    except Exception:
        pass

    # Additional BRANDED conflict validation rules
    try:
        entities_lower = [str(getattr(e, "canonical_name", "")).strip().lower() for e in (ctx.approved_entities or [])]
        known_controls = [str(c.canonical_name).lower() for c in (ctx.existing_controls or []) if str(c.canonical_name).strip()]
        # MDR not deployed but asserted in text
        if (("sophos mdr" in ltext) or ("sophos mdr plus" in ltext)) and not any(k in known_controls for k in ("sophos mdr", "sophos mdr plus")):
            issues.append(
                ValidationIssue(
                    rule_id="MDR_NOT_DEPLOYED",
                    status=ValidationStatus.BLOCK,
                    severity=ValidationSeverity.MEDIUM,
                    section_name=section_name,
                    offending_text=tnorm[:200],
                    explanation="MDR product asserted without adjudicated deployment evidence.",
                    required_action="rewrite",
                )
            )
        # Identity: Google vs Entra ID / Conditional Access asserted
        if any(("google workspace" in n) for n in entities_lower) and ("entra id" in ltext or "conditional access" in ltext):
            issues.append(
                ValidationIssue(
                    rule_id="GOOGLE_IDENTITY_CONTRADICTED",
                    status=ValidationStatus.BLOCK,
                    severity=ValidationSeverity.MEDIUM,
                    section_name=section_name,
                    offending_text=tnorm[:200],
                    explanation="Identity platform is Google; Entra ID / universal Conditional Access assertions are not permitted without corroboration.",
                    required_action="rewrite",
                )
            )
        # Universal MFA asserted without FTP exception acknowledgement
        if ("universal mfa" in ltext or "conditional access" in ltext) and ("ftp" not in ltext):
            issues.append(
                ValidationIssue(
                    rule_id="FTP_MFA_EXCEPTION_CONTRADICTED",
                    status=ValidationStatus.BLOCK,
                    severity=ValidationSeverity.MEDIUM,
                    section_name=section_name,
                    offending_text=tnorm[:200],
                    explanation="Universal MFA claimed without acknowledging the FTP MFA exception.",
                    required_action="rewrite",
                )
            )
        # Microsoft Defender email asserted without evidence
        if ("microsoft defender" in ltext) and ("microsoft defender" not in known_controls):
            issues.append(
                ValidationIssue(
                    rule_id="MICROSOFT_DEFENDER_EMAIL_ASSERTED",
                    status=ValidationStatus.BLOCK,
                    severity=ValidationSeverity.LOW,
                    section_name=section_name,
                    offending_text=tnorm[:200],
                    explanation="Microsoft Defender asserted as current email control without adjudicated evidence.",
                    required_action="rewrite",
                )
            )
        # Azure dependency asserted without approval (Google context)
        if (" azure " in ltext) and any(("google workspace" in n) for n in entities_lower):
            issues.append(
                ValidationIssue(
                    rule_id="AZURE_DEPENDENCY_ASSERTED",
                    status=ValidationStatus.BLOCK,
                    severity=ValidationSeverity.LOW,
                    section_name=section_name,
                    offending_text=tnorm[:200],
                    explanation="Azure dependency asserted in Google‑centric evidence context.",
                    required_action="rewrite",
                )
            )
        # Tested IR plan assertion
        if ("tested incident response" in ltext) or ("tested ir plan" in ltext):
            issues.append(
                ValidationIssue(
                    rule_id="TESTED_IR_PLAN_ASSERTED",
                    status=ValidationStatus.BLOCK,
                    severity=ValidationSeverity.LOW,
                    section_name=section_name,
                    offending_text=tnorm[:200],
                    explanation="Tested incident response plan asserted without adjudicated confirmation.",
                    required_action="rewrite",
                )
            )
        # Numeric RTO/RPO assertion without evidence
        import re as _re_rr
        if _re_rr.search(r"\bRTO\b\s*[:=]?\s*\d", tnorm) or _re_rr.search(r"\bRPO\b\s*[:=]?\s*\d", tnorm):
            issues.append(
                ValidationIssue(
                    rule_id="NO_NUMERIC_RTO_RPO_WITHOUT_EVIDENCE",
                    status=ValidationStatus.BLOCK,
                    severity=ValidationSeverity.LOW,
                    section_name=section_name,
                    offending_text=tnorm[:200],
                    explanation="Numeric RTO/RPO asserted without confirmed evidence.",
                    required_action="rewrite",
                )
            )
    except Exception:
        pass

    # Rule: Financial constraints — block quantified costs if planning_assumptions_only
    try:
        if getattr(ctx.financial_profile, "planning_assumptions_only", True):
            import re

            if re.search(r"\b(£|GBP|USD|EUR)\s?\d", tnorm):
                issues.append(
                    ValidationIssue(
                        rule_id="NO_CONCRETE_COSTS_WITHOUT_EVIDENCE",
                        status=ValidationStatus.BLOCK,
                        severity=ValidationSeverity.MEDIUM,
                        section_name=section_name,
                        offending_text=tnorm[:200],
                        explanation="Quantified financial outputs are not permitted without approved financial evidence profile.",
                        required_action="rewrite",
                    )
                )
    except Exception:
        pass

    # Rule: Scenario constraints — block named threat actors/CVEs unless allowed
    try:
        if not getattr(ctx.scenario_profile, "allow_named_threat_actors", False):
            if any(x in ltext for x in (" apt ", "lazarus", "conti", "lockbit", "fin7", "wizard spider")):
                issues.append(
                    ValidationIssue(
                        rule_id="SCENARIO_THREAT_ACTOR_NOT_APPROVED",
                        status=ValidationStatus.BLOCK,
                        severity=ValidationSeverity.LOW,
                        section_name=section_name,
                        offending_text=tnorm[:200],
                        explanation="Named threat actors are not approved by the scenario profile.",
                        required_action="rewrite",
                    )
                )
        if not getattr(ctx.scenario_profile, "allow_specific_cves", False):
            import re

            if re.search(r"\bCVE-\d{4}-\d{4,7}\b", tnorm, flags=re.IGNORECASE):
                issues.append(
                    ValidationIssue(
                        rule_id="SCENARIO_CVE_NOT_APPROVED",
                        status=ValidationStatus.BLOCK,
                        severity=ValidationSeverity.LOW,
                        section_name=section_name,
                        offending_text=tnorm[:200],
                        explanation="Specific CVEs are not approved by the scenario profile.",
                        required_action="rewrite",
                    )
                )
        # MITRE technique tethering: require confirmed attack paths before asserting technique tokens
        if not getattr(ctx.scenario_profile, "has_confirmed_attack_paths", False):
            if any(tok in ltext for tok in ("t1566.002", "t1078", "t1539", "t1087", "t1114", "t1530", "t1134", "t1570", "t1021", "t1560", "t1486")):
                issues.append(
                    ValidationIssue(
                        rule_id="SCENARIO_TECHNIQUE_NOT_TETHERED",
                        status=ValidationStatus.BLOCK,
                        severity=ValidationSeverity.LOW,
                        section_name=section_name,
                        offending_text=tnorm[:200],
                        explanation="Attack techniques referenced without confirmed attack paths; require linkage to adjudicated assets/exposures.",
                        required_action="rewrite",
                    )
                )
    except Exception:
        pass

    # Additional blocking rules (high-value subset)
    try:
        import re as _re_v
        # Unapproved vendor references (narrative-wide)
        if _re_v.search(r"\b(adlumin)\b", ltext):
            issues.append(
                ValidationIssue(
                    rule_id="UNAPPROVED_VENDOR",
                    status=ValidationStatus.BLOCK,
                    severity=ValidationSeverity.LOW,
                    section_name=section_name,
                    offending_text=tnorm[:200],
                    explanation="Vendor reference not in approved entities/catalogue.",
                    required_action="rewrite",
                )
            )
        # Insider scenario not approved
        if not getattr(ctx.scenario_profile, "allow_insider_threat", False):
            if any(tok in ltext for tok in ("insider threat", "malicious insider", "privileged insider", "internal threat actor")):
                issues.append(
                    ValidationIssue(
                        rule_id="INSIDER_SCENARIO_NOT_APPROVED",
                        status=ValidationStatus.BLOCK,
                        severity=ValidationSeverity.LOW,
                        section_name=section_name,
                        offending_text=tnorm[:200],
                        explanation="Insider threat scenario elements not approved by the scenario profile.",
                        required_action="rewrite",
                    )
                )
        # Generic fallback content patterns
        generic_markers = [
            "gap: missing policies or controls",
            "gap: coverage limited or untested",
            "enable baseline hardening with native controls",
            "apply configuration baselines and periodic reviews",
            "deploy consultative improvements aligned to risk and operational context",
            "adopt monitoring and validation to reduce dwell time",
            "integrate governance cadence to sustain improvements",
            # Compliance boilerplate clones
            "document scope, owners and acceptance criteria",
            "schedule validation test and governance review",
            "retain artefacts for auditability",
        ]
        if any(gm in ltext for gm in generic_markers):
            issues.append(
                ValidationIssue(
                    rule_id="GENERIC_FALLBACK_CONTENT",
                    status=ValidationStatus.BLOCK,
                    severity=ValidationSeverity.LOW,
                    section_name=section_name,
                    offending_text=tnorm[:200],
                    explanation="Generic boilerplate content detected; requires evidence-led specificity.",
                    required_action="rewrite",
                )
            )
        # Truncated content heuristics
        if any(ltext.strip().endswith(suf) for suf in ("dilute.", "to.", "involving.", "to address.", "leaves.")):
            issues.append(
                ValidationIssue(
                    rule_id="TRUNCATED_CONTENT",
                    status=ValidationStatus.BLOCK,
                    severity=ValidationSeverity.LOW,
                    section_name=section_name,
                    offending_text=tnorm[:200],
                    explanation="Content appears truncated/incomplete.",
                    required_action="rewrite",
                )
            )
    except Exception:
        pass

    status = ValidationStatus.PASS
    if any(i.status == ValidationStatus.BLOCK for i in issues):
        status = ValidationStatus.BLOCK
    elif any(i.status == ValidationStatus.WARNING for i in issues):
        status = ValidationStatus.WARNING

    return SectionValidationResult(section_name=section_name, status=status, issues=issues)


def enforce_report(
    original_report: Dict[str, Any],
    improved_report: Dict[str, Any],
    adjudication: EvidenceAdjudicationResult,
) -> Tuple[Dict[str, Any], ReportValidationResult]:
    """
    Deterministic enforcement + bounded auto-revision loop (revision loop stubbed for now).
    Fail closed: on persistent blocking errors, retain original section and flag human review.
    """
    ctx = _build_context(adjudication)
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
    section_results: List[SectionValidationResult] = []
    final_report = dict(improved_report or {})
    try:
        max_retries = int(get_config(ConfigKey.EVIDENCE_ENFORCEMENT_MAX_RETRIES, "1") or "1")
    except Exception:
        max_retries = 1

    for name in section_names:
        content = final_report.get(name)
        if content is None:
            continue
        # Convert to text for deterministic content validation; structured validators can be added per section later
        text = content if isinstance(content, str) else str(content)
        res = _validate_section_text(name, text, ctx)
        tries = 0
        while res.has_blocking_errors and tries < max_retries:
            tries += 1
            res.retry_count = tries
            # Deterministic controlled revision and revalidation (bounded)
            try:
                from services.report_improvement.evidence_enforcement.revision import revise_section_from_validation_errors  # type: ignore
                import asyncio
                try:
                    revised = asyncio.run(revise_section_from_validation_errors(
                        section_name=name,
                        original_section=str(original_report.get(name) or ""),
                        rejected_content=text,
                        issues=res.issues,
                        context=ctx,
                    ))
                except RuntimeError:
                    # Event loop already running (e.g., Streamlit); skip revision to avoid runtime error
                    revised = None
                if revised and getattr(revised, "revised_content", None):
                    text = revised.revised_content
            except Exception:
                # Non-fatal; keep previous text
                pass
            res = _validate_section_text(name, text, ctx)

        # Fail-closed on persistent blocking errors: validate original; preserve BLOCK; set workflow flags
        if res.has_blocking_errors:
            orig = original_report.get(name)
            if orig is not None:
                orig_text = orig if isinstance(orig, str) else str(orig)
                orig_res = _validate_section_text(name, orig_text, ctx)
                if not orig_res.has_blocking_errors and orig_res.status != ValidationStatus.BLOCK:
                    final_report[name] = orig
                    orig_res.human_review_required = True
                    orig_res.automatic_publication_allowed = False
                    orig_res.used_original_content = True
                    section_results.append(orig_res)
                    continue
            # Neither candidate nor original passed — preserve BLOCK
            res.status = ValidationStatus.BLOCK
            res.human_review_required = True
            res.automatic_publication_allowed = False
        section_results.append(res)

    overall_status = ValidationStatus.PASS
    if any(r.status == ValidationStatus.HUMAN_REVIEW for r in section_results):
        overall_status = ValidationStatus.HUMAN_REVIEW
    elif any(r.status == ValidationStatus.BLOCK for r in section_results):
        overall_status = ValidationStatus.BLOCK
    elif any(r.status == ValidationStatus.WARNING for r in section_results):
        overall_status = ValidationStatus.WARNING

    rv = ReportValidationResult(
        status=overall_status,
        section_results=section_results,
        cross_section_issues=[],
        publication_issues=[],
        automatic_publication_allowed=(overall_status == ValidationStatus.PASS),
        human_review_required=(overall_status in (ValidationStatus.BLOCK, ValidationStatus.HUMAN_REVIEW)),
    )
    return final_report, rv