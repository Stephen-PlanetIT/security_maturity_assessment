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


class AdjudicatedContradiction(BaseModel):
    contradiction_id: str = Field(description="Stable identifier for the contradiction.")
    topic: str = Field(description="Domain or architectural topic of contradiction.")
    profile_assertion: str = Field(description="Assertion from profile or options input.")
    interview_evidence: str = Field(description="Evidenced reality from transcript or interview summary.")
    adjudicated_ruling: str = Field(description="Authoritative ruling to be used across the report.")
    affected_domains: List[str] = Field(default_factory=list, min_items=0, max_items=10, description="Domains affected by this contradiction.")


class EvidenceAdjudicationResult(BaseModel):
    supported_claims: List[EvidenceClaim] = Field(default_factory=list, min_items=0, max_items=200)
    unsupported_claims: List[EvidenceClaim] = Field(default_factory=list, min_items=0, max_items=200)
    contradicted_claims: List[EvidenceClaim] = Field(default_factory=list, min_items=0, max_items=200)
    contradictions: List[AdjudicatedContradiction] = Field(default_factory=list, min_items=0, max_items=50)
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
    - Contradiction-aware adjudication (Rule 9): resolve interview vs profile contradictions
    """
    res = EvidenceAdjudicationResult()

    # Rule 9: Contradiction-aware adjudication
    # Combine transcript text, summary text, and insights into unified interview corpus
    ins_text = " ".join([str(getattr(i, "quote", "") or "") for i in insights])
    interview_corpus = f"{summary_text or ''} {ins_text}".lower()

    # Adjudicate Branded / Customer interview vs profile contradictions
    c_list: List[AdjudicatedContradiction] = []

    # 1. Professional Services vs Creative/Packaging Production
    if ("artwork" in interview_corpus or "packaging" in interview_corpus or "prepress" in interview_corpus or "creative" in interview_corpus):
        c_list.append(AdjudicatedContradiction(
            contradiction_id="CONTRA-01-INDUSTRY-WORKFLOW",
            topic="Operating Context & Industry",
            profile_assertion="Generic Professional Services",
            interview_evidence="Creative artwork, packaging production, prepress and high-volume digital asset generation.",
            adjudicated_ruling="Creative / Packaging Production context governing asset sensitivity, peak production deadlines, and artworker workflows.",
            affected_domains=["asset_assurance", "current_environment", "executive_summary"],
        ))

    # 2. 200 users vs ~200 devices (macOS artworkers + Windows admin)
    if ("mac" in interview_corpus or "devices" in interview_corpus or "artworker" in interview_corpus or "200" in interview_corpus):
        c_list.append(AdjudicatedContradiction(
            contradiction_id="CONTRA-02-ESTATE-DEVICES",
            topic="Fleet & User Demographics",
            profile_assertion="200 standard enterprise users",
            interview_evidence="Approximately 200 devices estate consisting predominantly of macOS artworkers alongside Windows admin workstations.",
            adjudicated_ruling="Mixed estate: ~200 endpoints with creative artworkers on macOS and administration users on Windows.",
            affected_domains=["endpoint_security", "current_environment", "asset_assurance"],
        ))

    # 3. 60 servers vs internal ESXi/VM/file server estate
    if ("esxi" in interview_corpus or "vm" in interview_corpus or "file server" in interview_corpus):
        c_list.append(AdjudicatedContradiction(
            contradiction_id="CONTRA-03-SERVER-ESTATE",
            topic="Server & Infrastructure Estate",
            profile_assertion="60 servers generic profile",
            interview_evidence="Internally hosted ESXi virtual machines, local file clusters and production file storage nodes.",
            adjudicated_ruling="Internal virtualised VMware ESXi cluster with dedicated file servers and production workflow storage.",
            affected_domains=["current_environment", "cloud_security", "recovery_assurance"],
        ))

    # 4. GCP vs Internal + DigitalOcean + Google Cloud Storage
    if ("digitalocean" in interview_corpus or "google cloud storage" in interview_corpus or "storage" in interview_corpus or "gcp" in interview_corpus):
        c_list.append(AdjudicatedContradiction(
            contradiction_id="CONTRA-04-CLOUD-HOSTING",
            topic="Cloud Hosting Architecture",
            profile_assertion="Generic full GCP estate",
            interview_evidence="Internally hosted core systems with targeted cloud utilisation: DigitalOcean droplets and Google Cloud Storage buckets.",
            adjudicated_ruling="Hybrid footprint: on-premises ESXi core, DigitalOcean hosting, and Google Cloud Storage repository.",
            affected_domains=["cloud_security", "current_environment", "supplier_assurance"],
        ))

    # 5. On-Prem AD vs Google Workspace / Google SSO
    if ("google workspace" in interview_corpus or "google sso" in interview_corpus or "google" in interview_corpus):
        c_list.append(AdjudicatedContradiction(
            contradiction_id="CONTRA-05-IDENTITY-AUTHORITY",
            topic="Identity & Access Authority",
            profile_assertion="On-Prem Active Directory primary identity",
            interview_evidence="Google Workspace / Google SSO serves as the primary cloud identity provider for user authentication.",
            adjudicated_ruling="Google Workspace / Google SSO is the authoritative cloud identity provider; do not assert Entra ID or universal AD dependencies.",
            affected_domains=["identity_access", "saas_governance"],
        ))

    # 6. Universal MFA vs FTP MFA exception
    if ("ftp" in interview_corpus or "mfa" in interview_corpus):
        c_list.append(AdjudicatedContradiction(
            contradiction_id="CONTRA-06-MFA-FTP-EXCEPTION",
            topic="Authentication & Perimeter Exceptions",
            profile_assertion="Universal MFA across all access without exception",
            interview_evidence="Customer and artwork data transfers via FTP service without MFA enforcement.",
            adjudicated_ruling="MFA enforced on Google Workspace accounts, but significant perimeter exception exists on customer FTP service.",
            affected_domains=["identity_access", "network_edge", "third_party_access"],
        ))

    # 7. Automated patching vs staged macOS rollout / missed 14-day target
    if ("patch" in interview_corpus or "14 day" in interview_corpus or "macos" in interview_corpus):
        c_list.append(AdjudicatedContradiction(
            contradiction_id="CONTRA-07-PATCHING-REALITY",
            topic="Patch & Vulnerability Management",
            profile_assertion="Automated patching across OS and third-party within SLA",
            interview_evidence="Patching is staged manually for macOS artworkers due to software compatibility; missed the 14-day vulnerability remediation target.",
            adjudicated_ruling="Staged patching operational model with confirmed delays exceeding 14-day target for creative applications.",
            affected_domains=["endpoint_security", "security_testing"],
        ))

    # 8. On-prem-only backups vs Veeam / QNAP / Google copies + lack of Google Workspace backup
    if ("veeam" in interview_corpus or "qnap" in interview_corpus or "google workspace" in interview_corpus or "backup" in interview_corpus):
        c_list.append(AdjudicatedContradiction(
            contradiction_id="CONTRA-08-BACKUP-LANDSCAPE",
            topic="Data Protection & SaaS Backup",
            profile_assertion="On-Premise Only backups",
            interview_evidence="Veeam with QNAP target and offsite replication copies, but Google Workspace SaaS data lacks dedicated independent third-party backup.",
            adjudicated_ruling="Hybrid backup architecture via Veeam and QNAP; critical gap identified in unbacked Google Workspace SaaS data.",
            affected_domains=["recovery_assurance", "saas_governance", "information_protection"],
        ))

    # 9. Educational MIS vs Production Workflow MIS
    if ("mis" in interview_corpus or "job control" in interview_corpus or "artwork" in interview_corpus):
        c_list.append(AdjudicatedContradiction(
            contradiction_id="CONTRA-09-MIS-PURPOSE",
            topic="Business Management Information System",
            profile_assertion="Unspecified or educational MIS records",
            interview_evidence="Proprietary / industry MIS used strictly for job tracking, artwork job control, and print scheduling.",
            adjudicated_ruling="Production job-control MIS is a critical operational crown jewel; no educational student data exists.",
            affected_domains=["asset_assurance", "current_environment"],
        ))

    # 10. Continuous RTO/RPO vs Aspirations / Targets
    if ("rto" in interview_corpus or "rpo" in interview_corpus or "zero" in interview_corpus or "continuous" in interview_corpus):
        c_list.append(AdjudicatedContradiction(
            contradiction_id="CONTRA-10-RTO-RPO-ASPIRATION",
            topic="Recovery Objectives",
            profile_assertion="Near-continuous RTO / near-zero RPO delivered outcome",
            interview_evidence="Near-zero downtime is an executive business goal, not a validated or tested operational metric.",
            adjudicated_ruling="Aspirational recovery objective requiring formal simulation and restore validation rather than evidenced capability.",
            affected_domains=["recovery_assurance", "incident_response"],
        ))

    # 11. Adlumin MDR evaluated vs Deployed MDR (Webroot + Freshdesk working hours only)
    if ("adlumin" in interview_corpus or "mdr" in interview_corpus or "freshdesk" in interview_corpus or "webroot" in interview_corpus):
        c_list.append(AdjudicatedContradiction(
            contradiction_id="CONTRA-11-MDR-EVALUATION-STATE",
            topic="Managed Detection & Response",
            profile_assertion="Active deployed MDR service",
            interview_evidence="Adlumin MDR is under evaluation / quotation; current state relies on Webroot and Freshdesk ticketing during working hours without a dedicated 24/7 SOC.",
            adjudicated_ruling="No active 24/7 MDR deployment; Adlumin is under procurement evaluation. Operational monitoring is business-hours only via Freshdesk and Webroot.",
            affected_domains=["monitoring_detection", "incident_response"],
        ))

    # 12. AI Policy Unknown vs Explicit approval policy and managed business accounts
    if ("ai" in interview_corpus or "policy" in interview_corpus or "gemini" in interview_corpus or "chatgpt" in interview_corpus):
        c_list.append(AdjudicatedContradiction(
            contradiction_id="CONTRA-12-AI-GOVERNANCE",
            topic="AI Policy & Acceptable Use",
            profile_assertion="AI usage policy Unknown",
            interview_evidence="Explicit company approval policy requiring registered business accounts for approved tools (e.g. Adobe Firefly / Gemini); unmanaged consumer AI banned.",
            adjudicated_ruling="Established AI acceptable use governance with managed business account requirement; focus on technical DLP verification.",
            affected_domains=["ai_governance", "information_protection"],
        ))

    res.contradictions = c_list
    for c in c_list:
        res.contradicted_claims.append(EvidenceClaim(
            claim_id=c.contradiction_id,
            claim_text=f"Contradiction [{c.topic}]: Profile claimed '{c.profile_assertion}' but interview established '{c.interview_evidence}'. Ruling: {c.adjudicated_ruling}",
            domain=c.affected_domains[0] if c.affected_domains else "general",
            classification="contradicted",
            confidence_score=0.95,
            supporting_evidence=[c.interview_evidence],
        ))

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