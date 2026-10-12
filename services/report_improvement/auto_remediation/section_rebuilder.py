from __future__ import annotations
from services.report_improvement.auto_remediation.models import EGRevisedSection, RevisedDomainAssessment

# Phase 2 scaffold for section-level rebuilds.
# These functions will be wired into the orchestrator as a final pass after evidence-grounded rewrites.
# They MUST produce conservative, evidence-aligned outputs and will always be deterministically revalidated.


async def rebuild_attack_scenario(profile, evidence_ctx) -> EGRevisedSection:
    """
    Evidence-led rebuild with strict constraints (no named actors/CVEs/tools; no guarantees).
    Deterministic structure assembled from approved inputs only; unknowns are labelled as planning assumptions.
    """
    try:
        aai = getattr(evidence_ctx, "approved_attack_inputs", None)
        crown = list(getattr(aai, "confirmed_crown_jewels", []) or [])
        techs = list(getattr(aai, "confirmed_technologies", []) or [])
        paths = list(getattr(aai, "confirmed_attack_paths", []) or [])
    except Exception:
        crown, techs, paths = [], [], []

    disclaimer = (
        "Scenario disclaimer: This narrative is constructed for planning purposes from approved evidence only. "
        "It avoids prohibited specifics (named actors, CVEs, tools) and does not assume guaranteed defensive outcomes."
    )

    if paths:
        initial = f"Initial access (approved): {str(paths[0])}."
    else:
        initial = "Initial access (planning assumption): An externally accessible service or identity route will be confirmed."

    if techs:
        prog = "Progression through approved systems only: " + ", ".join([str(t) for t in techs]) + "."
    else:
        prog = "Progression through approved systems only will be defined once system scope is confirmed."

    if crown:
        impact = "Impact focuses on approved crown jewels/business processes: " + ", ".join([str(c) for c in crown]) + "."
    else:
        impact = "Impact targets approved crown jewels/business processes once confirmed."

    detect = (
        "Existing controls may detect or constrain activity; confirm coverage and operational integration. "
        "No guaranteed containment is assumed."
    )
    response = (
        "Response and recovery: Validate escalation arrangements, containment authority and representative restore testing."
    )
    recs = (
        "Recommendations: Prioritise scope confirmation, telemetry quality, containment authority and recovery readiness. "
        "Assess managed monitoring options separately where relevant."
    )

    revised_content = "\n\n".join([disclaimer, initial, prog, impact, detect, response, recs]).strip()

    return EGRevisedSection(
        section_name="threat_scenarios",
        revised_content=revised_content,
        addressed_rule_ids=[],
        unresolved_rule_ids=[],
        evidence_ids_used=[],
        named_entities_used=[],
        recommendations_used=[],
    )


async def rebuild_domain_assessment(domain_name: str, domain_evidence, context) -> RevisedDomainAssessment:
    """
    Conservative, evidence-led rebuild for a domain. Unknowns become validation requirements.
    Existing controls are recognised as strengths. No invented gaps or systems are introduced.
    """
    # Extract minimal signals; implementations consuming richer structured evidence can extend this safely.
    strengths = []
    gaps = []
    validation_reqs = []
    recs = []
    evidence_ids = []

    try:
        # domain_evidence may provide existing controls, confirmed gaps and references
        for ec in getattr(domain_evidence, "existing_controls", []) or []:
            name = str(getattr(ec, "control_name", "") or "").strip()
            if name:
                strengths.append(name)
        for g in getattr(domain_evidence, "confirmed_gaps", []) or []:
            txt = str(getattr(g, "text", "") or "").strip()
            if txt:
                gaps.append(txt)
                try:
                    evidence_ids.extend([str(e) for e in (getattr(g, "evidence_ids", []) or [])])
                except Exception:
                    pass
        for u in getattr(domain_evidence, "unknowns", []) or []:
            txt = str(getattr(u, "text", "") or "").strip()
            if txt:
                validation_reqs.append(txt)
    except Exception:
        pass

    # Partnership text specific to actions (avoid repeated generic phrasing)
    partnership = (
        f"Partnership focus for {domain_name}: align actions to confirmed strengths and validated gaps, "
        "with measurable outcomes and explicit ownership."
    )

    # Limited-assurance message if evidence is insufficient
    if not strengths and not gaps:
        maturity_rationale = (
            "The consultation did not provide sufficient evidence to assign a confident maturity position for this domain. "
            "Immediate priority is to confirm ownership, documented process, technical coverage and retained assurance evidence."
        )
    else:
        maturity_rationale = (
            "Maturity position reflects current strengths and evidence-backed gaps. Unknown items require validation before further conclusions."
        )

    return RevisedDomainAssessment(
        domain_name=domain_name,
        current_maturity="",
        maturity_rationale=maturity_rationale,
        technical_analysis="",
        business_impact_and_risk="",
        confirmed_strengths=strengths,
        confirmed_gaps=gaps,
        validation_requirements=validation_reqs,
        zero_cost_quick_wins=[],
        recommended_solutions=recs,
        strategic_rationale="",
        partnership_recommendation=partnership,
        evidence_ids_used=evidence_ids,
    )
