"""domain_evidence_packager.py — Phase 1B: DomainEvidencePackage generation.

Reads authoritative_facts.json (from exports/) and produces domain_packages.json
with domain-specific fact packages for IAM, Monitoring, Recovery, Supplier, Governance.

Success criteria: IAM specialist receives Google Workspace + FTP MFA Exception
without generic Microsoft assumptions.
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ──────────────────────────────────────────────
# Domain Evidence Package Models
# ──────────────────────────────────────────────

@dataclass
class ControlEvidence:
    """Single confirmed or planned control for a domain package."""
    canonical_name: str
    canonical_value: str
    deployment_state: str
    confidence: float
    authority_source: str
    evidence_excerpt: str


@dataclass
class ContradictionRecord:
    """A rejected alternative with resolution details."""
    canonical_name: str
    winner_value: str
    loser_value: str
    resolution_strategy: str
    rejection_reason: str


@dataclass
class KnownUnknownEntry:
    """An uncertainty or conflict requiring review."""
    issue: str
    contradictions: List[ContradictionRecord] = field(default_factory=list)


@dataclass
class DomainEvidencePackage:
    """Complete evidence package for a single domain."""
    domain: str
    confirmed_controls: List[ControlEvidence] = field(default_factory=list)
    planned_controls: List[ControlEvidence] = field(default_factory=list)
    known_unknowns: List[KnownUnknownEntry] = field(default_factory=list)
    known_unknowns_partial: List[KnownUnknownEntry] = field(default_factory=list)


@dataclass
class DomainPackagesOutput:
    """Top-level output structure."""
    customer_id: str
    package_version: str = "1.0"
    generated_from: str = "authoritative_facts.json"
    domains: Dict[str, DomainEvidencePackage] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "customer_id": self.customer_id,
            "package_version": self.package_version,
            "generated_from": self.generated_from,
            "domains": {
                domain: _domain_package_to_dict(pkg)
                for domain, pkg in self.domains.items()
            },
        }


def _domain_package_to_dict(pkg: DomainEvidencePackage) -> dict:
    """Serialize a DomainEvidencePackage to JSON-serialisable dict."""
    return {
        "confirmed_controls": [
            {
                "canonical_name": c.canonical_name,
                "canonical_value": c.canonical_value,
                "deployment_state": c.deployment_state,
                "confidence": c.confidence,
                "authority_source": c.authority_source,
                "evidence_excerpt": c.evidence_excerpt,
            }
            for c in pkg.confirmed_controls
        ],
        "planned_controls": [
            {
                "canonical_name": c.canonical_name,
                "canonical_value": c.canonical_value,
                "deployment_state": c.deployment_state,
                "confidence": c.confidence,
                "authority_source": c.authority_source,
                "evidence_excerpt": c.evidence_excerpt,
            }
            for c in pkg.planned_controls
        ],
        "known_unknowns": [
            {
                "issue": u.issue,
                "contradictions": [
                    {
                        "canonical_name": cr.canonical_name,
                        "winner_value": cr.winner_value,
                        "loser_value": cr.loser_value,
                        "resolution_strategy": cr.resolution_strategy,
                        "rejection_reason": cr.rejection_reason,
                    }
                    for cr in u.contradictions
                ],
            }
            for u in pkg.known_unknowns
        ],
        "known_unknowns_partial": [
            {
                "issue": u.issue,
                "contradictions": [
                    {
                        "canonical_name": cr.canonical_name,
                        "winner_value": cr.winner_value,
                        "loser_value": cr.loser_value,
                        "resolution_strategy": cr.resolution_strategy,
                        "rejection_reason": cr.rejection_reason,
                    }
                    for cr in u.contradictions
                ],
            }
            for u in pkg.known_unknowns_partial
        ],
    }


# ──────────────────────────────────────────────
# Canonical → Domain Routing
# ──────────────────────────────────────────────

# Maps canonical_name to set of domains that should receive it
_CANONICAL_DOMAIN_MAP: Dict[str, List[str]] = {
    "identity_provider": ["iam"],
    "mfa_enforcement": ["iam", "monitoring"],
    "mfa_exception": ["iam", "monitoring"],
    "edr_vendor": ["monitoring"],
    "backup_solution": ["recovery_ir"],
    "cold_storage": ["recovery_ir"],
    "on_premises_storage": ["supplier"],
    "cloud_provider": ["supplier"],
    "helpdesk_system": ["monitoring"],
    "existing_control": [],  # value-dependent routing below
    "technology": [],  # value-dependent routing below
}

# Value-based routing for generic canonical names
_VALUE_DOMAIN_MAP: Dict[str, List[str]] = {
    "microsoft azure": ["supplier", "iam"],
    "azure ad connected": ["iam"],
    "hoxhunt": ["governance"],
    "digitalocean": ["supplier"],
}


def _get_domains_for_canonical(canonical_name: str, canonical_value: str) -> List[str]:
    """Determine which domains should receive a fact."""
    # First check value-dependent routing
    lower_val = canonical_value.lower() if canonical_value else ""
    for val_pattern, domains in _VALUE_DOMAIN_MAP.items():
        if val_pattern in lower_val:
            return domains

    # Then check canonical name routing
    return _CANONICAL_DOMAIN_MAP.get(canonical_name, ["general"])


# ──────────────────────────────────────────────
# Domain-Specific Unknown Detection Rules
# ──────────────────────────────────────────────

# Rules for detecting known_unknowns vs known_unknowns_partial per domain
_DOMAIN_UNKNOWN_RULES: Dict[str, List[Dict[str, Any]]] = {
    "iam": [
        {
            "condition": lambda w, l: w == "identity_provider",
            "issue": "Identity provider migration uncertainty — baseline_normalised contains conflicting vendor claim vs transcript confirmation",
        },
        {
            "condition": lambda w, l: w == "mfa_exception",
            "issue": "MFA exception for FTP server requires review and remediation planning",
        },
    ],
    "monitoring": [
        {
            "condition": lambda w, l: w in ("edr_vendor",),
            "issue": "{loser} claimed as edr/xdr but not confirmed in transcript — vendor selection may be incomplete",
        },
    ],
    "recovery_ir": [],  # No known unknowns expected for BRANDED recovery
    "supplier": [
        {
            "condition": lambda w, l: w == "cloud_provider",
            "issue": "{loser} claimed as cloud provider but rejected in favour of {winner} — pilot/complementary status unclear",
        },
    ],
    "governance": [
        {
            "condition": lambda w, l: True,  # catch-all for unverified claims
            "issue": "No confirmed evidence for {canonical_name} in any source — requires consultant verification",
        },
    ],
}


def _detect_unknowns(
    domain: str,
    canonical_name: str,
    winner_value: str,
    loser_value: str,
    strategy: str,
) -> Optional[KnownUnknownEntry]:
    """Detect whether a contradiction should surface as a known_unknown."""
    rules = _DOMAIN_UNKNOWN_RULES.get(domain, [])

    for rule in rules:
        cond = rule["condition"]
        # Evaluate condition with context
        ctx = {
            "w": canonical_name,
            "l": loser_value.lower(),
            "winner": winner_value,
            "loser": loser_value,
            "canonical_name": canonical_name,
        }
        if cond(ctx["w"], ctx["l"]):
            issue_template = rule["issue"]
            issue = issue_template.format(**ctx)
            cr = ContradictionRecord(
                canonical_name=canonical_name,
                winner_value=winner_value,
                loser_value=loser_value,
                resolution_strategy=strategy,
                rejection_reason=f"Winner '{winner_value}' overcomes loser '{loser_value}'",
            )
            return KnownUnknownEntry(issue=issue, contradictions=[cr])

    return None


# ──────────────────────────────────────────────
# Core Package Builder
# ──────────────────────────────────────────────

# Identity-critical canonical names that suppress superseded alternatives
_IDENTITY_ROLES = {"identity_provider", "mfa_enforcement", "mfa_exception"}

# Supersession map: if identity_role is confirmed, these superseded facts are excluded from IAM
_SUPERSEDED_BY_IDENTITY_ROLE = {"existing_control", "technology"}


def _is_superseded(fact_dict: dict, domain: str, all_facts: dict) -> bool:
    """Check if a fact should be suppressed because a higher-authority source already claims the role.

    Suppression applies when:
    1. canonical_name is in _SUPERSEDED_BY_IDENTITY_ROLE (existing_control, technology)
    2. An identity_role fact has higher confidence and in-use deployment_state
    Source (transcript vs baseline_normalised) does not matter — the identity_role
    fact represents the current operational truth that supersedes legacy infrastructure claims.
    """
    if domain != "iam":
        return False

    canonical_name = fact_dict.get("canonical_name", "")
    if canonical_name not in _SUPERSEDED_BY_IDENTITY_ROLE:
        return False

    my_confidence = fact_dict.get("confidence", 0)

    # Check if any identity_role fact has higher confidence and in-use state
    for other_name, other_fact in all_facts.items():
        if other_name not in _IDENTITY_ROLES:
            continue
        if other_fact.get("deployment_state") != "in-use":
            continue
        other_confidence = other_fact.get("confidence", 0)
        if other_confidence <= my_confidence:
            continue
        # This identity_role fact supersedes ours
        return True

    return False


def build_domain_packages(
    facts: dict,
    customer_id: str = "BRANDED",
) -> DomainPackagesOutput:
    """Build domain evidence packages from authoritative_facts.json.

    Args:
        facts: Parsed authoritative_facts.json dict (canonical_name → fact dict)
        customer_id: Customer identifier for the output package

    Returns:
        DomainPackagesOutput with all 5 domains populated
    """
    packages = {
        "iam": DomainEvidencePackage(domain="iam"),
        "monitoring": DomainEvidencePackage(domain="monitoring"),
        "recovery_ir": DomainEvidencePackage(domain="recovery_ir"),
        "supplier": DomainEvidencePackage(domain="supplier"),
        "governance": DomainEvidencePackage(domain="governance"),
    }

    # Track which domains each fact goes to (for contradiction routing)
    fact_domains: Dict[str, List[str]] = {}  # canonical_name → [domains]

    for canonical_name, fact_dict in facts.items():
        canonical_value = fact_dict.get("canonical_value", "")
        deployment_state = fact_dict.get("deployment_state", "unknown")
        confidence = fact_dict.get("confidence", 0.0)
        authority_source = fact_dict.get("authority_source", "unknown")
        evidence_excerpt = fact_dict.get("source_excerpt", "")

        # Determine target domains
        target_domains = _get_domains_for_canonical(canonical_name, canonical_value)
        fact_domains[canonical_name] = target_domains

        # Check supersession: suppress baseline_normalised facts when identity_role is confirmed
        if _is_superseded(fact_dict, "iam", facts):
            ctrl_evidence = ControlEvidence(
                canonical_name=canonical_name,
                canonical_value=str(canonical_value),
                deployment_state="superseded",
                confidence=confidence * 0.3,  # Very low confidence to mark as rejected
                authority_source="superseded_by_" + facts.get("identity_provider", {}).get("canonical_value", "identity_role"),
                evidence_excerpt=f"Superseded by {facts.get('identity_provider', {}).get('canonical_value', 'identity provider migration')}",
            )
            # Add as known_unknown to iam domain instead of confirmed/planned
            cr = ContradictionRecord(
                canonical_name=canonical_name,
                winner_value=str(facts.get("identity_provider", {}).get("canonical_value", "")),
                loser_value=str(canonical_value),
                resolution_strategy="superseded_by_identity_role",
                rejection_reason=f"'{canonical_value}' from baseline_normalised superseded by transcript-confirmed identity provider migration",
            )
            for domain in target_domains:
                if domain == "iam":
                    existing_issues = [u.issue for u in packages[domain].known_unknowns]
                    unknown_issue = f"'{canonical_name}' ({canonical_value}) superseded by Google Workspace identity migration"
                    if unknown_issue not in existing_issues:
                        packages[domain].known_unknowns.append(
                            KnownUnknownEntry(issue=unknown_issue, contradictions=[cr])
                        )
            continue

        ctrl_evidence = ControlEvidence(
            canonical_name=canonical_name,
            canonical_value=str(canonical_value),
            deployment_state=deployment_state,
            confidence=confidence,
            authority_source=authority_source,
            evidence_excerpt=evidence_excerpt,
        )

        # Add to confirmed or planned based on deployment state
        if deployment_state == "in-use" and confidence >= 0.50:
            for domain in target_domains:
                packages[domain].confirmed_controls.append(ctrl_evidence)
        elif deployment_state in ("piloting", "planned") and confidence >= 0.50:
            for domain in target_domains:
                packages[domain].planned_controls.append(ctrl_evidence)

    # Second pass: populate known_unknowns from rejected_alternatives in facts
    for canonical_name, fact_dict in facts.items():
        rejected_alt = fact_dict.get("rejected_alternatives", [])
        if not rejected_alt:
            continue

        target_domains = fact_domains.get(canonical_name, ["general"])
        winner_value = str(fact_dict.get("canonical_value", ""))

        for alt in rejected_alt:
            loser_value = str(alt.get("canonical_value", ""))
            strategy = alt.get("resolution_strategy", "unknown")
            rejection_reason = alt.get("rejection_reason", "")

            for domain in target_domains:
                # Check if this contradiction should be surfaced as a known_unknown
                unknown_entry = _detect_unknowns(
                    domain, canonical_name, winner_value, loser_value, strategy
                )
                if unknown_entry:
                    # Avoid duplicate issues
                    existing_issues = [u.issue for u in packages[domain].known_unknowns]
                    if unknown_entry.issue not in existing_issues:
                        packages[domain].known_unknowns.append(unknown_entry)

    return DomainPackagesOutput(
        customer_id=customer_id,
        domains={k: v for k, v in packages.items()},
    )


def load_authoritative_facts(path: Optional[str] = None) -> dict:
    """Load authoritative_facts.json from exports/ or provided path."""
    if path is None:
        # Try relative to this file's parent, then cwd, then exports/
        candidates = [
            "exports/authoritative_facts.json",
            "authoritative_facts.json",
        ]
        for p in candidates:
            if os.path.exists(p):
                path = p
                break

    if path is None or not os.path.exists(path):
        raise FileNotFoundError(f"authoritative_facts.json not found in expected locations")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_domain_packages(
    packages: DomainPackagesOutput,
    output_path: Optional[str] = None,
) -> str:
    """Save domain_packages.json to specified path (or exports/ by default)."""
    if output_path is None:
        output_path = "exports/domain_packages.json"

    # Ensure parent directory exists
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(packages.to_dict(), f, indent=2, ensure_ascii=False)

    return output_path


# ──────────────────────────────────────────────
# CLI Entry Point
# ──────────────────────────────────────────────

def main() -> None:
    """Run domain package generation for BRANDED customer."""
    facts = load_authoritative_facts()
    packages = build_domain_packages(facts, customer_id="BRANDED")

    output_path = save_domain_packages(packages)
    print(f"Domain packages saved to {output_path}")

    # Print summary
    for domain_name in sorted(packages.domains.keys()):
        pkg = packages.domains[domain_name]
        confirmed_count = len(pkg.confirmed_controls)
        planned_count = len(pkg.planned_controls)
        unknown_count = len(pkg.known_unknowns) + len(pkg.known_unknowns_partial)
        print(f"  {domain_name}: {confirmed_count} confirmed, {planned_count} planned, {unknown_count} unknowns")


if __name__ == "__main__":
    main()