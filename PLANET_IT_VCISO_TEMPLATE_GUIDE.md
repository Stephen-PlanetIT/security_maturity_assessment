PLANET IT VCISO TEMPLATE GUIDE

Overview
- This guide documents the integration of governance-specific fields into planet_it_vciso_template.docx and how to populate them from the VCISO data model.

Threat Scenario Generator integration (new)
- The Threat Scenario Generator (TSG) can be embedded as a value-add in the VCISO workflow. It outputs a ThreatScenarioEnvelope payload that maps into the Word-based VCISO templates via a defined rendering pipeline.
- The VCISO template now supports integration with a Threat Scenario Outline, including an executive summary, timeline, impact narrative, and mitigations.

Governance placeholders and mapping
- partnership_details: Narrative describing the governing arrangement of the engagement (Fully Managed vs Co-Managed) and key responsibilities.
- partnership_links: A list of URLs to governance resources, standards, or policy documents. Rendered in the template as a comma-separated string or bullet points depending on the template design.
- microsoft_healthchecks_summary: Summary of healthchecks related to Microsoft security controls in use.
- threat_intelligence_context: Contextual threat intelligence snippet to accompany governance narrative.
- validation_status: A short indicator of validation status for governance controls (e.g., 'Validated', 'Awaiting Evidence').
- cost_of_inaction_summary: Condensed section describing the cost of inaction, derived from MonetaryCostGBP if present.
- compliance_gap_details: Detailed gaps against compliance standards with remediation guidance.
- remediation_summary: Summary of remediation actions and owners.
- Threat Scenario placeholders (new):
- - ThreatScenarioOutline
- - ThreatScenarioExecutiveSummary
- - ThreatScenarioTimeline
- - ThreatScenarioImpact
- - ThreatScenarioMitigations

-Template wiring guidance
- Governance placeholders mapping
- The VCISO Word template planet_it_vciso_template.docx now includes governance placeholders and Threat Scenario placeholders to support the Threat Scenario Generator integration. Add the following placeholders as merge fields or Jinja2 tags if not already present:
- - {{ partnership_details }}
- - {{ partnership_links }}
- - {{ microsoft_healthchecks_summary }}
- - {{ threat_intelligence_context }}
- - {{ validation_status }}
- - {{ cost_of_inaction_summary }}
- - {{ compliance_gap_details }}
- - {{ remediation_summary }}
- - {{ ThreatScenarioOutline }}  [container placeholder for the outline payload]
- - {{ ThreatScenarioExecutiveSummary }}
- - {{ ThreatScenarioTimeline }}
- - {{ ThreatScenarioImpact }}
- - {{ ThreatScenarioMitigations }}
- If rendering fails due to missing fields, guard the template context with default values in export.py.
- For multi-valued fields like partnership_links, render as a bullet list in Word if supported, else join with semicolons.
- GBP cost narrative integration: If MonetaryCostGBP is provided, populate cost_of_inaction_summary with a clearly formatted GBP amount (e.g., The estimated cost of inactivity is £1,234,567.89 over the forecast period.). Always format GBP with a leading £ and two decimals.
- Threat intelligence integration: threat_intelligence_context should render as a narrative snippet in governance outputs rather than remaining empty.
- Governance narrative rendering: partnership_links should render as bullets in Word-enabled renderers; otherwise, a safe semicolon-delimited string should be produced.

Data model wiring recommendations
- Extend prompts.py MaturityReport to include partnership_details (Optional[str]) and partnership_links (Optional[List[str]]) as already planned.
- In data.py, maintain FULLY_MANAGED_URL and CO_MANAGED_URL constants and expose a format_governance_narrative helper to combine narrative with URLs for templates.
- In export.py, map the new fields to the template context keys (partnership_details, partnership_links, microsoft_healthchecks_recommendations, etc.).

Validation & QA checks (high level)
- Ensure the VCISO template renders partnership_details and partnership_links in both DOCX and PDF outputs.
- Validate that the GBP cost of inaction (MonetaryCostGBP) is represented in the VCISO narrative where applicable.
- Verify the governance model string (Fully Managed vs Co-Managed) is surfaced in the VCISO preview and the final document.
- Confirm that placeholder presence aligns with the current version of planet_it_vciso_template.docx.

Quick-start example (reviewers)
- partnership_details: "Fully Managed arrangement with Planet IT responsible for ongoing governance, patching, monitoring, and reporting. Client retains business policy ownership."
- partnership_links: ["https://planet-it.example.com/governance", "https://planet-it.example.com/partner-terms"]
- microsoft_healthchecks_summary: "Microsoft 365 Defender + Defender for Cloud integration with policy-driven hardening."
- threat_intelligence_context: "Contextual threat intelligence snippet relevant to the client’s sector and Crown Jewels."

Payload integration guide (example)
- Example Threat Scenario payload shape (mapped to placeholders):
```json
{
  "customer_id": "CUST-001",
  "maturity_level": "Pillar 2: Proactive Cybersecurity",
  "outline": {
    "title": "Threat Scenario for Customer",
    "executive_summary": "Executive summary describing the scenario at a high level, tailored to Pillar 2.",
    "timeline": [
      "Initial access (phishing) - placeholder",
      "Lateral movement - placeholder",
      "Impact phase - placeholder"
    ],
    "threat_events": [
      {
        "event_id": "evt-1",
        "name": "Initial Access",
        "description": "Placeholder: initial access vector considered for the threat scenario.",
        "severity": 2
      }
    ],
    "impact": "Pillar 2 alignment with potential business impact."
  }
}
```

Validation & consistency
- Ensure all new fields use strict typing as defined in prompts.py (no open dictionaries).
- Ensure the Pillar-based constraints are adhered to, and no narrative introduces guarded assumptions beyond the stated maturity and industry context.
- Validate rendering with a representative sample payload to confirm placeholders populate deterministically.

Template documentation updates
- PLANET IT VCISO TEMPLATE GUIDE now documents Threat Scenario generation integration, placeholder mappings, payload shape, and rendering guidance.

Acceptance criteria
- The VCISO workflow can produce a ThreatScenarioEnvelope payload from a sample client_inputs and maturity level.
- Placeholders in PLANET_IT_VCISO_TEMPLATE_GUIDE.md describe exactly how to map the payload into the Word template.
- The rendering layer produces a coherent Threat Scenario block in the final document, with sections for executive summary, timeline, impact, and mitigations.
- All new data models retain min_length constraints and avoid open dictionaries.

Impact on existing work
- This integration adds Threat Scenario support without removing existing governance placeholders. It complements the current Threat Scenario skeleton.

Next steps
- Complete the automated integration test using the real document template and the placeholder insertion tool, wiring the envelope into the docx flow.
- Update PLANET_IT_VCISO_TEMPLATE_GUIDE.md with concrete examples from the validation run (payload shape, placeholder mappings, and expected render formats).

TASK PROGRESSION:
- [x] Add Threat Scenario Generator integration documentation in the template guide
- [x] Document payload shape and placeholder mappings
- [ ] Wire the threat scenario integration into the docx rendering pipeline
- [ ] Validate with sample payloads and render
- [ ] Final QA and sign-off