# Execution Plan: Enhancements to Security Use Case & vCISO Generator

Date: 24 June 2026
Mode: PLAN

Scope
- Implement monetary value for the cost of inaction (GBP) based on real-world intelligence, but avoid over-estimation.
- Validate and stabilise radar chart data generation to ensure correct representation and scaling constraints.
- Expand compliance and framework alignment by detailing critical gaps and actionable remediation.
- Adjust email security recommendations to exclude Sophos; propose Mimecast or Barracuda with rationale.
- Clarify partner engagement: specify fully-managed or co-managed support in partnership narrative; add a dedicated section for these offerings.
- Introduce dedicated co-managed or fully-managed solution content in the recommended partnership section.
- Add Microsoft healthchecks as a sensible review point, including Microsoft hardening considerations where Microsoft tools are used.
- Remove Cloud Optix from the recommended solutions.

Assumptions
- The plan will operate within the existing file architecture:
  - app.py, core.py, prompts.py, data.py, export.py, catalog.py
- No new top-level directories are introduced unless necessary to house plan artefacts; current_execution_plan.md will be the sole plan artefact in repository root.
- All changes will be implemented iteratively in ACT MODE after plan approval.

Proposed Modifications by File

1) prompts.py
- Add a real-world GBP cost model to the Maturity/Assessment schema.
  - Introduce new models:
    - MonetaryCostGBP
      - amount_gbp: float (ge=0)
      - source: Optional[str]
      - rationale: Optional[str]
    - GapRemediationPlan
      - gap_description: str
      - recommended_actions: List[str]
      - owner: Optional[str]
      - due_by: Optional[str] (ISO date)
  - Extend existing MaturityReport (or equivalent) to include:
    - monetary_cost_of_inaction: Optional[MonetaryCostGBP]
    - compliance_alignment: Optional[List[ComplianceSection]]
      - ComplianceSection:
        - standard: str
        - critical_gaps: List[str]
        - fill_plan: List[GapRemediationPlan]
  - Guidance in Field descriptions:
    - “Monetary cost must be grounded in industry baselines (UK/GB) with conservative estimates to avoid overestimation. Use credible ranges and provide rationale where possible.”

- Compliance/Gaps expansion scaffolding:
  - Add explicit fields to capture critical gaps and remediation plans per standard (e.g., ISO 27001, NIST CSF).
  - Ensure prompts builder produces a structured “how to fill” narrative per gap.

2) data.py
- Introduce cost estimator:
  - Function: estimate_cost_of_inaction_gbp(risk_level: int, workforce_size: int = 50, industry_multiplier: float = 1.0) -> MonetaryCostGBP
    - risk_level: 1 (low), 2 (medium), 3 (high)
    - Base costs by risk:
      - 1 -> 1,000 GBP
      - 2 -> 5,000 GBP
      - 3 -> 15,000 GBP
    - Apply a conservative cap and adjust with industry_multiplier to prevent over-estimation.
    - Produce a single, defensible GBP figure with a plain-language rationale in the function docstring.
  - Expose a small helper: derive_risk_adjustment(risk_level) -> float
  - Return: MonetaryCostGBP(amount_gbp=<computed_value>, source="Industry baselines (UK), adjusted for workforce and context", rationale="Conservative middle-ground estimate; avoids over-estimation; uses real-world intelligence baselines")

- Wire into core flow:
  - Where MaturityReport.monetary_cost_of_inaction is generated, call estimate_cost_of_inaction_gbp with the appropriate risk_level and workforce_size inferred from the context.

3) export.py
- Radar chart wiring:
  - Enforce maximum radius = 3 (Three-Pillar Cyber Resiliency Matrix)
  - Ensure axes do not auto-scale beyond 0..3
  - If data exceeds, cap values to 3
  - Add a small commentary annotation for the max radius boundary
  - Update function to accept a parameter max_radius=3 and use it as hard cap for plt.ylim or equivalent

- Validation points:
  - Confirm no automatic re-scaling to 5 or 10; enforce hard cap

4) app.py
- UI enhancements:
  - Display monetary_cost_of_inaction_gbp (GBP) in the Maturity/Assessment section, with a short rationale
  - Expand Compliance gaps: render “Critical gaps” and “Remediation plan” blocks per standard
  - Email strategy: replace Sophos with Mimecast or Barracuda
    - Show justification side-by-side for Mimecast vs Barracuda
  - Partnership section: clearly call out fully-managed or co-managed engagement
  - Add a new “Microsoft healthchecks” toggle/section where Microsoft hardening considerations appear when Microsoft tools are used
  - Remove any references to Cloud Optix from the recommended solutions

5) catalog.py
- Recommendations data model adjustments:
  - Remove Cloud Optix from the recommended solutions set
  - Replace with Mimecast or Barracuda options
  - Include justification text blocks:
    - Mimecast: enhanced email security, phishing protection, attachment policies, integration with Microsoft 365
    - Barracuda: scalable email security, data loss prevention, cloud-native controls
  - Ensure the rationale is embedded in the data structure so UI can present a concise justification

- Partnership narrative adjustments:
  - Add a dedicated section “Co-managed or Fully Managed Solutions” with:
    - A template outline: service boundaries, SLAs, escalation paths, and typical cost models
    - Clear distinction between fully-managed and co-managed offerings
    - Notes about Planet’s role in provisioning, monitoring, and support

6) Microsoft healthchecks (Cross-cutting)
- Where Microsoft workloads are used, add a healthcheck checklist:
  - Security posture, patching cadence, MFA enforcement status, conditional access policies
  - 30/60/90-day review cadence
  - Tie back to the discovered gaps and remediation plans

7) Validation & Documentation
- Create or update a dedicated section in current_execution_plan.md for:
  - How to validate radar data (data integrity, radius cap)
  - How to validate GBP cost calculations (trace inputs, edge cases)
  - How to verify email solution recommendations (Sophos removal, Mimecast/Barracuda justification)
  - How to validate co-managed/fully-managed partnership content

Implementation & Verification Plan
- Implement changes file-by-file in ACT MODE, in this order:
  1) Update prompts.py models (MonetaryCostGBP, GapRemediationPlan, ComplianceSection) and MaturityReport extension
  2) Implement data.py: cost estimation function and wiring
  3) Update export.py radar chart to enforce max radius 3
  4) Update catalog.py: remove Cloud Optix, add Mimecast/Barracuda with rationale; add co-managed/fully-managed section scaffolding
  5) Update app.py: UI to reflect new sections (GBP, compliance gaps, healthchecks, partnership section)
  6) Integrate Microsoft healthchecks as optional section
  7) Update any templates or docs to reflect the new content
  8) Run a lightweight test pass to ensure the data flows through prompts -> models -> UI
  9) Remove plan artefact when all steps are verified and deliverable is ready

Notes on Real-World Intelligence for GBP Cost
- The GBP cost should be a defensible, non-exaggerated estimate derived from credible baselines (e.g., industry reports on average ransomware costs, business interruption costs, and incident response costs). To implement in code:
  - Base the cost on risk level (low/med/high) with conservative midpoints
  - Scale by workforce size and industry context if available
  - Document sources in the MonetaryCostGBP.source field
  - If live intelligence feeds exist, provide a configuration switch to pull from that feed; otherwise default to the internal baseline table described above
- The plan prohibits arbitrary inflation of numbers; all numbers must be accompanied by rationale and, where possible, credible references.

Next Steps
- Approve this execution plan to proceed to ACT MODE, after which I will implement changes in a controlled, verifiable manner and report back with live test results and updated artefacts.

Risk & Dependencies
- Dependency on existing prompts structure and data models; changes must be backward compatible where feasible
- Radar cap must align with downstream visual expectations and existing UI layout
- Ensure there is no regression in formatting or JSON schema parsing when new fields are added

Deliverables on completion
- Updated prompts.py and data.py with new GBP cost mechanics
- Updated export.py with radar cap enforcement
- Updated app.py and catalog.py to reflect new guidance and pricing logic
- Updated current_execution_plan.md removed at the end of execution (per cleanup policy)

Planned timeline
- 2–4 iterations of incremental edits and verification, then finalisation