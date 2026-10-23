"""Production four-stage tabletop generation contract and bounded validation.

This module validates the same ``TabletopMasterPlan`` payload consumed by the
Designer and keeps internal incident state separate from participant surfaces.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

STAGE_PHASES = (
    "Weak signal",
    "Confirmed compromise",
    "Operational or business impact",
    "External or executive pressure",
)

_GENERIC_QUESTION_MARKERS = (
    "what would you do",
    "what happens next",
    "how would you respond",
    "what are your next steps",
)

_QUESTION_ANCHORS = (
    "service",
    "platform",
    "system",
    "workflow",
    "account",
    "identity",
    "role",
    "authority",
    "approve",
    "authorise",
    "contain",
    "continuity",
    "impact",
    "business",
    "supplier",
    "vendor",
    "minute",
    "hour",
    "deadline",
    "timebox",
    "trade-off",
    "tradeoff",
    "risk",
    "dispatch",
    "delivery",
    "harbourtrack",
    "dockflow",
    "entra",
    "mfa",
    "session",
    "major incident",
    "stakeholder",
    "regulator",
    "cut-off",
    "cut off",
)

_DECISION_MARKERS = (
    "decide",
    "choose",
    "approve",
    "authorise",
    "authorize",
    "contain",
    "revoke",
    "isolate",
    "continue",
    "pause",
    "failover",
    "escalate",
    "declare",
    "notify",
    "accept",
    "classify",
    "prioritise",
    "prioritize",
)

_QUESTION_DECISION_MARKERS = (
    "should",
    "must",
    "will you",
    "can the",
    "who will approve",
    "authorise",
    "authorize",
    "decide",
    "choose",
    "accept",
    "prioritise",
    "prioritize",
    "contain",
    "continue",
    "pause",
    "reject",
)

_EVIDENCE_ONLY_QUESTION_MARKERS = (
    "what evidence",
    "which evidence",
    "what logs",
    "which logs",
    "what telemetry",
    "which telemetry",
    "what systems",
    "which systems",
    "who should be informed",
    "who needs to be informed",
    "whether escalation is required",
)

_DECISION_AUTHORITY_MARKERS = (
    "incident manager",
    "iam lead",
    "service owner",
    "operations manager",
    "security analyst",
    "responsible authority",
)

_DECISION_TIME_MARKERS = (
    "within ",
    "before ",
    "by ",
    "immediately",
    "timebox",
    "cut-off",
    "cut off",
    "decision window",
)

_DECISION_TRADEOFF_MARKERS = (
    "accepting ",
    "accept ",
    "balancing ",
    "trade-off",
    "tradeoff",
    "at the cost of",
    "residual risk",
)

_HIDDEN_MARKERS = (
    "hidden_root_cause_context",
    "root cause",
    "attacker",
    "threat actor",
    "phishing attack",
    "compromised account",
    "unauthorised access",
    "malicious activity",
    "known threat actor",
    "exfiltrated",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _meaningful(value: Any) -> bool:
    text = _text(value)
    return len(text) >= 24 and text.lower() not in {"context", "state", "revealed", "indicator", "decision"}


def validate_four_stage_plan(plan: Any) -> tuple[bool, list[str]]:
    """Return ``(valid, defects)`` for a live TabletopMasterPlan dictionary."""
    defects: list[str] = []
    if not isinstance(plan, dict):
        return False, ["generation did not return an object"]

    scenarios = plan.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) != 1:
        defects.append("exactly one coherent scenario is required")
        return False, defects

    scenario = scenarios[0]
    injects = scenario.get("injects") if isinstance(scenario, dict) else None
    if not isinstance(injects, list) or len(injects) != 4:
        defects.append("exactly four ordered stages are required")
        return False, defects

    previous_new_facts: set[str] = set()

    for index, inject in enumerate(injects):
        label = f"stage {index + 1}"
        if not isinstance(inject, dict):
            defects.append(f"{label} is not an object")
            continue

        state = inject.get("inject_state")
        artefact = inject.get("participant_artefact")
        questions = inject.get("participant_questions")
        guidance = inject.get("facilitator_guidance")

        if not isinstance(state, dict):
            defects.append(f"{label} is missing InjectState-compatible internal state")
            continue
        if _text(state.get("phase")) != STAGE_PHASES[index]:
            defects.append(f"{label} must have phase '{STAGE_PHASES[index]}'")
        if not _text(state.get("inject_id")):
            defects.append(f"{label} is missing inject_id")
        if index == 0:
            if state.get("previous_inject_id") not in (None, ""):
                defects.append("first stage must not require a previous_inject_id")
        elif _text(state.get("previous_inject_id")) != _text(injects[index - 1].get("inject_id")):
            defects.append(f"{label} has no valid previous_inject_id")
            if not (_text(state.get("known_facts_before")) and previous_new_facts.intersection(
                {_text(x).lower() for x in state.get("known_facts_before", [])}
            )):
                defects.append(f"{label} is not causally linked to the preceding stage")

        required_state = (
            "known_facts_before", "new_confirmed_facts", "remaining_unknowns",
            "business_impact", "stakeholder_pressure", "decisions_required",
            "facilitator_context", "hidden_root_cause_context",
        )
        for field in required_state:
            value = state.get(field)
            if isinstance(value, list):
                if not value or not all(_meaningful(x) for x in value):
                    defects.append(f"{label} has weak {field}")
            elif not _meaningful(value):
                defects.append(f"{label} has empty {field}")

        decisions = state.get("decisions_required", [])
        if isinstance(decisions, list):
            weak_decisions = [
                _text(decision) for decision in decisions
                if not _meaningful(decision) or not any(marker in _text(decision).lower() for marker in _DECISION_MARKERS)
            ]
            if weak_decisions:
                defects.append(f"{label} has weak decisions_required: {weak_decisions}")
            for decision in decisions:
                decision_text = _text(decision).lower()
                if not any(marker in decision_text for marker in _DECISION_AUTHORITY_MARKERS):
                    defects.append(f"{label} decision lacks a responsible authority: {_text(decision)}")
                if not any(marker in decision_text for marker in _DECISION_TIME_MARKERS):
                    defects.append(f"{label} decision lacks a decision window: {_text(decision)}")
                if not any(marker in decision_text for marker in _DECISION_TRADEOFF_MARKERS):
                    defects.append(f"{label} decision lacks an accepted consequence or trade-off: {_text(decision)}")
            if index == 1:
                joined_decisions = " ".join(_text(decision).lower() for decision in decisions)
                required_decisions = (
                    ("session/identity containment", ("session", "identity", "contain")),
                    ("containment authority", ("authority",)),
                    ("affected-service continuity", ("continuity", "continue", "pause")),
                    ("escalation scope", ("escalat", "scope")),
                )
                missing = [
                    name for name, markers in required_decisions
                    if not all(marker in joined_decisions for marker in markers)
                ]
                if len(decisions) < 4 or missing:
                    defects.append(
                        f"{label} confirmed-compromise decisions_required must contain separate concrete decisions "
                        f"for session/identity containment, containment authority, affected-service continuity and "
                        f"escalation scope; missing={missing}"
                    )

        new_facts = {_text(x).lower() for x in state.get("new_confirmed_facts", []) if _text(x)}
        if not new_facts:
            defects.append(f"{label} introduces no materially new fact")
        previous_new_facts = new_facts

        if index == 3 and state.get("next_inject_trigger") not in (None, ""):
            defects.append("final stage must not require a next_inject_trigger")

        if not isinstance(artefact, dict):
            defects.append(f"{label} is missing participant_artefact")
        else:
            required_artefact_fields = (
                "author", "audience", "author_knowledge_boundary",
                "relative_timestamp", "purpose",
            )
            if not all(_text(artefact.get(field)) for field in required_artefact_fields):
                defects.append(f"{label} artefact is empty or metadata-only")
            if len(_text(artefact.get("content"))) < 80:
                defects.append(f"{label} artefact is empty or metadata-only")
            content = _text(artefact.get("content")).lower()
            hidden = _text(state.get("hidden_root_cause_context")).lower()
            if hidden and hidden in content:
                defects.append(f"{label} participant artefact leaks hidden root cause")
            if any(marker in content for marker in _HIDDEN_MARKERS):
                defects.append(f"{label} participant artefact leaks facilitator conclusions")

        if not isinstance(questions, list) or not 3 <= len(questions) <= 5:
            defects.append(f"{label} must contain 3–5 participant questions")
        else:
            stage_questions: set[str] = set()
            for question in questions:
                prompt = _text(question.get("prompt") if isinstance(question, dict) else question)
                normalised = prompt.casefold()
                if not _meaningful(prompt):
                    defects.append(f"{label} contains a weak participant question")
                if normalised in stage_questions:
                    defects.append(f"{label} contains a duplicated question")
                stage_questions.add(normalised)
                if any(marker in normalised for marker in _GENERIC_QUESTION_MARKERS):
                    defects.append(f"{label} contains a generic participant question")
                if any(marker in normalised for marker in _EVIDENCE_ONLY_QUESTION_MARKERS):
                    defects.append(f"{label} contains an evidence-only participant question")
                anchor_count = sum(1 for anchor in _QUESTION_ANCHORS if anchor in normalised)
                decision_language = any(marker in normalised for marker in _QUESTION_DECISION_MARKERS)
                if anchor_count < 2 or not decision_language:
                    defects.append(
                        f"{label} participant question lacks two scenario anchors and a required decision"
                    )
                if any(marker in normalised for marker in _HIDDEN_MARKERS):
                    defects.append(f"{label} participant questions leak hidden root cause")

        if not isinstance(guidance, dict):
            defects.append(f"{label} is missing facilitator guidance")
        else:
            for field in (
                "inject_purpose", "facts_participants_may_rely_on",
                "information_not_yet_available", "optional_probes",
                "expected_discussion_themes", "escalation_cue",
                "information_supplied_only_if_requested", "common_failure_modes",
                "reveal_timing", "after_action_observation",
            ):
                value = guidance.get(field)
                if isinstance(value, list):
                    if not value or not all(_meaningful(x) for x in value):
                        defects.append(f"{label} has incomplete facilitator guidance: {field}")
                elif not _meaningful(value):
                    defects.append(f"{label} has incomplete facilitator guidance: {field}")

    wrap_up = scenario.get("facilitator_reveal")
    if not isinstance(wrap_up, dict):
        defects.append("controlled root-cause wrap-up is missing")
    elif not _meaningful(wrap_up.get("reveal_narrative")):
        defects.append("controlled root-cause wrap-up is empty")

    return not defects, defects


def generate_with_one_repair(
    initial_plan: Any,
    repair: Optional[Callable[[list[str]], Any]] = None,
) -> tuple[Any, list[str], int]:
    """Validate once and permit at most one targeted repair callback."""
    plan = initial_plan.model_dump() if hasattr(initial_plan, "model_dump") else initial_plan
    valid, defects = validate_four_stage_plan(plan)
    if valid:
        return plan, [], 0
    if repair is None:
        return plan, defects, 0

    repaired = repair(defects)
    repaired_dict = repaired.model_dump() if hasattr(repaired, "model_dump") else repaired
    repaired_valid, repaired_defects = validate_four_stage_plan(repaired_dict)
    if repaired_valid:
        return repaired_dict, [], 1
    return repaired_dict, repaired_defects, 1


class TabletopGenerationError(RuntimeError):
    """Raised when tabletop generation or mandatory enrichment fails."""

    def __init__(self, stage: str, message: str, defects: Optional[list[str]] = None):
        self.stage = stage
        self.defects = defects or []
        detail = f"{stage}: {message}"
        if self.defects:
            detail += f" | validation defects: {'; '.join(self.defects)}"
        super().__init__(detail)


def _repair_prompt(
    prompt: str,
    defects: list[str],
    plan: dict[str, Any],
) -> str:
    """Build the single permitted repair prompt without any UI/session dependency."""
    repair_fields: list[str] = []
    scenarios = plan.get("scenarios", []) if isinstance(plan, dict) else []
    injects = scenarios[0].get("injects", []) if scenarios and isinstance(scenarios[0], dict) else []
    failed_stage_indexes = {
        int(match.group(1))
        for defect in defects
        for match in [__import__("re").search(r"stage (\d+)", defect, __import__("re").IGNORECASE)]
        if match
    }
    for stage_index, stage in enumerate(injects, 1):
        if stage_index not in failed_stage_indexes:
            continue
        state = stage.get("inject_state", {}) if isinstance(stage, dict) else {}
        stage_defects = [
            defect for defect in defects
            if f"stage {stage_index}" in defect.lower()
        ]
        fields = [f"Stage {stage_index} ({state.get('phase', 'unknown')})"]
        if any("question" in defect.lower() for defect in stage_defects):
            fields.append(
                "rejected_questions=" + str([
                    question.get("prompt", "")
                    for question in stage.get("participant_questions", [])
                    if isinstance(question, dict)
                ])
            )
        if any("decision" in defect.lower() for defect in stage_defects):
            fields.append("rejected_decisions=" + str(state.get("decisions_required", [])))
        fields.append(
            "relevant_stage_facts=" + str({
                "known_facts_before": state.get("known_facts_before", []),
                "new_confirmed_facts": state.get("new_confirmed_facts", []),
                "business_impact": state.get("business_impact", ""),
                "stakeholder_pressure": state.get("stakeholder_pressure", ""),
            })
        )
        repair_fields.append("; ".join(fields))

    return (
        prompt
        + "\n\nTARGETED REPAIR PASS (THE ONLY ALLOWED REPAIR):\n"
        "Repair only the participant question and decisions_required fields named by the "
        "failed validator rules below. Preserve valid artefacts, facilitator guidance, "
        "scenario facts, stage phases, causal links, and boundary values. Do not regenerate "
        "unrelated fields, add scenarios, or add stages. The structured-output API requires "
        "the complete corrected TabletopMasterPlan object.\n"
        "Failed validator rules:\n"
        + "\n".join(f"- {defect}" for defect in defects)
        + "\nRejected fields and relevant scenario facts:\n"
        + "\n".join(repair_fields)
        + "\nREPAIR USING THESE EXACT CONTENT RULES, NOT GENERAL ADVICE:\n"
        "Replace each rejected participant question with a stage-specific question requiring "
        "a choice, authorisation, prioritisation, or explicit risk acceptance under a timebox. "
        "Use at least two concrete anchors from that stage's own facts or artefact, including "
        "the named service or platform, affected identity or role, operational consequence, "
        "supplier dependency, authority, or time constraint. Never leave an evidence-only, "
        "telemetry-only, notification-only, escalation-only, or generic question.\n"
        "Replace each rejected decisions_required value with complete decisions. Every item must "
        "name the choice, responsible authority, affected service/identity/process, decision "
        "window or trigger, and accepted consequence or trade-off. Do not use verify, monitor, "
        "investigate, assess, determine, notify, or engage as the principal action.\n"
        "For Confirmed compromise, provide four separate decisions: session/identity "
        "containment; containment authority; affected-service continuity; and escalation scope. "
        "Use customer-specific names from the supplied stage facts, never example customer names. "
        "Set the final stage next_inject_trigger to null."
    )


def generate_tabletop_plan(
    client: Any,
    deployment: str,
    client_inputs: dict[str, Any],
    selected_themes: list[str],
    custom_brief: Optional[str] = None,
    audience: str = "Blended",
    exercise_profile: str = "blended",
    presentation_detail_profile: str = "standard",
    *,
    model_runner: Optional[Callable[..., Any]] = None,
    blueprint: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Generate, validate, repair once, enrich and validate one tabletop plan.

    This is the production orchestration boundary. It deliberately accepts all
    dependencies explicitly and never imports a Streamlit page or accesses
    Streamlit session state.
    """
    try:
        from core import LLMEngine
        from facilitator_guidance import attach_facilitation_to_plan, generate_inject_facilitation
        from participant_artefacts import synthesise_participant_artefacts
        from prompts import (
            SYSTEM_PERSONA_TABLETOP,
            TabletopMasterPlan,
            build_tabletop_plan_prompt,
        )
    except Exception as exc:
        raise TabletopGenerationError("initialisation", str(exc)) from exc

    runner = model_runner or LLMEngine.generate_structured_report
    prompt = build_tabletop_plan_prompt(
        client_inputs,
        selected_themes,
        custom_brief=custom_brief,
        audience=audience,
        exercise_profile=exercise_profile,
        presentation_detail_profile=presentation_detail_profile,
    )

    try:
        initial = runner(
            client,
            deployment,
            SYSTEM_PERSONA_TABLETOP,
            prompt,
            TabletopMasterPlan,
        )
    except Exception as exc:
        raise TabletopGenerationError("azure_request", str(exc)) from exc
    if initial is None:
        raise TabletopGenerationError("azure_response", "structured generation returned no result")

    plan = initial.model_dump() if hasattr(initial, "model_dump") else initial
    valid, defects = validate_four_stage_plan(plan)
    if not valid:
        repair_prompt = _repair_prompt(prompt, defects, plan)
        try:
            repaired = runner(
                client,
                deployment,
                SYSTEM_PERSONA_TABLETOP,
                repair_prompt,
                TabletopMasterPlan,
            )
        except Exception as exc:
            raise TabletopGenerationError("repair_request", str(exc), defects) from exc
        if repaired is None:
            raise TabletopGenerationError("repair_response", "repair returned no result", defects)
        plan = repaired.model_dump() if hasattr(repaired, "model_dump") else repaired
        valid, defects = validate_four_stage_plan(plan)
        if not valid:
            raise TabletopGenerationError("repair_validation", "one repair did not produce a valid plan", defects)

    try:
        plan = synthesise_participant_artefacts(plan, blueprint, audience=audience)
    except Exception as exc:
        raise TabletopGenerationError("artefact_synthesis", str(exc)) from exc

    try:
        fac_map = generate_inject_facilitation(plan, blueprint, audience=audience)
        plan = attach_facilitation_to_plan(plan, fac_map)
    except Exception as exc:
        raise TabletopGenerationError("facilitator_guidance", str(exc)) from exc

    valid, defects = validate_four_stage_plan(plan)
    if not valid:
        raise TabletopGenerationError("final_validation", "enriched plan failed final validation", defects)
    return plan


__all__ = [
    "STAGE_PHASES",
    "TabletopGenerationError",
    "validate_four_stage_plan",
    "generate_with_one_repair",
    "generate_tabletop_plan",
]
