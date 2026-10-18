# Phase B Baseline Certification

## 1. Executive Summary & Closure Notice
Phase B is officially closed. No further B2.x checkpoints will be created. The Phase B baseline establishes deterministic, evidence-grounded report reconstruction and legacy export compatibility bypass without regressions to tabletop or maturity boundaries.

---

## 2. Accepted Contracts & Architectural Invariants
1. **Specialist Output Preservation**: Existing specialist outputs survive `MaturityReport` reconstruction without field truncation or silent drop.
2. **Legacy Export Recomputation Bypass**: Improved report contexts bypass legacy recomputation in `export.py` and project directly into DOCX templates.
3. **Authoritative Domain Score Eligibility**: `DomainScoreEligibilityDecision` is authoritative. Count-based heuristics (`pos + gaps > 0`) are removed. A domain requires domain-specific contributing evidence, configured required dimensions, minimum evidenced dimensions (>=2), minimum distinct parent sources (>=2), permitted scoring roles, and an adequate assurance state.
4. **Honest Score Withholding**: Evidence-insufficient domains remain unscored (`indicative_score: None`). Overall scores remain null (`overall_score: None`, status: `WITHHELD_INSUFFICIENT_EVIDENCE`) when coverage policy is unmet; arbitrary scores (e.g., 60/100) are not protected or invented.
5. **Diagnostic Sentinel Isolation**: Sentinels (such as `TRACE_EXEC_` and `TRACE_SCENARIO_`) are detected, logged, and isolated from customer-facing exports.
6. **Partnership Authority**: Partnership baseline prose is classified as `PROPOSED_OPERATING_MODEL`. Raw prose cannot claim that Planet IT currently delivers 24/7 Managed SOC / MDR, vCISO advisory, or SLAs without confirmed evidence IDs.
7. **Tabletop Boundary Integrity**: Tabletop generation, models, and information barriers remain strictly segregated from the maturity report change boundary.

---

## 3. Frozen Modules & Interfaces
The following components are frozen and must not be modified unless a future regression test demonstrates a concrete defect:
- `services/report_improvement/authority_map.py` (Precedence, sanitisation, registry mapping)
- Canonical score transport and `DomainScoreInput` structures
- Model-reconciliation mappings in `authority_map.reconcile_maturity_report_dict`
- Legacy compatibility bypass logic in `export.py`
- `DomainScoreEligibilityDecision` and `DomainAllocationRegistry`
- Score-withholding semantics in `services/report_improvement/section_generators/security_rating.py`
- Diagnostic sentinel isolation guards
- Tabletop models (`tabletop_models.py`) and prompt boundaries

---

## 4. Key Files Changed Across Phase B
- `services/report_improvement/authority_map.py`: Single source of truth precedence map, sentinel stripping, partnership prose sanitisation.
- `services/report_improvement/section_generators/security_rating.py`: Deterministic score calculation deferring strictly to `DomainScoreEligibilityDecision`.
- `services/report_improvement/orchestrator.py`: Domain package integration, score input wiring, and specialist pipeline execution.
- `export.py`: Direct template projection bypassing legacy export recomputations.
- `tests/test_checkpoint_b2_contract.py`: B2 baseline contract tests.
- `tests/test_checkpoint_b2_2_contract.py`: B2.2 lifecycle & disposition consistency tests.
- `tests/test_checkpoint_b2_3_contract.py`: B2.3 eligibility, score-withholding, and partnership sanitisation tests.
- `tests/test_tabletop_models.py`: Tabletop validation and information barrier tests.

---

## 5. Regression Test Suites
All Phase B contracts and tabletop boundaries pass with zero failures:
- `tests/test_checkpoint_b2_3_contract.py`: PASSED (7 tests)
- `tests/test_checkpoint_b2_2_contract.py`: PASSED (4 tests)
- `tests/test_phase2_1_semantic_eligibility.py`: PASSED (4 tests)
- `tests/test_tabletop_models.py`: PASSED (3 tests)
- `tests/test_decision_questions.py`: PASSED (1 test)
- `tests/test_tabletop_custom.py`: PASSED (2 tests)

Execution command:
`./.venv/bin/python -m pytest tests/test_checkpoint_b2_3_contract.py tests/test_checkpoint_b2_2_contract.py tests/test_phase2_1_semantic_eligibility.py tests/test_tabletop_models.py tests/test_decision_questions.py tests/test_tabletop_custom.py -v`

---

## 6. Known Limitations
- When fewer than 2 distinct parent sources or 2 evidenced dimensions are available, overall score is withheld (`None`), requiring complete consultation evidence to produce a published score.
- Test fixture data for branded customer profiles is derived from sample profiles and test runners rather than direct live CRM/consultation ingestion.

---

## 7. Rollback Commit
- **Rollback Base Git Commit**: `23b1717acb911bb1e3ae0f3c67066f2e08534271`

---

## 8. Matters Explicitly Deferred to Phase C
The following work items are deferred to Phase C and must not reopen Phase B:
1. Production input acquisition
2. Real-customer source lineage
3. Specialist evidence selection
4. Compliance differentiation
5. Cost-of-inaction differentiation
6. Consultant-quality domain narratives
7. Executive synthesis
8. Roadmap quality
9. Editorial and DOCX quality
