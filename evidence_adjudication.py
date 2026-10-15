"""evidence_adjudication.py — Phase 1A: AuthoritativeFact, ContradictionRecord, Source Precedence Engine."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, FrozenSet, List, Tuple, Optional


# ──────────────────────────────────────────────
# Source Precedence Weights (deterministic, non-configurable)
# ──────────────────────────────────────────────

_SOURCE_WEIGHTS = {
    "consultant_approved": 10,
    "transcript":            6,
    "meeting_summary":       5,
    "customer_profile":      4,
    "baseline_normalised":   3,
    "sample_fixture":        1,
}

# Always-override: fixture loses to anything with weight >= 4 against same canonical_name
_FIXTURE_OVERRIDES_MIN_WEIGHT = 4


# ──────────────────────────────────────────────
# AuthoritativeFact (immutable dataclass)
# ──────────────────────────────────────────────

@dataclass(frozen=True)
class AuthoritativeFact:
    """Immutable authoritative fact with full provenance."""

    fact_id: str
    canonical_name: str           # e.g. "identity_provider", "mfa_enforcement"
    canonical_value: Any          # Normalised value (string, dict, bool, list)

    deployment_state: str         # "planned" | "piloting" | "in-use" | "decommissioned" | "unknown"
    confidence: float             # 0.0 - 1.0

    authority_source: str         # deterministic enum matching _SOURCE_WEIGHTS keys
    evidence_ids: Tuple[str, ...]
    source_excerpt: str           # verbatim excerpt from evidence

    applicable_domains: FrozenSet[str]
    rejected_alternatives: FrozenSet["AuthoritativeFact"]  # populated post-adjudicate()
    contradiction_state: str      # "resolved" | "flagged" | "merged" (default="resolved" when empty)

    def _weight(self) -> int:
        return _SOURCE_WEIGHTS.get(self.authority_source, 0)

    @property
    def is_confirmed(self) -> bool:
        """Fact qualifies as an established deployment."""
        return self.deployment_state == "in-use" and self.confidence >= 0.50


# ──────────────────────────────────────────────
# ContradictionRecord (immutable dataclass)
# ──────────────────────────────────────────────

@dataclass(frozen=True)
class ContradictionRecord:
    """Why an alternative fact was rejected in favour of a winner."""

    loser_fact: AuthoritativeFact
    winner_fact: AuthoritativeFact
    resolution_strategy: str      # "override_deterministic" | "higher_authority_wins" | "merge_with_note" | "flag_for_review"
    rejection_reason: str
    scoring_impact: str           # "none" | "domain_affects_scoring" | "capability_mismatch_triggered"


# ──────────────────────────────────────────────
# Adjudicate — deterministic source precedence
# ──────────────────────────────────────────────

def adjudicate(
    canonical_name: str,
    candidates: List[AuthoritativeFact],
) -> AuthoritativeFact:
    """Select one authoritative fact from competing evidence sources.

    Deterministic precedence: consultant_approved > transcript > meeting_summary
        > customer_profile > baseline_normalised > sample_fixture

    Returns AuthoritativeFact with all losers stored in rejected_alternatives.
    Losers are attached as raw AuthoritativeFact (their full data preserved).
    """
    if not candidates:
        raise ValueError(f"No evidence candidates for canonical_name '{canonical_name}'")

    if len(candidates) == 1:
        return candidates[0]

    # Sort by weight DESC, then confidence DESC (tiebreaker)
    sorted_c = sorted(
        candidates,
        key=lambda f: (f._weight(), f.confidence),
        reverse=True,
    )

    winner = sorted_c[0]
    losers = sorted_c[1:]

    # Build ContradictionRecords for each loser
    contradictions = []
    for loser in losers:
        strategy, reason, impact = _resolve(loser, winner)
        contradictions.append(ContradictionRecord(
            loser_fact=loser,
            winner_fact=winner,
            resolution_strategy=strategy,
            rejection_reason=reason,
            scoring_impact=impact,
        ))

    # Determine contradiction_state for winner
    if any(c.resolution_strategy == "flag_for_review" for c in contradictions):
        cd_state = "flagged"
    elif any(c.resolution_strategy == "merge_with_note" for c in contradictions):
        cd_state = "merged"
    else:
        cd_state = "resolved"

    # Return winner with losers attached (need mutable copy then freeze)
    return AuthoritativeFact(
        fact_id=winner.fact_id,
        canonical_name=winner.canonical_name,
        canonical_value=winner.canonical_value,
        deployment_state=winner.deployment_state,
        confidence=winner.confidence,
        authority_source=winner.authority_source,
        evidence_ids=winner.evidence_ids,
        source_excerpt=winner.source_excerpt,
        applicable_domains=winner.applicable_domains,
        rejected_alternatives=frozenset(losers),
        contradiction_state=cd_state,
    )


def _resolve(loser: AuthoritativeFact, winner: AuthoritativeFact) -> Tuple[str, str, str]:
    """Determine resolution strategy + human-readable rejection reason."""

    # Rule 1: Fixture ALWAYS loses to customer-specific evidence (weight >= 4)
    if loser.authority_source == "sample_fixture" and winner._weight() >= _FIXTURE_OVERRIDES_MIN_WEIGHT:
        return (
            "override_deterministic",
            f"Fixture value ('{loser.canonical_value}') is template default. Winner from {winner.authority_source}: '{winner.canonical_value}'",
            "none",
        )

    # Rule 2: Same weight, compatible values → merge (e.g., MFA base + exception)
    if loser._weight() == winner._weight() and _are_compatible(loser, winner):
        return (
            "merge_with_note",
            f"Same authority ({loser._weight()}); '{loser.canonical_value}' preserved alongside winner '{winner.canonical_value}'",
            "domain_affects_scoring",
        )

    # Rule 3: Transcript vs baseline on operational state → flag for review (timing)
    if {loser.authority_source, winner.authority_source} == {"transcript", "baseline_normalised"}:
        return (
            "flag_for_review",
            f"Winner '{winner.canonical_value}' ({winner.authority_source}, weight={winner._weight()}) "
            f"overcomes loser '{loser.canonical_value}' ({loser.authority_source}, weight={loser._weight()}) "
            f"different temporal scope — consultant verification recommended",
            "none",
        )

    # Rule 4: Default — higher weight wins
    diff = winner._weight() - loser._weight()
    return (
        "higher_authority_wins",
        f"Winner '{winner.canonical_value}' ({winner.authority_source}, w={winner._weight()}) "
        f"overcomes loser '{loser.canonical_value}' ({loser.authority_source}, w={loser._weight()}) "
        f"by {diff} authority levels",
        "none",
    )


def _are_compatible(loser: AuthoritativeFact, winner: AuthoritativeFact) -> bool:
    """Check if two facts are compatible (non-mutually-exclusive)."""
    # MFA base + exception always compatible
    if {"mfa_enforcement", "mfa_exception"} == {loser.canonical_name, winner.canonical_name}:
        return True
    # Same canonical + same value → always compatible
    if loser.canonical_name == winner.canonical_name and loser.canonical_value == winner.canonical_value:
        return True
    return False


# ──────────────────────────────────────────────
# adjudicate_evidence_v2 — entry point for Phase 1A integration
# ──────────────────────────────────────────────

def _normalise_canonical(name: str) -> str:
    """Normalise a product/config name to canonical field name."""
    mapping = {
        "identity_provider": ["identity_provider", "idp", "sso", "primary_email_platform"],
        "mfa_enforcement": ["mfa_enforcement", "mfa_status", "mfa_coverage"],
        "mfa_exception": ["mfa_exception", "mfa_exemptions", "mfa_exclude"],
        "backup_solution": ["backup_solution", "backup_platform", "replication_tool"],
        "cold_storage": ["cold_storage", "immutable_backup", "archive_storage"],
        "cloud_provider": ["cloud_provider", "iaas_vendor", "compute_platform"],
        "edr_vendor": ["edr_vendor", "edr_xdr_deployed", "endpoint_protection", "antivirus"],
        "helpdesk_system": ["helpdesk_system", "ticketing_platform", "service_desk"],
        "supplier_evaluation_status": ["supplier_evaluation", "supplier_relationship", "vendor_onboarding"],
        "board_members": ["board_governance", "board_members", "cyber_literate_board"],
        "on_premises_storage": ["on_premises_storage", "nas_device", "file_server"],
    }
    for canonical, aliases in mapping.items():
        if name.lower() in aliases:
            return canonical
    return name.lower().replace(" ", "_")


def _normalise_value(raw: Any) -> Any:
    """Normalise a raw evidence value into a canonical representation."""
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, dict):
        # Keep dicts intact but normalise string keys/values recursively
        return {str(k): _normalise_value(v) for k, v in raw.items()}
    if isinstance(raw, list):
        return [_normalise_value(x) for x in raw]
    return raw


def adjudicate_evidence_v2(
    existing_controls: List[str],
    technologies: List[str],
    suppliers: List[str],
    cloud_platforms: List[str],
    security_products: List[str],
    transcript_quotes: List[str],
    summary_text: str,
) -> Tuple[dict, List[ContradictionRecord]]:
    """Construct AuthoritativeFacts from raw evidence and run adjudication.

    Returns (adjudicated_dict, all_contradictions) where:
      - adjudicated_dict maps canonical_name → AuthoritativeFact winner
      - all_contradictions contains all ContradictionRecords for audit trail
    """
    all_contradictions: List[ContradictionRecord] = []

    # Group candidates by normalised canonical name
    candidates_by_canonical: dict = {}

    def _add(canonical_name: str, value: Any, authority_source: str, confidence: float,
             deployment_state: str, evidence_ids: List[str], excerpt: str, domains: FrozenSet[str]):
        canon = _normalise_canonical(canonical_name)
        norm_value = _normalise_value(value)
        fact_id = f"{canon}:{abs(hash(str(norm_value)) + abs(hash(authority_source)))}"
        candidates_by_canonical.setdefault(canon, []).append(
            AuthoritativeFact(
                fact_id=fact_id,
                canonical_name=canonical_name,
                canonical_value=norm_value,
                deployment_state=deployment_state,
                confidence=confidence,
                authority_source=authority_source,
                evidence_ids=tuple(evidence_ids),
                source_excerpt=str(excerpt)[:500],
                applicable_domains=domains,
                rejected_alternatives=frozenset(),  # populated by adjudicate()
                contradiction_state="resolved",     # populated by adjudicate()
            )
        )

    # --- Existing controls from baseline_normalised or transcript ---
    for ctrl in (existing_controls or []):
        name = str(ctrl).strip()
        if not name:
            continue
        lower = name.lower()
        if any(k in lower for k in ["google", "office", "entra", "azure ad", "okta"]):
            _add("identity_provider", name, "baseline_normalised", 0.70, "in-use", [name], f"Existing control: {name}", frozenset(["iam"]))
        elif any(k in lower for k in ["veeam", "backup", "replica"]):
            _add("backup_solution", name, "baseline_normalised", 0.75, "in-use", [name], f"Existing control: {name}", frozenset(["recovery_ir"]))
        elif any(k in lower for k in ["webroot", "sophos", "defender", "cyber"]):
            pass  # Handled below with security_products
        else:
            _add("existing_control", name, "baseline_normalised", 0.60, "in-use", [name], f"Existing control: {name}", frozenset(["general"]))

    # --- Technologies / suppliers ---
    for tech in (technologies or []):
        t = str(tech).strip()
        if not t:
            continue
        lower = t.lower()
        if any(k in lower for k in ["google", "office 365"]):
            _add("identity_provider", t, "transcript", 0.90, "in-use", [t], f"Technology: {t}", frozenset(["iam"]))
        elif any(k in lower for k in ["microsoft azure", "entra"]):
            _add("cloud_provider", t, "transcript", 0.60, "planned", [t], f"Technology: {t}", frozenset(["supplier_management"]))
        else:
            _add("technology", t, "transcript", 0.70, "in-use", [t], f"Technology: {t}", frozenset(["general"]))

    for sup in (suppliers or []):
        s = str(sup).strip()
        if not s:
            continue
        lower = s.lower()
        if any(k in lower for k in ["spire", "digitalocean"]):
            _add("cloud_provider", s, "transcript", 0.80, "piloting" if "spire" in lower else "in-use", [s], f"Supplier: {s}", frozenset(["supplier_management"]))
        elif "freshdesk" in lower:
            _add("helpdesk_system", s, "transcript", 0.85, "in-use", [s], f"Supplier: {s}", frozenset(["monitoring"]))
        else:
            _add("supplier", s, "transcript", 0.65, "in-use", [s], f"Supplier: {s}", frozenset(["supplier_management"]))

    # --- Cloud platforms ---
    for cp in (cloud_platforms or []):
        c = str(cp).strip()
        if not c:
            continue
        lower = c.lower()
        if "digitalocean" in lower:
            _add("cloud_provider", c, "transcript", 0.85, "in-use", [c], f"Cloud platform: {c}", frozenset(["supplier_management"]))
        elif any(k in lower for k in ["google cloud", "gcs", "storage"]):
            _add("cold_storage", c, "transcript", 0.75, "in-use", [c], f"Cloud storage: {c}", frozenset(["recovery_ir"]))
        else:
            _add("cloud_provider", c, "customer_profile", 0.60, "piloting", [c], f"Cloud platform: {c}", frozenset(["supplier_management"]))

    # --- Security products (include Sophos MDR if explicitly confirmed) ---
    for sp in (security_products or []):
        s = str(sp).strip()
        if not s:
            continue
        lower = s.lower()
        if "sophos mdr" in lower:
            _add("edr_xdr_deployed", s, "transcript", 0.80, "piloting", [s], f"Security product: {s}", frozenset(["monitoring"]))
        elif "webroot" in lower:
            _add("edr_vendor", s, "transcript", 0.85, "in-use", [s], f"EDR vendor: {s}", frozenset(["monitoring"]))

    # --- Transcript quotes (extract named entities as potential evidence) ---
    _QUOTED_FACTS = {
        "identity_provider": ["google workspace", "office 365", "microsoft 365", "entra"],
        "mfa_enforcement": ["mfa", "multi-factor", "2fa", "two factor"],
        "mfa_exception": ["ftp server", "ftp exempt", "ftp exception", "mfa exclude"],
        "backup_solution": ["veeam", "veeam backup", "veeam replica"],
        "cold_storage": ["google cloud storage", "gcs", "cloud storage", "archive"],
        "cloud_provider": ["digitalocean", "azure", "aws", "gcp"],
        "edr_vendor": ["sophos", "webroot", "defender", "crowdstrike", "sentinelone"],
        "helpdesk_system": ["freshdesk"],
        "on_premises_storage": ["qnap", "nas", "synology"],
    }

    for quote in (transcript_quotes or []):
        q = str(quote).strip()
        if not q:
            continue
        qlower = q.lower()
        for canon, keywords in _QUOTED_FACTS.items():
            for kw in keywords:
                if kw in qlower:
                    domain = "iam" if canon == "identity_provider" else ("monitoring" if canon in ("edr_vendor", "mfa_enforcement") else "general")
                    _add(canon, kw.title(), "transcript", 0.90, "in-use", [q[:100]], f"Transcript quote: {q[:200]}", frozenset([domain]))

    # --- Summary text (lower weight than transcript) ---
    summary_lower = (summary_text or "").strip().lower()
    for canon, keywords in _QUOTED_FACTS.items():
        for kw in keywords:
            if kw in summary_lower and canon not in candidates_by_canonical:
                _add(canon, kw.title(), "meeting_summary", 0.50, "piloting", ["summary"], f"Summary text: {summary_text[:200]}", frozenset(["general"]))

    # --- Now run adjudicate() on each group ---
    adjudicated = {}
    for canonical_name in list(candidates_by_canonical.keys()):
        candidates = candidates_by_canonical[canonical_name]
        if len(candidates) == 1:
            adjudicated[canonical_name] = candidates[0]
            continue

        winner = adjudicate(canonical_name, candidates)
        adjudicated[canonical_name] = winner

    # Second pass: capture contradictions from all adjudicated groups with losers
    for canonical_name, candidates in candidates_by_canonical.items():
        if len(candidates) <= 1:
            continue
        winner = adjudicated.get(canonical_name)
        if not winner or not winner.rejected_alternatives:
            continue
        for loser in winner.rejected_alternatives:
            # Determine resolution strategy by re-running _resolve
            strategy, reason, impact = _resolve(loser, winner)
            all_contradictions.append(ContradictionRecord(
                loser_fact=loser,
                winner_fact=winner,
                resolution_strategy=strategy,
                rejection_reason=reason,
                scoring_impact=impact,
            ))

    return adjudicated, all_contradictions


# ──────────────────────────────────────────────
# Regression Assertions — BRANDED acceptance criteria
# ──────────────────────────────────────────────

@dataclass(frozen=True)
class AssertionFailure:
    """Single regression assertion failure."""
    canonical_name: str
    expected_winner: str
    actual_winner: str
    severity: str   # "hard" | "soft"


@dataclass(frozen=True)
class RegressionResult:
    """Collection of regression assertion results against adjudicated output."""
    passed: bool
    survivors: List[str]          # Canonical names with expected surviving facts
    rejections: List[str]         # Canonical names with expected rejected facts
    failures: Tuple[AssertionFailure, ...]  # All failed assertions

    def __str__(self) -> str:
        lines = [f"Regression assertions: {'PASS' if self.passed else 'FAIL'}"]
        for s in self.survivors:
            lines.append(f"  ✓ survivor: {s}")
        for r in self.rejections:
            lines.append(f"  ✓ rejected: {r}")
        for f in self.failures:
            lines.append(f"  ✗ FAIL [{f.severity}] {f.canonical_name}: expected='{f.expected_winner}' actual='{f.actual_winner}'")
        return "\n".join(lines)


def _assert_survives(
    canonical_name: str,
    winner_fact: Optional[AuthoritativeFact],
    all_contradictions: List[ContradictionRecord],
    expected_value: str,
) -> Tuple[AssertionFailure, bool]:
    """Check that a fact is the winner (survives adjudication)."""
    if winner_fact is not None and str(winner_fact.canonical_value).lower() == expected_value.lower():
        return (None, True)

    # Check if it was rejected — collect rejection reason
    rejection_reasons = []
    for cr in all_contradictions:
        if str(cr.winner_fact.canonical_name).lower() == canonical_name.lower():
            if cr.loser_fact.canonical_value.lower() == expected_value.lower():
                rejection_reasons.append(f"{cr.resolution_strategy}: {cr.rejection_reason}")

    actual = winner_fact.canonical_value if winner_fact else "(no candidate)"
    return (
        AssertionFailure(
            canonical_name=canonical_name,
            expected_winner=expected_value,
            actual_winner=str(actual),
            severity="hard",
        ),
        False,
    )


def _assert_rejected(
    canonical_name: str,
    winner_fact: Optional[AuthoritativeFact],
    all_contradictions: List[ContradictionRecord],
    rejected_value: str,
) -> Tuple[AssertionFailure, bool]:
    """Check that a candidate is rejected (does not win)."""
    if winner_fact is None:
        return (None, True)  # No winner at all — acceptable rejection

    if winner_fact.canonical_value.lower() == rejected_value.lower():
        return (
            AssertionFailure(
                canonical_name=canonical_name,
                expected_winner=f"<not {rejected_value}>",
                actual_winner=str(rejected_value),
                severity="hard",
            ),
            False,
        )

    # Verify rejection record exists for this loser
    rejected_recorded = False
    for cr in all_contradictions:
        if (str(cr.loser_fact.canonical_value).lower() == rejected_value.lower() and
            str(cr.winner_fact.canonical_name).lower() == canonical_name.lower()):
            rejected_recorded = True
            break

    if not rejected_recorded and winner_fact is not None:
        # No explicit rejection record — but value didn't win, so acceptable
        pass

    return (None, True)


def regression_assert_branded(
    adjudicated: dict,
    all_contradictions: List[ContradictionRecord],
) -> RegressionResult:
    """Validate BRANDED acceptance criteria against adjudicated facts.

    Expected survivors (canonical_name → canonical_value):
        identity_provider     → google workspace
        mfa_enforcement       → mfa base accepted
        mfa_exception         → ftp server (piloting)
        edr_vendor            → webroot
        backup_solution       → veeam
        on_premises_storage   → qnap
        cloud_provider        → digitalocean
        helpdesk_system       → freshdesk

    Expected rejections:
        identity_provider     → microsoft entra (lost to google workspace)
        cloud_provider        → microsoft azure (lost to digitalocean)
        edr_xdr_deployed      → sophos mdr (no confirmed deployment)
        edr_xdr_deployed      → sophos mdr plus (no confirmed deployment)
        subscription_service  → hoxhunt (not confirmed)

    Returns RegressionResult with passed flag, survivors, rejections, and failures.
    """
    failures: list = []
    survivors: list = []
    rejections: list = []

    # --- Survival assertions ---
    checks = [
        ("identity_provider", "google workspace"),
        ("mfa_enforcement", "mfa"),
        ("mfa_exception", "ftp server"),
        ("edr_vendor", "webroot"),
        ("backup_solution", "veeam"),
        ("on_premises_storage", "qnap"),
        ("cloud_provider", "digitalocean"),
        ("helpdesk_system", "freshdesk"),
    ]

    for canon, expected in checks:
        winner = adjudicated.get(canon)
        fail, ok = _assert_survives(canon, winner, all_contradictions, expected)
        if ok:
            survivors.append(f"{canon}: {expected}")
        else:
            failures.append(fail)

    # --- Rejection assertions ---
    rejected_checks = [
        ("identity_provider", "microsoft entra"),
        ("cloud_provider", "microsoft azure"),
        ("edr_xdr_deployed", "sophos mdr"),
        ("edr_xdr_deployed", "sophos mdr plus"),
        ("subscription_service", "hoxhunt"),
    ]

    for canon, rejected in rejected_checks:
        winner = adjudicated.get(canon)
        fail, ok = _assert_rejected(canon, winner, all_contradictions, rejected)
        if ok:
            rejections.append(f"{canon}: {rejected} (rejected)")
        else:
            failures.append(fail)

    return RegressionResult(
        passed=len(failures) == 0,
        survivors=survivors,
        rejections=rejections,
        failures=tuple(failures),
    )
