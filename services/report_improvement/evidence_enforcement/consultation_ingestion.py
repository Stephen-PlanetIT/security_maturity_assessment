from __future__ import annotations

"""
Generic, Customer-Agnostic Consultation Ingestion Adapter (Phase 2.1).

Converts raw customer consultation dictionaries into typed canonical EvidenceRecord
objects using field-aware semantic interpretation and compound decomposition.

MULTI-CUSTOMER & GENERALISATION COMPLIANCE:
- Operates strictly from canonical field keys and field-aware semantic interpretation.
- No customer-name checks or customer-specific branches.
- No hard-coded references to specific organizations or sectors.
- Every valid record carries a non-null source locator, parent lineage, and calibrated confidence.
"""

from typing import Any, Dict, List, Tuple, Optional
import hashlib
from services.report_improvement.evidence_enforcement.canonical_models import (
    AssuranceState,
    EvidenceScope,
    ScoringRole,
    EvidenceRecord,
)
from services.report_improvement.evidence_enforcement.semantic_normalisation import (
    interpret_field_value,
)


def ingest_consultation_profile(
    profile: Dict[str, Any],
    source_path: str = "consultation_profile",
    client_id: Optional[str] = None,
) -> Tuple[List[EvidenceRecord], List[str], Dict[str, Any]]:
    """
    Ingests a raw consultation dictionary and produces:
    - valid canonical EvidenceRecords with real source locators, parent lineage, and explicit scoring roles
    - rejected field names
    - metadata summary (fingerprint, raw_count, etc.)
    """
    records: List[EvidenceRecord] = []
    rejected: List[str] = []
    raw_count = len(profile)

    # Compute deterministic fingerprint of input object
    raw_serialized = str(sorted(profile.items()))
    input_fingerprint = hashlib.sha256(raw_serialized.encode("utf-8")).hexdigest()

    for field_key, raw_val in profile.items():
        if raw_val is None:
            raw_val_str = ""
        else:
            raw_val_str = str(raw_val).strip()

        # Handle compliance targets: explicit COMPLIANCE_TARGET_ONLY scoring role
        if field_key == "compliance":
            if raw_val_str:
                targets = [t.strip() for t in raw_val_str.replace(";", ",").split(",") if t.strip()]
                for t_idx, target in enumerate(targets):
                    eid = f"ev_compliance_{t_idx}_{hashlib.md5(target.encode('utf-8')).hexdigest()[:8]}"
                    records.append(EvidenceRecord(
                        evidence_id=eid,
                        canonical_topic=f"compliance_target_{t_idx}",
                        assurance_state=AssuranceState.REPORTED_PRESENT,
                        evidence_scope=EvidenceScope.COMPLIANCE_TARGET,
                        scoring_role=ScoringRole.COMPLIANCE_TARGET_ONLY,
                        raw_statement=target,
                        normalised_statement=target,
                        source_type="customer_profile",
                        source_locator=f"{source_path}:compliance[{t_idx}]",
                        applicable_domains=["compliance_alignment"],
                        confidence=0.85,
                        supplier_owned=False,
                    ))
            continue

        # Handle critical assets: explicit INVENTORY_ONLY or BUSINESS_IMPACT_ONLY
        if field_key == "critical_asset_profile" and isinstance(raw_val, dict):
            for cat, items in raw_val.items():
                if isinstance(items, list):
                    for idx, item in enumerate(items):
                        item_str = str(item).strip()
                        if item_str:
                            eid = f"ev_asset_{cat}_{idx}_{hashlib.md5(item_str.encode('utf-8')).hexdigest()[:8]}"
                            records.append(EvidenceRecord(
                                evidence_id=eid,
                                canonical_topic=f"asset_{cat}",
                                assurance_state=AssuranceState.REPORTED_PRESENT,
                                evidence_scope=EvidenceScope.CRITICAL_ASSET,
                                scoring_role=ScoringRole.INVENTORY_ONLY,
                                raw_statement=item_str,
                                normalised_statement=item_str,
                                source_type="customer_profile",
                                source_locator=f"{source_path}:critical_asset_profile.{cat}[{idx}]",
                                applicable_domains=["asset_assurance", "information_protection"],
                                confidence=0.90,
                            ))
                elif isinstance(items, str) and items.strip():
                    eid = f"ev_asset_{cat}_{hashlib.md5(items.strip().encode('utf-8')).hexdigest()[:8]}"
                    records.append(EvidenceRecord(
                        evidence_id=eid,
                        canonical_topic=f"asset_{cat}",
                        assurance_state=AssuranceState.REPORTED_PRESENT,
                        evidence_scope=EvidenceScope.CRITICAL_ASSET,
                        scoring_role=ScoringRole.INVENTORY_ONLY,
                        raw_statement=items.strip(),
                        normalised_statement=items.strip(),
                        source_type="customer_profile",
                        source_locator=f"{source_path}:critical_asset_profile.{cat}",
                        applicable_domains=["asset_assurance"],
                        confidence=0.90,
                    ))
            continue

        # Skip non-evidence metadata
        if field_key in ("customer_name", "consultant_name", "industry"):
            continue

        # General fields: Apply field-aware semantic interpretation and decomposition
        parent_eid = f"ev_{field_key}_{hashlib.md5(raw_val_str.encode('utf-8')).hexdigest()[:8]}"
        field_locator = f"{source_path}:{field_key}"
        decomposed = interpret_field_value(
            field_key=field_key,
            raw_val=raw_val,
            source_locator=field_locator,
            parent_evidence_id=parent_eid,
        )

        if not decomposed:
            rejected.append(field_key)
        else:
            records.extend(decomposed)

    meta = {
        "input_fingerprint": input_fingerprint,
        "source_path": source_path,
        "client_identifier": client_id or profile.get("customer_name", "unknown_client"),
        "raw_field_count": raw_count,
        "normalised_evidence_count": len(records),
        "rejected_field_count": len(rejected),
        "rejected_fields": rejected,
    }
    return records, rejected, meta
