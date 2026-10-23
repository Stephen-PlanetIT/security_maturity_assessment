from typing import List, Optional, Dict
from pydantic import BaseModel, Field, conlist

class RootCauseRevealModel(BaseModel):
    hidden_context: str = Field(..., description="Internal RCA framing not shown to participants")
    facilitator_visible_context: str = Field(..., description="RCA context visible to facilitators")
    wrap_up_reveal_point: str = Field(..., description="Gating point when RCA is revealed to participants")

class IncidentSpine(BaseModel):
    identity_role: Optional[str] = Field(default=None, description="Role of the person affected (e.g., 'Executive').")
    device_id: Optional[str] = Field(default=None, description="Device identifier (e.g., BYOD_Device_01).")
    identity: Optional[str] = Field(default=None, description="Identity (e.g., 'Entra ID (Azure AD) - Executive').")
    service: Optional[str] = Field(default=None, description="Affected service (e.g., 'Corporate Email').")
    business_process: Optional[str] = Field(default=None, description="Critical business process under impact.")
    supplier_dependency: Optional[str] = Field(default=None, description="Supplier or platform dependency (e.g., 'Fortinet FortiGate').")

class InjectState(BaseModel):
    inject_id: str
    slide_reference: str
    scenario_id: str
    phase: Optional[str] = None
    known_facts_before: conlist[str, min_items=1] = Field(..., min_items=1)
    new_confirmed_facts: conlist[str, min_items=1] = Field(..., min_items=1)
    remaining_unknowns: conlist[str, min_items=1] = Field(..., min_items=1)
    business_impact: Optional[str] = None
    stakeholder_pressure: Optional[str] = None
    decisions_required: conlist[str, min_items=1] = Field(..., min_items=1)
    previous_inject_id: Optional[str] = None
    next_inject_trigger: Optional[str] = None
    artefact_reference: Optional[str] = None
    artefact_type: Optional[str] = None
    root_cause_reveal: RootCauseRevealModel
    artefact_author: Optional[str] = None
    artefact_knowledge_level: Optional[str] = None
    artefact_audience: Optional[str] = None
    injection_context_tag: Optional[str] = None
    author_notes: Optional[str] = None
    artefact_class: Optional[str] = None
    spine: Optional[IncidentSpine] = None
    # New fields to support the four-stage path
    hidden_root_cause_context: Optional[str] = None
    facilitator_context: Optional[str] = None

def to_participant_view(inject: InjectState) -> dict:
    return {
        "known_facts_before": inject.known_facts_before,
        "new_confirmed_facts": inject.new_confirmed_facts,
        "remaining_unknowns": inject.remaining_unknowns,
        "business_impact": inject.business_impact,
        "stakeholder_pressure": inject.stakeholder_pressure,
        "decisions_required": list(inject.decisions_required),
        "phase": inject.phase,
        "previous_inject_id": inject.previous_inject_id,
        "next_inject_trigger": inject.next_inject_trigger,
        "facilitator_context": inject.facilitator_context,
        "hidden_root_cause_context": (
            inject.hidden_root_cause_context
            if inject.hidden_root_cause_context is not None
            else inject.root_cause_reveal.hidden_context
        ),
    }

def basic_validate_inject(data: dict) -> bool:
    mandatory_keys = [
        "inject_id","slide_reference","scenario_id",
        "known_facts_before","new_confirmed_facts","remaining_unknowns",
        "business_impact","stakeholder_pressure","decisions_required","root_cause_reveal"
    ]
    # Basic presence checks
    for k in mandatory_keys:
        if k not in data:
            return False
    # Basic type checks
    if not isinstance(data["known_facts_before"], list) or len(data["known_facts_before"]) < 1:
        return False
    if not isinstance(data["new_confirmed_facts"], list) or len(data["new_confirmed_facts"]) < 1:
        return False
    if not isinstance(data["remaining_unknowns"], list) or len(data["remaining_unknowns"]) < 1:
        return False
    if not isinstance(data["decisions_required"], list) or len(data["decisions_required"]) < 1:
        return False
    if not isinstance(data["slide_reference"], str) or not data["slide_reference"].strip():
        return False
    if not isinstance(data["inject_id"], str) or not data["inject_id"].strip():
        return False
    root = data.get("root_cause_reveal")
    if not isinstance(root, dict):
        return False
    if not all(k in root for k in ("hidden_context","facilitator_visible_context","wrap_up_reveal_point")):
        return False
    return True