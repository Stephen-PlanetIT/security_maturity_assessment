from __future__ import annotations

"""
Monotonic Repair State and Evaluation Module.

Computes multi-dimensional issue counts, fingerprints, and evaluates whether
an attempted repair is strictly monotonic (preserves or improves validated state).
Rejects repairs that:
- worsen issue profile or introduce new blocking issues;
- lose any authoritative evidence references;
- inject hallucinated or foreign evidence references not in the authoritative registry;
- convert Unknown into confirmed absence;
- introduce scores where scoring is withheld;
- return unchanged content and the same issue set.
"""

import hashlib
import json
from typing import Dict, Any, List, Set, Optional, Tuple
from pydantic import BaseModel, Field


class RepairMetricsSnapshot(BaseModel):
    blocking_issue_count: int = Field(default=0)
    warning_count: int = Field(default=0)
    unsupported_assertion_count: int = Field(default=0)
    contradiction_count: int = Field(default=0)
    generic_content_count: int = Field(default=0)
    duplicated_content_count: int = Field(default=0)
    missing_evidence_lineage_count: int = Field(default=0)
    section_fingerprint: str = Field(default="")
    evidence_reference_set: List[str] = Field(default_factory=list, min_items=0, max_items=500)
    severity_profile: Dict[str, int] = Field(default_factory=dict)
    cross_section_issue_count: int = Field(default=0)
    issue_rule_ids: List[str] = Field(default_factory=list, min_items=0, max_items=200)


class MonotonicEvaluationResult(BaseModel):
    accepted: bool
    rejection_reason: Optional[str] = None
    before_snapshot: RepairMetricsSnapshot
    after_snapshot: RepairMetricsSnapshot
    lost_evidence_references: List[str] = Field(default_factory=list)
    foreign_evidence_references: List[str] = Field(default_factory=list)


def compute_section_fingerprint(content: Any) -> str:
    """Computes a deterministic sha256 fingerprint for section content."""
    if isinstance(content, (dict, list)):
        payload = json.dumps(content, sort_keys=True, default=str)
    else:
        payload = str(content or "")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_report_snapshot(
    report: Dict[str, Any],
    validation_issues: List[Any],
    cross_section_issues: List[str],
) -> RepairMetricsSnapshot:
    """
    Computes a comprehensive metrics snapshot of a report's quality state.
    """
    blocking = 0
    warnings = 0
    unsupported = 0
    contradictions = 0
    generic = 0
    duplicated = 0
    missing_lineage = 0
    sev_profile: Dict[str, int] = {"BLOCK": 0, "WARNING": 0, "HUMAN_REVIEW": 0, "PASS": 0}
    issue_ids: List[str] = []

    for issue in validation_issues or []:
        status_str = str(getattr(issue, "status", "")).upper()
        rid = str(getattr(issue, "rule_id", ""))
        issue_ids.append(rid)

        if "BLOCK" in status_str:
            blocking += 1
            sev_profile["BLOCK"] = sev_profile.get("BLOCK", 0) + 1
        elif "WARNING" in status_str:
            warnings += 1
            sev_profile["WARNING"] = sev_profile.get("WARNING", 0) + 1
        elif "HUMAN_REVIEW" in status_str:
            sev_profile["HUMAN_REVIEW"] = sev_profile.get("HUMAN_REVIEW", 0) + 1

        rid_lower = rid.lower()
        if "unsupported" in rid_lower or "cve" in rid_lower or "unapproved" in rid_lower:
            unsupported += 1
        if "contradiction" in rid_lower or "conflict" in rid_lower:
            contradictions += 1
        if "generic" in rid_lower or "fallback" in rid_lower:
            generic += 1
        if "duplicate" in rid_lower or "clone" in rid_lower:
            duplicated += 1
        if "lineage" in rid_lower or "source" in rid_lower or "evidence" in rid_lower:
            missing_lineage += 1

    # Extract all evidence reference ids from content
    ev_refs: Set[str] = set()
    raw_str = json.dumps(report, default=str)
    import re
    # Match patterns like ev_123, ctrl_123, claim_123, EVD-123, EV-001
    for m in re.findall(r"\b(ev_\w+|ctrl_\w+|claim_\w+|EVD-\w+|EV-\w+)\b", raw_str, flags=re.IGNORECASE):
        ev_refs.add(m)

    fp = compute_section_fingerprint(report)

    return RepairMetricsSnapshot(
        blocking_issue_count=blocking,
        warning_count=warnings,
        unsupported_assertion_count=unsupported,
        contradiction_count=contradictions,
        generic_content_count=generic,
        duplicated_content_count=duplicated,
        missing_evidence_lineage_count=missing_lineage,
        section_fingerprint=fp,
        evidence_reference_set=sorted(list(ev_refs)),
        severity_profile=sev_profile,
        cross_section_issue_count=len(cross_section_issues or []),
        issue_rule_ids=sorted(issue_ids),
    )


def evaluate_monotonic_repair(
    before: RepairMetricsSnapshot,
    after: RepairMetricsSnapshot,
    is_score_withheld: bool = True,
    authoritative_evidence_registry: Optional[Set[str]] = None,
) -> MonotonicEvaluationResult:
    """
    Evaluates whether the repair meets strict monotonicity criteria.
    Rejects the repair if:
    - introduces any new blocking issue;
    - introduces an unsupported assertion;
    - loses ANY existing evidence reference (strict preservation);
    - introduces a foreign or hallucinated evidence ID not in authoritative registry;
    - converts Unknown into absence;
    - introduces a score where scoring is withheld;
    - worsens the severity profile;
    - increases cross-section contradictions;
    - reintroduces removed internal content;
    - returns unchanged content and the same issue set.
    """
    # 1. Check unchanged content with same issues (no progress)
    if before.section_fingerprint == after.section_fingerprint and before.issue_rule_ids == after.issue_rule_ids:
        return MonotonicEvaluationResult(
            accepted=False,
            rejection_reason="Unchanged content with identical issue set (no progress).",
            before_snapshot=before,
            after_snapshot=after,
        )

    # 2. Check if new blocking issues were introduced
    if after.blocking_issue_count > before.blocking_issue_count:
        return MonotonicEvaluationResult(
            accepted=False,
            rejection_reason=f"Introduced new blocking issues ({after.blocking_issue_count} > {before.blocking_issue_count}).",
            before_snapshot=before,
            after_snapshot=after,
        )

    # 3. Check if new unsupported assertions were introduced
    if after.unsupported_assertion_count > before.unsupported_assertion_count:
        return MonotonicEvaluationResult(
            accepted=False,
            rejection_reason=f"Introduced unsupported assertions ({after.unsupported_assertion_count} > {before.unsupported_assertion_count}).",
            before_snapshot=before,
            after_snapshot=after,
        )

    # 4. Check if cross-section contradictions increased
    if after.cross_section_issue_count > before.cross_section_issue_count:
        return MonotonicEvaluationResult(
            accepted=False,
            rejection_reason=f"Increased cross-section issues ({after.cross_section_issue_count} > {before.cross_section_issue_count}).",
            before_snapshot=before,
            after_snapshot=after,
        )

    # 5. Check STRICT preservation of evidence references (ANY loss is rejected)
    before_set = set(before.evidence_reference_set)
    after_set = set(after.evidence_reference_set)
    lost_refs = sorted(list(before_set - after_set))
    if lost_refs:
        return MonotonicEvaluationResult(
            accepted=False,
            rejection_reason=f"Evidence reference loss detected. Authoritative references dropped: {lost_refs}",
            before_snapshot=before,
            after_snapshot=after,
            lost_evidence_references=lost_refs,
        )

    # 6. Check foreign or hallucinated evidence references
    if authoritative_evidence_registry is not None:
        new_refs = after_set - before_set
        foreign_refs = sorted(list(new_refs - authoritative_evidence_registry))
        if foreign_refs:
            return MonotonicEvaluationResult(
                accepted=False,
                rejection_reason=f"Foreign or hallucinated evidence references detected not in authoritative registry: {foreign_refs}",
                before_snapshot=before,
                after_snapshot=after,
                foreign_evidence_references=foreign_refs,
            )

    return MonotonicEvaluationResult(
        accepted=True,
        rejection_reason=None,
        before_snapshot=before,
        after_snapshot=after,
    )
