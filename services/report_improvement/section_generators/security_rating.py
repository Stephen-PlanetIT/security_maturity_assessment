from __future__ import annotations

"""
Deterministic Security Rating and Weighted Scoring

Implements:
- DomainScoreInput -> DomainScoreResult calculation (Python only)
- Overall SecurityRatingOutput assembly with deterministic arithmetic
- Assurance penalty (Capability Mismatch clamp) when supported by evidence
- Distinct, evidence-referenced rationales per domain
- Primary strengths/gaps derived from adjudicated evidence (controls/gaps only)
- Direction of travel policy

Notes:
- No LLM scoring; arithmetic is strictly in Python.
- Weights are normalised to sum to 100%; weighted contributions computed deterministically.
- Unknowns do not default a domain to zero; they are handled via evidence_coverage and flags.
- Recommendations cannot appear as strengths (enforced at source selection).
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, List, Tuple, Optional

from services.report_improvement.section_generators.models import (  # type: ignore
    DomainScoreInput,
    DomainScoreResult,
    SecurityRatingOutput,
    SectionGenerationMetadata,
    GeneratedClaim,
)
from services.report_improvement.evidence_enforcement.models import (  # type: ignore
    EvidenceEnforcementContext,
)
from services.report_improvement.evidence_adjudicator import (  # type: ignore
    EvidenceAdjudicationResult,
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

# Policy constants (configurable via environment in future iteration)
SCORING_POLICY_VERSION = "v1"
# Maturity bands configured for 1.0–3.0 scoring scale
# Defaults:
#   [1.0, <1.75) -> "Phase 1"
#   [1.75, <2.5) -> "Phase 2"
#   [2.5, 3.0] -> "Phase 3"
DEFAULT_BANDS: List[Tuple[Decimal, str]] = [
    (Decimal("2.50"), "Phase 3"),
    (Decimal("1.75"), "Phase 2"),
    (Decimal("1.00"), "Phase 1"),
]


def _normalise_weights(inputs: Iterable[DomainScoreInput]) -> List[Tuple[DomainScoreInput, Decimal]]:
    """
    Return list of (input, normalised_weight_percent) ensuring sum=100 exactly (as Decimal).
    Accepts configured_weight as percentage value; non-sensical values are clamped [0,100].
    """
    items = list(inputs or [])
    weights = []
    total = Decimal("0")
    for i in items:
        w = i.configured_weight
        try:
            if w < 0:
                w = Decimal("0")
        except Exception:
            w = Decimal("0")
        weights.append(w)
        total += w
    # Avoid divide-by-zero; distribute equally if total=0
    if total == 0:
        n = len(items) if items else 0
        if n == 0:
            return []
        eq = (Decimal("100") / Decimal(n)).quantize(Decimal("0.01"))
        return [(items[idx], eq) for idx in range(n)]
    # Rescale to 100%
    scaled = []
    for idx, i in enumerate(items):
        nw = (weights[idx] / total) * Decimal("100")
        scaled.append((i, nw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)))
    # Adjust final element to correct rounding drift
    acc = sum(w for _, w in scaled)
    drift = Decimal("100.00") - acc
    if scaled:
        last_i, last_w = scaled[-1]
        scaled[-1] = (last_i, (last_w + drift).quantize(Decimal("0.01")))
    return scaled


def _indicative_score(i: DomainScoreInput) -> Decimal:
    """
    Compute indicative score on [1.0, 3.0] scale.

    Policy:
    - Base neutral score 2.0 when coverage is limited but no strong signal of gaps.
    - Ratio = strengths / max(1, strengths + gaps), mapped to [1.0, 3.0] via 1.0 + 2*ratio.
    - Evidence coverage (0..1) adjusts towards neutral:
        score = neutral*(1 - (1-cov)) + base*(cov)
    - Unvalidated controls reduce assurance slightly: -0.1 per unvalidated (cap -0.3).
    - Unknowns do not penalise directly; they reduce coverage (caller provides evidence_coverage).
    """
    # Base strength/gap ratio mapped
    total_pos = max(0, int(i.confirmed_strength_count))
    total_gap = max(0, int(i.confirmed_gap_count))
    denom = max(1, total_pos + total_gap)
    ratio = Decimal(total_pos) / Decimal(denom)
    base = Decimal("1.0") + (Decimal("2.0") * ratio)  # 1.0..3.0
    # Coverage blend towards neutral 2.0
    cov = i.evidence_coverage
    if cov < Decimal("0"):
        cov = Decimal("0")
    if cov > Decimal("1"):
        cov = Decimal("1")
    neutral = Decimal("2.0")
    score = (neutral * (Decimal("1.0") - cov)) + (base * cov)
    # Unvalidated controls slight penalty
    uv = max(0, int(i.unvalidated_control_count))
    pen = min(uv * 0.1, 0.3)
    score = score - Decimal(str(pen))
    # Clamp to [1.0, 3.0]
    if score < Decimal("1.0"):
        score = Decimal("1.0")
    if score > Decimal("3.0"):
        score = Decimal("3.0")
    return score.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _maturity_band(score: Decimal, bands: List[Tuple[Decimal, str]] = None) -> str:
    b = bands or DEFAULT_BANDS
    # Sort bands by threshold descending
    b_sorted = sorted(b, key=lambda x: x[0], reverse=True)
    for thr, label in b_sorted:
        if score >= thr:
            return label
    return b_sorted[-1][1] if b_sorted else "Phase 1"


def _capability_mismatch_present(ctx: EvidenceEnforcementContext, adjudication: EvidenceAdjudicationResult) -> bool:
    """
    Capability Mismatch Path (preserve rule): If MDR present AND (MFA absent OR Patching absent OR Backups absent)
    then enforce a clamp to Phase 1.

    Detection heuristic (deterministic, evidence-bound):
    - MDR present if any existing control/product contains 'mdr' or known MDR provider.
    - Hygiene gaps supported if any confirmed gap statement contains keywords: 'mfa', 'backup', 'patch', 'restore', 'immutab'.
      Unknowns are NOT considered gaps.
    """
    try:
        # MDR presence
        mdr_present = False
        for ctrl in (ctx.existing_controls or []):
            for p in (ctrl.products or []):
                pl = str(p).lower()
                if "mdr" in pl or "defender experts" in pl or "sentinelone watchtower" in pl or "sophos mdr" in pl or "adlumin" in pl:
                    mdr_present = True
                    break
            if mdr_present:
                break
        if not mdr_present:
            return False
        # Hygiene gaps
        gaps = []
        try:
            gaps = (adjudication.unsupported_claims or []) + (adjudication.contradicted_claims or [])
        except Exception:
            gaps = []
        hygiene_tokens = (
            "mfa",
            "multi-factor",
            "multi factor",
            "backup",
            "backups",
            "restore",
            "immutab",
            "patch",
            "patching",
            "vulnerability",
            "vulnerab",
        )
        for g in gaps:
            txt = str(getattr(g, "claim_text", "")).lower()
            # normalise simple hyphen variants for detection
            txt_norm = txt.replace("-", " ")
            if any(tok in txt_norm for tok in hygiene_tokens):
                return True
        return False
    except Exception:
        return False


def _distinct_rationale(domain_name: str, i: DomainScoreInput) -> str:
    """
    Construct a concise, domain-specific rationale referencing evidence signals.
    Enforce distinctness by including domain name and count-specific phrasing.
    """
    parts = []
    pos = max(0, int(i.confirmed_strength_count))
    gaps = max(0, int(i.confirmed_gap_count))
    unk = max(0, int(i.unknown_count))
    uv = max(0, int(i.unvalidated_control_count))
    if pos > 0:
        parts.append(f"{pos} confirmed practice{'s' if pos != 1 else ''} provide a baseline.")
    if gaps > 0:
        parts.append(f"{gaps} confirmed gap{'s' if gaps != 1 else ''} reduce assurance.")
    if uv > 0:
        parts.append(f"{uv} unvalidated control{'s' if uv != 1 else ''} require verification.")
    if unk > 0:
        parts.append("Unknowns require validation rather than being treated as failures.")
    if not parts:
        parts.append("Insufficient domain evidence; neutral position pending validation.")
    return f"[{domain_name}] " + " ".join(parts)


def calculate_security_rating(
    domain_inputs: List[DomainScoreInput],
    ctx: EvidenceEnforcementContext,
    adjudication: EvidenceAdjudicationResult,
) -> SecurityRatingOutput:
    """
    Compute deterministic domain scores and overall rating. Returns SecurityRatingOutput.
    """
    # Normalise weights
    norm = _normalise_weights(domain_inputs)
    domain_results: List[DomainScoreResult] = []
    metadata_claims: List[GeneratedClaim] = []
    # Compute per-domain
    for (i, w_percent) in norm:
        score = _indicative_score(i)
        weight_fraction = (w_percent / Decimal("100")).quantize(Decimal("0.0001"))
        contrib = (score * weight_fraction).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        band = _maturity_band(score)
        rationale = _distinct_rationale(i.domain_name, i)
        dr = DomainScoreResult(
            domain_name=i.domain_name,
            weight=w_percent.quantize(Decimal("0.01")),
            indicative_score=score,
            weighted_contribution=contrib,
            maturity_band=band,
            rationale=rationale,
            rationale_claim_ids=list(i.supporting_claim_ids or [])[:10],
            assurance_penalty_applied=Decimal("0"),
            consultant_review_required=False,
            consultant_question=None,
        )
        domain_results.append(dr)
        # Create internal GeneratedClaim linking rationale to evidence
        if i.supporting_claim_ids:
            metadata_claims.append(GeneratedClaim(
                claim_text=f"Rationale for {i.domain_name}: {rationale}",
                claim_type="consultant_judgement",
                evidence_ids=list(i.supporting_claim_ids or [])[:10],
                confidence="medium",
            ))
    # Overall score = sum contributions
    overall = sum((d.weighted_contribution for d in domain_results), Decimal("0")).quantize(Decimal("0.01"))
    overall_band = _maturity_band(overall)
    # Capability Mismatch clamp (Phase 1) when supported
    assurance_penalty = Decimal("0")
    if _capability_mismatch_present(ctx, adjudication):
        # Clamp overall band to Phase 1; set a visible internal penalty flag
        overall_band = "Phase 1"
        assurance_penalty = Decimal("0.50")  # informational magnitude only; does not alter arithmetic
        # Mark all domain results with penalty for transparency (internal)
        for dr in domain_results:
            dr.assurance_penalty_applied = assurance_penalty
    # Direction of travel (not established by default)
    direction = "Not yet established from a single point-in-time assessment."
    # Primary strengths/gaps (evidence-driven lists)
    strengths: List[str] = []
    gaps_list: List[str] = []
    try:
        # Existing controls as strengths (names only; do not include recommendations)
        for c in (ctx.existing_controls or [])[:6]:
            for p in (c.products or [])[:1]:  # keep concise
                nm = str(p).strip()
                if nm:
                    strengths.append(nm)
        strengths = list(dict.fromkeys(strengths))[:5]
    except Exception:
        strengths = []
    try:
        # Confirmed gaps from adjudication (unsupported/contradicted claims)
        for cl in ((adjudication.unsupported_claims or []) + (adjudication.contradicted_claims or []))[:8]:
            txt = str(getattr(cl, "claim_text", "")).strip()
            if txt:
                gaps_list.append(txt)
        gaps_list = list(dict.fromkeys(gaps_list))[:5]
    except Exception:
        gaps_list = []
    # Board takeaway (concise, customer-specific placeholder; specialist ES will refine)
    board_takeaway = "Stabilise foundational hygiene, validate unverified controls, and strengthen detection and response capabilities proportionately."
    # Scoring limitations disclosure
    scoring_limitations = "Indicative scores reflect available evidence coverage and verified control operation; unknowns require validation and do not imply absence."
    # Metadata assembly
    md = SectionGenerationMetadata(
        section_name="security_rating",
        generated_claims=metadata_claims,
        existing_controls_recognised=strengths[:],
        confirmed_gaps_used=gaps_list[:],
        known_unknowns_used=[],
        recommendations_used=[],
        evidence_limitations_disclosed=[scoring_limitations],
    )
    out = SecurityRatingOutput(
        overall_score=overall,
        maturity_band=overall_band,
        direction_of_travel=direction,
        primary_strengths=strengths,
        primary_gaps=gaps_list,
        board_takeaway=board_takeaway,
        domain_scores=domain_results,
        scoring_limitations=scoring_limitations,
        metadata=md,
    )
    # Diagnostics: inject sentinel token and record generator-stage lineage (diagnostic mode only)
    try:
        if is_diagnostics_enabled():
            _rid = ensure_run_id()
            try:
                # Inject runtime-only marker into board takeaway
                out.board_takeaway = f"{out.board_takeaway} TRACE_SECURITY_{_rid}".strip()
            except Exception:
                pass
            try:
                _payload = out.model_dump() if hasattr(out, "model_dump") else out
                _trace = SectionLineageTrace(run_id=_rid, section_name="security_rating")
                record_stage_hash(_trace, "generator", _payload)
                write_lineage_trace(_trace)
            except Exception:
                pass
    except Exception:
        pass
    return out
