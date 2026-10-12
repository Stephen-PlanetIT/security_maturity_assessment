from __future__ import annotations
from typing import List, Optional, Union
from pydantic import BaseModel, Field
from services.report_improvement.evidence_adjudicator import EvidenceAdjudicationResult


class EnvironmentField(BaseModel):
    field_name: str
    value: Union[str, int, List[str], None] = None
    status: str = Field(description="confirmed|customer_stated|unvalidated|unknown|contradicted")
    evidence_ids: List[str] = Field(default_factory=list, min_items=0, max_items=50)


class CanonicalEnvironment(BaseModel):
    fields: List[EnvironmentField] = Field(default_factory=list, min_items=0, max_items=200)


def build_canonical_environment(adjudication: EvidenceAdjudicationResult) -> CanonicalEnvironment:
    """
    Deterministically derive canonical environment from adjudicated evidence.
    No GPT usage; conservative inference only.
    """
    fields: List[EnvironmentField] = []

    # Example extraction: crown jewels (confirmed)
    try:
        aai = getattr(adjudication, "approved_attack_inputs", None)
        for cj in getattr(aai, "confirmed_crown_jewels", []) or []:
            fields.append(
                EnvironmentField(
                    field_name="crown_jewel",
                    value=str(cj),
                    status="confirmed",
                    evidence_ids=[],
                )
            )
    except Exception:
        pass

    # Additional deterministic enrichment (best-effort; conservative classification)
    try:
        # Example: capture cloud platforms (customer_stated unless confirmed by evidence)
        clouds = []
        try:
            clouds = list(getattr(adjudication, "cloud_platforms_confirmed", []) or [])
            st = "confirmed"
        except Exception:
            clouds = list(getattr(adjudication, "cloud_platforms_reported", []) or [])
            st = "customer_stated" if clouds else "unknown"
        for cp in clouds:
            fields.append(
                EnvironmentField(
                    field_name="cloud_platform",
                    value=str(cp),
                    status=st,
                    evidence_ids=[],
                )
            )
    except Exception:
        pass

    return CanonicalEnvironment(fields=fields)


def render_field(env_field: EnvironmentField) -> str:
    """
    Render a single environment field according to status rules.
    """
    name = env_field.field_name
    val = env_field.value
    st = (env_field.status or "").strip().lower()
    if st == "confirmed":
        return f"{name}: {val}"
    if st == "customer_stated":
        return f"{name}: {val} (customer-stated)"
    if st == "unvalidated":
        return f"{name}: {val} (reported, not independently validated)"
    if st == "unknown":
        return f"{name}: Not established during the assessment"
    if st == "contradicted":
        return f"{name}: Contradicted; requires focused consultant decision"
    return f"{name}: {val or ''}"