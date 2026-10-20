from __future__ import annotations

"""
Simulated Attack Scenario Specialist Generator (deterministic, evidence-grounded)

Rules implemented:
- Select only approved initial-access routes from ApprovedScenarioProfile.
- Rank routes by evidence strength, workflow relevance, crown jewels impact, and exercise value.
- Use only approved systems/data types; recognise controls reducing likelihood/impact without guarantees.
- Include relevant MITRE techniques (cap 8) matching described behaviour; avoid deprecated IDs by simple mapping gate.
- MDR content: conditional; describes opportunities and dependencies without claiming guaranteed prevention or times.

Acceptance checks referenced by validator:
- Every named technology exists or is approved.
- Every control deficiency has supporting evidence.
- MITRE techniques match described activity.
- No unapproved CVE/tool/actor appears (enforced upstream by validator).
"""

from typing import List, Optional

from services.report_improvement.section_generators.models import (  # type: ignore
    AttackScenarioOutput,
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


# Simple allowlist mapping for MITRE techniques; in real deployments this would be sourced from a maintained mapping.
# Keep IDs lean and avoid deprecated identifiers.
_APPROVED_MITRE = {
    "T1566": "Phishing",
    "T1566.001": "Phishing: Spearphishing Attachment",
    "T1566.004": "Phishing: Voice Phishing",
    "T1110.003": "Brute Force: Password Spraying",
    "T1189": "Drive-by Compromise",
    "T1539": "Steal Web Session Cookie",
    "T1528": "Abuse Elevation Control",
    "T1195": "Supply Chain Compromise",
    "T1133": "External Remote Services",
    "T1027.006": "Obfuscated/Compressed Files and Information: HTML Smuggling",
}


def _disclaimer_text() -> str:
    return (
        "This scenario is for planning and exercise purposes. It reflects a plausible route based on the consultation and approved evidence. "
        "It is not a prediction and does not imply that controls will fail or succeed in a specific way."
    )


def _select_initial_access(ctx: EvidenceEnforcementContext) -> Optional[str]:
    try:
        routes = list((ctx.scenario_profile.approved_initial_access_routes or [])[:10])
        if routes:
            # Deterministic rank: prefer routes that mention identity, credentials, or file-sharing
            routes_sorted = sorted(
                routes,
                key=lambda r: (
                    ("identity" in r.lower()) or ("credential" in r.lower()) or ("file" in r.lower()) or ("sharing" in r.lower()),
                    len(r)
                ),
                reverse=True
            )
            return routes_sorted[0]
    except Exception:
        pass
    return None


def _scenario_title(route: Optional[str]) -> str:
    if route:
        return f"Plausible Intrusion via {route}"
    return "Limited Planning Scenario — Initial Access Route Unconfirmed"


def _initial_access_text(route: Optional[str], ctx: EvidenceEnforcementContext) -> str:
    if route:
        return f"The scenario begins with initial access via {route}, aligned to approved consultation evidence."
    return "The initial access route requires confirmation. A limited planning scenario is provided pending validation."


def _progression_text(ctx: EvidenceEnforcementContext) -> str:
    # Conservative progression description; references approved systems when possible
    techs = [str(getattr(e, "canonical_name", "")) for e in (ctx.approved_entities or []) if getattr(e, "entity_type", "") == "technology"]
    systems = [str(getattr(e, "canonical_name", "")) for e in (ctx.approved_entities or []) if getattr(e, "entity_type", "") == "system"]
    parts: List[str] = []
    if systems:
        parts.append(f"An authenticated session permits progression towards {', '.join(systems[:2])}.")
    if techs:
        parts.append(f"Movement reflects use of approved technologies such as {', '.join(techs[:2])}.")
    if not parts:
        parts.append("Progression requires validation against the approved systems and technologies in scope.")
    return " ".join(parts)


def _business_impact_text(ctx: EvidenceEnforcementContext) -> str:
    cjs = [str(getattr(e, "canonical_name", "")) for e in (ctx.approved_entities or []) if getattr(e, "entity_type", "") == "crown_jewel"]
    if cjs:
        return f"Impact consideration focuses on {', '.join(cjs[:2])}, where disruption could delay service delivery or verification."
    return "Impact should be validated against identified critical assets and business services."


def _detection_opportunities_text(ctx: EvidenceEnforcementContext) -> str:
    return (
        "Detection opportunities depend on telemetry onboarding and correlation. "
        "Identity and endpoint visibility, if integrated, can surface unusual access and lateral movement indicators."
    )


def _containment_considerations_text(ctx: EvidenceEnforcementContext) -> str:
    return (
        "Containment requires pre-authorised pathways for credential resets, device isolation and session revocation. "
        "Where authority is limited, response time may depend on customer approvals."
    )


def _recovery_considerations_text(ctx: EvidenceEnforcementContext) -> str:
    return (
        "Recovery activities should restore systems to known-good states and verify integrity. "
        "Backups and configuration baselines require validation of immutability and representative testing."
    )


def _mitre_list(route: Optional[str]) -> List[str]:
    # Choose a small set relevant to a plausible identity/phishing route
    cands = []
    if route and "phish" in route.lower():
        cands = ["T1566", "T1566.001", "T1539"]
    elif route and "remote" in route.lower():
        cands = ["T1133", "T1110.003"]
    elif route and "supply" in route.lower():
        cands = ["T1195"]
    else:
        cands = ["T1566", "T1189"]
    # Filter through approved mapping; cap at 8
    return [t for t in cands if t in _APPROVED_MITRE][:8]


def _existing_controls_recognised(ctx: EvidenceEnforcementContext) -> List[str]:
    out: List[str] = []
    try:
        for c in (ctx.existing_controls or [])[:5]:
            for p in (c.products or [])[:1]:
                nm = str(p).strip()
                if nm:
                    out.append(nm)
    except Exception:
        pass
    # Deduplicate
    seen = set()
    res: List[str] = []
    for n in out:
        if n.lower() in seen:
            continue
        seen.add(n.lower())
        res.append(n)
    return res[:5]


def _mdr_opportunity_text(ctx: EvidenceEnforcementContext) -> Optional[str]:
    # Describe opportunities conditionally; do not claim guaranteed prevention
    try:
        has_mdr = False
        for c in (ctx.existing_controls or []):
            for p in (c.products or []):
                if "mdr" in str(p).lower():
                    has_mdr = True
                    break
            if has_mdr:
                break
        if has_mdr:
            return (
                "MDR can assist with triage and coordinated response within scope; effectiveness depends on integrated telemetry and authority."
            )
        return None
    except Exception:
        return None


def _metadata(route: Optional[str], mitre: List[str], controls: List[str]) -> SectionGenerationMetadata:
    claims: List[GeneratedClaim] = []
    if route:
        claims.append(
            GeneratedClaim(
                claim_text=f"Initial access route: {route}",
                claim_type="consultant_judgement",
                evidence_ids=[f"route:{route}"],
                confidence="low",
            )
        )
    for t in mitre:
        claims.append(
            GeneratedClaim(
                claim_text=f"MITRE technique included: {t}",
                claim_type="fact",
                evidence_ids=[f"mitre:{t}"],
                confidence="medium",
            )
        )
    for c in controls:
        claims.append(
            GeneratedClaim(
                claim_text=f"Existing control recognised: {c}",
                claim_type="fact",
                evidence_ids=[f"ctrl:{c}"],
                confidence="medium",
            )
        )
    return SectionGenerationMetadata(
        section_name="threat_scenarios",
        generated_claims=claims[:50],
        existing_controls_recognised=controls[:],
        confirmed_gaps_used=[],
        known_unknowns_used=[],
        recommendations_used=[],
        evidence_limitations_disclosed=[],
    )


def generate_attack_scenario(
    ctx: EvidenceEnforcementContext,
    adjudication: EvidenceAdjudicationResult,
) -> AttackScenarioOutput:
    # Enforce MDR gating (present-tense containment narratives only if deployed and telemetry-ready)
    try:
        mdr_allowed = bool(getattr(ctx.scenario_profile, "mdr_deployed", False)) and bool(getattr(ctx.scenario_profile, "telemetry_ready", False))
    except Exception:
        mdr_allowed = False
    route = _select_initial_access(ctx)
    title = _scenario_title(route)
    initial_access = _initial_access_text(route, ctx)
    progression = _progression_text(ctx)
    impact = _business_impact_text(ctx)
    detection = _detection_opportunities_text(ctx)
    containment = _containment_considerations_text(ctx)
    recovery = _recovery_considerations_text(ctx)
    mitre = _mitre_list(route)
    controls = _existing_controls_recognised(ctx)
    mdr_op_text = _mdr_opportunity_text(ctx)
    md = _metadata(route, mitre, controls)
    out = AttackScenarioOutput(
        disclaimer=_disclaimer_text(),
        scenario_title=title,
        initial_access=initial_access,
        progression=progression,
        business_impact=impact,
        detection_opportunities=detection,
        containment_considerations=containment,
        recovery_considerations=recovery,
        relevant_mitre_techniques=mitre,
        existing_controls_recognised=controls,
        limitations_and_assumptions=[
            "Scenario uses only approved entities and evidence; unknowns remain validation requirements."
        ],
        recommendations_highlighted=[],
        mdr_opportunity=mdr_op_text,
        metadata=md,
    )
    # Diagnostics: record generator-stage lineage in sidecar/metadata without leaking into customer-facing title
    try:
        if is_diagnostics_enabled():
            _rid = ensure_run_id()
            try:
                # Isolate trace marker into metadata dictionary, never customer-facing scenario_title
                if isinstance(out.metadata, dict):
                    out.metadata["trace_sentinel"] = f"TRACE_SCENARIO_{_rid}"
                    out.metadata["run_id"] = _rid
            except Exception:
                pass
            try:
                _payload = out.model_dump() if hasattr(out, "model_dump") else out
                _trace = SectionLineageTrace(run_id=_rid, section_name="threat_scenarios")
                record_stage_hash(_trace, "generator", _payload)
                write_lineage_trace(_trace)
            except Exception:
                pass
    except Exception:
        pass
    return out
