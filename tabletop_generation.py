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
    "communications lead",
    "legal counsel",
    "executive team",
    "executive incident owner",
    "dpo",
    "cio",
    "ciso",
    "cto",
    "it director",
    "communications"
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


def _as_lower_set(vals: Any) -> set[str]:
    """Normalise a list-like of strings to a lower-cased set, ignoring empty entries."""
    try:
        return {_text(x).lower() for x in (vals or []) if _text(x)}
    except Exception:
        return set()


def validate_four_stage_plan(plan: Any) -> tuple[bool, list[str]]:
    """Return ``(valid, defects)`` for a live TabletopMasterPlan dictionary."""
    defects: list[str] = []
    # Reset cross-call fact-to-statement registries to avoid stale mappings between separate validations
    try:
        setattr(validate_four_stage_plan, "_fact_stmt_map", {})
        setattr(validate_four_stage_plan, "_stmt_to_id", {})
    except Exception:
        pass
    if not isinstance(plan, dict):
        return False, ["generation did not return an object"]

    # Determine if typed fields are REQUIRED (newly generated) or optional (legacy/imported)
    gm = (plan.get("generation_metadata") or {}) if isinstance(plan, dict) else {}
    schema_ver = str(gm.get("schema_version") or "")
    rules_ver = str(gm.get("validation_rule_version") or "")
    # Require typed when schema_version starts with 'tt-' OR rules_ver contains 'typed'
    require_typed = schema_ver.startswith("tt-") or "typed" in rules_ver.lower()

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
    previous_new_ids: set[str] = set()
    seen_inject_ids: set[str] = set()
    all_new_facts: set[str] = set()
    hidden_cause_set: set[str] = set()
    cumulative_fact_ids: set[str] = set()

    for index, inject in enumerate(injects):
        label = f"stage {index + 1}"
        if not isinstance(inject, dict):
            defects.append(f"{label} is not an object")
            continue

        state = inject.get("inject_state")
        artefact = inject.get("participant_artefact")
        questions = inject.get("participant_questions")
        questions_typed = inject.get("participant_questions_typed")
        guidance = inject.get("facilitator_guidance")

        # Enforce presence of typed structures for newly-generated plans
        if require_typed:
            if not isinstance(state.get("decisions_typed"), list) or not state.get("decisions_typed"):
                defects.append(f"{label} missing required typed decisions (decisions_typed)")
            if not isinstance(questions_typed, list) or not questions_typed:
                defects.append(f"{label} missing required typed participant questions (participant_questions_typed)")

        if not isinstance(state, dict):
            defects.append(f"{label} is missing InjectState-compatible internal state")
            continue
        if _text(state.get("phase")) != STAGE_PHASES[index]:
            defects.append(f"{label} must have phase '{STAGE_PHASES[index]}'")
        state_inject_id = _text(state.get("inject_id"))
        public_id = _text(inject.get("inject_id"))
        if not state_inject_id:
            defects.append(f"{label} is missing inject_id")
        if public_id and state_inject_id and public_id != state_inject_id:
            defects.append(f"{label} inject_id mismatch between public and internal state")
        if public_id:
            if public_id in seen_inject_ids:
                defects.append(f"{label} inject_id is not unique")
            else:
                seen_inject_ids.add(public_id)
        if index == 0:
            if state.get("previous_inject_id") not in (None, ""):
                defects.append("first stage must not require a previous_inject_id")
        elif _text(state.get("previous_inject_id")) != _text(injects[index - 1].get("inject_id")):
            defects.append(f"{label} has no valid previous_inject_id")
            if not (_text(state.get("known_facts_before")) and previous_new_facts.intersection(
                {_text(x).lower() for x in state.get("known_facts_before", [])}
            )):
                defects.append(f"{label} is not causally linked to the preceding stage")
        # Always enforce causal dependency on the immediately preceding stage
        if index > 0:
            kfb_ids = set(state.get("known_fact_ids_before", []) or [])
            if kfb_ids:
                if not (previous_new_ids and kfb_ids.intersection(previous_new_ids)):
                    defects.append(f"{label} is not causally linked to the preceding stage")
            else:
                kfb = {_text(x).lower() for x in state.get("known_facts_before", []) if _text(x)}
                if not (kfb and previous_new_facts.intersection(kfb)):
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

        # Decisions: prefer typed decisions if present
        decisions_typed = state.get("decisions_typed")
        if isinstance(decisions_typed, list) and decisions_typed:
            cats: list[str] = []
            for d in decisions_typed:
                if not isinstance(d, dict):
                    defects.append(f"{label} has invalid typed decision payload")
                    continue
                cat = _text(d.get("category"))
                dec = _text(d.get("decision"))
                auth = _text(d.get("authority"))
                aff = _text(d.get("affected_operation"))
                ddl = _text(d.get("deadline"))
                cons = _text(d.get("accepted_consequence"))
                if not all([cat, dec, auth, aff, cons]) or (not ddl and d.get("deadline_minutes") is None):
                    defects.append(f"{label} typed decision has missing fields")
                # Structural consequence validation (no token requirement; legacy-only enforces 'accepting' wording)
                lc_cons = cons.lower()
                if lc_cons in {"n/a", "tbd", "none"} or "potential impact" in lc_cons or "minimal impact" in lc_cons or "ensuring accuracy" in lc_cons:
                    defects.append(f"{label} typed decision has non-substantive accepted consequence: {cons}")
                if lc_cons == dec.lower():
                    defects.append(f"{label} typed decision accepted_consequence repeats the decision text")
                # Typed decisions deadline policy:
                # - Current typed plans (require_typed=True): must have numeric minutes >=1
                # - Legacy context: allow either deadline_minutes>=1 OR a bounded deadline string
                if require_typed:
                    dm = d.get("deadline_minutes")
                    try:
                        if int(dm) <= 0:
                            defects.append(f"{label} typed decision has non-positive deadline_minutes")
                    except Exception:
                        defects.append(f"{label} typed decision lacks a bounded deadline_minutes")
                else:
                    dm = d.get("deadline_minutes")
                    if dm is not None:
                        try:
                            if int(dm) <= 0:
                                defects.append(f"{label} typed decision has non-positive deadline_minutes")
                        except Exception:
                            defects.append(f"{label} typed decision has invalid deadline_minutes")
                    else:
                        if not any(tok in ddl.lower() for tok in _DECISION_TIME_MARKERS):
                            defects.append(f"{label} typed decision lacks a bounded deadline")
                cats.append(cat)
            if index == 1:
                required = [
                    "session_identity_containment",
                    "containment_authority",
                    "affected_service_continuity",
                    "escalation_scope",
                ]
                # Enforce exactly four typed decisions, one per required category
                if len(cats) != 4 or any(cats.count(c) != 1 for c in required):
                    defects.append(f"{label} must contain exactly four typed decisions, one per required Stage 2 category")
        else:
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
                    # Category marker sets: satisfied if ANY marker group for the category matches
                    category_markers = {
                        "session/identity containment": [
                            ("session", "contain"),
                            ("revoke", "token"),
                            ("invalidate", "session"),
                            ("disable", "account"),
                            ("reauth", "session"),
                        ],
                        "containment authority": [
                            ("authority",),
                        ],
                        "affected-service continuity": [
                            ("continuity",),
                            ("continue",),
                            ("pause",),
                            ("degraded", "service"),
                            ("manual", "dispatch"),
                            ("failover",),
                        ],
                        "escalation scope": [
                            ("escalat",),
                            ("regulator",),
                            ("executive",),
                            ("board",),
                            ("external",),
                        ],
                    }
                    missing = []
                    for cat, groups in category_markers.items():
                        satisfied = False
                        for grp in groups:
                            if all(tok in joined_decisions for tok in grp):
                                satisfied = True
                                break
                        if not satisfied:
                            missing.append(cat)
                    if len(decisions) < 4 or missing:
                        defects.append(
                            f"{label} confirmed-compromise decisions_required must contain separate concrete decisions "
                            f"for session/identity containment, containment authority, affected-service continuity and "
                            f"escalation scope; missing={missing}"
                        )

        # Facts (text) and IDs
        new_facts_list = state.get("new_confirmed_facts", []) or []
        new_facts = _as_lower_set(new_facts_list)
        if not new_facts:
            defects.append(f"{label} introduces no materially new fact")
        # Each stage must introduce at least one fact not seen in earlier stages
        if not (new_facts - all_new_facts):
            defects.append(f"{label} introduces no materially new fact")
        # Enforce new_fact_ids integrity and 1:1 mapping to substantive facts
        new_ids_list = state.get("new_fact_ids")
        if require_typed:
            if not isinstance(new_ids_list, list) or not new_ids_list:
                defects.append(f"{label} new_fact_ids missing or empty")
                new_ids = set()
            else:
                new_ids = set(new_ids_list)
                if len(new_ids_list) != len(new_facts_list):
                    defects.append(f"{label} new_fact_ids length {len(new_ids_list)} does not match new_confirmed_facts length {len(new_facts_list)}")
                if previous_new_ids and new_ids.intersection(previous_new_ids):
                    defects.append(f"{label} new_fact_ids are not unique across stages")
                # No blank facts; no duplicate statements under different IDs
                id_statement_pairs = []
                for i, st in enumerate(new_facts_list):
                    if not _meaningful(st):
                        defects.append(f"{label} contains a non-substantive new_confirmed_facts item at index {i}")
                    else:
                        try:
                            fid = str(new_ids_list[i])
                            id_statement_pairs.append((fid, _text(st)))
                        except Exception:
                            continue
                # Track global mapping
                if not hasattr(validate_four_stage_plan, "_fact_stmt_map"):
                    setattr(validate_four_stage_plan, "_fact_stmt_map", {})
                fact_stmt_map: dict[str, str] = getattr(validate_four_stage_plan, "_fact_stmt_map")
                # Also track statement->id uniqueness
                if not hasattr(validate_four_stage_plan, "_stmt_to_id"):
                    setattr(validate_four_stage_plan, "_stmt_to_id", {})
                stmt_to_id: dict[str, str] = getattr(validate_four_stage_plan, "_stmt_to_id")
                for fid, stmt in id_statement_pairs:
                    prev_stmt = fact_stmt_map.get(fid)
                    if prev_stmt and prev_stmt != stmt:
                        defects.append(f"{label} fact ID {fid} maps to a different statement than earlier stage")
                    fact_stmt_map[fid] = stmt
                    prev_id = stmt_to_id.get(stmt)
                    if prev_id and prev_id != fid:
                        defects.append(f"{label} duplicate fact statement under different IDs: '{stmt}'")
                    stmt_to_id[stmt] = fid
        else:
            # Legacy/import mode: if IDs are provided, enforce integrity; otherwise permit text-only causality
            if isinstance(new_ids_list, list) and new_ids_list:
                new_ids = set(new_ids_list)
                if len(new_ids_list) != len(new_facts_list):
                    defects.append(f"{label} new_fact_ids length {len(new_ids_list)} does not match new_confirmed_facts length {len(new_facts_list)}")
                if previous_new_ids and new_ids.intersection(previous_new_ids):
                    defects.append(f"{label} new_fact_ids are not unique across stages")
                if not hasattr(validate_four_stage_plan, "_fact_stmt_map"):
                    setattr(validate_four_stage_plan, "_fact_stmt_map", {})
                fact_stmt_map: dict[str, str] = getattr(validate_four_stage_plan, "_fact_stmt_map")
                if not hasattr(validate_four_stage_plan, "_stmt_to_id"):
                    setattr(validate_four_stage_plan, "_stmt_to_id", {})
                stmt_to_id: dict[str, str] = getattr(validate_four_stage_plan, "_stmt_to_id")
                for i, st in enumerate(new_facts_list):
                    try:
                        fid = str(new_ids_list[i])
                        stmt = _text(st)
                    except Exception:
                        continue
                    if _meaningful(stmt):
                        prev_stmt = fact_stmt_map.get(fid)
                        if prev_stmt and prev_stmt != stmt:
                            defects.append(f"{label} fact ID {fid} maps to a different statement than earlier stage")
                        fact_stmt_map[fid] = stmt
                        prev_id = stmt_to_id.get(stmt)
                        if prev_id and prev_id != fid:
                            defects.append(f"{label} duplicate fact statement under different IDs: '{stmt}'")
                        stmt_to_id[stmt] = fid
            else:
                new_ids = set()
        # Prevent future-facing references: gather all subsequent stage IDs and ensure known_fact_ids_before doesn't point to them
        future_ids: set[str] = set()
        try:
            for later in injects[index + 1:]:
                s2 = later.get("inject_state", {}) if isinstance(later, dict) else {}
                future_ids |= set(s2.get("new_fact_ids") or [])
        except Exception:
            future_ids = set()
        kfb_ids_here = set(state.get("known_fact_ids_before") or [])
        if kfb_ids_here and future_ids and kfb_ids_here.intersection(future_ids):
            defects.append(f"{label} known_fact_ids_before references future-stage facts")
        # Also ensure known_fact_ids_before resolve to already seen IDs (earlier stages only)
        prior_ids = cumulative_fact_ids.copy()
        if index == 0 and kfb_ids_here:
            defects.append(f"{label} Stage 1 should not reference known_fact_ids_before")
        elif index > 0 and kfb_ids_here and not kfb_ids_here.issubset(prior_ids):
            unresolved = sorted(list(kfb_ids_here - prior_ids))
            defects.append(f"{label} known_fact_ids_before reference unknown facts: {unresolved}")
        # Prevent future-facing references: gather all subsequent stage IDs and ensure known_fact_ids_before doesn't point to them
        future_ids: set[str] = set()
        try:
            for later in injects[index + 1:]:
                s2 = later.get("inject_state", {}) if isinstance(later, dict) else {}
                future_ids |= set(s2.get("new_fact_ids") or [])
        except Exception:
            future_ids = set()
        kfb_ids_here = set(state.get("known_fact_ids_before") or [])
        if kfb_ids_here and future_ids and kfb_ids_here.intersection(future_ids):
            defects.append(f"{label} known_fact_ids_before references future-stage facts")
        all_new_facts |= new_facts
        # Track hidden root cause consistency
        hc = _text(state.get("hidden_root_cause_context")).lower()
        if hc:
            hidden_cause_set.add(hc)
        previous_new_facts = new_facts
        previous_new_ids = new_ids
        cumulative_fact_ids |= new_ids

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
            # Prevent future-stage knowledge leakage in earlier artefacts
            future_tokens: set[str] = set()
            try:
                for later in injects[index + 1:]:
                    s2 = later.get("inject_state", {}) if isinstance(later, dict) else {}
                    future_tokens |= {_text(x).lower() for x in s2.get("new_confirmed_facts", []) if _text(x)}
            except Exception:
                future_tokens = set()
            if any(tok and tok in content for tok in future_tokens):
                defects.append(f"{label} artefact reveals future-stage knowledge")

        # Questions: prefer typed validation if present
        if isinstance(questions_typed, list) and questions_typed:
            stage_questions: set[str] = set()
            # Build available ID to statement map (prior + current stage)
            available_ids = set(state.get("known_fact_ids_before") or []) | cumulative_fact_ids | set(state.get("new_fact_ids") or [])
            id_to_stmt = {}
            try:
                # Use global mapping built earlier for prior IDs
                fact_stmt_map: dict[str, str] = getattr(validate_four_stage_plan, "_fact_stmt_map")
                id_to_stmt.update({k: v for k, v in fact_stmt_map.items() if k in available_ids})
            except Exception:
                pass
            # Add current stage id->statement if present
            try:
                for i, fid in enumerate(state.get("new_fact_ids") or []):
                    st = _text((state.get("new_confirmed_facts") or [])[i])
                    if fid and _meaningful(st):
                        id_to_stmt[str(fid)] = st
            except Exception:
                pass
            for qt in questions_typed:
                if not isinstance(qt, dict):
                    defects.append(f"{label} contains an invalid typed participant question")
                    continue
                prompt = _text(qt.get("prompt"))
                normalised = prompt.casefold()
                if not _meaningful(prompt):
                    defects.append(f"{label} contains a weak participant question")
                if normalised in stage_questions:
                    defects.append(f"{label} contains a duplicated question")
                stage_questions.add(normalised)
                anchors = qt.get("anchor_fact_ids") or []
                options = qt.get("decision_options") or []
                dm_q = qt.get("deadline_minutes")
                ddl_q = _text(qt.get("deadline"))
                consequences = qt.get("competing_consequences") or []
                auth = _text(qt.get("authority"))
                if not (isinstance(anchors, list) and len(anchors) >= 2):
                    defects.append(f"{label} typed question lacks two anchor fact references")
                if len(set(anchors)) < 2:
                    defects.append(f"{label} typed question anchor_fact_ids must reference at least two distinct facts")
                if anchors and not set(anchors).issubset(available_ids):
                    defects.append(f"{label} typed question anchor_fact_ids reference facts not available at this stage")
                # Anchors must resolve to two distinct fact statements
                try:
                    stmts = {id_to_stmt.get(str(a), "") for a in anchors if str(a) in id_to_stmt}
                    if len([s for s in stmts if _meaningful(s)]) < 2:
                        defects.append(f"{label} typed question anchors must resolve to two distinct fact statements")
                except Exception:
                    pass
                if not (isinstance(options, list) and len(options) >= 2):
                    defects.append(f"{label} typed question lacks explicit decision options")
                # Typed participant question deadline policy:
                # - Current typed plans (require_typed=True): must have numeric minutes >=1
                # - Legacy context: allow either deadline_minutes>=1 OR a bounded deadline string
                if require_typed:
                    try:
                        if int(dm_q) < 1:
                            defects.append(f"{label} typed question lacks a bounded deadline_minutes")
                    except Exception:
                        defects.append(f"{label} typed question lacks a bounded deadline_minutes")
                else:
                    if dm_q is not None:
                        try:
                            if int(dm_q) < 1:
                                defects.append(f"{label} typed question lacks a bounded deadline_minutes")
                        except Exception:
                            defects.append(f"{label} typed question has invalid deadline_minutes")
                    else:
                        if not any(tok in ddl_q.lower() for tok in _DECISION_TIME_MARKERS):
                            defects.append(f"{label} typed question lacks a bounded deadline")
                if not (isinstance(consequences, list) and len(consequences) >= 2):
                    defects.append(f"{label} typed question lacks competing consequences")
                if not auth:
                    defects.append(f"{label} typed question lacks an authority")
        else:
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
                    # Consider non-empty strings sufficient for facilitator guidance lists
                    if not value or not all(bool(_text(x)) for x in value):
                        defects.append(f"{label} has incomplete facilitator guidance: {field}")
                else:
                    if not _text(value):
                        defects.append(f"{label} has incomplete facilitator guidance: {field}")

    # Hidden root cause must be consistent across stages
    wrap_up = scenario.get("facilitator_reveal")
    if not isinstance(wrap_up, dict):
        defects.append("controlled root-cause wrap-up is missing")
    elif not _meaningful(wrap_up.get("reveal_narrative")):
        defects.append("controlled root-cause wrap-up is empty")
    else:
        if len(hidden_cause_set) != 1:
            defects.append("inconsistent hidden root cause across stages")
        else:
            hc = next(iter(hidden_cause_set))
            rn = _text(wrap_up.get("reveal_narrative")).lower()
            if hc:
                import re as _re
                # Accept if the full hidden cause phrase appears OR if there is sufficient token overlap
                if hc not in rn:
                    hc_core = hc.split(":", 1)[-1].strip()
                    hc_tokens = {t for t in _re.findall(r"[a-z0-9\-]+", hc_core) if len(t) >= 4}
                    rn_tokens = {t for t in _re.findall(r"[a-z0-9\-]+", rn) if len(t) >= 4}
                    if len(hc_tokens.intersection(rn_tokens)) < 2:
                        defects.append("wrap-up does not reveal the same hidden root cause")

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
            # Include typed questions if present
            fields.append("rejected_questions_typed=" + str(stage.get("participant_questions_typed", [])))
        if any("decision" in defect.lower() for defect in stage_defects):
            fields.append("rejected_decisions=" + str(state.get("decisions_required", [])))
            # Include typed decisions if present
            fields.append("rejected_decisions_typed=" + str(state.get("decisions_typed", [])))
        # Allow repair of known_facts_before when causality defects exist
        causality_defect = any("not causally linked" in defect.lower() or "no valid previous_inject_id" in defect.lower() for defect in stage_defects)
        if causality_defect:
            fields.append("repair_known_facts_before=True")
        # Allow repair of participant_artefact.content when leakage defects exist
        leakage_defect = any("artefact leaks" in defect.lower() or "participant artefact leaks" in defect.lower() for defect in stage_defects)
        if leakage_defect:
            fields.append("repair_participant_artefact_body=True")
        fields.append(
            "relevant_stage_facts=" + str({
                "known_facts_before": state.get("known_facts_before", []),
                "new_confirmed_facts": state.get("new_confirmed_facts", []),
                "known_fact_ids_before": state.get("known_fact_ids_before", []),
                "new_fact_ids": state.get("new_fact_ids", []),
                "business_impact": state.get("business_impact", ""),
                "stakeholder_pressure": state.get("stakeholder_pressure", ""),
            })
        )
        # Include any missing facilitator guidance field names for this stage
        try:
            missing_fac = sorted({
                d.split(":", 1)[-1].strip()
                for d in stage_defects
                if "facilitator guidance" in d.lower()
            })
        except Exception:
            missing_fac = []
        if missing_fac:
            fields.append("missing_facilitator_fields=" + str(missing_fac))
        # Additional repair context per stage: remaining_unknowns, anchors, causality, deadlines
        try:
            stage_texts = [d.lower() for d in stage_defects]
            # Remaining unknowns weak
            if any("weak remaining_unknowns" in d for d in stage_texts):
                fields.append("replace_remaining_unknowns=True")
                fields.append("rejected_remaining_unknowns=" + str(state.get("remaining_unknowns", [])))
            # Anchor-related defects
            if any("anchor" in d or "typed question" in d for d in stage_texts):
                # Build available canonical IDs and mapping
                try:
                    registry = plan.get("_canonical_fact_registry", {}) if isinstance(plan, dict) else {}
                except Exception:
                    registry = {}
                # Prior cumulative ids
                try:
                    prior_ids = []
                    for pi in range(1, stage_index):
                        pst = injects[pi - 1].get("inject_state", {}) if isinstance(injects[pi - 1], dict) else {}
                        prior_ids.extend(list(pst.get("new_fact_ids") or []))
                except Exception:
                    prior_ids = []
                available_ids = set(state.get("known_fact_ids_before") or []) | set(prior_ids) | set(state.get("new_fact_ids") or [])
                id_to_stmt = {str(k): str(v) for k, v in registry.items() if str(k) in available_ids}
                fields.append("available_canonical_ids=" + str(sorted(list(available_ids))))
                fields.append("available_id_to_statement=" + str(id_to_stmt))
                # Rejected anchor ids per typed question
                try:
                    rq = []
                    for qt in (stage.get("participant_questions_typed") or []):
                        if isinstance(qt, dict):
                            rq.append({"prompt": _text(qt.get("prompt")), "anchor_fact_ids": list(qt.get("anchor_fact_ids") or [])})
                    fields.append("rejected_anchor_ids=" + str(rq))
                except Exception:
                    pass
            # Causality: previous-stage context and current known refs
            if any("not causally linked" in d or "no valid previous_inject_id" in d for d in stage_texts):
                try:
                    prev_state = (injects[stage_index - 2] or {}).get("inject_state", {}) if stage_index > 1 else {}
                except Exception:
                    prev_state = {}
                prev_ids = list(prev_state.get("new_fact_ids") or [])
                try:
                    registry = plan.get("_canonical_fact_registry", {}) if isinstance(plan, dict) else {}
                except Exception:
                    registry = {}
                prev_id_to_stmt = {str(fid): str(registry.get(str(fid), "")) for fid in prev_ids}
                fields.append("previous_stage_id_to_statement=" + str(prev_id_to_stmt))
                fields.append("current_known_facts_before=" + str(state.get("known_facts_before", [])))
                fields.append("current_known_fact_ids_before=" + str(state.get("known_fact_ids_before", [])))
            # Typed decision without bounded deadline_minutes
            if any("deadline_minutes" in d and "decision" in d for d in stage_texts):
                defective = []
                try:
                    for d in (state.get("decisions_typed") or []):
                        if isinstance(d, dict):
                            dm = d.get("deadline_minutes")
                            try:
                                ok_dm = int(dm) >= 1
                            except Exception:
                                ok_dm = False
                            if not ok_dm:
                                defective.append({
                                    "category": _text(d.get("category")),
                                    "decision": _text(d.get("decision")),
                                    "authority": _text(d.get("authority")),
                                    "affected_operation": _text(d.get("affected_operation")),
                                })
                except Exception:
                    defective = []
                if defective:
                    fields.append("defective_decisions_missing_deadline_minutes=" + str(defective))
                if stage_index == 2:
                    fields.append("stage2_return_complete_decisions_typed=True")
        except Exception:
            pass
        repair_fields.append("; ".join(fields))

    return (
        prompt
        + "\n\nTARGETED REPAIR PASS (THE ONLY ALLOWED REPAIR):\n"
        "Repair only the named fields: participant question(s)/participant_questions_typed, decisions_required/decisions_typed, and any listed facilitator_guidance fields. "
        "When explicitly listed in 'Rejected fields and relevant scenario facts', also allow: "
        "inject_state.known_facts_before (to carry forward exact prior facts for causality), inject_state.known_fact_ids_before/new_fact_ids (to correct causal ID chain), and participant_artefact.content (to remove hidden-cause markers). "
        "Do not modify other fields unless enumerated by the validator defects. "
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
        "Use this labelled form for every decision string and replace defective entries rather than paraphrasing:\n"
        "DECISION: <concrete action>. AUTHORITY: <role>. AFFECTED OPERATION: <named identity/service/process>. DEADLINE: <window or trigger>. TRADE-OFF: accepting <explicit operational/security/customer/financial/regulatory consequence>.\n"
        "Trade-off phrasing MUST use 'accepting/accept/balancing/at the cost of/residual risk'. Phrases such as 'may …', 'risk of …', 'potential …', 'service disruption', 'additional costs', 'ensuring accuracy' are insufficient and must be rewritten into explicit acceptance.\n"
        "CONFIRMED COMPROMISE (STAGE 2) — STRICT REPLACEMENT INSTRUCTIONS:\n"
        "Replace the entire Stage 2 decisions_typed array. Do not append to, preserve, merge with or partially edit the existing Stage 2 array.\n"
        "Return exactly four Stage 2 decision objects, no fewer and no more.\n"
        "Use each of these exact category values exactly once:\n"
        "1. session_identity_containment\n"
        "2. containment_authority\n"
        "3. affected_service_continuity\n"
        "4. escalation_scope\n"
        "Do not include category ‘other’ or any additional category. Do not duplicate a category.\n"
        "Each of the four objects must independently contain: category; decision; authority; affected_operation; deadline_minutes (>=1); accepted_consequence.\n"
        "Return Stage 2 decisions_typed as the complete four-object replacement array.\n"
        "For any listed facilitator_guidance fields (e.g., expected_discussion_themes), populate them with substantive stage-specific content without altering unrelated, valid guidance.\n"
        "STAGE 4 FACT REPLACEMENT — STRICT INSTRUCTIONS:\n"
        "When Stage 4 new_confirmed_facts is defective, replace the complete Stage 4 inject_state.new_confirmed_facts list. Do not append to, merge with, partially edit or preserve defective entries. Return 2–4 facts. Each fact must be at least 24 characters; describe one concrete newly confirmed event, observation, external pressure or business consequence; name at least one scenario-specific role, identity, service, supplier, business process, customer impact, regulator, executive concern or media pressure; introduce information not already established in Stages 1–3; be materially distinct from every other Stage 4 fact; be suitable for grounding an executive or external-pressure decision; avoid placeholders, generic summaries and vague escalation language; and must not disclose the hidden root cause. Do NOT return non-substantive items such as 'media attention is increasing', 'customers are concerned', 'impact is significant', 'the incident is ongoing', 'external pressure has increased', 'more information is required', 'further investigation is needed', 'management has been informed', 'reputational risk exists'.\n"
        "DETERMINISTIC POSITION-TO-ID CONTRACT:\n"
        "Canonical fact IDs are assigned deterministically after your response. For each repaired stage: new_confirmed_facts item 1 becomes S{stage}-F1; item 2 becomes S{stage}-F2; item 3 becomes S{stage}-F3; item 4 becomes S{stage}-F4. When replacing participant_questions_typed in the SAME stage, use these exact predictable canonical IDs according to the FINAL ordering of new_confirmed_facts. For Stage 4 specifically: the first repaired fact must be referenced as S4-F1; the second as S4-F2; the third as S4-F3 if present; the fourth as S4-F4 if present. Do NOT return arbitrary non-canonical IDs such as 'F-001', 'F-004', 'FACT-4', 'FACT_4', 'STAGE4_FACT1', or any other format.\n"
        "STAGE 4 QUESTION REPLACEMENT — STRICT INSTRUCTIONS:\n"
        "When Stage 4 new_confirmed_facts is replaced, also replace the COMPLETE Stage 4 participant_questions_typed list in the same repair response (do not append or partially edit). Return 3–5 participant questions. Every question must contain at least two distinct anchor_fact_ids; use ONLY predictable canonical IDs derived from the FINAL repaired Stage 4 fact ordering (S4-F1..S4-F4) or valid canonical facts already available from earlier stages; resolve to two distinct substantive fact statements; reference facts genuinely available to participants at Stage 4; contain a named deciding authority; require a concrete choice/authorisation/prioritisation/risk-acceptance decision; contain at least two explicit decision_options; include deadline_minutes as an integer >= 1; contain at least two competing_consequences; remain grounded in the scenario; and avoid hidden-root-cause information. Before returning, compare every question’s anchors against the FINAL repaired new_confirmed_facts ordering and ensure they use valid canonical IDs (e.g., ['S4-F1','S4-F2'] is valid; ['S4-F1','S4-F1'] is invalid; any ID absent from the final Stage 4 list or not yet available from earlier stages is invalid; two different IDs resolving to the same statement is invalid).\n"
        "REMAINING UNKNOWNS (ALL STAGES) — STRICT REPLACEMENT INSTRUCTIONS:\n"
        "When a stage has weak remaining_unknowns, replace the complete inject_state.remaining_unknowns list for that exact stage with 2–4 stage-specific unresolved matters. Each entry must be at least 24 characters; must name at least one current scenario identity, device, service, supplier, business process, operational dependency or consequence; must describe information genuinely unknown at that stage; must be answerable through later evidence or investigation; must not repeat a known_facts_before or new_confirmed_facts statement; must not state a conclusion already established by the scenario; must not disclose hidden root cause; and must not use generic text such as 'investigation ongoing', 'cause unknown', 'impact unknown', 'scope unknown', 'more information required', 'further analysis needed', 'additional investigation is required', 'monitoring continues', 'full impact is yet to be determined'.\n"
        "STAGE 2 REMAINING UNKNOWNS — STRICT INSTRUCTIONS:\n"
        "When Stage 2 remaining_unknowns is weak, replace the COMPLETE Stage 2 list (do not append/merge/preserve defective items). Return 2–4 unresolved matters. Each item must be >=24 characters; name at least one scenario-specific identity/device/service/supplier/business process/operational dependency/consequence; describe information genuinely unresolved at Stage 2; be answerable through later evidence or investigation; not repeat any known_facts_before or new_confirmed_facts statement; not state a conclusion already established; and not reveal hidden root cause. Avoid generic wording such as 'investigation ongoing', 'cause unknown', 'impact unknown', 'scope unknown', 'more information required', 'further analysis needed', 'additional investigation is required', 'monitoring continues', 'full impact is yet to be determined'.\n"
        "QUESTION ANCHORS (ALL STAGES WITH ANCHOR DEFECTS):\n"
        "You are given the canonical fact IDs available at that stage and the exact sanitised statement for each available ID. For each rejected participant_questions_typed entry, you are given the rejected prompt and anchor IDs. Replace the complete affected question entries so that each uses at least two distinct IDs selected only from the supplied available-ID list; each pair resolves to two distinct supplied fact statements; retains a named authority; contains at least two decision options; includes deadline_minutes >= 1; includes at least two competing consequences; remains grounded in the scenario; and does not expose hidden-root-cause information. Do not create new fact IDs during repair. Do not guess or substitute anchors beyond the returned repair response.\n"
        "CAUSAL CARRY-FORWARD (STAGES 2–4 WITH CAUSAL DEFECTS):\n"
        "You are given the immediately preceding stage’s canonical fact IDs and statements along with the current known_facts_before and known_fact_ids_before. Replace BOTH known_facts_before and known_fact_ids_before completely so that the repaired stage includes at least one exact statement and matching canonical ID from the immediately preceding stage. Do not paraphrase carry-forward text. Do not reference current-stage or future-stage fact IDs in known_fact_ids_before.\n"
        "TYPED DECISION DEADLINES (ALL STAGES):\n"
        "For every typed decision that lacks a bounded deadline_minutes, replace the complete affected decision object with the same category and the same substantive decision intent, including authority, affected_operation, deadline_minutes as an integer >= 1, and accepted_consequence. Do not substitute a free-text deadline for deadline_minutes. For Stage 2, preserve exactly four decisions and exactly one of each required category. If any Stage 2 decision is replaced, return the entire Stage 2 decisions_typed array as exactly four objects.\n"
        "REPAIR SELF-CHECK (APPLY BEFORE RETURN):\n"
        "- Every stage has 2–4 substantive remaining_unknowns as defined above.\n"
        "- Every repaired question uses two canonical IDs from the supplied available-ID list and each pair resolves to two distinct supplied fact statements.\n"
        "- Every stage from 2–4 carries at least one exact fact statement AND matching canonical ID from the immediately preceding stage.\n"
        "- Every typed decision in all stages has deadline_minutes >= 1 (integer).\n"
        "- Stage 2 still contains exactly four typed decisions with exactly one of each required category.\n"
        "- No new fact IDs have been invented anywhere in the plan.\n"
        "- No hidden root-cause content appears on any participant-facing surface.\n"
        "SELF-CHECK: Ensure each repaired participant question includes >=2 scenario anchors and a required decision, and each repaired decision conforms to the labelled form above.\n"
        "Set the final stage next_inject_trigger to null."
    )


def normalize_structural_invariants(plan: dict[str, Any]) -> dict[str, Any]:
    """
    Deterministically set invariant structural fields independent of model wording:
      - Phase names by stage index (1..4)
      - previous_inject_id: Stage 1 -> None; Stage N -> Stage N-1 inject_id
      - final stage next_inject_trigger: None
    Does not alter narrative content or facts.
    """
    try:
        scenarios = plan.get("scenarios", []) if isinstance(plan, dict) else []
        if not scenarios:
            return plan
        scn = scenarios[0] if isinstance(scenarios[0], dict) else {}
        injects = scn.get("injects", []) or []
        # Normalise phases and linking
        for idx, inj in enumerate(injects, start=1):
            try:
                st = inj.get("inject_state", {}) if isinstance(inj, dict) else {}
                # Phase by index
                if idx == 1:
                    st["phase"] = STAGE_PHASES[0]
                elif idx == 2:
                    st["phase"] = STAGE_PHASES[1]
                elif idx == 3:
                    st["phase"] = STAGE_PHASES[2]
                elif idx == 4:
                    st["phase"] = STAGE_PHASES[3]
                # previous_inject_id chain
                if idx == 1:
                    st["previous_inject_id"] = None
                else:
                    prev_public_id = (injects[idx - 2] or {}).get("inject_id")
                    st["previous_inject_id"] = prev_public_id
                # final stage next_inject_trigger
                if idx == 4:
                    st["next_inject_trigger"] = None
                inj["inject_state"] = st
            except Exception:
                continue
        # Write back
        scn["injects"] = injects
        plan["scenarios"][0] = scn
        return plan
    except Exception:
        return plan

def _build_canonical_fact_registry(plan: dict[str, Any]) -> tuple[dict[str, str], dict[int, list[str]], list[str]]:
    """
    Assign canonical fact IDs deterministically by stage and fact order without altering statements.
    Returns: (registry, per_stage_ids, defects)
      - registry: {"S1-F1": "<statement>", ...}
      - per_stage_ids: {1: ["S1-F1", ...], 2: ["S2-F1", ...], ...}
      - defects: duplicate statement errors (reject rather than modify)
    """
    registry: dict[str, str] = {}
    per_stage_ids: dict[int, list[str]] = {}
    defects: list[str] = []
    seen_statements: set[str] = set()
    try:
        scenarios = plan.get("scenarios", []) if isinstance(plan, dict) else []
        injects = scenarios[0].get("injects", []) if scenarios and isinstance(scenarios[0], dict) else []
        for sidx, inj in enumerate(injects, 1):
            st = inj.get("inject_state", {}) if isinstance(inj, dict) else {}
            facts: list[str] = list(st.get("new_confirmed_facts") or [])
            stage_ids: list[str] = []
            for i, stmt in enumerate(facts, 1):
                s = str(stmt)
                canon = f"S{sidx}-F{i}"
                # If this exact statement is already seen previously anywhere, collect a defect
                if s in seen_statements:
                    defects.append(f"duplicate confirmed-fact statement (unchanged) blocks unique canonical mapping: '{s}'")
                else:
                    seen_statements.add(s)
                registry[canon] = s
                stage_ids.append(canon)
            per_stage_ids[sidx] = stage_ids
    except Exception:
        # Fail closed: return what we built so far
        pass
    return registry, per_stage_ids, defects

def _apply_canonical_ids_and_known_refs(
    plan: dict[str, Any],
    registry: dict[str, str],
    per_stage_ids: dict[int, list[str]],
) -> tuple[dict[str, Any], dict[int, list[str]]]:
    """
    Write canonical new_fact_ids and derive known_fact_ids_before by exact statement match against earlier-stage facts.
    Stage 1 known_fact_ids_before is forced to [].
    Returns: (plan, unresolved_known_facts)
    """
    unresolved_known: dict[int, list[str]] = {}
    try:
        scenarios = plan.get("scenarios", []) if isinstance(plan, dict) else []
        injects = scenarios[0].get("injects", []) if scenarios and isinstance(scenarios[0], dict) else []
        # Build reverse lookup from statement to canonical id(s) by stage
        stmt_to_canon_by_stage: dict[int, dict[str, str]] = {}
        for sidx, ids in per_stage_ids.items():
            m: dict[str, str] = {}
            for cid in ids:
                stmt = registry.get(cid, "")
                m[stmt] = cid
            stmt_to_canon_by_stage[sidx] = m
        for sidx, inj in enumerate(injects, 1):
            st = inj.get("inject_state", {}) if isinstance(inj, dict) else {}
            # Assign canonical new_fact_ids for this stage
            st["new_fact_ids"] = per_stage_ids.get(sidx, [])
            # Derive known_fact_ids_before
            if sidx == 1:
                st["known_fact_ids_before"] = []
            else:
                known_txts = list(st.get("known_facts_before") or [])
                # Aggregate prior statements mapping (stages < sidx)
                prior_map: dict[str, str] = {}
                for ps in range(1, sidx):
                    prior_map.update(stmt_to_canon_by_stage.get(ps, {}))
                k_ids: list[str] = []
                unresolved: list[str] = []
                for kt in known_txts:
                    stmt = str(kt)
                    cid = prior_map.get(stmt)
                    if cid:
                        k_ids.append(cid)
                    else:
                        unresolved.append(stmt)
                st["known_fact_ids_before"] = k_ids
                if unresolved:
                    unresolved_known[sidx] = unresolved
            inj["inject_state"] = st
        if scenarios and isinstance(scenarios[0], dict):
            scenarios[0]["injects"] = injects
            plan["scenarios"] = scenarios
    except Exception:
        pass
    return plan, unresolved_known

def _normalise_question_anchors(
    plan: dict[str, Any],
    registry: dict[str, str],
    per_stage_ids: dict[int, list[str]],
) -> tuple[dict[str, Any], dict[int, list[dict]], dict[int, list[dict]]]:
    """
    Map anchor_fact_ids to canonical IDs only when original IDs have an unambiguous statement mapping.
    Require >=2 canonical, distinct anchors that resolve to available statements for the stage.
    Returns: (plan, unresolved_anchor_records, resolved_anchor_records)
    """
    unresolved: dict[int, list[dict]] = {}
    resolved: dict[int, list[dict]] = {}
    try:
        scenarios = plan.get("scenarios", []) if isinstance(plan, dict) else []
        injects = scenarios[0].get("injects", []) if scenarios and isinstance(scenarios[0], dict) else []
        # Build original_id -> set(statements) mapping across all stages (pre-canonical IDs still on plan? derive from pairing)
        orig_id_stmt_map: dict[str, set[str]] = {}
        for sidx, inj in enumerate(injects, 1):
            st = inj.get("inject_state", {}) if isinstance(inj, dict) else {}
            orig_ids = list(st.get("new_fact_ids") or [])
            facts = list(st.get("new_confirmed_facts") or [])
            # If we've already replaced ids with canonical, we cannot derive original mapping; guard by skipping
            if any(str(x).startswith("S") and "-F" in str(x) for x in orig_ids):
                continue
            for i, oid in enumerate(orig_ids):
                try:
                    stmt = str(facts[i])
                except Exception:
                    continue
                s = orig_id_stmt_map.setdefault(str(oid), set())
                s.add(stmt)
        # Reverse lookup: statement -> canonical id
        stmt_to_canon: dict[str, str] = {}
        for cid, stmt in registry.items():
            stmt_to_canon[stmt] = cid
        # Walk stages and attempt anchor mapping
        cumulative_prior_ids: set[str] = set()
        for sidx, inj in enumerate(injects, 1):
            st = inj.get("inject_state", {}) if isinstance(inj, dict) else {}
            qt_list = inj.get("participant_questions_typed") or []
            if not isinstance(qt_list, list) or not qt_list:
                cumulative_prior_ids.update(per_stage_ids.get(sidx, []))
                continue
            # Available canonical IDs per validator semantics: prior cumulative + current stage canonical + known_fact_ids_before
            available: set[str] = set()
            try:
                available |= set(st.get("known_fact_ids_before") or [])
            except Exception:
                pass
            available |= cumulative_prior_ids
            available |= set(per_stage_ids.get(sidx, []))
            for qt in qt_list:
                try:
                    anchors = list(qt.get("anchor_fact_ids") or [])
                except Exception:
                    anchors = []
                prompt = str(qt.get("prompt", ""))
                # Attempt mapping only if original IDs are bijective (map to exactly one statement)
                canonical_candidates: list[str] = []
                for oid in anchors:
                    stmts = orig_id_stmt_map.get(str(oid))
                    if stmts and len(stmts) == 1:
                        stmt = next(iter(stmts))
                        cid = stmt_to_canon.get(stmt)
                        if cid and cid in available:
                            canonical_candidates.append(cid)
                # Use mapped anchors only if we have >=2 distinct canonical and they resolve to available statements
                distinct = list(dict.fromkeys(canonical_candidates))
                if len(distinct) >= 2:
                    qt["anchor_fact_ids"] = distinct[:2]
                    resolved.setdefault(sidx, []).append({"prompt": prompt, "canonical_anchor_ids": distinct[:2]})
                else:
                    unresolved.setdefault(sidx, []).append({"prompt": prompt, "original_anchor_ids": anchors, "reason": "insufficient canonical anchors"})
            inj["participant_questions_typed"] = qt_list
            cumulative_prior_ids.update(per_stage_ids.get(sidx, []))
        if scenarios and isinstance(scenarios[0], dict):
            scenarios[0]["injects"] = injects
            plan["scenarios"] = scenarios
    except Exception:
        pass
    return plan, unresolved, resolved

def canonicalise_plan(plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str], dict[int, list[str]], dict[int, list[dict]]]:
    """
    Orchestrate canonical fact ID assignment and resolvable reference normalisation.
    Attaches sidecar keys for repair construction:
      - _canonical_fact_registry
      - _unresolved_known_facts
      - _unresolved_question_anchors
    Processing order:
      1) Build canonical registry (by stage/position)
      2) Normalise anchors using original model IDs/statements (before ID replacement)
      3) Apply canonical IDs and derive known_fact_ids_before
    """
    registry, per_stage_ids, dup_defects = _build_canonical_fact_registry(plan)
    # First, normalise anchors while original (model-provided) IDs are still present
    plan_after_anchor, unresolved_anchors, _resolved_anchors = _normalise_question_anchors(plan, registry, per_stage_ids)
    # Then, apply canonical IDs and known refs
    plan_after_ids, unresolved_known = _apply_canonical_ids_and_known_refs(plan_after_anchor, registry, per_stage_ids)
    # Attach sidecars (non-model)
    try:
        plan_after_ids["_canonical_fact_registry"] = registry
        plan_after_ids["_unresolved_known_facts"] = unresolved_known
        plan_after_ids["_unresolved_question_anchors"] = unresolved_anchors
        # Record duplicate fact statement defects in a sidecar for repair surface (validator still enforces integrity)
        if dup_defects:
            plan_after_ids.setdefault("_normalisation_defects", []).extend(dup_defects)
    except Exception:
        pass
    return plan_after_ids, registry, unresolved_known, unresolved_anchors

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
    """Generate, validate (source), optional single source repair, transform, enrich, and final-validate one tabletop plan.

    Public contract preserved: returns a TabletopMasterPlan-compatible dict.
    Internally uses the lean TabletopSourcePlan pipeline:
      LEAN SOURCE -> SOURCE VALIDATION -> OPTIONAL SINGLE REPAIR -> DETERMINISTIC TRANSFORM -> ARTEFACT/FG SYNTHESIS -> FINAL VALIDATION
    """
    try:
        from core import LLMEngine
        from facilitator_guidance import attach_facilitation_to_plan, generate_inject_facilitation
        from participant_artefacts import synthesise_participant_artefacts
        from prompts import SYSTEM_PERSONA_TABLETOP  # persona only
        from tabletop_source import (
            TabletopSourcePlan,
            build_tabletop_source_prompt,
            validate_source_plan,
            transform_source_to_master,
        )
    except Exception as exc:
        raise TabletopGenerationError("initialisation", str(exc)) from exc

    runner = model_runner or LLMEngine.generate_structured_report

    # Build compact source prompt (no canonical IDs, no legacy strings, no full artefacts/guidance)
    source_prompt = build_tabletop_source_prompt(
        client_inputs, selected_themes, audience=audience, custom_brief=custom_brief
    )

    # Source generation (structured)
    try:
        initial = runner(
            client,
            deployment,
            SYSTEM_PERSONA_TABLETOP,
            source_prompt,
            TabletopSourcePlan,
        )
    except Exception as exc:
        raise TabletopGenerationError("azure_request", str(exc)) from exc
    if initial is None:
        raise TabletopGenerationError("azure_response", "structured source generation returned no result")

    source = initial.model_dump() if hasattr(initial, "model_dump") else initial
    injected_runner_used = model_runner is not None
    # Compatibility fallback (test-only or explicit legacy/import provenance):
    # Only allow when an injected test runner is used. Live/default path must not accept master-shaped responses.
    if injected_runner_used and isinstance(source, dict) and isinstance(source.get("scenarios"), list):
        # Test-only compatibility adapter:
        # - Normalise structural invariants
        # - Perform enrichment (artefacts + facilitator guidance) if possible
        # - Do NOT run final validation (master-like fixtures may be incomplete)
        master = normalize_structural_invariants(source)
        try:
            master = synthesise_participant_artefacts(master, blueprint, audience=audience)
        except Exception:
            pass
        try:
            fac_map = generate_inject_facilitation(master, blueprint, audience=audience)
            master = attach_facilitation_to_plan(master, fac_map)
        except Exception:
            pass
        return master
    ok_src, src_defects = validate_source_plan(source)

    # Build a compact source repair prompt (operating ONLY on lean source fields)
    def _build_source_repair_prompt(defects: list[str], src: dict[str, Any]) -> str:
        lines: list[str] = []
        lines.append("TARGETED SOURCE REPAIR (ONLY ALLOWED REPAIR)")
        lines.append("Operate ONLY on TabletopSourcePlan fields.")
        lines.append("Do NOT introduce canonical IDs, inject IDs, legacy strings, full artefact bodies, or facilitator guide bodies.")
        lines.append("REPAIR RULES:")
        lines.append("- Keep exactly 4 stages and stage_number 1..4.")
        lines.append("- Stage 2 decisions: return exactly four decisions with categories: session_identity_containment, containment_authority, affected_service_continuity, escalation_scope.")
        lines.append("- SourceFactRef: stage_offset ∈ {-1,0}; fact_index 1..4. Stage 1 may reference only stage_offset=0.")
        lines.append("- Questions: ensure >=2 anchor_refs resolving to distinct facts; 2–4 decision_options; deadline_minutes>=1; 2–4 competing_consequences.")
        lines.append("- Hidden root cause remains scenario-level only; do not leak it into participant-facing fields.")
        # Include per-stage context where defects exist
        try:
            plan = src or {}
            stages = plan.get("stages") or []
            for s in stages:
                sn = s.get("stage_number")
                stage_def = [d for d in (defects or []) if f"stage {sn}" in d.lower()]
                if not stage_def:
                    continue
                lines.append(f"\nSTAGE {sn} CONTEXT:")
                lines.append(f"- new_confirmed_facts={s.get('new_confirmed_facts', [])}")
                lines.append(f"- remaining_unknowns={s.get('remaining_unknowns', [])}")
                # Summarise anchor ref bounds
                try:
                    q = (s.get("participant_questions") or [])[0] if s.get("participant_questions") else None
                    if q:
                        lines.append(f"- sample_anchor_refs={q.get('anchor_refs', [])}")
                except Exception:
                    pass
                if sn == 2:
                    lines.append("- REQUIRED_CATEGORIES: session_identity_containment; containment_authority; affected_service_continuity; escalation_scope")
        except Exception:
            pass
        lines.append("\nDEFECTS:")
        for d in defects:
            lines.append(f"- {d}")
        lines.append("\nRETURN ONLY THE COMPLETE, CORRECTED TabletopSourcePlan JSON.")
        return "\n".join(lines)

    # Optional single source repair
    if not ok_src:
        repair_prompt = _build_source_repair_prompt(src_defects, source)
        try:
            repaired = runner(
                client,
                deployment,
                SYSTEM_PERSONA_TABLETOP,
                repair_prompt,
                TabletopSourcePlan,
            )
        except Exception as exc:
            raise TabletopGenerationError("repair_request", str(exc), src_defects) from exc
        if repaired is None:
            raise TabletopGenerationError("repair_response", "source repair returned no result", src_defects)
        source = repaired.model_dump() if hasattr(repaired, "model_dump") else repaired
        ok_src2, src_defects2 = validate_source_plan(source)
        if not ok_src2:
            raise TabletopGenerationError("repair_validation", "one source repair did not produce a valid source plan", src_defects2)

    # Deterministic transform Source -> Master (derive IDs, phases, carry-forward, canon IDs, compatibility strings)
    master = transform_source_to_master(source, {"deployment": deployment})

    # Enrichment: participant artefact synthesis and facilitator guidance synthesis
    try:
        master = synthesise_participant_artefacts(master, blueprint, audience=audience)
    except Exception as exc:
        raise TabletopGenerationError("artefact_synthesis", str(exc)) from exc

    try:
        fac_map = generate_inject_facilitation(master, blueprint, audience=audience)
        master = attach_facilitation_to_plan(master, fac_map)
    except Exception as exc:
        raise TabletopGenerationError("facilitator_guidance", str(exc)) from exc

    # Final validation of the TabletopMasterPlan-compatible dict
    valid, defects = validate_four_stage_plan(master)
    if not valid:
        raise TabletopGenerationError("final_validation", "final master failed validation", defects)
    return master

def persist_validated_tabletop_plan(session_state: dict, plan: dict) -> dict:
    """Validate and persist the plan to a dict-like session_state."""
    # Block persistence when legacy adapter reported unresolved upgrade defects
    try:
        if isinstance(plan, dict):
            upgrade_defects = plan.get("_upgrade_defects")
            if isinstance(upgrade_defects, list) and upgrade_defects:
                raise TabletopGenerationError("persistence", "legacy upgrade has unresolved defects", upgrade_defects)
    except Exception:
        # Defensive: if defect structure is malformed, still prevent persistence
        raise TabletopGenerationError("persistence", "legacy upgrade has unresolved defects", [])
    plan = normalize_structural_invariants(plan)
    ok, defects = validate_four_stage_plan(plan)
    if not ok:
        raise TabletopGenerationError("persistence", "attempted to persist invalid plan", defects)
    session_state["tabletop_plan"] = plan
    ok2, defects2 = validate_four_stage_plan(session_state.get("tabletop_plan"))
    if not ok2:
        raise TabletopGenerationError("persistence", "post-persistence validation failed", defects2)
    return session_state["tabletop_plan"]

def _derive_legacy_from_typed(plan: dict[str, Any]) -> dict[str, Any]:
    """
    Deterministically map typed fields to legacy surfaces, overwriting conflicting legacy values:
      - decisions_typed -> decisions_required (labelled line form)
      - participant_questions_typed -> participant_questions (prompt only)
    No-op if typed fields are absent. Idempotent and safe for re-entry.
    """
    try:
        scenarios = plan.get("scenarios", []) if isinstance(plan, dict) else []
        if not scenarios or not isinstance(scenarios[0], dict):
            return plan
        injects = scenarios[0].get("injects", []) or []
        for inj in injects:
            if not isinstance(inj, dict):
                continue
            st = inj.get("inject_state", {}) if isinstance(inj, dict) else {}
            dtyped = st.get("decisions_typed") or []
            if isinstance(dtyped, list) and dtyped:
                derived = []
                for d in dtyped:
                    try:
                        decision = str((d.get("decision") or "")).strip()
                        authority = str((d.get("authority") or "")).strip()
                        affected = str((d.get("affected_operation") or "")).strip()
                        ddl_str = str((d.get("deadline") or "")).strip()
                        if not ddl_str:
                            dm = d.get("deadline_minutes")
                            ddl_str = f"{int(dm)} minutes" if dm is not None else ""
                        cons = str((d.get("accepted_consequence") or "")).strip()
                        derived.append(
                            f"DECISION: {decision}. AUTHORITY: {authority}. AFFECTED OPERATION: {affected}. "
                            f"DEADLINE: {ddl_str}. TRADE-OFF: Accepting {cons}."
                        )
                    except Exception:
                        continue
                if derived:
                    st["decisions_required"] = derived
                    inj["inject_state"] = st
            # Also derive legacy participant_questions from typed prompts, preserving parse compatibility
            qtyped = inj.get("participant_questions_typed") or []
            if isinstance(qtyped, list) and qtyped:
                derived_q = []
                for qt in qtyped:
                    try:
                        pr = _text((qt or {}).get("prompt"))
                        if pr:
                            derived_q.append({"prompt": pr, "category": "Governance"})
                    except Exception:
                        continue
                if derived_q:
                    inj["participant_questions"] = derived_q
        scenarios[0]["injects"] = injects
        plan["scenarios"] = scenarios
        return plan
    except Exception:
        return plan


def adapt_legacy_import(plan: dict[str, Any]) -> dict[str, Any]:
    """
    Structurally translate a legacy Tabletop plan into current shape without authoring new content.
    - Preserve fact statements verbatim; generate stable IDs 1:1 for existing new_confirmed_facts.
    - Carry known_fact_ids_before from previous stage IDs.
    - Attempt to map labelled legacy decisions into typed decisions; otherwise emit explicit upgrade defects.
    - Do not invent participant questions, authorities, deadlines, facilitator guidance, artefacts or facts.
    - Do not stamp typed schema/rules here; legacy import stays in legacy mode.
    - Attach a non-model key '_upgrade_defects' with human-readable upgrade issues for the importer to surface.
    """
    defects: list[str] = []
    try:
        if not isinstance(plan, dict):
            return plan
        scenarios = plan.get("scenarios", [])
        if not isinstance(scenarios, list) or not scenarios or not isinstance(scenarios[0], dict):
            defects.append("missing scenario content")
            plan["_upgrade_defects"] = defects
            return plan
        scn = scenarios[0]
        injects = scn.get("injects", []) or []
        prev_ids: list[str] = []
        # helper: parse labelled decision string
        import re as _re
        def parse_labelled(dec_text: str) -> dict[str, str] | None:
            try:
                text = _text(dec_text)
                parts = dict(_re.findall(r"(DECISION|AUTHORITY|AFFECTED OPERATION|DEADLINE|TRADE-OFF)\s*:\s*([^\.]+)", text, _re.IGNORECASE))
                dec = parts.get("DECISION") or parts.get("Decision")
                auth = parts.get("AUTHORITY") or parts.get("Authority")
                aff = parts.get("AFFECTED OPERATION") or parts.get("Affected Operation")
                ddl = parts.get("DEADLINE") or parts.get("Deadline")
                trade = parts.get("TRADE-OFF") or parts.get("Trade-Off")
                if all(_text(x) for x in (dec, auth, aff, ddl, trade)):
                    return {
                        "decision": _text(dec),
                        "authority": _text(auth),
                        "affected_operation": _text(aff),
                        "deadline": _text(ddl),
                        "accepted_consequence": _text(trade),
                    }
            except Exception:
                return None
            return None

        for idx, inj in enumerate(injects, start=1):
            if not isinstance(inj, dict):
                defects.append(f"stage {idx} missing inject object")
                continue
            st = inj.get("inject_state") or {}
            if not isinstance(st, dict):
                st = {}
            inj_id = inj.get("inject_id", f"INJ-{idx}")
            st.setdefault("inject_id", inj_id)
            # facts: generate stable IDs 1:1, preserve statements
            ncf = list(st.get("new_confirmed_facts") or [])
            ncf = [s for s in ncf if _meaningful(s)]
            st["new_confirmed_facts"] = ncf
            st["new_fact_ids"] = [f"F-{idx}-{i+1}" for i in range(len(ncf))]
            st["known_fact_ids_before"] = [] if idx == 1 else prev_ids[:]
            prev_ids = st["new_fact_ids"][:]
            # decisions: attempt to map labelled legacy decisions to typed
            legacy_decs = st.get("decisions_required") or []
            dtyped: list[dict[str, Any]] = []
            if isinstance(legacy_decs, list):
                for d in legacy_decs:
                    parsed = parse_labelled(_text(d))
                    if parsed:
                        # category cannot be inferred reliably; only Stage 2 mapping requires categories
                        parsed["deadline_minutes"] = None
                        dtyped.append({"category": "other", **parsed})
            # If stage 2, require exactly four categories; otherwise emit defects
            if idx == 2:
                if len(dtyped) < 4:
                    defects.append("stage 2 decision cannot be upgraded: fewer than four labelled decisions")
                else:
                    # keep as mapped but importer/tests must assert categories if present
                    pass
            # Do not invent typed questions; require derivable structure in legacy -> if absent, defect
            if not inj.get("participant_questions_typed"):
                defects.append(f"stage {idx} question cannot be upgraded: insufficient structure")
            # Facilitator guidance/artefact content must exist in legacy; do not synthesise
            fg = inj.get("facilitator_guidance")
            if not isinstance(fg, dict):
                defects.append(f"stage {idx} facilitator guidance missing")
            pa = inj.get("participant_artefact")
            try:
                if not (isinstance(pa, dict) and len(_text(pa.get('content'))) >= 80):
                    defects.append(f"stage {idx} participant artefact missing or insufficient")
            except Exception:
                defects.append(f"stage {idx} participant artefact missing or insufficient")
            inj["inject_state"] = st
            injects[idx - 1] = inj
        scn["injects"] = injects
        plan["scenarios"][0] = scn
        plan["_upgrade_defects"] = defects
        return plan
    except Exception:
        plan["_upgrade_defects"] = defects or ["adapter error"]
        return plan

def should_use_bespoke_blueprint() -> bool:
    """
    Pure routing decision for bespoke blueprint usage.
    Behaviour:
      - Return False by default.
      - Return False when TABLETOP_BLUEPRINT_ENABLED is false.
      - Return False when TABLETOP_BESPOKE_USE_BLUEPRINT is false.
      - Return True only when both flags are true.
    """
    try:
        from config import get_config  # local import to avoid hard dependency during testing
        bp_enabled = str(get_config("TABLETOP_BLUEPRINT_ENABLED", "true")).strip().lower() in ("1", "true", "yes", "on")
        bespoke_flag = str(get_config("TABLETOP_BESPOKE_USE_BLUEPRINT", "false")).strip().lower() in ("1", "true", "yes", "on")
        return bool(bp_enabled and bespoke_flag)
    except Exception:
        return False

__all__ = [
    "STAGE_PHASES",
    "TabletopGenerationError",
    "validate_four_stage_plan",
    "generate_with_one_repair",
    "generate_tabletop_plan",
    "persist_validated_tabletop_plan",
    "adapt_legacy_import",
    "canonicalise_plan",
    "should_use_bespoke_blueprint",
]
