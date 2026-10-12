from __future__ import annotations

"""
Quality checks and coherence validation for specialist section outputs.

Scope (Phase 3/4 scaffolding):
- Lightweight, deterministic acceptance checks for specialist sections
- Cross‑section coherence validator (initial placeholder; expanded in Phase 4)
- Generic content heuristics (conservative; used to avoid replacing non‑generic content)

Notes:
- This module intentionally avoids introducing new BaseModels to keep footprint small.
- Deterministic only: no model calls, no external IO.
"""

from typing import List, Tuple

from services.report_improvement.section_generators.models import (  # type: ignore
    ExecutiveSummaryOutput,
    SecurityRatingOutput,
    AttackScenarioOutput,
    ComplianceAlignmentOutput,
    CostOfInactionOutput,
    DomainAssessmentOutput,
    CrossSectionNarrativeMap,
)


def is_generic(text: str) -> bool:
    """
    Conservative heuristic to detect obviously generic placeholders.
    Returns True when multiple tell‑tale placeholders are present.
    """
    if not text:
        return True
    lower = text.lower()
    generic_markers = [
        "insert",
        "placeholder",
        "lorem ipsum",
        "to be confirmed",
        "tbc",
        "generic",
        "sample",
    ]
    count = sum(1 for m in generic_markers if m in lower)
    return count >= 2


def check_executive_summary_acceptance(es: ExecutiveSummaryOutput) -> List[str]:
    """
    Deterministic acceptance checks for Executive Summary per spec (subset):
    1. Customer business context appears early (approximate by non‑empty business_overview).
    2. At least two strengths if evidence supports (we check len(key_strengths) >= 2).
    3. Each priority gap is non‑empty (basic guard).
    4. Board‑level takeaway present and non‑generic.
    5. Unknowns are not presented as failures (basic guard via evidence_limitations wording).
    6. MDR positioning is linked to requirement (presence allowed but not mandatory).
    """
    issues: List[str] = []
    # 1: Business context
    if not es.business_overview or len(es.business_overview.strip()) < 20:
        issues.append("ES_BUSINESS_CONTEXT_MISSING")
    # 2: Strengths (if provided)
    if es.key_strengths is not None and len(es.key_strengths) > 0 and len(es.key_strengths) < 2:
        issues.append("ES_TOO_FEW_STRENGTHS")
    # 3: Priority gaps non‑empty
    for g in (es.priority_gaps or []):
        if not g or not g.strip():
            issues.append("ES_EMPTY_PRIORITY_GAP")
            break
    # 4: Board‑level takeaway
    if not es.board_level_takeaway or len(es.board_level_takeaway.strip()) < 10:
        issues.append("ES_BOARD_TAKEAWAY_WEAK")
    # 5: Evidence limitations present
    if not es.evidence_limitations or len(es.evidence_limitations.strip()) < 10:
        issues.append("ES_EVIDENCE_LIMITATIONS_WEAK")
    return issues


def check_security_rating_acceptance(sr: SecurityRatingOutput) -> List[str]:
    """
    Security Rating acceptance checks (deterministic arithmetic assumed correct by generator):
    - Overall score equals sum of domain contributions (approximate by tolerance 0.01).
    - Primary strengths are controls/practices (ensured upstream; here we only check presence when evidence suggests).
    """
    issues: List[str] = []
    try:
        total = sum((d.weighted_contribution for d in (sr.domain_scores or [])), 0)
        if round(float(total) - float(sr.overall_score), 2) != 0.0:
            issues.append("SR_OVERALL_SCORE_MISMATCH")
    except Exception:
        issues.append("SR_OVERALL_SCORE_MISMATCH")
    return issues


def check_attack_scenario_acceptance(asr: AttackScenarioOutput) -> List[str]:
    """
    Attack Scenario acceptance checks (subset):
    - MITRE list capped and non‑empty
    - No empty core narrative fields
    """
    issues: List[str] = []
    if not asr.relevant_mitre_techniques or len(asr.relevant_mitre_techniques) > 8:
        issues.append("SCENARIO_MITRE_LIST_INVALID")
    core_fields = [
        asr.disclaimer,
        asr.scenario_title,
        asr.initial_access,
        asr.progression,
        asr.business_impact,
        asr.detection_opportunities,
        asr.containment_considerations,
        asr.recovery_considerations,
    ]
    if any((not f or not f.strip()) for f in core_fields):
        issues.append("SCENARIO_CORE_FIELDS_MISSING")
    return issues


def check_compliance_alignment_acceptance(ca: ComplianceAlignmentOutput) -> List[str]:
    """
    Compliance acceptance checks (subset):
    - Scope/limitations statement present (non‑audit)
    - Each row has framework name and a recommended focus
    """
    issues: List[str] = []
    if not ca.scope_and_limitations or "not a certification audit" not in ca.scope_and_limitations.lower():
        issues.append("CA_SCOPE_LIMITATIONS_WEAK")
    for r in (ca.rows or []):
        if not r.framework_name or not r.recommended_focus:
            issues.append("CA_ROW_MISSING_FIELDS")
            break
    return issues


def check_cost_of_inaction_acceptance(coi: CostOfInactionOutput) -> List[str]:
    """
    Cost of Inaction acceptance checks (subset):
    - No currency mentions unless quantified_narrative present
    - At least one cost driver
    """
    issues: List[str] = []
    qn = coi.quantified_narrative or ""
    ql = coi.qualitative_narrative or ""
    # Currency heuristic
    currency_tokens = ("£", "gbp", "usd", "eur")
    if any(tok in ql.lower() for tok in currency_tokens) and not qn:
        issues.append("COI_ILLEGAL_CURRENCY_IN_QUALITATIVE")
    if not coi.cost_drivers or len(coi.cost_drivers) == 0:
        issues.append("COI_NO_COST_DRIVERS")
    return issues


def check_domain_assessment_acceptance(da: DomainAssessmentOutput) -> List[str]:
    """
    Domain assessment acceptance checks (subset):
    - current_maturity and maturity_rationale present
    - strengths/gaps/validation lists may be empty but not contain empty entries
    """
    issues: List[str] = []
    if not da.current_maturity or not da.maturity_rationale:
        issues.append("DA_MATURITY_FIELDS_MISSING")
    for lst_name, lst in [
        ("DA_STRENGTHS_EMPTY_ENTRY", da.confirmed_strengths),
        ("DA_GAPS_EMPTY_ENTRY", da.confirmed_gaps),
        ("DA_VALIDATION_EMPTY_ENTRY", da.validation_requirements),
    ]:
        for item in (lst or []):
            if not item or not str(item).strip():
                issues.append(lst_name)
                break
    return issues


def build_cross_section_map(
    es: ExecutiveSummaryOutput | None,
    sr: SecurityRatingOutput | None,
    asr: AttackScenarioOutput | None,
    ca: ComplianceAlignmentOutput | None,
    coi: CostOfInactionOutput | None,
    domains: List[DomainAssessmentOutput] | None,
) -> CrossSectionNarrativeMap:
    """
    Construct a basic CrossSectionNarrativeMap from generated sections.
    Phase 4 will add richer extraction and validation logic.
    """
    primary_strengths: List[str] = []
    if sr and sr.primary_strengths:
        primary_strengths = list(sr.primary_strengths)
    primary_gaps: List[str] = []
    if sr and sr.primary_gaps:
        primary_gaps = list(sr.primary_gaps)
    approved_frameworks: List[str] = []
    if ca and ca.rows:
        approved_frameworks = list({r.framework_name for r in ca.rows if r.framework_name})
    cost_drivers: List[str] = []
    if coi and coi.cost_drivers:
        cost_drivers = [d.driver_name for d in coi.cost_drivers]
    scenario_priorities: List[str] = []
    if asr and asr.relevant_mitre_techniques:
        scenario_priorities = list(asr.relevant_mitre_techniques)

    return CrossSectionNarrativeMap(
        customer_profile_summary=(es.business_overview if es else ""),
        primary_strengths=primary_strengths,
        primary_gaps=primary_gaps,
        critical_findings=[],  # populated from validator in Phase 4
        approved_recommendations=[],  # populated in Phase 4
        roadmap_priorities=[],  # populated in Phase 4
        approved_frameworks=approved_frameworks,
        cost_drivers=cost_drivers,
        scenario_priorities=scenario_priorities,
    )


def validate_coherence(cs: CrossSectionNarrativeMap) -> List[str]:
    """
    Deterministic cross‑section coherence checks (Phase 4 subset):
    - CONTROL_BOTH_STRENGTH_AND_GAP: the same control appears in strengths and gaps
    - SCENARIO_TECHNIQUE_COUNT_EXCEEDED: >8 techniques listed
    - FRAMEWORK_NAME_EMPTY: any empty framework name present
    - DUPLICATE_COST_DRIVER: duplicated cost driver names
    - EMPTY_CUSTOMER_PROFILE_SUMMARY: missing exec overview proxy
    Notes:
    - This subset avoids false positives while still blocking obvious contradictions.
    - Rule IDs are stable strings suitable for validator/reporting.
    """
    issues: List[str] = []

    # Normalise helper
    def _norm_list(xs: List[str]) -> List[str]:
        try:
            return [x.strip().lower() for x in (xs or []) if x and str(x).strip()]
        except Exception:
            return []

    # 1) Same token present in strengths and gaps
    try:
        s_norm = set(_norm_list(cs.primary_strengths))
        g_norm = set(_norm_list(cs.primary_gaps))
        inter = s_norm.intersection(g_norm)
        if inter:
            issues.append("CONTROL_BOTH_STRENGTH_AND_GAP")
    except Exception:
        pass

    # 2) Scenario techniques cap
    try:
        if cs.scenario_priorities and len(cs.scenario_priorities) > 8:
            issues.append("SCENARIO_TECHNIQUE_COUNT_EXCEEDED")
    except Exception:
        pass

    # 3) Empty framework names
    try:
        if any((not f or not str(f).strip()) for f in (cs.approved_frameworks or [])):
            issues.append("FRAMEWORK_NAME_EMPTY")
    except Exception:
        pass

    # 4) Duplicate cost drivers
    try:
        seen = set()
        dups = False
        for d in (cs.cost_drivers or []):
            key = (d or "").strip().lower()
            if not key:
                continue
            if key in seen:
                dups = True
                break
            seen.add(key)
        if dups:
            issues.append("DUPLICATE_COST_DRIVER")
    except Exception:
        pass

    # 5) Empty exec overview proxy
    try:
        if not cs.customer_profile_summary or not cs.customer_profile_summary.strip():
            issues.append("EMPTY_CUSTOMER_PROFILE_SUMMARY")
    except Exception:
        pass

    return issues


def map_coherence_issue_to_section(rule_id: str) -> str | None:
    """
    Deterministic mapping of coherence rule IDs to the responsible section for a single regeneration attempt.
    Conservative subset; extend only when a rule has a clear owner.
    """
    mapping = {
        "CONTROL_BOTH_STRENGTH_AND_GAP": "executive_summary",
        "EMPTY_CUSTOMER_PROFILE_SUMMARY": "executive_summary",
        "SCENARIO_TECHNIQUE_COUNT_EXCEEDED": "threat_scenarios",
        "FRAMEWORK_NAME_EMPTY": "compliance_alignment",
        "DUPLICATE_COST_DRIVER": "cost_of_inaction",
    }
    return mapping.get(rule_id)
