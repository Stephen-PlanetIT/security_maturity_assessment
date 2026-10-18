from __future__ import annotations

"""
Structured Output Schema Repair and Normalisation Engine.

Guarantees resilience for specialist BaseModel outputs:
- Missing required fields evaluated against FieldCategory policy:
    * SAFE_STRUCTURAL_DEFAULT: type-safe empty defaults allowed.
    * REQUIRED_ANALYTICAL_CONTENT: NEVER synthesised with fabricated/neutral prose.
    * OPTIONAL_ANALYTICAL_CONTENT: allowed to remain None/empty.
    * DIAGNOSTIC_ONLY: diagnostic metadata populated.
- Wrong list shapes coerced or normalised;
- Decimal / string / float types converted deterministically;
- Missing optional arrays populated with empty list defaults;
- Unexpected extra fields preserved or pruned safely without rejection;
- Model timeouts and exceptions handled fail-closed with explicit diagnostic logging;
- Explicit disposition returned for all repairs.
"""

from enum import Enum
from typing import Dict, Any, Type, Optional, Tuple, List, Set
from decimal import Decimal
from pydantic import BaseModel, ValidationError


class FieldCategory(str, Enum):
    SAFE_STRUCTURAL_DEFAULT = "SAFE_STRUCTURAL_DEFAULT"
    REQUIRED_ANALYTICAL_CONTENT = "REQUIRED_ANALYTICAL_CONTENT"
    OPTIONAL_ANALYTICAL_CONTENT = "OPTIONAL_ANALYTICAL_CONTENT"
    DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY"


class StructuredRepairDisposition(str, Enum):
    VALID_UNCHANGED = "VALID_UNCHANGED"
    REPAIRED_STRUCTURAL_ONLY = "REPAIRED_STRUCTURAL_ONLY"
    REGENERATED_AND_VALIDATED = "REGENERATED_AND_VALIDATED"
    LAST_VALID_RETAINED = "LAST_VALID_RETAINED"
    WITHHELD_SECTION = "WITHHELD_SECTION"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


# Explicit mapping of analytical fields across maturity specialists
ANALYTICAL_FIELD_POLICY: Dict[str, FieldCategory] = {
    # Required Analytical Content - Prohibited from deterministic synthesis
    "assessment_context": FieldCategory.REQUIRED_ANALYTICAL_CONTENT,
    "security_posture_narrative": FieldCategory.REQUIRED_ANALYTICAL_CONTENT,
    "board_level_takeaway": FieldCategory.REQUIRED_ANALYTICAL_CONTENT,
    "strategic_direction": FieldCategory.REQUIRED_ANALYTICAL_CONTENT,
    "evidence_limitations": FieldCategory.REQUIRED_ANALYTICAL_CONTENT,
    "technical_analysis": FieldCategory.REQUIRED_ANALYTICAL_CONTENT,
    "business_impact": FieldCategory.REQUIRED_ANALYTICAL_CONTENT,
    "maturity_rationale": FieldCategory.REQUIRED_ANALYTICAL_CONTENT,
    "recommendation_rationale": FieldCategory.REQUIRED_ANALYTICAL_CONTENT,
    "current_position": FieldCategory.REQUIRED_ANALYTICAL_CONTENT,
    "recommended_focus": FieldCategory.REQUIRED_ANALYTICAL_CONTENT,
    "scenario_reasoning": FieldCategory.REQUIRED_ANALYTICAL_CONTENT,
    "qualitative_cost_narrative": FieldCategory.REQUIRED_ANALYTICAL_CONTENT,
    "executive_summary_text": FieldCategory.REQUIRED_ANALYTICAL_CONTENT,
    "narrative": FieldCategory.REQUIRED_ANALYTICAL_CONTENT,
    "rationale": FieldCategory.REQUIRED_ANALYTICAL_CONTENT,
    "description": FieldCategory.REQUIRED_ANALYTICAL_CONTENT,

    # Safe Structural Defaults
    "evidence_references": FieldCategory.SAFE_STRUCTURAL_DEFAULT,
    "evidence_reference_set": FieldCategory.SAFE_STRUCTURAL_DEFAULT,
    "caveats": FieldCategory.SAFE_STRUCTURAL_DEFAULT,
    "tags": FieldCategory.SAFE_STRUCTURAL_DEFAULT,
    "metadata": FieldCategory.SAFE_STRUCTURAL_DEFAULT,
    "phases": FieldCategory.SAFE_STRUCTURAL_DEFAULT,
    "action_items": FieldCategory.SAFE_STRUCTURAL_DEFAULT,
    "key_findings": FieldCategory.SAFE_STRUCTURAL_DEFAULT,

    # Diagnostic Only
    "diagnostic_info": FieldCategory.DIAGNOSTIC_ONLY,
    "rule_ids": FieldCategory.DIAGNOSTIC_ONLY,
    "validation_notes": FieldCategory.DIAGNOSTIC_ONLY,
}


def get_field_category(field_name: str) -> FieldCategory:
    """Classifies a field name into its analytical policy category."""
    if field_name in ANALYTICAL_FIELD_POLICY:
        return ANALYTICAL_FIELD_POLICY[field_name]
    lower_name = field_name.lower()
    for k, cat in ANALYTICAL_FIELD_POLICY.items():
        if k in lower_name:
            return cat
    # Default heuristics based on conventions
    if any(term in lower_name for term in ["narrative", "rationale", "context", "takeaway", "impact", "reasoning"]):
        return FieldCategory.REQUIRED_ANALYTICAL_CONTENT
    if any(term in lower_name for term in ["list", "refs", "references", "items", "metadata", "caveats"]):
        return FieldCategory.SAFE_STRUCTURAL_DEFAULT
    return FieldCategory.OPTIONAL_ANALYTICAL_CONTENT


class StructuredRepairRecord(BaseModel):
    section_name: str
    owning_specialist: str
    original_validation_errors: List[str] = []
    fields_repaired: List[str] = []
    fields_not_repairable_deterministically: List[str] = []
    regeneration_attempted: bool = False
    attempt_count: int = 0
    pre_repair_fingerprint: str = ""
    candidate_fingerprint: str = ""
    accepted_fingerprint: str = ""
    monotonic_result: Optional[str] = None
    final_disposition: StructuredRepairDisposition


def safely_parse_specialist_output(
    model_cls: Type[BaseModel],
    raw_data: Any,
    section_name: str,
    last_valid_instance: Optional[BaseModel] = None,
    owning_specialist: str = "UnknownSpecialist",
) -> Tuple[Optional[BaseModel], StructuredRepairDisposition, StructuredRepairRecord]:
    """
    Attempts deterministic schema repair and normalisation before instantiating model_cls.
    Strictly forbids fabricating required analytical prose.
    Returns (parsed_model_or_none, disposition, record).
    """
    import hashlib
    import json

    pre_fp = hashlib.sha256(json.dumps(raw_data if isinstance(raw_data, (dict, list)) else str(raw_data), default=str).encode("utf-8")).hexdigest()
    
    record = StructuredRepairRecord(
        section_name=section_name,
        owning_specialist=owning_specialist,
        pre_repair_fingerprint=pre_fp,
        final_disposition=StructuredRepairDisposition.VALID_UNCHANGED,
    )

    if isinstance(raw_data, model_cls):
        record.accepted_fingerprint = pre_fp
        record.candidate_fingerprint = pre_fp
        return raw_data, StructuredRepairDisposition.VALID_UNCHANGED, record

    if not isinstance(raw_data, dict):
        record.original_validation_errors.append(f"Raw data is not a dict: {type(raw_data).__name__}")
        if last_valid_instance:
            record.final_disposition = StructuredRepairDisposition.LAST_VALID_RETAINED
            return last_valid_instance, StructuredRepairDisposition.LAST_VALID_RETAINED, record
        record.final_disposition = StructuredRepairDisposition.REVIEW_REQUIRED
        return None, StructuredRepairDisposition.REVIEW_REQUIRED, record

    data = dict(raw_data)
    repaired_fields: List[str] = []
    unrepairable_fields: List[str] = []

    # 1. Decimal / numeric string normalisation
    for k, v in list(data.items()):
        if isinstance(v, (int, float)) and "score" in k.lower():
            try:
                data[k] = Decimal(str(v))
                repaired_fields.append(k)
            except Exception:
                pass
        elif isinstance(v, str) and "score" in k.lower() and v.replace(".", "", 1).isdigit():
            try:
                data[k] = Decimal(v)
                repaired_fields.append(k)
            except Exception:
                pass

    # 2. Missing optional arrays
    for fname, ffield in getattr(model_cls, "model_fields", {}).items():
        annotation = getattr(ffield, "annotation", None)
        annotation_str = str(annotation or "")
        if "list" in annotation_str.lower() or "List" in annotation_str:
            if fname not in data or data[fname] is None:
                data[fname] = []
                repaired_fields.append(fname)
            elif not isinstance(data[fname], list):
                data[fname] = [data[fname]]
                repaired_fields.append(fname)

    # 3. Check for missing required fields against Analytical Field Policy
    for fname, ffield in getattr(model_cls, "model_fields", {}).items():
        if ffield.is_required() and (fname not in data or data[fname] is None or data[fname] == ""):
            category = get_field_category(fname)
            if category == FieldCategory.REQUIRED_ANALYTICAL_CONTENT:
                # STRICT RULE: DO NOT FABRICATE OR SYNTHESISE REQUIRED ANALYTICAL PROSE
                unrepairable_fields.append(fname)
                record.original_validation_errors.append(
                    f"Required analytical field '{fname}' is missing or empty. Deterministic prose fabrication is prohibited."
                )
            elif category == FieldCategory.SAFE_STRUCTURAL_DEFAULT:
                annotation = getattr(ffield, "annotation", None)
                if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                    sub_instance, sub_disp, _ = safely_parse_specialist_output(annotation, {}, fname, owning_specialist=owning_specialist)
                    if sub_instance:
                        data[fname] = sub_instance
                        repaired_fields.append(fname)
                else:
                    data[fname] = []
                    repaired_fields.append(fname)
            elif category == FieldCategory.DIAGNOSTIC_ONLY:
                data[fname] = f"Auto-remediation diagnostic for {fname}"
                repaired_fields.append(fname)
            else:
                unrepairable_fields.append(fname)

    # If any required analytical field was missing and could not be deterministically synthesised:
    if unrepairable_fields:
        record.fields_not_repairable_deterministically = unrepairable_fields
        record.fields_repaired = repaired_fields
        if last_valid_instance:
            record.final_disposition = StructuredRepairDisposition.LAST_VALID_RETAINED
            record.accepted_fingerprint = hashlib.sha256(str(last_valid_instance).encode("utf-8")).hexdigest()
            return last_valid_instance, StructuredRepairDisposition.LAST_VALID_RETAINED, record
        record.final_disposition = StructuredRepairDisposition.REVIEW_REQUIRED
        return None, StructuredRepairDisposition.REVIEW_REQUIRED, record

    # Strip unexpected extra fields if extra="forbid" or not allowed
    allowed = set(model_cls.model_fields.keys())
    extra_keys = [k for k in data.keys() if k not in allowed]
    if extra_keys:
        for k in extra_keys:
            del data[k]
        repaired_fields.extend(extra_keys)

    try:
        instance = model_cls.model_validate(data)
        cand_fp = hashlib.sha256(json.dumps(data, default=str).encode("utf-8")).hexdigest()
        record.candidate_fingerprint = cand_fp
        record.accepted_fingerprint = cand_fp
        record.fields_repaired = repaired_fields
        disp = StructuredRepairDisposition.REPAIRED_STRUCTURAL_ONLY if repaired_fields else StructuredRepairDisposition.VALID_UNCHANGED
        record.final_disposition = disp
        return instance, disp, record
    except ValidationError as ve:
        record.original_validation_errors.append(str(ve))
        if last_valid_instance:
            record.final_disposition = StructuredRepairDisposition.LAST_VALID_RETAINED
            return last_valid_instance, StructuredRepairDisposition.LAST_VALID_RETAINED, record
        record.final_disposition = StructuredRepairDisposition.REVIEW_REQUIRED
        return None, StructuredRepairDisposition.REVIEW_REQUIRED, record
    except Exception as e:
        record.original_validation_errors.append(str(e))
        if last_valid_instance:
            record.final_disposition = StructuredRepairDisposition.LAST_VALID_RETAINED
            return last_valid_instance, StructuredRepairDisposition.LAST_VALID_RETAINED, record
        record.final_disposition = StructuredRepairDisposition.REVIEW_REQUIRED
        return None, StructuredRepairDisposition.REVIEW_REQUIRED, record
