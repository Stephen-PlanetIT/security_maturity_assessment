from __future__ import annotations

"""
Deterministic Section Evidence Selector

Build a constrained SpecialistSectionInput per section using adjudicated evidence and
the EvidenceEnforcementContext. This selector is deterministic and does not fetch
arbitrary facts. Unknowns remain unknown and do not become gaps.

Rules:
- Use only adjudicated supported/contradicted claims and known unknowns.
- Recognise existing controls from the enforcement context.
- Populate a canonical environment summary from approved entities and controls.
- Keep lists bounded and preserve British English phrasing where applicable.
"""

from typing import List
from pydantic import Field
from services.report_improvement.evidence_enforcement.models import (  # type: ignore
    EvidenceEnforcementContext,
    ApprovedEntity,
    ExistingControlRecord,
    ApprovedGapRecord,
)
from services.report_improvement.evidence_adjudicator import (  # type: ignore
    EvidenceAdjudicationResult,
    EvidenceClaim,
    KnownUnknown,
    CustomerPriority,
)
from evidence_extraction import TranscriptInsight  # type: ignore
from .models import (  # type: ignore
    SpecialistSectionInput,
    CanonicalEnvironment,
    BusinessDependency,
    ApprovedFramework,
    ApprovedProductRecommendation,
    SectionSummaryKV,
    ApprovedRecommendationRecordLite,
    ApprovedEntity as CEApprovedEntity,  # alias to clarify semantic use in SpecialistSectionInput
)


def _build_canonical_environment(ctx: EvidenceEnforcementContext) -> CanonicalEnvironment:
    """
    Canonicalised environment derived deterministically from enforcement context.
    Entity types observed in enforcement models: product, crown_jewel, technology.
    """
    customers: List[str] = []
    industries: List[str] = []  # Not present in context; reserved for future adapters
    locations: List[str] = []
    technologies: List[str] = []
    systems: List[str] = []
    services: List[str] = []
    platforms: List[str] = []
    products: List[str] = []
    crown_jewels: List[str] = []

    try:
        for ent in (ctx.approved_entities or []):
            ename = str(getattr(ent, "canonical_name", "")).strip()
            etype = str(getattr(ent, "entity_type", "")).strip().lower()
            if not ename:
                continue
            if etype == "customer":
                if ename not in customers:
                    customers.append(ename)
            elif etype == "technology":
                if ename not in technologies:
                    technologies.append(ename)
            elif etype == "platform":
                if ename not in platforms:
                    platforms.append(ename)
            elif etype == "system":
                if ename not in systems:
                    systems.append(ename)
            elif etype == "service":
                if ename not in services:
                    services.append(ename)
            elif etype == "crown_jewel":
                if ename not in crown_jewels:
                    crown_jewels.append(ename)
            elif etype == "vendor" or etype == "product":
                if ename not in products:
                    products.append(ename)
            elif etype == "location":
                if ename not in locations:
                    locations.append(ename)
            elif etype == "data_type" or etype == "business_process":
                # Map into technologies/services as a conservative placeholder without inventing new types
                if etype == "data_type" and ename not in technologies:
                    technologies.append(ename)
                if etype == "business_process" and ename not in services:
                    services.append(ename)
    except Exception:
        pass

    # Also derive products from existing controls deterministically
    try:
        for ctrl in (ctx.existing_controls or []):
            for p in (getattr(ctrl, "products", []) or []):
                pname = str(p).strip()
                if pname and pname not in products:
                    products.append(pname)
    except Exception:
        pass

    return CanonicalEnvironment(
        customers=customers[:5],
        industries=industries[:5],
        locations=locations[:25],
        technologies=technologies[:200],
        systems=systems[:100],
        services=services[:100],
        platforms=platforms[:50],
        products=products[:200],
        crown_jewels=crown_jewels[:50],
    )


def _classify_evidence_quality(
    existing_controls: List[ExistingControlRecord],
    supported_claims: List[EvidenceClaim],
    confirmed_gaps: List[ApprovedGapRecord],
    known_unknowns: List[KnownUnknown],
) -> str:
    """
    Heuristic evidence quality classification (deterministic):
    - strong: multiple controls and supported claims present OR multiple confirmed gaps with support
    - mixed: at least one control or supported claim or gap; unknowns present
    - limited: otherwise
    """
    try:
        ctrl_n = len(existing_controls or [])
        sup_n = len(supported_claims or [])
        gap_n = len(confirmed_gaps or [])
        unk_n = len(known_unknowns or [])
        if (ctrl_n >= 2 and sup_n >= 1) or gap_n >= 2:
            return "strong"
        if (ctrl_n + sup_n + gap_n) >= 1:
            return "mixed"
        return "limited"
    except Exception:
        return "limited"


def _select_supported_claims(adjudication: EvidenceAdjudicationResult) -> List[EvidenceClaim]:
    try:
        return list((adjudication.supported_claims or [])[:200])
    except Exception:
        return []


def _select_partially_supported_claims(adjudication: EvidenceAdjudicationResult) -> List[EvidenceClaim]:
    # EvidenceAdjudicationResult does not currently expose partially_supported; keep empty
    return []


def _select_existing_controls(ctx: EvidenceEnforcementContext) -> List[ExistingControlRecord]:
    try:
        return list((ctx.existing_controls or [])[:500])
    except Exception:
        return []


def _select_confirmed_gaps(adjudication: EvidenceAdjudicationResult) -> List[ApprovedGapRecord]:
    """
    Deterministically create gap records from adjudication.unsupported/contradicted claims.
    Enforcement already creates gaps; prefer those when available in ctx;
    fall back to adjudication-derived statements as general gaps.
    """
    gaps: List[ApprovedGapRecord] = []
    try:
        # Prefer enforcement-approved gaps if present in context
        # Note: selector receives ctx; but to keep selector pure, rely on ctx-approved gaps externally when wiring.
        pass
    except Exception:
        pass
    # Build from adjudication (non-invasive; status confirmed)
    try:
        gi = 0
        for src in [
            getattr(adjudication, "unsupported_claims", []) or [],
            getattr(adjudication, "contradicted_claims", []) or [],
        ]:
            for cl in src:
                st = str(getattr(cl, "claim_text", "")).strip()
                if not st:
                    continue
                gaps.append(
                    ApprovedGapRecord(
                        gap_id=f"sel-gap-{gi}",
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
    return gaps[:500]


def _select_known_unknowns(adjudication: EvidenceAdjudicationResult) -> List[KnownUnknown]:
    try:
        return list((adjudication.known_unknowns or [])[:100])
    except Exception:
        return []


def _select_contradicted_claims(adjudication: EvidenceAdjudicationResult) -> List[EvidenceClaim]:
    try:
        return list((adjudication.contradicted_claims or [])[:200])
    except Exception:
        return []


def _select_customer_priorities(adjudication: EvidenceAdjudicationResult) -> List[CustomerPriority]:
    try:
        return list((adjudication.customer_priorities or [])[:50])
    except Exception:
        return []


def _select_frameworks_from_entities(ctx: EvidenceEnforcementContext) -> List[ApprovedFramework]:
    """
    Extract frameworks deterministically from approved entities if they exist as 'framework' entities.
    """
    out: List[ApprovedFramework] = []
    try:
        for ent in (ctx.approved_entities or []):
            etype = str(getattr(ent, "entity_type", "")).strip().lower()
            name = str(getattr(ent, "canonical_name", "")).strip()
            if etype == "framework" and name:
                out.append(ApprovedFramework(framework_name=name, applicability_status="potentially_relevant", scope_hint=None))
    except Exception:
        pass
    return out[:20]


def _select_products_from_controls(ctx: EvidenceEnforcementContext) -> List[ApprovedProductRecommendation]:
    """
    Build a conservative list of approved product mentions from existing controls; no new vendors are introduced.
    """
    out: List[ApprovedProductRecommendation] = []
    seen = set()
    try:
        for ctrl in (ctx.existing_controls or []):
            for p in (getattr(ctrl, "products", []) or []):
                pname = str(p).strip()
                if pname and pname.lower() not in seen:
                    seen.add(pname.lower())
                    out.append(ApprovedProductRecommendation(vendor=pname, rationale=None, evidence_ids=[]))
    except Exception:
        pass
    return out[:200]


def select_section_evidence(
    section_name: str,
    context: EvidenceEnforcementContext,
    adjudication: EvidenceAdjudicationResult,
    transcript_insights: List[TranscriptInsight],
) -> SpecialistSectionInput:
    """
    Deterministic specialist input assembler.

    This function is deliberately conservative. It does not augment evidence and does not
    infer absent controls. It provides bounded lists for each field, leaving room for
    section-specific generators to select and shape content within acceptance checks.
    """
    canon_env = _build_canonical_environment(context)

    supported_claims = _select_supported_claims(adjudication)
    partially_supported_claims = _select_partially_supported_claims(adjudication)
    existing_controls = _select_existing_controls(context)
    confirmed_gaps = _select_confirmed_gaps(adjudication)
    known_unknowns = _select_known_unknowns(adjudication)
    contradicted_claims = _select_contradicted_claims(adjudication)
    customer_priorities = _select_customer_priorities(adjudication)
    approved_frameworks = _select_frameworks_from_entities(context)
    approved_products = _select_products_from_controls(context)

    # Primary domain routing via applicable_domains; fallback to keywords only when domain tags absent
    try:
        keywords_map = {
            "identity_access": ["google workspace", "google sso", "mfa", "ftp"],
            "endpoint_security": ["webroot", "kanji", "iru", "mdm", "patch"],
            "recovery_assurance": ["veeam", "qnap", "backup", "drive", "restore"],
            "monitoring_detection": ["webroot", "freshdesk", "mdr", "soc", "hours"],
            "network_edge": ["mpls", "fortinet", "vpn", "esxi", "hong kong"],
            "cloud_security": ["digitalocean", "google cloud storage", "google workspace", "m365", "saas"],
            "saas_governance": ["google workspace", "google sso", "breathe", "digitalocean", "google cloud storage", "m365"],
            "information_protection": ["branded os", "we transfer", "ftp", "google drive", "dlp", "classification"],
            "supplier_assurance": ["spire", "digitalocean", "google cloud storage", "webroot", "kanji", "we transfer", "breathe"],
            "ai_governance": ["ai policy", "gemini", "claude", "chatgpt", "adobe"],
            "incident_response": ["incident response", "tabletop", "retainer", "out of hours", "escalation"],
        }
        kw = set([k.lower() for k in keywords_map.get(str(section_name or ""), [])])

        # 1) Filter existing controls by applicable_domains if present
        def _ctrl_in_domain(c: ExistingControlRecord) -> bool:
            try:
                doms = [str(d).strip().lower() for d in (getattr(c, "applicable_domains", []) or [])]
                return str(section_name or "").strip().lower() in doms if doms else False
            except Exception:
                return False
        filtered_controls = [c for c in (existing_controls or []) if _ctrl_in_domain(c)]
        if filtered_controls:
            existing_controls = filtered_controls
        else:
            # Fallback to keyword filtering only when domain tags absent
            def _match_ctrl_kw(c: ExistingControlRecord) -> bool:
                try:
                    nm = str(getattr(c, "canonical_name", "")).strip().lower()
                    return any(k in nm for k in kw)
                except Exception:
                    return False
            filtered_controls_kw = [c for c in (existing_controls or []) if _match_ctrl_kw(c)]
            if filtered_controls_kw:
                existing_controls = filtered_controls_kw

        # 2) Filter approved products by vendor name using keywords (no domain tags available)
        try:
            approved_products = [p for p in (approved_products or []) if any(k in str(getattr(p, "vendor", "")).strip().lower() for k in kw)]
        except Exception:
            approved_products = approved_products

        # 3) Assign relevant transcript insights by filtering provided structured insights; preserve categories
        relevant_ins: List[TranscriptInsight] = []
        try:
            for ins in (transcript_insights or [])[:200]:
                qt = str(getattr(ins, "quote", "") or "").strip().lower()
                if qt and any(k in qt for k in kw):
                    relevant_ins.append(ins)
        except Exception:
            relevant_ins = list((transcript_insights or [])[:200])
        transcript_insights = relevant_ins
    except Exception:
        pass

    # Business dependencies not explicitly available; leave empty until adapters provide them
    business_dependencies: List[BusinessDependency] = []

    # Crown jewels from context entities (already mapped into CanonicalEnvironment)
    cjs: List[CEApprovedEntity] = []
    try:
        for ent in (context.approved_entities or []):
            if str(getattr(ent, "entity_type", "")).strip().lower() == "crown_jewel":
                cjs.append(ent)  # type: ignore
    except Exception:
        pass

    # Evidence quality heuristic
    evidence_quality = _classify_evidence_quality(existing_controls, supported_claims, confirmed_gaps, known_unknowns)

    # Preceding summaries are populated upstream; provide empty bounded list here
    preceding_summaries: List[SectionSummaryKV] = []

    # Customer name derivation: attempt from entities first; else blank
    customer_name = ""
    try:
        for ent in (context.approved_entities or []):
            if str(getattr(ent, "entity_type", "")).strip().lower() == "customer":
                cname = str(getattr(ent, "canonical_name", "")).strip()
                if cname:
                    customer_name = cname
                    break
    except Exception:
        pass

    return SpecialistSectionInput(
        section_name=str(section_name or "").strip(),
        customer_name=customer_name or "Client",
        canonical_environment=canon_env,
        supported_claims=supported_claims,
        partially_supported_claims=partially_supported_claims,
        existing_controls=existing_controls,
        confirmed_gaps=confirmed_gaps,
        known_unknowns=known_unknowns,
        contradicted_claims=contradicted_claims,
        customer_priorities=customer_priorities,
        business_dependencies=business_dependencies,
        crown_jewels=cjs[:50],
        relevant_transcript_insights=transcript_insights[:200],
        approved_frameworks=approved_frameworks,
        approved_recommendations=[],  # adapters will populate where available
        approved_products=approved_products,
        source_section=None,
        preceding_section_summaries=preceding_summaries,
        evidence_quality=evidence_quality,  # 'strong' | 'mixed' | 'limited'
        evidence_limitations=[],
    )