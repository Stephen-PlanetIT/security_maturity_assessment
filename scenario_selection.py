"""
scenario_selection.py — Deterministic threat-scenario candidate engine

Selects a highest‑relevance scenario candidate using shared consultation evidence.
Unknown evidence contributes weakly; Not Applicable is neutral. Outputs a dict with
keys: name, score, reasons, required_conditions, asset_context, and attack_vector
text suitable for prompts.build_scenario_prompt.

British English wording is used.
"""
from __future__ import annotations

from typing import Dict, List, Any


def _val(d: Dict[str, Any], *path: str, default: Any = "Unknown") -> Any:
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
    return cur


def _score_flag(value: str, *, bad: List[str], unknown_weight: float = 0.3) -> float:
    if not isinstance(value, str):
        return 0.0
    if value in bad:
        return 1.0
    if value in ("Unknown", "Not established during consultation", ""):
        return unknown_weight
    if value == "Not applicable":
        return 0.0
    return 0.0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    return s in ("1", "true", "yes", "y", "on")


def _has_cap_service(cap: Dict[str, Any], token: str) -> bool:
    try:
        bs = cap.get("business_services", []) or []
        return any(token.lower() in str(x).lower() for x in bs)
    except Exception:
        return False


def select_scenario_candidate(inputs: Dict[str, Any]) -> Dict[str, Any]:
    cap = inputs.get("critical_asset_profile", {}) or {}
    idg = inputs.get("identity_governance_profile", {}) or {}
    sg = inputs.get("saas_governance_profile", {}) or {}
    mon = inputs.get("monitoring_assurance_profile", {}) or {}
    rec = inputs.get("recovery_assurance_profile", {}) or {}
    tp = inputs.get("third_party_access_profile", {}) or {}
    appsec = inputs.get("application_security_profile", {}) or {}
    integ = inputs.get("integration_assurance_profile", {}) or {}

    candidates: List[Dict[str, Any]] = []

    # 1) Privileged access weakness
    pa_score = 0.0
    pa_score += _score_flag(_val(idg, "legacy_authentication_status"), bad=["Enabled and not reviewed"])  # legacy auth
    pa_score += _score_flag(_val(idg, "pim_pam_status"), bad=["None", "Planned"])  # no PIM/PAM
    pa_score += _score_flag(_val(idg, "shared_account_usage"), bad=["Widespread", "Used in selected operational scenarios"])  # shared accts
    if pa_score > 0:
        reasons = [
            r for r in [
                "Legacy authentication enabled or unverified" if _val(idg, "legacy_authentication_status") in ("Enabled and not reviewed", "Unknown") else "",
                "PIM/PAM not implemented" if _val(idg, "pim_pam_status") in ("None", "Planned", "Unknown") else "",
                "Shared accounts present" if _val(idg, "shared_account_usage") in ("Widespread", "Used in selected operational scenarios", "Unknown") else "",
            ] if r
        ]
        candidates.append({
            "key": "privileged_access",
            "name": "Privileged Access Abuse leading to Domain Escalation",
            "score": pa_score,
            "reasons": reasons,
            "required_conditions": ["Administrative identities or shared accounts exploitable"],
            "asset_context": cap,
            "attack_vector": "Privilege escalation via legacy authentication and absence of just‑in‑time privileged access; attacker pivots using shared or poorly governed admin credentials to reach critical services.",
        })

    # 2) OAuth consent abuse / unmanaged SaaS
    oauth = _val(sg, "oauth_app_governance")
    sso = _val(sg, "sso_coverage")
    oauth_score = _score_flag(oauth, bad=["User consent unrestricted or unknown"]) + _score_flag(sso, bad=["Limited"]) * 0.7
    if oauth_score > 0:
        reasons = [
            "OAuth consent unrestricted or unverified" if oauth in ("User consent unrestricted or unknown", "Unknown") else "",
            "SSO coverage limited" if sso in ("Limited", "Selected critical applications", "Unknown") else "",
        ]
        candidates.append({
            "key": "oauth_consent",
            "name": "OAuth Consent Phishing leading to Tenant Compromise",
            "score": oauth_score,
            "reasons": [r for r in reasons if r],
            "required_conditions": ["Users can grant high‑risk consents without strong approval"],
            "asset_context": cap,
            "attack_vector": "Illicit consent grant to a malicious application to access mail and files; absence of strong OAuth governance and partial SSO coverage enable persistence and data access.",
        })

    # 3) Supplier access weakness
    id_model = _val(tp, "identity_model")
    sup_mfa = _val(tp, "mfa_status")
    sup_score = _score_flag(id_model, bad=["Shared accounts"]) + _score_flag(sup_mfa, bad=["Not enforced", "Inconsistent"]) * 0.8
    if sup_score > 0:
        candidates.append({
            "key": "supplier_access",
            "name": "Third‑Party Access Abuse via Shared or Weakly Governed Accounts",
            "score": sup_score,
            "reasons": [
                "Shared supplier accounts" if id_model == "Shared accounts" else "",
                f"Supplier MFA {sup_mfa}" if sup_mfa in ("Not enforced", "Inconsistent", "Unknown") else "",
            ],
            "required_conditions": ["Supplier access present without strict identity controls"],
            "asset_context": cap,
            "attack_vector": "Compromise of a third‑party account with weak controls; lateral movement through vendor pathways to business services and sensitive data.",
        })

    # 4) Monitoring gaps
    cov = _val(mon, "monitoring_coverage")
    resp = _val(mon, "response_authority")
    mon_score = _score_flag(cov, bad=["Business hours only", "Critical alerts outside hours"]) + _score_flag(resp, bad=["Notify only", "Investigate and recommend"]) * 0.6
    if mon_score > 0:
        candidates.append({
            "key": "monitoring_gaps",
            "name": "Out‑of‑Hours Intrusion with Limited Monitoring Response",
            "score": mon_score,
            "reasons": [
                f"Coverage: {cov}" if cov in ("Business hours only", "Critical alerts outside hours", "Unknown") else "",
                f"Authority: {resp}" if resp in ("Notify only", "Investigate and recommend", "Unknown") else "",
            ],
            "required_conditions": ["Limited 24/7 coverage or notify‑only authority"],
            "asset_context": cap,
            "attack_vector": "Intrusion during out‑of‑hours windows where alerts are not actively investigated or containment is not pre‑authorised, enabling progression towards critical assets.",
        })

    # 5) Recovery assurance gaps
    rt = _val(rec, "restore_testing")
    im = _val(rec, "immutability_status")
    rec_score = _score_flag(rt, bad=["Never", "Ad hoc"]) + _score_flag(im, bad=["None"]) * 0.7
    if rec_score > 0:
        candidates.append({
            "key": "recovery_gaps",
            "name": "Ransomware with Targeted Backup Destruction",
            "score": rec_score,
            "reasons": [
                f"Restore testing: {rt}" if rt in ("Never", "Ad hoc", "Unknown") else "",
                f"Immutability: {im}" if im in ("None", "Unknown") else "",
            ],
            "required_conditions": ["Backups not immutable and restores untested"],
            "asset_context": cap,
            "attack_vector": "Targeted destruction or encryption of backup repositories prior to ransomware deployment; lack of immutability and untested restores increase impact.",
        })

    # 6) Public application/API weakness
    if bool(inputs.get("public_web_apps")):
        candidates.append({
            "key": "public_app",
            "name": "Public Web Application/API Exploitation",
            "score": 1.2,
            "reasons": ["Public web applications exposed"],
            "required_conditions": ["Externally accessible application with insufficient AppSec controls"],
            "asset_context": cap,
            "attack_vector": "Exploitation of a vulnerability in a public‑facing application or API to gain foothold and pivot towards internal systems and data.",
        })

    # 7) Acquisition/new site integration gaps
    if _bool(inputs.get("acquisition_or_new_site_growth")):
        due = _val(integ, "security_due_diligence")
        idint = _val(integ, "identity_integration")
        sc = _score_flag(due, bad=["None"]) + _score_flag(idint, bad=["None"]) * 0.6
        candidates.append({
            "key": "integration_gap",
            "name": "Acquisition or New‑Site Integration Risk",
            "score": sc if sc > 0 else 0.5,
            "reasons": [
                f"Due diligence: {due}" if due else "",
                f"Identity integration: {idint}" if idint else "",
            ],
            "required_conditions": ["M&A or new site with limited pre‑connection assurance"],
            "asset_context": cap,
            "attack_vector": "Integration of a new environment without sufficient pre‑connection assurance allows inherited vulnerabilities to bridge into the core estate.",
        })

    # 8) Payment fraud (conditional on CAP services)
    if _has_cap_service(cap, "Payment") or _has_cap_service(cap, "Finance") or _has_cap_service(cap, "ERP"):
        candidates.append({
            "key": "payment_fraud",
            "name": "Business Email/Process Compromise (Payments)",
            "score": 0.8,
            "reasons": ["Finance‑related services present"],
            "required_conditions": ["Finance operations reliant on email approvals or weak verification"],
            "asset_context": cap,
            "attack_vector": "Business email compromise targeting payment change workflows; weak out‑of‑band verification enables fraudulent transfers.",
        })

    # Default scenario if none scored > 0
    if not candidates:
        return {
            "key": "default",
            "name": "Multi‑Stage Intrusion via Business Email Compromise",
            "score": 0.5,
            "reasons": ["Generic exposure baseline"],
            "required_conditions": ["Standard email‑centric attack paths"],
            "asset_context": cap,
            "attack_vector": "Compromise of an executive mailbox followed by social engineering to authorise fraudulent transactions or access sensitive data.",
        }

    # Select highest score (tie‑break by list order)
    best = max(candidates, key=lambda c: c.get("score", 0.0))
    return best


def select_candidate_attack_vector(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Compatibility wrapper: returns a dict with attack_vector and reasons."""
    return select_scenario_candidate(inputs)
