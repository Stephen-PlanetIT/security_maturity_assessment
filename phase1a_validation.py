"""phase1a_validation.py — Phase 1A Validation checkpoint.

Runs Transcript → Normalisation → AuthoritativeFact → ContradictionRecord.
Outputs authoritative_facts.json and contradictions.json.
Validates BRANDED acceptance criteria before Domain Packages unlock.

BRANDED fixture data:
  Survivors: Google Workspace, Google SSO, FTP MFA exception, Webroot,
             Veeam, QNAP, Spire, Freshdesk, DigitalOcean, Google Cloud Storage
  Rejected:  Entra, Azure, Sophos MDR, Sophos MDR Plus, Hoxhunt
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, List

# Import Phase 1A core models
from evidence_adjudication import (
    AuthoritativeFact,
    ContradictionRecord,
    adjudicate_evidence_v2,
    regression_assert_branded,
)


# ──────────────────────────────────────────────
# BRANDED Test Fixture — Transcript, Summary, Profile
# ──────────────────────────────────────────────

BRANDED_TRANSQUOTES: List[str] = [
    "They run Google Workspace for identity and SSO across the organisation.",
    "MFA is enforced for all users with an exception for the legacy FTP server.",
    "Endpoint protection is Webroot — confirmed operational and in use.",
    "Backups are handled by Veeam with a replica to the primary site.",
    "QNAP NAS provides on-premises file storage for finance and HR teams.",
    "Spire is piloting for some workloads before full migration.",
    "Freshdesk is our helpdesk system for ITSM and ticketing.",
    "Cloud infrastructure runs on DigitalOcean with Google Cloud Storage for cold archive.",
]

BRANDED_SUMMARY: str = (
    "The customer uses Google Workspace as their identity provider with MFA enforced. "
    "Webroot is deployed for endpoint protection. Veeam handles backups. "
    "DigitalOcean hosts production workloads, with Google Cloud Storage for cold archive. "
    "QNAP provides on-premises storage. Spire is piloting migration. "
    "Freshdesk manages helpdesk operations."
)

BRANDED_PROFILE: dict = {
    "identity_provider": "google workspace",
    "industry": "professional services",
    "employee_count": 150,
}


# ──────────────────────────────────────────────
# BRANDED competing signals (the rejections)
# These simulate evidence that should be overridden by higher-authority transcript/profile data.
# ──────────────────────────────────────────────

BRANDED_FIXTURE_CONTENDERS: List[str] = [
    "microsoft entra",          # Should lose to google workspace
    "microsoft azure",          # Should lose to digitalocean
    "sophos mdr",              # Should lose — piloting only, no confirmed deployment
    "sophos mdr plus",         # Should lose — piloting only
    "hoxhunt",                 # Should lose — not confirmed
]

BRANDED_TECHNOLOGIES: List[str] = [
    "microsoft entra idp",      # Competing identity provider (should lose)
    "azure ad connected",       # Competing cloud platform (should lose)
]

BRANDED_SUPPLIERS: List[str] = [
    "spire - piloting migration",
    "freshdesk itsm ticketing",
]

BRANDED_CLOUD_PLATFORMS: List[str] = [
    "digitalocean droplet",     # Winner for cloud_provider
    "microsoft azure gateway",  # Competing cloud platform (should lose)
    "google cloud storage bucket",  # Maps to cold_storage (survives)
]

BRANDED_SECURITY_PRODUCTS: List[str] = [
    "webroot securelight",      # Winner for edr_vendor
    "sophos mdr advanced",      # Competing EDR (should lose)
    "sophos mdr plus tier",     # Competing EDR (should lose)
]

BRANDED_MFA_EXCEPTIONS: List[str] = [
    "ftp server mfa exemption", # Should survive as MFA exception
]


# ──────────────────────────────────────────────
# Validation harness
# ──────────────────────────────────────────────

def run_phase1a_validation() -> tuple[dict, list[ContradictionRecord], ContradictionRecord]:
    """Run BRANDED transcript → normalisation → AuthoritativeFact → ContradictionRecord.

    Returns (adjudicated_dict, all_contradictions, regression_result).
    """
    # Call adjudicate_evidence_v2 with BRANDED fixture data
    adjudicated, contradictions = adjudicate_evidence_v2(
        existing_controls=BRANDED_FIXTURE_CONTENDERS + BRANDED_MFA_EXCEPTIONS,
        technologies=BRANDED_TECHNOLOGIES,
        suppliers=BRANDED_SUPPLIERS,
        cloud_platforms=BRANDED_CLOUD_PLATFORMS,
        security_products=BRANDED_SECURITY_PRODUCTS,
        transcript_quotes=BRANDED_TRANSQUOTES,
        summary_text=BRANDED_SUMMARY,
    )

    # Run BRANDED regression assertions
    regression = regression_assert_branded(adjudicated, contradictions)

    return adjudicated, contradictions, regression


def _authoritative_fact_to_dict(fact: AuthoritativeFact) -> dict[str, Any]:
    """Serialise an AuthoritativeFact to JSON-compatible dict."""
    return {
        "fact_id": fact.fact_id,
        "canonical_name": fact.canonical_name,
        "canonical_value": str(fact.canonical_value),
        "deployment_state": fact.deployment_state,
        "confidence": fact.confidence,
        "authority_source": fact.authority_source,
        "evidence_ids": list(fact.evidence_ids),
        "source_excerpt": fact.source_excerpt[:200],
        "applicable_domains": list(fact.applicable_domains),
        "rejected_alternatives_count": len(fact.rejected_alternatives),
        "contradiction_state": fact.contradiction_state,
        "is_confirmed": fact.is_confirmed,
    }


def _contradiction_to_dict(cr: ContradictionRecord) -> dict[str, Any]:
    """Serialise a ContradictionRecord to JSON-compatible dict."""
    return {
        "loser_fact": _authoritative_fact_to_dict(cr.loser_fact),
        "winner_fact": _authoritative_fact_to_dict(cr.winner_fact),
        "resolution_strategy": cr.resolution_strategy,
        "rejection_reason": cr.rejection_reason,
        "scoring_impact": cr.scoring_impact,
    }


def write_output_files(
    adjudicated: dict,
    contradictions: list[ContradictionRecord],
    output_dir: Path = Path("exports"),
) -> None:
    """Write authoritative_facts.json and contradictions.json to exports/."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write authoritative facts
    facts_out = {}
    for canon_name, fact in adjudicated.items():
        facts_out[canon_name] = _authoritative_fact_to_dict(fact)

    facts_path = output_dir / "authoritative_facts.json"
    with open(facts_path, "w", encoding="utf-8") as f:
        json.dump(facts_out, f, indent=2, ensure_ascii=False)
    print(f"  → Written: {facts_path}")

    # Write contradictions
    contradictions_out = [_contradiction_to_dict(cr) for cr in contradictions]

    contra_path = output_dir / "contradictions.json"
    with open(contra_path, "w", encoding="utf-8") as f:
        json.dump(contradictions_out, f, indent=2, ensure_ascii=False)
    print(f"  → Written: {contra_path}")


def print_summary(adjudicated: dict, contradictions: list[ContradictionRecord]) -> None:
    """Print human-readable summary of Phase 1A results."""
    print("\n=== PHASE 1A RESULTS ===")
    print(f"\nAdjudicated facts ({len(adjudicated)} canonical names):")
    for canon, fact in sorted(adjudicated.items()):
        status = "✓ WINNER" if fact.is_confirmed else "○ survivor"
        print(f"  {canon}: {fact.canonical_value} [{status}] (weight={fact._weight()}, state={fact.deployment_state})")

    print(f"\nContradiction records ({len(contradictions)} total):")
    for cr in contradictions:
        print(f"  ✗ {cr.loser_fact.canonical_value} → ✓ {cr.winner_fact.canonical_value}")
        print(f"    strategy={cr.resolution_strategy}: {cr.rejection_reason[:80]}...")


def main() -> None:
    """Run Phase 1A validation checkpoint."""
    print("PHASE 1A VALIDATION CHECKPOINT")
    print("=" * 40)
    print("\nRunning: Transcript → Normalisation → AuthoritativeFact → ContradictionRecord")

    # Run adjudication
    adjudicated, contradictions, regression = run_phase1a_validation()

    # Print summary
    print_summary(adjudicated, contradictions)

    # Write output files
    print("\nOutput files:")
    write_output_files(adjudicated, contradictions)

    # Regression assertions
    print(f"\n{'='*40}")
    print("REGRESSION ASSERTIONS (BRANDED):")
    print(regression)

    if not regression.passed:
        print("\n⚠ Phase 1A FAILED — do NOT proceed to Domain Packages.")
        raise SystemExit(1)
    else:
        print("\n✓ Phase 1A PASSED — safe to proceed to Domain Packages.")


if __name__ == "__main__":
    main()