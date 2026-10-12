from __future__ import annotations

"""
Executive Summary Specialist Generator (deterministic, evidence-grounded)

Produces ExecutiveSummaryOutput from SpecialistSectionInput with the following constraints:
- Customer-specific context from adjudicated evidence only.
- Recognises existing controls (3–6 items) without converting recommendations into strengths.
- Priority gaps (3–5) must be evidenced (confirmed/contradicted claims).
- Board-level takeaway and strategic direction use proportionate business language.
- MDR positioning included only when evidence supports a monitoring/response/out-of-hours requirement.
- Unknowns are treated as validation requirements; do not present unknowns as failures.
"""

from typing import List, Optional

from services.report_improvement.section_generators.models import (  # type: ignore
    SpecialistSectionInput,
    ExecutiveSummaryOutput,
    SectionGenerationMetadata,
    GeneratedClaim,
)
from services.report_improvement.evidence_enforcement.models import (  # type: ignore
    ExistingControlRecord,
    ApprovedGapRecord,
)
from services.report_improvement.evidence_adjudicator import (  # type: ignore
    EvidenceClaim,
    CustomerPriority,
    KnownUnknown,
)
# Diagnostics lineage (env‑gated; non-invasive)
try:
    from services.report_improvement.lineage import (  # type: ignore
        is_diagnostics_enabled,
        ensure_run_id,
        SectionLineageTrace,
        record_stage_hash,
        write_lineage_trace,
    )
except Exception:  # safe no-ops if lineage utilities unavailable
    def is_diagnostics_enabled() -> bool:
        return False
    def ensure_run_id() -> str:
        return ""
    class SectionLineageTrace:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass
    def record_stage_hash(*args, **kwargs):
        return None
    def write_lineage_trace(*args, **kwargs):
        return None


def _assessment_context_text() -> str:
    return (
        "This consultant-led assessment provides a point-in-time view based on the information supplied. "
        "It is not a certification or an independent technical validation."
    )


def _business_overview_text(si: SpecialistSectionInput) -> str:
    # Compose a succinct overview using canonical environment fields and priorities.
    env = si.canonical_environment
    parts: List[str] = []
    if env.industries:
        parts.append(f"The organisation operates within {env.industries[0]}.")
    if env.locations:
        parts.append(f"Operations span {', '.join(env.locations[:3])}.")
    if env.services:
        parts.append(f"Critical services include {', '.join(env.services[:3])}.")
    if env.crown_jewels:
        parts.append(f"Low-tolerance dependencies include {', '.join(env.crown_jewels[:3])}.")
    if not parts:
        parts.append("The consultation identified critical services and dependencies requiring validation.")
    return " ".join(parts)


def _controls_to_strengths(ctrls: List[ExistingControlRecord]) -> List[str]:
    out: List[str] = []
    seen = set()
    for c in (ctrls or []):
        for p in (c.products or [])[:1]:
            name = str(p).strip()
            if name and name.lower() not in seen:
                seen.add(name.lower())
                out.append(name)
            if len(out) >= 6:
                break
        if len(out) >= 6:
            break
    return out


def _gaps_from_approved(gaps: List[ApprovedGapRecord], max_items: int = 5) -> List[str]:
    out: List[str] = []
    seen = set()
    for g in (gaps or []):
        s = str(getattr(g, "statement", "")).strip()
        if not s:
            continue
        k = s.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(s)
        if len(out) >= max_items:
            break
    return out


def _priorities_from_customer(prs: List[CustomerPriority]) -> List[str]:
    out: List[str] = []
    seen = set()
    for p in (prs or []):
        name = str(getattr(p, "priority", "")).strip()
        if not name:
            continue
        k = name.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(name)
        if len(out) >= 5:
            break
    return out


def _security_posture_narrative(si: SpecialistSectionInput, strengths: List[str], gaps: List[str]) -> str:
    # Short, balanced narrative that recognises strengths and identifies assurance/prioritisation needs.
    parts: List[str] = []
    if strengths:
        parts.append(f"Existing investments such as {', '.join(strengths[:3])} provide a foundation.")
    if gaps:
        parts.append(f"Assurance gaps include {', '.join(gaps[:3])}, prioritised according to operational impact.")
    if not parts:
        parts.append("Evidence indicates a mixed position requiring targeted validation and proportionate uplift.")
    return " ".join(parts)


def _board_takeaway(si: SpecialistSectionInput, gaps: List[str]) -> str:
    # Customer-specific direction using evidence.
    if gaps:
        return (
            "Prioritise validation of current control operation, strengthen identity and recovery assurance, and "
            "formalise response readiness based on the most material gaps."
        )
    return "Validate current control operation and confirm governance cadence to sustain improvements."


def _strategic_direction_text(si: SpecialistSectionInput) -> str:
    return (
        "Validate, strengthen and test existing controls before considering replacement. "
        "Formalise ownership, extend monitoring coverage where appropriate, and sequence remediation according to business dependencies."
    )


def _mdr_positioning(si: SpecialistSectionInput, strengths: List[str]) -> Optional[str]:
    # Include MDR positioning only if existing controls indicate MDR or priorities imply response/out-of-hours needs.
    has_mdr = any("mdr" in s.lower() for s in strengths)
    needs_response = any(p.priority in ("Operational Concern", "Downtime Concern", "Recovery Concern") for p in (si.customer_priorities or []))
    if not (has_mdr or needs_response):
        return None
    return (
        "Monitoring and response should be validated against current telemetry and authority. "
        "Selection requires evidence of coverage and integration dependencies, and alignment with existing endpoint and network tooling."
    )


def _evidence_limitations_text(si: SpecialistSectionInput, kus: List[KnownUnknown]) -> str:
    if si.evidence_quality == "limited":
        return "Evidence was limited; several areas require validation before firm conclusions are drawn."
    if kus:
        return "Unknowns are recorded as validation requirements and will be clarified during subsequent discovery."
    return "This summary reflects the supplied evidence and prioritises validation where information is incomplete."


def _metadata(si: SpecialistSectionInput, strengths: List[str], gaps: List[str], priorities: List[str]) -> SectionGenerationMetadata:
    claims: List[GeneratedClaim] = []
    # Map strengths to claims referencing existing control placeholders
    for s in strengths:
        claims.append(
            GeneratedClaim(
                claim_text=f"Existing control recognised: {s}",
                claim_type="fact",
                evidence_ids=[f"ctrl:{s}"],
                confidence="medium",
            )
        )
    for g in gaps:
        claims.append(
            GeneratedClaim(
                claim_text=f"Priority gap identified: {g}",
                claim_type="consultant_judgement",
                evidence_ids=[f"gap:{abs(hash(g))}"],
                confidence="low",
            )
        )
    for p in priorities:
        claims.append(
            GeneratedClaim(
                claim_text=f"Customer priority: {p}",
                claim_type="customer_statement",
                evidence_ids=[f"priority:{p}"],
                confidence="medium",
            )
        )
    return SectionGenerationMetadata(
        section_name="executive_summary",
        generated_claims=claims[:50],
        existing_controls_recognised=strengths[:],
        confirmed_gaps_used=gaps[:],
        known_unknowns_used=[str(getattr(ku, "statement", "")) for ku in (si.known_unknowns or [])][:10],
        recommendations_used=[],
        evidence_limitations_disclosed=[],
    )


def generate_executive_summary(si: SpecialistSectionInput) -> ExecutiveSummaryOutput:
    # A. Assessment context (required)
    assessment_context = _assessment_context_text()
    # B. Customer business context
    business_overview = _business_overview_text(si)
    # C. Existing security foundation (3–6 evidenced controls)
    strengths = _controls_to_strengths(si.existing_controls)
    # D. Priority assurance and improvement areas (3–5)
    priority_gaps = _gaps_from_approved(si.confirmed_gaps, max_items=5)
    # Business priorities (evidenced)
    priorities = _priorities_from_customer(si.customer_priorities)
    # Security posture narrative
    security_posture = _security_posture_narrative(si, strengths, priority_gaps)
    # Board-level direction and strategic direction
    board_takeaway = _board_takeaway(si, priority_gaps)
    strategic_direction = _strategic_direction_text(si)
    # MDR positioning (conditional)
    mdr_pos = _mdr_positioning(si, strengths)
    # Evidence limitations
    ev_limitations = _evidence_limitations_text(si, si.known_unknowns or [])
    # Metadata (internal traceability)
    md = _metadata(si, strengths, priority_gaps, priorities)

    out = ExecutiveSummaryOutput(
        assessment_context=assessment_context,
        business_overview=business_overview,
        security_posture_narrative=security_posture,
        key_strengths=strengths[:6],
        priority_gaps=priority_gaps[:5],
        business_priorities=priorities[:5],
        board_level_takeaway=board_takeaway,
        strategic_direction=strategic_direction,
        mdr_positioning=mdr_pos,
        evidence_limitations=ev_limitations,
        metadata=md,
    )
    # Diagnostics: inject sentinel token and record generator-stage lineage (diagnostic mode only)
    try:
        if is_diagnostics_enabled():
            _rid = ensure_run_id()
            try:
                # Inject a runtime-only marker into a safe text field within the specialist output
                out.assessment_context = f"{out.assessment_context}\nTRACE_EXEC_{_rid}".strip()
            except Exception:
                pass
            try:
                _payload = out.model_dump() if hasattr(out, "model_dump") else out
                _trace = SectionLineageTrace(run_id=_rid, section_name="executive_summary")
                record_stage_hash(_trace, "generator", _payload)
                write_lineage_trace(_trace)
            except Exception:
                pass
    except Exception:
        pass
    return out
