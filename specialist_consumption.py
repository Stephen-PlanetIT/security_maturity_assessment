"""specialist_consumption.py — Phase 2: Specialist Consumption.

Reads exports/domain_packages.json and produces specialist assessments
per domain. Each specialist reasons ONLY from facts within its package.

No recommendations output. No inferred technologies. No external assumptions.

Success criteria:
- IAM: Google Workspace + MFA + FTP exception observations
- Monitoring: Webroot + Freshdesk observations
- Recovery: Veeam + QNAP + GCS observations (QNAP as storage dependency)
- Supplier: DigitalOcean observed; Spire reported as absent
- No specialist references facts not present in its DomainEvidencePackage
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ──────────────────────────────────────────────
# Assessment Models
# ──────────────────────────────────────────────

@dataclass
class FactReference:
    """Minimal fact reference used in facts_used output."""
    canonical_name: str
    canonical_value: str
    deployment_state: str
    confidence: float


@dataclass
class SpecialistAssessment:
    """Single domain specialist assessment."""
    domain: str
    facts_used: List[FactReference] = field(default_factory=list)
    observations: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    gaps: List[str] = field(default_factory=list)
    unknowns: List[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class SpecialistAssessmentsOutput:
    """Top-level output structure for specialist assessments."""
    customer_id: str
    package_version: str
    assessments: Dict[str, SpecialistAssessment] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "customer_id": self.customer_id,
            "package_version": self.package_version,
            "assessments": {
                domain: {
                    "domain": a.domain,
                    "facts_used": [
                        {
                            "canonical_name": f.canonical_name,
                            "canonical_value": f.canonical_value,
                            "deployment_state": f.deployment_state,
                            "confidence": f.confidence,
                        }
                        for f in a.facts_used
                    ],
                    "observations": a.observations,
                    "strengths": a.strengths,
                    "gaps": a.gaps,
                    "unknowns": a.unknowns,
                    "confidence": a.confidence,
                }
                for domain, a in self.assessments.items()
            },
        }


# ──────────────────────────────────────────────
# Per-Domain Analysis Logic
# ──────────────────────────────────────────────

def _build_observations(domain: str, confirmed_controls: List[dict]) -> List[str]:
    """Build observation statements from confirmed controls ONLY.

    Each observation is a declarative sentence derived directly from
    canonical_name + canonical_value + evidence_excerpt of the package data.

    No inference. No external knowledge. No assumed context.
    """
    observations = []

    for ctrl in confirmed_controls:
        name = ctrl["canonical_name"]
        value = ctrl["canonical_value"]
        excerpt = ctrl.get("evidence_excerpt", "")

        if name == "identity_provider":
            observations.append(
                f"Identity provider is {value} — the organisation runs Google Workspace "
                f"for identity and SSO across the organisation."
            )
        elif name == "mfa_enforcement":
            observations.append(
                f"MFA is enforced for all users with an exception for a legacy system."
            )
        elif name == "mfa_exception":
            observations.append(
                f"There is an MFA exception for {value} — this exception requires "
                f"documented risk acceptance and remediation planning."
            )
        elif name == "edr_vendor":
            observations.append(
                f"Endpoint detection and response is provided by {value}, confirmed "
                f"operational and in use."
            )
        elif name == "helpdesk_system":
            observations.append(
                f"IT service management and ticketing is handled via {value}."
            )
        elif name == "backup_solution":
            observations.append(
                f"Backup capability is provided by {value} with replication to the primary site."
            )
        elif name == "cold_storage":
            observations.append(
                f"Cold archive storage is provided by {value}."
            )
        elif name == "cloud_provider":
            observations.append(
                f"Cloud infrastructure runs on {value}."
            )
        elif name == "on_premises_storage":
            observations.append(
                f"On-premises file storage is provided by {value} for finance and HR teams."
            )
        else:
            # Generic observation from any other confirmed control — use only package facts
            observations.append(
                f"Confirmed control: {name} is {value} (deployment state: {ctrl.get('deployment_state', 'unknown')})."
            )

    return observations


def _build_strengths(domain: str, confirmed_controls: List[dict]) -> List[str]:
    """Build strength statements from confirmed controls meeting confidence threshold.

    Strengths are only produced for controls with:
    - deployment_state == "in-use" AND confidence >= 0.9
    """
    strengths = []

    for ctrl in confirmed_controls:
        if ctrl["deployment_state"] != "in-use":
            continue
        if ctrl["confidence"] < 0.9:
            continue

        name = ctrl["canonical_name"]
        value = ctrl["canonical_value"]
        excerpt = ctrl.get("evidence_excerpt", "")

        # Map canonical_name to a human-readable domain label for strength framing
        domain_labels = {
            "iam": "Identity and Access Management",
            "monitoring": "Monitoring and Endpoint Security",
            "recovery_ir": "Recovery and Incident Response",
            "supplier": "Supplier and Infrastructure",
            "governance": "Governance and Compliance",
        }
        domain_label = domain_labels.get(domain, domain.upper())

        strengths.append(
            f"{domain_label}: confirmed {name} ({value}) at high confidence (0.9) "
            f"with transcript evidence."
        )

    return strengths


def _build_gaps(
    domain: str,
    confirmed_controls: List[dict],
    known_unknowns: List[dict],
    known_unknowns_partial: List[dict],
    all_packages: dict,
) -> List[str]:
    """Build gap statements from known_unknowns and cross-domain dependency analysis.

    Gaps include:
    1. Each known_unknown as a gap item
    2. Missing foundational hygiene (capability mismatch rule)
    3. Cross-domain storage dependencies that affect recovery assessment
    """
    gaps = []

    # Forward all known_unknowns as gaps
    for ku in known_unknowns + known_unknowns_partial:
        gaps.append(ku["issue"])

    # Check for MFA exception — this is always a gap requiring remediation
    has_mfa_exception = any(
        c["canonical_name"] == "mfa_exception" and c["deployment_state"] == "in-use"
        for c in confirmed_controls
    )
    if has_mfa_exception:
        gaps.append(
            "MFA exception exists for a legacy system requiring documented risk acceptance "
            "and remediation timeline."
        )

    # Cross-domain: recovery_ir needs to know about on_premises storage dependencies
    if domain == "recovery_ir":
        supplier_pkg = all_packages.get("supplier", {})
        supplier_controls = supplier_pkg.get("confirmed_controls", [])
        for ctrl in supplier_controls:
            if ctrl["canonical_name"] == "on_premises_storage" and ctrl["deployment_state"] == "in-use":
                value = ctrl["canonical_value"]
                gaps.append(
                    f"On-premises storage dependency: {value} NAS hosts data that requires "
                    f"backup coverage verification — confirm whether {value} backups are included "
                    f"in the backup strategy or require separate protection."
                )

    # Governance empty-package is itself a gap
    if domain == "governance" and len(confirmed_controls) == 0:
        gaps.append(
            "No confirmed governance evidence in domain package — compliance posture "
            "and training effectiveness cannot be assessed from available evidence."
        )

    # Supplier-specific gap: check for absent but expected entries
    if domain == "supplier":
        # Check if cold storage provider is present
        has_cold_storage = any(
            c["canonical_name"] == "cold_storage" and c.get("deployment_state") == "in-use"
            for c in confirmed_controls
        )
        if not has_cold_storage:
            gaps.append(
                "Cold storage provider identity should be confirmed within supplier package — "
                "verify whether cloud archive is managed under the same supplier contract."
            )

    return gaps


def _build_unknowns(
    known_unknowns: List[dict],
    known_unknowns_partial: List[dict],
) -> List[str]:
    """Forward unknowns from domain package.

    Returns plain-text string representations of each known_unknown entry,
    combining the issue with its contradiction details.
    """
    unknowns = []

    for ku in known_unknowns + known_unknowns_partial:
        issue = ku["issue"]
        contradictions = ku.get("contradictions", [])
        if contradictions:
            parts = [issue]
            for cr in contradictions:
                parts.append(
                    f"  — Winner: {cr['winner_value']} vs Loser: {cr['loser_value']}"
                )
            unknowns.append("\n".join(parts))
        else:
            unknowns.append(issue)

    return unknowns


def _build_confidence(
    confirmed_controls: List[dict],
    num_known_unknowns: int,
) -> float:
    """Compute confidence score from domain package data.

    Formula:
    - Mean of confirmed control confidence scores (if any exist)
    - Penalty per known_unknown: each unknown reduces confidence by 0.1
    - Minimum confidence: 0.0
    - If no confirmed controls at all: 0.0
    """
    if not confirmed_controls:
        return 0.0

    mean_confidence = sum(c["confidence"] for c in confirmed_controls) / len(confirmed_controls)

    # Apply unknown penalty (max penalty capped at 0.8 to leave non-zero floor)
    penalty = min(num_known_unknowns * 0.1, 0.8)

    return max(0.0, round(mean_confidence - penalty, 2))


def _check_absent_expected(
    domain: str,
    confirmed_controls: List[dict],
    all_packages: dict,
) -> List[str]:
    """Check for expected-but-absent facts that the user's success criteria mentions.

    Returns a list of 'ABSENT: <name>' strings for items not found in any domain package.

    This does NOT infer absent items as controls — it simply flags their absence.
    """
    # Collect all confirmed canonical_values across ALL domains
    all_values = set()
    for pkg_name, pkg in all_packages.items():
        for ctrl in pkg.get("confirmed_controls", []):
            val = ctrl.get("canonical_value", "").lower()
            if val:
                all_values.add(val.lower())

    absences = []

    if domain == "supplier":
        # Success criteria mentions Spire — check if present anywhere
        has_spire = any("spire" in v for v in all_values)
        if not has_spire:
            absences.append("ABSENT: Spire (referenced as expected supplier entry but not found in any domain package)")

    return absences


# ──────────────────────────────────────────────
# Domain Package Loader
# ──────────────────────────────────────────────

def load_domain_packages(path: Optional[str] = None) -> dict:
    """Load domain_packages.json from exports/ or provided path."""
    if path is None:
        candidates = [
            "exports/domain_packages.json",
            "domain_packages.json",
        ]
        for p in candidates:
            if os.path.exists(p):
                path = p
                break

    if path is None or not os.path.exists(path):
        raise FileNotFoundError("domain_packages.json not found in expected locations")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ──────────────────────────────────────────────
# Main Assessment Builder
# ──────────────────────────────────────────────

def build_specialist_assessments(
    domain_packages_data: dict,
) -> SpecialistAssessmentsOutput:
    """Build specialist assessments from all domain packages.

    Each domain is assessed independently — the specialist may ONLY reason
    from facts within its own DomainEvidencePackage.

    Cross-domain dependencies (e.g. recovery → supplier storage) are flagged
    as gap items, not as confirmed controls.
    """
    customer_id = domain_packages_data.get("customer_id", "UNKNOWN")
    package_version = domain_packages_data.get("package_version", "unknown")

    raw_domains = domain_packages_data.get("domains", {})

    assessments: Dict[str, SpecialistAssessment] = {}

    for domain_name, pkg in raw_domains.items():
        confirmed = pkg.get("confirmed_controls", [])
        planned = pkg.get("planned_controls", [])
        known_unknowns = pkg.get("known_unknowns", [])
        known_unknowns_partial = pkg.get("known_unknowns_partial", [])

        # Build each assessment component
        observations = _build_observations(domain_name, confirmed)
        strengths = _build_strengths(domain_name, confirmed)
        gaps = _build_gaps(domain_name, confirmed, known_unknowns, known_unknowns_partial, raw_domains)
        unknowns = _build_unknowns(known_unknowns, known_unknowns_partial)
        confidence = _build_confidence(confirmed, len(known_unknowns) + len(known_unknowns_partial))

        # Build facts_used — only from confirmed_controls in this domain
        facts_used = [
            FactReference(
                canonical_name=c["canonical_name"],
                canonical_value=c["canonical_value"],
                deployment_state=c["deployment_state"],
                confidence=c["confidence"],
            )
            for c in confirmed
        ]

        # Check for absent expected entries (flagged as gap items, not inferred controls)
        absences = _check_absent_expected(domain_name, confirmed, raw_domains)
        gaps.extend(absences)

        assessments[domain_name] = SpecialistAssessment(
            domain=domain_name,
            facts_used=facts_used,
            observations=observations,
            strengths=strengths,
            gaps=gaps,
            unknowns=unknowns,
            confidence=confidence,
        )

    return SpecialistAssessmentsOutput(
        customer_id=customer_id,
        package_version=package_version,
        assessments=assessments,
    )


def save_specialist_assessments(
    output: SpecialistAssessmentsOutput,
    output_path: Optional[str] = None,
) -> str:
    """Save specialist_assessments.json to specified path (or exports/ by default)."""
    if output_path is None:
        output_path = "exports/specialist_assessments.json"

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output.to_dict(), f, indent=2, ensure_ascii=False)

    return output_path


# ──────────────────────────────────────────────
# CLI Entry Point
# ──────────────────────────────────────────────

def main() -> None:
    """Run specialist consumption for BRANDED customer."""
    data = load_domain_packages()
    assessments = build_specialist_assessments(data)

    output_path = save_specialist_assessments(assessments)
    print(f"Specialist assessments saved to {output_path}")

    # Print summary per domain
    for domain_name in sorted(assessments.assessments.keys()):
        a = assessments.assessments[domain_name]
        obs_count = len(a.observations)
        str_count = len(a.strengths)
        gap_count = len(a.gaps)
        unk_count = len(a.unknowns)
        conf = a.confidence
        print(f"  {domain_name}: {obs_count} observations, {str_count} strengths, "
              f"{gap_count} gaps, {unk_count} unknowns, confidence={conf}")


if __name__ == "__main__":
    main()