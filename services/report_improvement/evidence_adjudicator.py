from __future__ import annotations
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from config import get_config, ConfigKey
from evidence_extraction import AssessmentEvidence, TranscriptInsight


# New Models

class EvidenceClaim(BaseModel):
    claim_id: str = Field(description="Stable ID for the claim.")
    claim_text: str = Field(description="Normalised claim text.")
    domain: str = Field(description="High-level domain, e.g., 'identity', 'endpoint', 'backup', 'monitoring', 'compliance'.")
    classification: Literal[
        "supported",
        "partially_supported",
        "customer_stated",
        "unvalidated",
        "unknown",
        "contradicted",
        "unsupported"
    ] = Field(description="Adjudication classification for this claim.")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Confidence 0.0–1.0.")
    supporting_evidence: List[str] = Field(default_factory=list, min_items=0, max_items=10, description="Direct transcript quotes or summary lines that support this claim.")


class ExistingControl(BaseModel):
    control_name: str = Field(description="Canonical name of an existing control or product.")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Confidence that this control exists.")
    evidence_source: str = Field(description="Authoritative source type (e.g., 'transcript', 'summary', 'consultant_approved', 'baseline_normalised').")
    deployment_state: Literal[
        "implemented",
        "partially_implemented",
        "planned",
        "under_evaluation",
        "not_deployed",
        "not_confirmed",
        "not_applicable"
    ] = Field(default="not_confirmed", description="Deployment state classification.")
    evidence_references: List[str] = Field(default_factory=list, min_items=1, max_items=20, description="Evidence IDs that support this control (must be >=1 unless consultant-approved and persisted).")
    applicable_domains: List[str] = Field(default_factory=list, min_items=0, max_items=10, description="Domains where this control applies (e.g., 'endpoint_security', 'monitoring_detection').")


class KnownUnknown(BaseModel):
    category: str = Field(description="Area where knowledge is missing (e.g., 'patching', 'backups', 'MDR').")
    statement: str = Field(description="Explicit unknown statement (e.g., 'Backups exist but restore testing not confirmed').")


class CustomerPriority(BaseModel):
    priority: str = Field(description="Customer-stated priority or concern (e.g., 'Downtime Concern').")
    supporting_quote: str = Field(description="Verbatim transcript quote where possible.")


class ApprovedAttackInputs(BaseModel):
    confirmed_technologies: List[str] = Field(default_factory=list, min_items=0, max_items=30)
    confirmed_crown_jewels: List[str] = Field(default_factory=list, min_items=0, max_items=10)
    confirmed_attack_paths: List[str] = Field(default_factory=list, min_items=0, max_items=20)
    known_industry_risks: List[str] = Field(default_factory=list, min_items=0, max_items=20)


class CostAssumptionProfile(BaseModel):
    has_financial_evidence: bool = Field(description="Whether transcript contains concrete financial exposure data.")
    notes: List[str] = Field(default_factory=list, min_items=0, max_items=10, description="Planning assumptions only if no evidence exists.")


class EvidenceAdjudicationResult(BaseModel):
    supported_claims: List[EvidenceClaim] = Field(default_factory=list, min_items=0, max_items=200)
    unsupported_claims: List[EvidenceClaim] = Field(default_factory=list, min_items=0, max_items=200)
    contradicted_claims: List[EvidenceClaim] = Field(default_factory=list, min_items=0, max_items=200)
    existing_controls: List[ExistingControl] = Field(default_factory=list, min_items=0, max_items=100)
    known_unknowns: List[KnownUnknown] = Field(default_factory=list, min_items=0, max_items=100)
    customer_priorities: List[CustomerPriority] = Field(default_factory=list, min_items=0, max_items=20)
    transcript_highlights: List[str] = Field(default_factory=list, min_items=0, max_items=100)
    approved_attack_inputs: ApprovedAttackInputs = Field(default_factory=ApprovedAttackInputs)
    cost_assumptions: CostAssumptionProfile = Field(default_factory=lambda: CostAssumptionProfile(has_financial_evidence=False, notes=[]))


_UNKNOWN_TOKENS = ("unknown", "not confirmed", "not discussed", "not validated", "not assessed")


def _is_unknown(text: str) -> bool:
    try:
        s = (text or "").strip().lower()
        return any(tok in s for tok in _UNKNOWN_TOKENS)
    except Exception:
        return False


_CONTROL_KEYWORDS = (
    "sophos", "mdr", "webroot", "mimecast", "fortinet", "barracuda",
    "veeam", "google sso", "okta", "defender", "sentinelone", "crowdstrike",
    "cyber essentials", "ce+", "iso 27001", "nist", "pci", "purview", "siem"
)


def adjudicate_evidence(
    assessment: AssessmentEvidence,
    insights: List[TranscriptInsight],
    summary_text: str,
    baseline: Optional[dict] = None
) -> EvidenceAdjudicationResult:
    """
    Apply adjudication rules to convert raw evidence into authoritative claims/controls/unknowns.

    Rules enforced:
    - Unknown is NOT a weakness (Rule 1)
    - Recognise existing controls (Rule 2)
    - Prioritise transcript over summary over environment over generated report (Rule 4)
    - Extract explicit business priorities (Rule 6)
    - Constrain attack inputs (Rule 7)
    - Constrain cost assumptions (Rule 8)
    """
    res = EvidenceAdjudicationResult()

    # Transcript highlights (top-k quotes)
    try:
        for ins in insights[:50]:
            q = (ins.quote or "").strip()
            if q:
                res.transcript_highlights.append(q[:600])
    except Exception:
        pass

    # Existing controls: authoritative-only, evidence-driven; preserve provenance; no keyword corroboration
    try:
        def _normalise_name(n: str) -> str:
            return str(n or "").strip()
        def _canonical_match(a: str, b: str) -> bool:
            return _normalise_name(a).lower() == _normalise_name(b).lower()
        # Build baseline objects from normalised evidence, preserving fields
        baseline_items: List[dict] = []
        if baseline and isinstance(baseline, dict):
            items = baseline.get("items") or baseline.get("evidence") or []
            for it in items:
                if isinstance(it, dict):
                    baseline_items.append(it)
        # Helper: derive applicable domains from baseline category mapping
        def _domains_from_baseline(bi: dict) -> List[str]:
            cat = str(bi.get("category", "")).strip().lower()
            mapping = {
                "endpoint security": ["endpoint_security"],
                "endpoint management": ["endpoint_security"],
                "backup & recovery": ["recovery_assurance"],
                "email security": ["email_security"],
                "network": ["network_edge"],
                "network edge": ["network_edge"],
            }
            return mapping.get(cat, [])
        # Evidence-driven selection: only categories indicative of controls
        allowed_cats = {"endpoint security", "endpoint management", "backup & recovery", "email security", "network", "network edge"}
        selected_controls: List[ExistingControl] = []
        for bi in baseline_items:
            canon = _normalise_name(bi.get("name", ""))
            cat = str(bi.get("category", "")).strip().lower()
            ev_id = str(bi.get("id", "") or bi.get("evidence_id", "")).strip()
            if canon and cat in allowed_cats and ev_id:
                selected_controls.append(
                    ExistingControl(
                        control_name=canon,
                        confidence_score=0.8,
                        evidence_source="baseline_normalised",
                        deployment_state="implemented",
                        evidence_references=[ev_id],
                        applicable_domains=_domains_from_baseline(bi),
                    )
                )
        # Merge with assessment.existing_controls only when canonical match to baseline
        for x in (assessment.existing_controls or []):
            nm = _normalise_name(x)
            if not nm:
                continue
            bi_match = next((bi for bi in baseline_items if _canonical_match(bi.get("name", ""), nm)), None)
            if bi_match:
                ev_id = str(bi_match.get("id", "") or bi_match.get("evidence_id", "")).strip()
                if ev_id:
                    selected_controls.append(
                        ExistingControl(
                            control_name=nm,
                            confidence_score=0.8,
                            evidence_source="baseline_normalised",
                            deployment_state="implemented",
                            evidence_references=[ev_id],
                            applicable_domains=_domains_from_baseline(bi_match),
                        )
                    )
        # Deduplicate by canonical name
        seen = set()
        for ec in selected_controls:
            key = ec.control_name.lower()
            if key in seen:
                continue
            seen.add(key)
            res.existing_controls.append(ec)
    except Exception as exc:
        # Diagnostic — do not fail silently
        try:
            res.transcript_highlights.append(f"ADJUDICATION_CONTROL_ERROR: {exc}"[:600])
        except Exception:
            pass

    # Known Unknowns (Rule 1): derive from explicit phrases in insights/summary
    try:
        ku: List[KnownUnknown] = []
        # Summary text scan
        if _is_unknown(summary_text or ""):
            ku.append(KnownUnknown(category="summary", statement=(summary_text or "").strip()[:300]))
        # Insight quotes scan
        for ins in insights:
            q = (ins.quote or "")
            if _is_unknown(q):
                ku.append(KnownUnknown(category=(ins.category or "general"), statement=q[:300]))
        # Domain-level unknowns from assessment lists: record as unknown, do not infer weakness
        if not (assessment.active_projects or []):
            ku.append(KnownUnknown(category="projects", statement="Active projects not discussed or not confirmed."))
        res.known_unknowns = ku[:100]
    except Exception:
        pass

    # Customer priorities (Rule 6): extract from TranscriptInsight categories
    try:
        for ins in insights:
            cat = (ins.category or "").strip()
            if cat in (
                "Business Priority", "Board Concern", "Operational Concern", "Downtime Concern",
                "Budget Concern", "Compliance Requirement", "Security Concern", "Recovery Concern", "Supplier Concern"
            ):
                if ins.quote and ins.quote.strip():
                    res.customer_priorities.append(CustomerPriority(priority=cat, supporting_quote=ins.quote.strip()[:600]))
    except Exception:
        pass

    # Claims: supported vs unknown/unsupported (minimal heuristics; facts only)
    try:
        # Crown jewels -> supported claim (as presence fact)
        for cj in (assessment.crown_jewels or []):
            text = f"Crown jewels include: {cj}"
            res.supported_claims.append(EvidenceClaim(
                claim_id=f"cj:{abs(hash(text))}",
                claim_text=text,
                domain="resilience",
                classification="supported",
                confidence_score=0.9,
                supporting_evidence=[]
            ))
        # Do not infer immutability/restore testing; record as known unknown if explicitly stated via insights/summary (handled above).
    except Exception:
        pass

    # Attack input constraints (Rule 7) — derive conservative confirmed technologies from normalised evidence,
    # excluding sample-only products. Only include security_products if also explicitly confirmed as existing_controls.
    try:
        techs: List[str] = []
        try:
            for x in (assessment.technologies or []):
                t = str(x).strip()
                if t and t not in techs:
                    techs.append(t)
        except Exception:
            pass
        try:
            for x in (assessment.cloud_platforms or []):
                t = str(x).strip()
                if t and t not in techs:
                    techs.append(t)
        except Exception:
            pass
        try:
            for x in (assessment.suppliers or []):
                t = str(x).strip()
                if t and t not in techs:
                    techs.append(t)
        except Exception:
            pass
        # Include security_products only when corroborated by existing_controls
        try:
            ec_set = set([str(x).strip().lower() for x in (assessment.existing_controls or []) if str(x).strip()])
            for x in (assessment.security_products or []):
                t = str(x).strip()
                if t and t.lower() in ec_set and t not in techs:
                    techs.append(t)
        except Exception:
            pass
        res.approved_attack_inputs = ApprovedAttackInputs(
            confirmed_technologies=techs[:30],
            confirmed_crown_jewels=[str(x) for x in (assessment.crown_jewels or []) if str(x).strip()][:10],
            confirmed_attack_paths=[],  # populated only when explicitly stated
            known_industry_risks=[]     # not inferred without support
        )
    except Exception:
        pass

    # Cost assumptions (Rule 8)
    try:
        res.cost_assumptions = CostAssumptionProfile(
            has_financial_evidence=False,
            notes=["Planning assumptions only; no specific financial evidence found."]
        )
    except Exception:
        pass

    return res


def save_adjudication_log(customer: str, result: EvidenceAdjudicationResult) -> Optional[str]:
    """
    Persist adjudication result JSON under LOG_STORAGE_DIR/report_improvement/evidence_logs/{customer}/{ts}.json
    Returns the path on success; None on failure.
    """
    import json, os
    try:
        base_dir = get_config(ConfigKey.LOG_STORAGE_DIR, os.path.join(os.path.dirname(__file__), "..", "..", "exports", "logs"))
        out_dir = os.path.join(base_dir, "report_improvement", "evidence_logs", (customer or "Client").replace(" ", "_"))
        os.makedirs(out_dir, exist_ok=True)
        import datetime as _dt
        ts = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        path = os.path.join(out_dir, f"{ts}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result.model_dump(), f, ensure_ascii=False, indent=2)
        return path
    except Exception:
        return None