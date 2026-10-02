from __future__ import annotations

"""
Tabletop Domain Models (Isolated — Not Integrated)

This module codifies the domain layer for the Tabletop Generator Architecture:

    CustomerContext → ExerciseObjective → HiddenTruth → EscalationState → StoryBeat
    → KnowledgeState → ExerciseBlueprint → InjectPlan → ArtefactRequest
    → ParticipantArtefact → DecisionQuestion → FacilitationGuide

Architectural rules enforced by design:
1) PPTX rendering must not determine scenario narrative (models are presentation-agnostic).
2) LLM output must be structured and schema validated (strict Pydantic models).
3) Participant knowledge and scenario truth remain separate:
   - HiddenTruth appears only in FacilitationGuide; it is not present in participant artefacts.
4) Injects are designed around decisions (decision_threshold, timebox_hint).
5) Every inject materially changes participant knowledge (KnowledgeState).
6) Facilitator-only information never appears in participant artefacts.
7) Deterministic layout/overflow controls live outside this module.
8) Scenario generation completes and validates before any PPTX rendering.

British English is used throughout (e.g., programme, behaviour, organisation).
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from enum import Enum


# --------------------------
# Core Context & Objectives
# --------------------------

class CustomerContext(BaseModel):
    """Minimal, presentation-agnostic customer context used by the generator."""
    customer_name: str = Field(description="Client organisation name.")
    industry: str = Field(description="Client industry.")
    identity_provider: Optional[str] = Field(default=None, description="Identity provider (e.g., 'Microsoft Entra ID').")
    firewall_vendor: Optional[str] = Field(default=None, description="Firewall vendor (e.g., 'Fortinet', 'Sophos').")
    endpoint_vendor: Optional[str] = Field(default=None, description="Endpoint security vendor (e.g., 'Sophos', 'Microsoft Defender').")
    mdr_provider: Optional[str] = Field(default=None, description="MDR/SOC provider if applicable.")
    mfa_status: Optional[str] = Field(default=None, description="MFA enforcement position (e.g., 'Universal', 'Privileged Accounts Only', 'None').")
    patching: Optional[str] = Field(default=None, description="Patch management posture (e.g., 'Automated', 'Manual / Ad-hoc').")
    backups: Optional[str] = Field(default=None, description="Backup posture (e.g., 'Immutable', 'On-Premise Only', 'None').")
    banned_vendors: Optional[List[str]] = Field(default=None, description="Explicit vendor ban list.", min_items=0, max_items=30)


class ExerciseObjective(BaseModel):
    """A single objective the exercise is designed to test."""
    objective_id: str = Field(description="Stable identifier for the exercise objective (e.g., 'OBJ-01').")
    description: str = Field(description="Narrative description of the objective in British English.")
    outcomes: List[str] = Field(description="Intended, measurable outcomes for this objective.", min_items=1, max_items=5)


# --------------------------
# Facilitator-Only Constructs
# --------------------------

class HiddenTruth(BaseModel):
    """Facilitator-only ground truth that must not appear in participant artefacts."""
    reveal_point: str = Field(description="When the facilitator reveals this truth (e.g., after Inject 3, wrap-up).")
    truth_narrative: str = Field(description="Narrative truth about root cause or unseen events; facilitator-only.")
    restricted_to_facilitator: bool = Field(default=True, description="Facilitator-only guard (always True).")


class EscalationState(BaseModel):
    """Governance thresholds and escalation path associated with a story beat/inject."""
    decision_threshold: str = Field(description="Key governance decision (e.g., Major Incident declaration; ICO 72h).")
    regulator_clock: Optional[str] = Field(default=None, description="Regulatory clock if applicable (e.g., 'ICO 72h').")
    invoked_runbook: Optional[str] = Field(default=None, description="Invoked runbook ID/title if decided (e.g., 'IR‑01 Declaration').")


# --------------------------
# Knowledge & Narrative Beats
# --------------------------

class KnowledgeState(BaseModel):
    """Participant knowledge artefacts for a given story beat (no hidden truths)."""
    known_facts: List[str] = Field(description="Facts the participants have been given or derived.", min_items=0, max_items=20)
    open_questions: List[str] = Field(description="Questions outstanding at this point in the exercise.", min_items=0, max_items=10)
    assumptions: List[str] = Field(description="Assumptions voiced by participants needing validation.", min_items=0, max_items=10)


class StoryBeat(BaseModel):
    """A narrative beat forming the spine of an inject."""
    beat_id: str = Field(description="Stable reference for the story beat (e.g., 'BEAT-1.1').")
    phase_title: str = Field(description="Label for this beat (e.g., 'Initial Anomaly Detection').")
    simulated_timestamp: str = Field(description="Relative or clock time for this beat (e.g., 'Day 1 — 08:15 UTC').")
    participant_narrative: str = Field(description="Narrative shown to participants (no facilitator-only content).")
    knowledge_state: KnowledgeState = Field(description="Knowledge state for participants at this beat.")
    escalation_state: Optional[EscalationState] = Field(default=None, description="Escalation state if a governance threshold is relevant here.")


# --------------------------
# Artefacts & Decisions
# --------------------------

ArtefactType = Literal[
    "log", "email", "code", "ticket", "screenshot", "configuration",
    "press_release", "news", "regulator_notice", "customer_email", "exec_email", "board_pack", "social"
]

class ArtefactRequest(BaseModel):
    """A request for an artefact to support an inject; actual rendering occurs elsewhere."""
    artefact_type: ArtefactType = Field(description="Requested artefact category.")
    source_system: Optional[str] = Field(default=None, description="System/source to ground the artefact (e.g., 'Sophos Central', 'Microsoft Entra').")
    render_hint: Optional[str] = Field(default=None, description="Rendering hint (e.g., 'monospace', 'wrap-80').")
    required_tokens: Optional[List[str]] = Field(default=None, description="Tokens the artefact should include to be credible.", min_items=0, max_items=6)


class ParticipantArtefact(BaseModel):
    """A participant-facing artefact (no facilitator-only content)."""
    title: Optional[str] = Field(default=None, description="Short label (e.g., Alert name, Email subject).")
    artefact_type: ArtefactType = Field(description="Artefact category.")
    body: str = Field(description="Content of the artefact (logs/emails/code/etc.).")
    source_system: Optional[str] = Field(default=None, description="System/source of the artefact.")
    render_hint: Optional[str] = Field(default=None, description="Rendering hint (e.g., 'monospace').")
    metadata: Optional[List[str]] = Field(default=None, description="Additional contextual hints (e.g., 'profile: sophos/mdr/case').", min_items=0, max_items=6)

class FactType(str, Enum):
    VERIFIED_CUSTOMER_FACT = "verified_customer_fact"
    USER_PROVIDED_ASSUMPTION = "user_provided_assumption"
    EXERCISE_FICTION = "exercise_fiction"
    MODEL_ASSUMPTION = "model_assumption"

class ScenarioFact(BaseModel):
    """Provenance-bearing fact/claim supporting scenario content."""
    id: str = Field(description="Stable ID for the fact (e.g., 'F-001').")
    statement: str = Field(description="The factual statement or claim text.")
    fact_type: FactType = Field(description="Provenance classification for this claim.")
    source_ids: List[str] = Field(description="Source document IDs or references supporting this fact.", min_items=0, max_items=12)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Optional confidence 0.0–1.0 for VERIFIED_CUSTOMER_FACT or USER_PROVIDED_ASSUMPTION.")

class FictionPolicy(BaseModel):
    """Explicit contract defining allowed inventions for this scenario/exercise."""
    may_invent_people: bool = Field(description="Whether fictional people may be invented (e.g., names).")
    may_invent_email_addresses: bool = Field(description="Whether fictional email addresses may be invented.")
    may_invent_log_values: bool = Field(description="Whether synthetic log lines/values may be invented.")
    may_invent_customer_impact: bool = Field(description="Whether fictionalised customer impact narratives are allowed.")
    may_invent_supplier_responses: bool = Field(description="Whether invented supplier responses (e.g., support replies) are allowed.")
    prohibited_inventions: List[str] = Field(description="Explicitly prohibited inventions (e.g., 'undocumented production architecture').", min_items=0, max_items=20)

class InjectTiming(BaseModel):
    """Facilitation pacing and release conditions for an inject."""
    target_minutes: int = Field(ge=1, le=30, description="Target minutes allocated for this inject discussion.")
    minimum_minutes: int = Field(ge=0, le=30, description="Minimum minutes before forcing a release.")
    maximum_minutes: int = Field(ge=1, le=60, description="Maximum minutes before cut-over.")
    free_discussion_seconds: int = Field(ge=0, le=120, description="Initial free discussion seconds before directed probes.")
    release_condition: Literal["facilitator", "decision_reached", "time_elapsed", "topic_covered"] = Field(description="Condition that triggers release to next inject or probes.")

class FacilitatorBranch(BaseModel):
    """Non-linear facilitation branch for conditional responses."""
    trigger: str = Field(description="Condition phrasing (IF participants .../IF facilitator ...).")
    response_type: Literal["provide_information", "clarify_assumption", "release_evidence", "accelerate_inject", "challenge_decision"] = Field(description="Branch action type.")
    content: str = Field(description="Facilitator content to deliver (participant-safe).")
    prohibited_revelations: List[str] = Field(description="Tokens/phrases the branch must not reveal.", min_items=0, max_items=10)

class ParticipantGroup(BaseModel):
    """Audience role grouping for decisions/questions."""
    role_group: Literal["executive","it","security","operations","legal","privacy","communications","hr","finance"] = Field(description="Role group label.")
    exercise_responsibilities: List[str] = Field(description="Responsibilities in the exercise context.", min_items=1, max_items=6)

class GenerationMetadata(BaseModel):
    """Reproducibility and provenance metadata for scenario generation."""
    schema_version: str = Field(description="Schema version for tabletop plan.")
    prompt_version: str = Field(description="Prompt builder version string.")
    model: str = Field(description="LLM model identifier.")
    generation_timestamp: str = Field(description="ISO timestamp of generation event.")
    generator_version: Optional[str] = Field(default=None, description="Application generator version.")
    customer_context_hash: Optional[str] = Field(default=None, description="Hash of client_inputs snapshot.")
    blueprint_hash: Optional[str] = Field(default=None, description="Hash of ExerciseBlueprint (if used).")
    validation_rule_version: Optional[str] = Field(default=None, description="Validator ruleset version.")


class DecisionQuestion(BaseModel):
    """A single facilitator question designed to elicit a decision or evidence."""
    prompt: str = Field(description="Short, provocative question grounded in the client's stack and authority model.")
    category: Literal["Evidence", "Governance", "Authority", "Communications", "What‑if"] = Field(
        description="Question category (evidence validation, governance thresholds, authority, communications, what‑if)."
    )
    objective_id: str = Field(description="Exercise Objective ID this question supports (must match ExerciseObjective.objective_id).")
    decision_target: str = Field(description="Decision target for this question (e.g., label of EscalationState.decision_threshold or inject decision to be reached).")


# --------------------------
# Inject & Guide Layer
# --------------------------

class InjectFacilitation(BaseModel):
    guide_prompt: str = Field(description="Facilitator-only steering prompt for this inject.")
    probes_rationale: Optional[str] = Field(default=None, description="Why the probes matter at this point; facilitator-only.")
    escalation_cues: Optional[List[str]] = Field(default=None, description="Cues signalling escalation or authority thresholds.", min_items=0, max_items=4)
    wrap_if_deviation: Optional[str] = Field(default=None, description="Brief guidance if the room deviates; facilitator-only.")

class InjectPlan(BaseModel):
    """Design of a single inject (decision-centric)."""
    inject_id: str = Field(description="Stable reference for the inject (e.g., 'INJ-1.1').")
    sequence: int = Field(ge=1, le=20, description="Position within scenario (1-based).")
    story_beat: StoryBeat = Field(description="Narrative beat underpinning the inject.")
    decision_questions: List[DecisionQuestion] = Field(
        description="Facilitator questions; avoid yes/no, require justification and artefact reference.",
        min_items=2, max_items=5
    )
    artefact_requests: List[ArtefactRequest] = Field(
        description="Requested artefacts to support the inject.",
        min_items=1, max_items=3
    )
    # Structured pacing for facilitation timing and release conditions
    inject_timing: Optional[InjectTiming] = Field(default=None, description="Structured pacing and release control for this inject.")
    timebox_hint: str = Field(description="Timebox guidance for this inject (e.g., '5–7 minutes to decision').")
    # Provenance-bearing facts; MODEL_ASSUMPTION cannot silently become participant truth
    scenario_facts: Optional[List[ScenarioFact]] = Field(default=None, description="Provenance-bearing facts supporting this inject.", min_items=0, max_items=20)
    facilitation: Optional[InjectFacilitation] = Field(default=None, description="Facilitator-only guidance for this inject.")

class FacilitationGuide(BaseModel):
    """Facilitator script and wrap-up materials (includes hidden truths)."""
    guide_id: str = Field(description="Stable reference for this guide (e.g., 'FG-01').")
    hidden_truths: Optional[List[HiddenTruth]] = Field(default=None, description="Facilitator-only truths and reveal points.", min_items=0, max_items=10)
    escalation_notes: Optional[str] = Field(default=None, description="Notes on escalation thresholds and authority transitions.")
    wrap_up_questions: List[str] = Field(description="Wrap-up questions for participants.", min_items=2, max_items=6)
    key_lessons: List[str] = Field(description="Key lessons to reinforce.", min_items=2, max_items=5)


# --------------------------
# Blueprint Layer
# --------------------------

class ExerciseBlueprint(BaseModel):
    """Top-level blueprint of the exercise, independent of presentation."""
    exercise_title: str = Field(description="Title of the tabletop workshop.")
    client_name: str = Field(description="Client name.")
    audience: Literal["Board", "Technical", "Blended"] = Field(description="Intended exercise audience.")
    housekeeping_rules: List[str] = Field(description="Ground rules (e.g., 'Only documented tools count').", min_items=3, max_items=5)
    objectives: List[ExerciseObjective] = Field(description="Exercise objectives.", min_items=1, max_items=5)
    inject_plan: List[InjectPlan] = Field(description="Ordered inject plan (decision-centric).", min_items=4, max_items=4)
    facilitation_guide: FacilitationGuide = Field(description="Facilitator script and wrap-up materials.")
    context: Optional[CustomerContext] = Field(default=None, description="Minimal customer context to bind story to actual stack.")
    fiction_policy: Optional[FictionPolicy] = Field(default=None, description="Explicit contract controlling acceptable exercise fiction.")


# Resolve forward refs (safety)
try:
    ExerciseBlueprint.update_forward_refs()
    InjectPlan.update_forward_refs()
    StoryBeat.update_forward_refs()
    KnowledgeState.update_forward_refs()
    FacilitationGuide.update_forward_refs()
    HiddenTruth.update_forward_refs()
except Exception:
    pass


__all__ = [
    "CustomerContext",
    "ExerciseObjective",
    "HiddenTruth",
    "EscalationState",
    "StoryBeat",
    "KnowledgeState",
    "ExerciseBlueprint",
    "InjectPlan",
    "ArtefactRequest",
    "ParticipantArtefact",
    "DecisionQuestion",
    "InjectFacilitation",
    "FacilitationGuide",
    "ArtefactType",
    "FactType",
    "ScenarioFact",
    "FictionPolicy",
    "InjectTiming",
    "FacilitatorBranch",
    "ParticipantGroup",
    "GenerationMetadata",
]
