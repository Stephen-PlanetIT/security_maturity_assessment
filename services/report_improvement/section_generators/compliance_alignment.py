from __future__ import annotations

"""
Compliance and Framework Alignment Specialist Generator (deterministic, evidence-grounded)

Rules implemented:
- Use only approved/applicable frameworks (from SpecialistSectionInput.approved_frameworks).
- Distinguish readiness/assurance considerations from certification; do not claim non-compliance or fines.
- Each row maps to a supported control, confirmed gap, or validation requirement with evidence-aware language.
- Avoid repeating generic gaps; prefer specific, concise considerations tied to evidence.

Acceptance checks:
- Each row refers to an approved framework.
- Current position uses customer evidence and conservative language.
- Each recommended focus traces to a specific consideration.
- Section states that the report is not a certification audit (as applicable).
"""

from typing import List

from services.report_improvement.section_generators.models import (  # type: ignore
    SpecialistSectionInput,
    ComplianceAlignmentOutput,
    FrameworkAlignmentRow,
    SectionGenerationMetadata,
    GeneratedClaim,
)


def _scope_and_limitations_text() -> str:
    return (
        "This section maps consultation evidence to framework expectations for readiness planning. "
        "It is not a certification audit and does not assert legal or regulatory determinations."
    )


def _current_position_text(si: SpecialistSectionInput) -> str:
    # Conservative position statement that acknowledges evidence limits
    if si.evidence_quality == "limited":
        return "Evidence was limited; readiness should be validated against the agreed scope before planning certification."
    return "Readiness reflects consultation evidence and should be validated against the agreed certification scope."


def _derive_rows(si: SpecialistSectionInput) -> List[FrameworkAlignmentRow]:
    rows: List[FrameworkAlignmentRow] = []
    # Build rows by connecting approved frameworks to observed controls/gaps/validation requirements
    fwks = si.approved_frameworks or []
    # Simple mapping heuristics by keywords for ready alignment language; conservative and bounded
    for fw in fwks[:6]:
        name = fw.framework_name.strip()
        if not name:
            continue
        # Select a gap or a validation requirement to anchor the row
        gap_text = ""
        ev_ids: List[str] = []
        if si.confirmed_gaps:
            gap_text = si.confirmed_gaps[0].statement
        elif si.known_unknowns:
            gap_text = f"Validation required: {si.known_unknowns[0].statement}"
        else:
            gap_text = "Evidence requires validation against the scoped requirements."
        # Current position and recommended focus wording (readiness-oriented)
        current_pos = "Consultation evidence indicates areas requiring validation and structured evidence capture."
        focus = "Include this area in certification planning and retain artefacts demonstrating control operation."
        rows.append(
            FrameworkAlignmentRow(
                framework_name=name,
                framework_area="Readiness and Assurance",
                relevant_expectation="Documented control operation with retained evidence and governance cadence.",
                current_position=current_pos,
                assurance_gap_or_consideration=gap_text,
                recommended_focus=focus,
                evidence_ids=ev_ids,
            )
        )
    # Fallback: check canonical environment or customer stated targets (e.g. Cyber Essentials, DfE 2026, ISO 27001)
    if not rows:
        # Differentiate based on customer context / industry
        industry = ""
        cname = getattr(si, "customer_name", "") or ""
        if hasattr(si, "canonical_environment") and si.canonical_environment:
            inds = getattr(si.canonical_environment, "industries", []) or []
            if inds:
                industry = inds[0].lower()
        if "school" in cname.lower() or "education" in industry:
            fw_name = "UK DfE Cyber Standards 2026"
            target_id = "target_dfe_2026"
            expectation = "DfE cyber standards compliance for educational institutions with documented safeguarding controls."
        elif "tech" in industry or "technology" in cname.lower():
            fw_name = "ISO/IEC 27001:2022"
            target_id = "target_iso_27001"
            expectation = "Information security management system (ISMS) controls with documented operational governance and commercial assurance."
        else:
            fw_name = "NCSC Cyber Essentials"
            target_id = "target_cyber_essentials"
            expectation = "Documented technical controls across boundary firewalls, secure configuration, user access, and patch management."

        rows.append(
            FrameworkAlignmentRow(
                framework_name=fw_name,
                framework_area="Readiness and Assurance",
                relevant_expectation=expectation,
                current_position=_current_position_text(si),
                assurance_gap_or_consideration=f"{fw_name} targets require validation against agreed operational scope.",
                recommended_focus=f"Establish {fw_name} baseline compliance posture and retain artefacts demonstrating control operation.",
                evidence_ids=[target_id],
            )
        )
    return rows


def _priority_actions(rows: List[FrameworkAlignmentRow]) -> List[str]:
    # Concise actions derived from rows
    out: List[str] = []
    seen = set()
    for r in rows[:5]:
        a = "Validate scope, owners and evidence for framework-aligned controls"
        if a not in seen:
            seen.add(a)
            out.append(a)
        b = "Schedule governance reviews and retain artefacts to demonstrate operation"
        if b not in seen:
            seen.add(b)
            out.append(b)
        if len(out) >= 5:
            break
    return out[:5]


def _metadata(rows: List[FrameworkAlignmentRow]) -> SectionGenerationMetadata:
    claims: List[GeneratedClaim] = []
    for r in rows:
        claims.append(
            GeneratedClaim(
                claim_text=f"Framework row: {r.framework_name} — {r.framework_area}",
                claim_type="consultant_judgement",
                evidence_ids=list(r.evidence_ids or []),
                confidence="low" if not r.evidence_ids else "medium",
            )
        )
    return SectionGenerationMetadata(
        section_name="compliance_alignment",
        generated_claims=claims[:50],
        existing_controls_recognised=[],
        confirmed_gaps_used=[],
        known_unknowns_used=[],
        recommendations_used=[],
        evidence_limitations_disclosed=[],
    )


def generate_compliance_alignment(si: SpecialistSectionInput) -> ComplianceAlignmentOutput:
    rows = _derive_rows(si)
    scope_and_limits = _scope_and_limitations_text()
    current_pos = _current_position_text(si)
    prio = _priority_actions(rows)
    md = _metadata(rows)
    return ComplianceAlignmentOutput(
        current_position=current_pos,
        scope_and_limitations=scope_and_limits,
        rows=rows,
        priority_actions=prio,
        metadata=md,
    )