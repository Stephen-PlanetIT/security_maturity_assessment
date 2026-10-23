GenerationContract v1.1

Title: Formal GenerationContract for RC-S1-like Tabletop Outputs (Version 1.1)

Overview
This document defines a formal, machine-checkable contract governing future generation of tabletop exercises to ensure parity with RC-S1-like quality, structural rigor, and facilitator/participant experience. It deliberately avoids duplicating RC-S1 content and instead codifies the behavioral and structural rules that generation must follow to produce consistent, high-fidelity tabletops. This version (v1.1) introduces explicit inject-state governance, a mandatory root-cause reveal model, and progression/artefact rules designed to enforce RC-S1-like behavior without reproducing RC-S1 content.

1) InjectStateSchema (mandatory model)
Purpose
Capture per-inject state for deterministic, testable generation across scenarios, including cross-inject progression cues.

Mandatory fields
- inject_id: string (unique per inject)
- slide_reference: string (non-empty)  // anchor to the corresponding inject in the deck
- scenario_id: string (e.g., "Scenario 1", "Scenario 2")
- known_facts_before: array[string] (min_items: 1)
- new_confirmed_facts: array[string] (min_items: 1)
- remaining_unknowns: array[string] (min_items: 1)
- business_impact_introduction_point: string (non-empty)
- stakeholder_pressure_introduction_point: string (non-empty)
- decisions_required: array[string] (min_items: 1)
- next_inject_trigger: string (non-empty)  // CAUSAL progression trigger to the next inject
- previous_inject_id: string (non-empty)    // must reference the preceding inject in the same scenario
- artefact_reference: string (optional but recommended)
- artefact_type: string (optional but recommended)
- root_cause_reveal: RootCauseRevealModel (mandatory)  // see Section 4 for model shape
- artefact_author: string (optional)
- artefact_knowledge_level: string (optional; e.g., "novice","practitioner","expert")
- artefact_audience: string (optional)

Optional/Recommended
- author_notes: string (optional)
- injection_context_tag: string (optional; e.g., "BYOD","Executive Risk","Impersonation")

Root-Cause Reveal Model (mandatory per InjectState)
- root_cause_reveal: RootCauseRevealModel
  - hidden_context: string (mandatory)      // internal RCA framing not shown to participants
  - facilitator_visible_context: string (mandatory) // RCA context shown to facilitators
  - wrap_up_reveal_point: string (mandatory) // gating point or condition when RCA is revealed to participants

Validation tests
- Test 1: All six core state arrays contain at least one element.
- Test 2: inject_id and slide_reference are non-empty; inject_id is unique within the generation cycle.
- Test 3: known_facts_before and new_confirmed_facts reflect a verifiable inject context (no invalid contradictions).
- Test 4: next_inject_trigger and previous_inject_id enforce a causal progression chain.
- Test 5: root_cause_reveal is present and its three fields are non-empty.
- Test 6: artefact_reference and artefact_type are populated when artefact_reference is provided.
- Test 7: artefact_author/artefact_knowledge_level/artefact_audience are optional but valid if present.

Failure conditions
- Missing required field, empty mandatory arrays, duplicate inject_id, or missing/empty next_inject_trigger or previous_inject_id.
- root_cause_reveal fields empty or missing.
- slide_reference invalid or empty.

Compliance
- Every inject must include a complete InjectState block with the six mandatory fields populated, plus the root-cause reveal and progression fields.

2) Participant-view rules
Mandatory
- Participant-facing injects must present a sanitized view that excludes internal InjectState metadata.
- Visible fields to participants (per-inject) must include:
  - known_facts_before
  - new_confirmed_facts
  - remaining_unknowns
  - business_impact_introduction_point
  - stakeholder_pressure_introduction_point
  - decisions_required
Validation tests
- Test: Each participant-facing inject block contains exactly the six fields above and no internal fields (inject_id, slide_reference, artefact_reference, artefact_type, next_inject_trigger, previous_inject_id, root_cause_reveal, artefact_author, artefact_knowledge_level, artefact_audience) are exposed.
Failure: Any participant-facing inject reveals internal fields or omits required participant fields.

3) Facilitator-view rules
Mandatory
- Each inject includes a facilitator cue sheet with:
  - at least one escalation cue
  - at least one risk/friction signal
  - at least one recommended action or decision trigger
- Facilitator cues MUST align with the inject_state context (including root-cause visibility as configured by the RootCauseRevealModel).

Validation tests
- Test: Facilitator cues exist for every inject and map to the inject’s content and gating conditions.
- Failure: Missing/top-level cues or misalignment with inject content.

4) Root-cause model
Mandatory
- Root-cause reveal is mandatory per InjectState as defined in Section 1.
- The reveal has a gating point (wrap_up_reveal_point) that determines when the RCA becomes visible to participants, ensuring RC-S1-like pacing without copying RC-S1 content verbatim.

Validation tests
- Test: Each inject includes a non-empty hidden_context, facilitator_visible_context, and wrap_up_reveal_point; gating works as intended.

Compliance
- Do not copy RC-S1 verbatim; root-cause reveal must mirror structure and pacing, not content.

5) Progression validation rules
Mandatory
- A causal progression chain must exist per scenario:
  - The next_inject_trigger for each inject must reference a valid injected condition that logically follows from the previous inject.
  - A per-scenario progression map must exist, detailing dependencies (1a → 1b → 2a → 2b → 3a → 3b).
Validation tests
- Test: Each inject has a non-empty next_inject_trigger and a valid previous_inject_id; progression map exists and is consistent.
- Failure: Missing or inconsistent progression data.

6) Artefact generation rules
Mandatory
- Artefacts must be categorized into approved artefact classes and include:
  - author
  - audience
  - knowledge_level
  - type: one of a defined set (artefact_class), with explicit taxonomy
- Artefacts must be labeled with metadata: source, date, author, purpose
- Consistency: Artefacts must be represented consistently across injects that reference the same artefact type.

Validation tests
- Test: Each artefact includes metadata fields and adheres to the approved artefact_class taxonomy.
- Failure: Missing author/audience/knowledge_level or misclassification.

7) Question quality rules
Mandatory
- All questions accompanying an inject must be:
  - clear, unambiguous
  - tightly coupled to the inject’s context
  - designed to drive a concrete decision
Validation tests
- Test: Each inject contains at least one decision-driven question; no vague or leading questions.

Cross-cutting validation (applies to all rules)
- Mandatory
  - Each inject must introduce at least one new_fact or new_confirmed_fact.
  - Each inject must require at least one decision.
  - Each inject must contain remaining_unknowns (non-empty).

Compliance tests
- Test 1: Any inject failing mandatory new_fact requirement is non-compliant.
- Test 2: Any inject with no decisions_required is non-compliant.
- Test 3: Any inject with empty remaining_unknowns is non-compliant.

8) Compliance, versioning, governance
- Generation contracts are versioned (e.g., GenerationContract v1.1).
- All changes require a formal review and changelog entry.
- The contract applies to all future generation cycles unless explicitly updated.
- No PPTX changes; no export changes; no visual changes are allowed by this contract.

9) Appendix and templates
- Appendix updated to reflect v1.1 features: InjectState Template with new fields and RootCauseModel guidance; Artefact taxonomy and author/audience/knowledge-level metadata templates.

10) Machine-readable artifact (optional)
- GenerationContract.json export containing the same rules in a structured schema to enable automated validation.

Enforcement, testing and CI
- Static validation: enforce presence and structure of InjectState across all generated injects, including the new fields.
- Dynamic validation: simulate aGenerationPass with mock payloads to ensure all tests pass and the contract’s rules hold.
- CI integration: enforce generation-compliance gates; non-compliant generations fail CI checks.

Versioning and governance
- GenerationContract v1.1 is the baseline. Any changes to rules require a new version (e.g., v1.2) with a changelog entry.

Operational considerations
- This contract governs generation behavior for future tabletops, ensuring they behave like RC-S1 in structure, rigor, and pacing while avoiding RC-S1 content leakage.
- All rules apply to future generation cycles; historical RC-S1 content remains a reference for structural intent rather than content replication.

What I need from you
- Confirm acceptance of GenerationContract.md as the baseline governing future generation cycles (v1.1).
- If you prefer a JSON-only version or a bilingual YAML+Markdown approach, specify now and I will provide accordingly.

End-state
- A formal, machine-checkable GenerationContract that enforces InjectState discipline, participant and facilitator interfaces, RCA reveal policy, progression, artefact realism, and question quality for consistent RC-S1-like tabletops in future planning and execution cycles.