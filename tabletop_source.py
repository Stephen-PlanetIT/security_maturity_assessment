from __future__ import annotations
"""
Lean Tabletop Source Path — Models, Prompt, Source Validation, Deterministic Transform

This module defines:
- TabletopSourcePlan (lean Azure response schema)
- SourceFactRef, SourceDecision, SourceQuestion, ArtefactSpec, FacilitatorIntent, StageSource
- build_tabletop_source_prompt(...) — compact prompt requesting only lean source content
- validate_source_plan(source: dict) -> tuple[bool, list[str]]
- transform_source_to_master(source: dict, generation_context: dict | None) -> dict

Notes:
- No Azure calls are made here.
- Canonical IDs and deterministic metadata are derived in transform_source_to_master.
- Participant artefact and facilitator guidance synthesis are NOT performed here; callers orchestrate them after transform.
"""

from typing import List, Optional, Literal, Tuple, Dict, Any
from pydantic import BaseModel, Field, ValidationError, model_validator

# Reuse the existing artefact type enum for compatibility with synthesis/renderers
try:
    from tabletop_models import ArtefactType  # existing enum used by participant_artefacts/export
except Exception:
    # Fallback literal if import not available during early refactor; keep names consistent
    ArtefactType = Literal[
        "log", "email", "code", "ticket", "screenshot", "configuration",
        "press_release", "news", "regulator_notice", "customer_email", "exec_email", "board_pack", "social"
    ]  # type: ignore


# --------- Lean Source Models ---------

class SourceFactRef(BaseModel):
    """Reference to a stage-local or previous-stage fact by position (no canonical IDs in source)."""
    stage_offset: Literal[-1, 0] = Field(description="0=current stage, -1=immediately previous stage")
    fact_index: int = Field(ge=1, le=4, description="1-based index of the target fact (max 4 per stage)")


# Stage 2 enforced set; other stages may use a small curated set (left permissive, enforced in validator)
STAGE2_REQUIRED_CATEGORIES = (
    "session_identity_containment",
    "containment_authority",
    "affected_service_continuity",
    "escalation_scope",
)


class SourceDecision(BaseModel):
    """Typed decision — single source of truth for decisions."""
    category: str = Field(description="For Stage 2: one of the four required categories; other stages use curated categories.")
    decision: str = Field(description="Concrete action to be decided.")
    authority: str = Field(description="Named role/group with authority to decide.")
    affected_operation: str = Field(description="Named identity/service/process affected.")
    deadline_minutes: int = Field(ge=1, description="Bounded decision window in minutes (>=1).")
    accepted_consequence: str = Field(description="Explicit acceptance of a concrete consequence/trade-off.")


class SourceQuestion(BaseModel):
    """Typed participant decision question — single source of truth for questions."""
    prompt: str = Field(description="Short, scenario-grounded question requiring a decision.")
    authority: str = Field(description="Named authority expected to decide.")
    anchor_refs: List[SourceFactRef] = Field(min_items=2, max_items=4, description="2–4 fact references; stage-local or previous-stage.")
    decision_options: List[str] = Field(min_items=2, max_items=4, description="2–4 explicit decision options.")
    deadline_minutes: int = Field(ge=1, description="Bounded decision window in minutes (>=1).")
    competing_consequences: List[str] = Field(min_items=2, max_items=4, description="2–4 competing consequences describing trade-offs.")


class ArtefactSpec(BaseModel):
    """Specification for a participant artefact; final body is synthesised deterministically."""
    artefact_type: ArtefactType = Field(description="Artefact category.")
    author_role: str = Field(description="Role of the author (e.g., 'SOC Analyst', 'Service Desk').")
    audience_role: str = Field(description="Intended audience (e.g., 'Incident Manager', 'Executive Incident Owner').")
    source_system: Optional[str] = Field(default=None, description="System/source for grounding (e.g., 'Microsoft Entra', 'FortiGate').")
    purpose: str = Field(description="Purpose of artefact in scenario progression.")
    required_details: Optional[List[str]] = Field(default=None, min_items=0, max_items=6, description="Short factual details to include.")
    rendering_hint: Optional[str] = Field(default=None, description="Optional hint (e.g., 'monospace', 'wrap-80').")


class FacilitatorIntent(BaseModel):
    """Intent/tension to guide deterministic facilitator guidance synthesis."""
    intended_decision_tension: str = Field(description="What decision pressure should be created/focused.")
    optional_probe_topics: Optional[List[str]] = Field(default=None, min_items=0, max_items=6, description="Optional probe topics to consider.")
    information_release_intent: str = Field(description="What information the facilitator intends to release at this stage (if any).")
    failure_modes_to_watch: Optional[List[str]] = Field(default=None, min_items=0, max_items=6, description="Expected common failure modes to watch for (labels only).")


class StageSource(BaseModel):
    """Lean stage object with only creative source content."""
    stage_number: Literal[1, 2, 3, 4] = Field(description="Stage index: 1..4")
    participant_situation_summary: str = Field(description="Short narrative paragraph; no facilitator-only truths.")
    new_confirmed_facts: List[str] = Field(min_items=2, max_items=4, description="2–4 substantive and distinct facts.")
    remaining_unknowns: List[str] = Field(min_items=2, max_items=4, description="2–4 unresolved matters; scenario-specific.")
    decisions: List[SourceDecision] = Field(min_items=1, max_items=6, description="Typed decisions for this stage.")
    participant_questions: List[SourceQuestion] = Field(min_items=3, max_items=5, description="3–5 typed participant questions.")
    artefact_spec: ArtefactSpec = Field(description="Specification for a single participant artefact to synthesise.")
    facilitator_intent: FacilitatorIntent = Field(description="Intent/tension for deterministic facilitator guidance synthesis.")


class TabletopSourcePlan(BaseModel):
    """Lean source plan returned by Azure; one scenario and exactly four stages."""
    scenario_title: str = Field(description="Title for the scenario.")
    audience: Literal["Board", "Technical", "Blended"] = Field(description="Intended audience.")
    hidden_root_cause_context: str = Field(description="Facilitator-only root cause context; must be private.")
    wrap_up_reveal: str = Field(description="Controlled reveal narrative for wrap-up; must align to hidden root cause.")
    stages: List[StageSource] = Field(min_items=4, max_items=4, description="Exactly four stages (StageSource).")

    @model_validator(mode="after")
    def _validate_stage_numbers(self):
        try:
            nums = [s.stage_number for s in self.stages]
            if nums != [1, 2, 3, 4]:
                raise ValueError("stages must include stage_number exactly [1,2,3,4] in order")
        except Exception as e:
            raise e
        return self


# --------- Compact Source Prompt ---------

def build_tabletop_source_prompt(client_inputs: dict, selected_themes: List[str], audience: str = "Blended", custom_brief: Optional[str] = None) -> str:
    """Request only the lean TabletopSourcePlan (no canonical IDs, no legacy strings, no full artefacts/guidance)."""
    cust = client_inputs.get("customer_name", "Client")
    industry = client_inputs.get("industry", "Industry")
    crown = client_inputs.get("critical_infra", "Crown Jewels")
    identity = client_inputs.get("identity", "Unknown")
    firewall = client_inputs.get("firewall", "Unknown")
    endpoint = client_inputs.get("endpoint", "Unknown")
    mfa = client_inputs.get("mfa_status", "Unknown")
    patching = client_inputs.get("patching", "Unknown")
    backups = client_inputs.get("backups", "Unknown")
    themes = ", ".join(selected_themes) if selected_themes else "Identity Attack; Operational Impact"

    brief = f"\nCUSTOM BRIEF: {custom_brief}\n" if custom_brief else ""

    return f"""ROLE: Incident Commander & Facilitator (Planet IT)

OBJECTIVE: Return ONLY a TabletopSourcePlan JSON object with keys:
 - scenario_title
 - audience ∈ {{'Board','Technical','Blended'}}
 - hidden_root_cause_context (facilitator-only)
 - wrap_up_reveal (consistent with hidden root cause; facilitator-only)
 - stages (exactly 4 StageSource objects, stage_number=1..4)

STRICT REQUIREMENTS:
- Exactly one coherent incident spine across roles, devices, identities, services, processes, and business consequence.
- Four stages in order: 1 Weak signal; 2 Confirmed compromise; 3 Operational/business impact; 4 External/executive pressure.
- Each stage:
  • participant_situation_summary: one short paragraph; NO facilitator-only truths.
  • new_confirmed_facts: 2–4 substantive, distinct facts.
  • remaining_unknowns: 2–4 substantive unresolved matters.
  • decisions: typed decisions with fields (category, decision, authority, affected_operation, deadline_minutes>=1, accepted_consequence).
  • participant_questions: 3–5 typed questions with fields (prompt, authority, anchor_refs (2–4 SourceFactRef), decision_options (2–4), deadline_minutes>=1, competing_consequences (2–4)).
  • artefact_spec: (artefact_type, author_role, audience_role, source_system?, purpose, required_details<=6, rendering_hint?); DO NOT generate full artefact content.
  • facilitator_intent: (intended_decision_tension, optional_probe_topics<=6, information_release_intent, failure_modes_to_watch<=6).
- SourceFactRef format:
  • stage_offset: 0 = current stage; -1 = immediately previous stage
  • fact_index: 1..4
  • Stage 1 questions may reference only stage_offset=0.
- Stage 2 decisions must contain exactly four decisions overall, exactly one of:
  • session_identity_containment
  • containment_authority
  • affected_service_continuity
  • escalation_scope
- The hidden_root_cause_context must be present once at scenario level; do NOT reveal it in participant-facing fields.
- The wrap_up_reveal must be consistent with the hidden root cause and must remain facilitator-only.

PROHIBITIONS (DO NOT RETURN):
- public or internal inject IDs; previous_inject_id; next_inject_trigger; phase strings
- canonical fact IDs; new_fact_ids; known_fact_ids_before
- duplicated known-fact text where transformation can derive it
- legacy decisions_required strings or legacy participant_questions strings
- complete participant artefact bodies; complete facilitator-guidance bodies
- compatibility/persistence/diagnostic sidecars; generation metadata

CONTEXT:
- Client: {cust} in {industry}
- Crown Jewels: {crown}
- Identity: {identity}
- Firewall: {firewall}
- Endpoint: {endpoint}
- Hygiene: MFA={mfa} | Patching={patching} | Backups={backups}
- Themes: {themes}
- Audience: {audience}{brief}

OUTPUT: Return ONLY a strict JSON object conforming to TabletopSourcePlan."""
    

# --------- Source Validation (structural/typed) ---------

def _meaningful(text: Any) -> bool:
    try:
        s = str(text or "").strip()
        return len(s) >= 24 and s.lower() not in {"context", "state", "revealed", "indicator", "decision"}
    except Exception:
        return False


def validate_source_plan(source: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate the lean source plan without scanning legacy phrase-markers."""
    defects: List[str] = []
    # Pydantic structural validation first
    try:
        TabletopSourcePlan.model_validate(source)
    except ValidationError as ve:
        for e in ve.errors():
            loc = ".".join(str(x) for x in e.get("loc", []))
            defects.append(f"schema violation at {loc}: {e.get('msg')}")
        return False, defects
    # Typed object for convenience
    plan = TabletopSourcePlan.model_validate(source)

    # Stage presence/order
    nums = [s.stage_number for s in plan.stages]
    if nums != [1, 2, 3, 4]:
        defects.append("stages must be [1,2,3,4] in order")

    # Facts and unknowns
    for s in plan.stages:
        label = f"stage {s.stage_number}"
        facts = s.new_confirmed_facts or []
        unknowns = s.remaining_unknowns or []
        if not (2 <= len(facts) <= 4):
            defects.append(f"{label} must contain 2–4 new_confirmed_facts")
        if not (2 <= len(unknowns) <= 4):
            defects.append(f"{label} must contain 2–4 remaining_unknowns")
        if any(not _meaningful(x) for x in facts):
            defects.append(f"{label} has non-substantive fact(s)")
        if any(not _meaningful(x) for x in unknowns):
            defects.append(f"{label} has non-substantive remaining_unknowns")
        if len({f.strip().lower() for f in facts}) != len(facts):
            defects.append(f"{label} new_confirmed_facts contain duplicates")

    # SourceFactRef integrity for questions
    for s in plan.stages:
        label = f"stage {s.stage_number}"
        cur_count = len(s.new_confirmed_facts or [])
        prev_count = len(plan.stages[s.stage_number - 2].new_confirmed_facts) if s.stage_number > 1 else 0
        for q in s.participant_questions:
            refs = q.anchor_refs or []
            if len(refs) < 2:
                defects.append(f"{label} typed question lacks >=2 anchor_refs")
                continue
            # Stage 1 cannot reference previous stage
            for rf in refs:
                if s.stage_number == 1 and rf.stage_offset == -1:
                    defects.append(f"{label} typed question references previous stage (invalid for stage 1)")
                if rf.stage_offset == 0 and not (1 <= rf.fact_index <= cur_count):
                    defects.append(f"{label} typed question anchor out of range for current stage: fact_index={rf.fact_index}")
                if rf.stage_offset == -1 and not (1 <= rf.fact_index <= prev_count):
                    defects.append(f"{label} typed question anchor out of range for previous stage: fact_index={rf.fact_index}")
            # Distinct fact statements
            def _resolve(r: SourceFactRef) -> str:
                if r.stage_offset == 0:
                    return s.new_confirmed_facts[r.fact_index - 1]
                else:
                    prev = plan.stages[s.stage_number - 2]
                    return prev.new_confirmed_facts[r.fact_index - 1]
            try:
                stmts = {_resolve(r).strip().lower() for r in refs}
                if len([x for x in stmts if _meaningful(x)]) < 2:
                    defects.append(f"{label} typed question anchors must resolve to two distinct substantive facts")
            except Exception:
                defects.append(f"{label} typed question anchors could not be resolved")

    # Typed decisions
    for s in plan.stages:
        label = f"stage {s.stage_number}"
        for d in s.decisions:
            if not all([
                str(d.category).strip(),
                _meaningful(d.decision),
                str(d.authority).strip(),
                str(d.affected_operation).strip(),
                _meaningful(d.accepted_consequence),
                int(d.deadline_minutes) >= 1
            ]):
                defects.append(f"{label} typed decision has missing or non-substantive fields")
        if s.stage_number == 2:
            cats = [d.category.strip() for d in s.decisions]
            if len(cats) != 4:
                defects.append("stage 2 must contain exactly four typed decisions")
            else:
                missing = [c for c in STAGE2_REQUIRED_CATEGORIES if cats.count(c) != 1]
                if missing:
                    defects.append(f"stage 2 must contain exactly one of each required category; missing={missing}")

    # Hidden root cause privacy
    hc = plan.hidden_root_cause_context.strip().lower()
    def _leaks(txt: str) -> bool:
        t = (txt or "").strip().lower()
        return bool(hc) and (hc in t)
    # Participant-surface leakage checks
    for s in plan.stages:
        if _leaks(s.participant_situation_summary):
            defects.append(f"stage {s.stage_number} participant_situation_summary leaks hidden root cause")
        for f in s.new_confirmed_facts or []:
            if _leaks(f):
                defects.append(f"stage {s.stage_number} fact leaks hidden root cause")
        for u in s.remaining_unknowns or []:
            if _leaks(u):
                defects.append(f"stage {s.stage_number} remaining_unknown leaks hidden root cause")
        spec = s.artefact_spec
        for d in (spec.required_details or []):
            if _leaks(d):
                defects.append(f"stage {s.stage_number} artefact_spec.required_details leaks hidden root cause")

    # Wrap-up consistency (simple token overlap check)
    import re as _re
    try:
        hc_core = hc.split(":", 1)[-1].strip()
        hc_tokens = {t for t in _re.findall(r"[a-z0-9\\-]+", hc_core) if len(t) >= 4}
        rn = plan.wrap_up_reveal.strip().lower()
        rn_tokens = {t for t in _re.findall(r"[a-z0-9\\-]+", rn) if len(t) >= 4}
        if len(hc_tokens.intersection(rn_tokens)) < 2 and hc and rn:
            defects.append("wrap_up_reveal does not sufficiently overlap hidden root cause")
    except Exception:
        pass

    return (not defects), defects


# --------- Deterministic Transform (Source -> Master) ---------

def transform_source_to_master(source: Dict[str, Any], generation_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Deterministically derive a TabletopMasterPlan-compatible dict from a validated TabletopSourcePlan.
    Responsibilities:
      - Inject IDs INJ-1..INJ-4
      - Phase names by index
      - previous_inject_id linkage; final next_inject_trigger=None
      - Canonical fact IDs S{stage}-F{n}; preserve fact text exactly
      - known_facts_before and known_fact_ids_before derived from previous stage
      - Convert SourceFactRef anchors to canonical fact IDs
      - Copy typed decisions/questions as authoritative; derive legacy strings
      - Derive minimal generation_metadata (no secrets)
      - Map hidden_root_cause_context and wrap_up_reveal to facilitator-only structure
    """
    try:
        plan = TabletopSourcePlan.model_validate(source)
    except ValidationError as ve:
        raise ValueError(f"transform_source_to_master: invalid source schema: {ve}") from ve

    # Phase names by stage index
    STAGE_PHASES = (
        "Weak signal",
        "Confirmed compromise",
        "Operational or business impact",
        "External or executive pressure",
    )

    def _inj_id(i: int) -> str:
        return f"INJ-{i}"

    def _canon(stage_num: int, index1: int) -> str:
        return f"S{stage_num}-F{index1}"

    # Build injects
    injects: List[Dict[str, Any]] = []
    prev_inj_id: Optional[str] = None
    prev_facts: List[str] = []

    # Map stage_num -> canonical facts for anchor resolution
    canon_registry: Dict[int, List[str]] = {}

    # First pass: assign canonical IDs and build base inject_state per stage
    for s in plan.stages:
        stage_num = s.stage_number
        inj_id = _inj_id(stage_num)
        facts = list(s.new_confirmed_facts or [])
        canon_ids = [_canon(stage_num, i + 1) for i in range(len(facts))]
        canon_registry[stage_num] = canon_ids

        state = {
            "inject_id": inj_id,
            "previous_inject_id": prev_inj_id if stage_num > 1 else None,
            "phase": STAGE_PHASES[stage_num - 1],
            "known_facts_before": (prev_facts if stage_num > 1 else []),
            "new_confirmed_facts": facts,
            "known_fact_ids_before": (canon_registry.get(stage_num - 1, []) if stage_num > 1 else []),
            "new_fact_ids": canon_ids,
            # These participant-surface/state fields will be enriched/synthesised later; keep placeholders
            "remaining_unknowns": list(s.remaining_unknowns or []),
            "facilitator_context": "",
            "hidden_root_cause_context": plan.hidden_root_cause_context,
            "business_impact": "",
            "stakeholder_pressure": "",
            "decisions_required": [],   # derive from typed later
            "decisions_typed": [],      # to be set below
        }

        # Copy typed decisions as authoritative
        state["decisions_typed"] = [
            {
                "category": d.category,
                "decision": d.decision,
                "authority": d.authority,
                "affected_operation": d.affected_operation,
                "deadline_minutes": int(d.deadline_minutes),
                "accepted_consequence": d.accepted_consequence,
            }
            for d in s.decisions
        ]

        # Derive legacy decision strings for compatibility
        legacy_decisions = []
        for d in s.decisions:
            legacy_decisions.append(
                f"DECISION: {d.decision}. AUTHORITY: {d.authority}. AFFECTED OPERATION: {d.affected_operation}. "
                f"DEADLINE: {d.deadline_minutes} minutes. TRADE-OFF: {d.accepted_consequence}."
            )
        state["decisions_required"] = legacy_decisions

        # Participant questions: convert anchor_refs to canonical IDs
        def _resolve_ref(ref: SourceFactRef) -> str:
            if ref.stage_offset == 0:
                return _canon(stage_num, ref.fact_index)
            else:
                return _canon(stage_num - 1, ref.fact_index)

        typed_qs = []
        legacy_qs = []
        for q in s.participant_questions:
            anchors = []
            for rf in q.anchor_refs:
                try:
                    anchors.append(_resolve_ref(rf))
                except Exception:
                    anchors.append(_canon(stage_num, 1))  # safe fallback; validator should prevent this path
            typed_qs.append({
                "prompt": q.prompt,
                "authority": q.authority,
                "anchor_fact_ids": anchors,
                "decision_options": list(q.decision_options or []),
                "deadline_minutes": int(q.deadline_minutes),
                "competing_consequences": list(q.competing_consequences or []),
            })
            legacy_qs.append({"prompt": q.prompt})
        # Build inject record
        inject = {
            "inject_id": inj_id,  # public id
            "inject_state": state,
            "participant_questions_typed": typed_qs,
            "participant_questions": legacy_qs,  # compatibility surface (string prompts)
            # Defer authoritative artefact and guidance to synthesis steps
            "participant_artefact": {},
            "facilitator_guidance": {}
        }
        injects.append(inject)
        prev_inj_id = inj_id
        prev_facts = facts

    # Final stage: ensure next_inject_trigger is None
    try:
        injects[-1]["inject_state"]["next_inject_trigger"] = None
    except Exception:
        pass

    # Final scenario structure with facilitator reveal
    master: Dict[str, Any] = {
        "scenarios": [
            {
                "scenario_id": "SCN-01",
                "scenario_title": plan.scenario_title,
                "injects": injects,
                "facilitator_reveal": {
                    "reveal_narrative": plan.wrap_up_reveal
                }
            }
        ],
        # Private facilitator notes map to be attached by synthesis step; keys must match inject_ids later
        "_facilitator_notes": {}
    }

    # Minimal generation metadata (no secrets)
    import time as _t
    try:
        master["generation_metadata"] = {
            "schema_version": "tt-source-lean-1",
            "validation_rule_version": "typed-source-lean",
            "model": (generation_context or {}).get("deployment", "unknown"),
            "generation_timestamp": _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime()),
        }
    except Exception:
        pass

    return master