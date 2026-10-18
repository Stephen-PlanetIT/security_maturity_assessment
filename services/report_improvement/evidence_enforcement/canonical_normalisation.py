from __future__ import annotations

"""
Deterministic Input Normalisation for Canonical Evidence (Phase 2).

Transforms arbitrary raw strings, consultation answers, and profile values into
explicit AssuranceState and EvidenceRecord representations.

Guarantees:
- Blank/None/whitespace -> NOT_ESTABLISHED_DURING_CONSULTATION or UNKNOWN
- "Unknown" / "Not confirmed" -> UNKNOWN
- "None" / "No" / "Not in place" -> REPORTED_ABSENT
- Supplier-managed / outsourced -> REQUIRES_SUPPLIER_CONFIRMATION
- "N/A" / "Not applicable" -> NOT_APPLICABLE
- Contradictory statements -> CONTRADICTED
- Known working tech / tool -> REPORTED_PRESENT or VERIFIED_PRESENT
"""

import re
from typing import Optional, Tuple
from services.report_improvement.evidence_enforcement.canonical_models import (
    AssuranceState,
    EvidenceScope,
    EvidenceRecord,
)


_ABSENT_PATTERNS = [
    re.compile(r"^(none|no|not in place|not used|not enabled|disabled|absent|nil)$", re.IGNORECASE),
    re.compile(r"\b(no mfa|no backups?|no patching|no policy|not configured|not implemented)\b", re.IGNORECASE),
]

_UNKNOWN_PATTERNS = [
    re.compile(r"^(unknown|unsure|not known|unclear|tbd|to be confirmed|tbc)$", re.IGNORECASE),
    re.compile(r"\b(not confirmed|not established|unvalidated|not assessed|not discussed)\b", re.IGNORECASE),
]

_NA_PATTERNS = [
    re.compile(r"^(n/a|na|not applicable|none applicable|out of scope)$", re.IGNORECASE),
]

_SUPPLIER_PATTERNS = [
    re.compile(r"\b(managed by supplier|third party|supplier owned|outsourced|vendor hosted|managed service)\b", re.IGNORECASE),
]

_VERIFIED_PATTERNS = [
    re.compile(r"\b(verified|demonstrated|tested and confirmed|audited|certified)\b", re.IGNORECASE),
]


def normalise_assurance_state(
    raw_value: Optional[str],
    is_supplier_owned: bool = False,
    is_contradicted: bool = False
) -> AssuranceState:
    """Deterministically maps any input string to an explicit AssuranceState."""
    if is_contradicted:
        return AssuranceState.CONTRADICTED

    if raw_value is None:
        return AssuranceState.NOT_ESTABLISHED_DURING_CONSULTATION

    val = str(raw_value).strip()
    if not val:
        return AssuranceState.NOT_ESTABLISHED_DURING_CONSULTATION

    if any(pat.search(val) for pat in _NA_PATTERNS):
        return AssuranceState.NOT_APPLICABLE

    if is_supplier_owned or any(pat.search(val) for pat in _SUPPLIER_PATTERNS):
        return AssuranceState.REQUIRES_SUPPLIER_CONFIRMATION

    if any(pat.search(val) for pat in _ABSENT_PATTERNS):
        return AssuranceState.REPORTED_ABSENT

    if any(pat.search(val) for pat in _UNKNOWN_PATTERNS):
        return AssuranceState.UNKNOWN

    if any(pat.search(val) for pat in _VERIFIED_PATTERNS):
        return AssuranceState.VERIFIED_PRESENT

    # Default for a populated, non-negative value is REPORTED_PRESENT
    return AssuranceState.REPORTED_PRESENT


def create_canonical_record(
    evidence_id: str,
    canonical_topic: str,
    raw_statement: str,
    scope: EvidenceScope = EvidenceScope.DOMAIN_SPECIFIC_CONTROL,
    source_type: str = "consultant_approved",
    applicable_domains: Optional[list[str]] = None,
    supplier_name: Optional[str] = None,
    confidence: float = 1.0,
    is_contradicted: bool = False,
) -> EvidenceRecord:
    """Helper to instantiate an EvidenceRecord with deterministic normalisation."""
    is_sup = supplier_name is not None or any(p.search(raw_statement) for p in _SUPPLIER_PATTERNS)
    state = normalise_assurance_state(raw_statement, is_supplier_owned=is_sup, is_contradicted=is_contradicted)

    return EvidenceRecord(
        evidence_id=evidence_id,
        canonical_topic=canonical_topic,
        assurance_state=state,
        evidence_scope=scope,
        raw_statement=raw_statement,
        normalised_statement=raw_statement.strip(),
        source_type=source_type,  # type: ignore
        applicable_domains=applicable_domains or [],
        confidence=confidence,
        supplier_owned=is_sup,
        supplier_name=supplier_name,
    )
