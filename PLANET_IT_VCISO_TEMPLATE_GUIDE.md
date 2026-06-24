PLANET IT VCISO TEMPLATE GUIDE

Overview
- This guide documents the integration of governance-specific fields into planet_it_vciso_template.docx and how to populate them from the VCISO data model.

Governance placeholders and mapping
- partnership_details: Narrative describing the governing arrangement of the engagement (Fully Managed vs Co-Managed) and key responsibilities.
- partnership_links: A list of URLs to governance resources, standards, or policy documents. Rendered in the template as a comma-separated string or bullet points depending on the template design.
- microsoft_healthchecks_summary: Summary of healthchecks related to Microsoft security controls in use.
- threat_intelligence_context: Contextual threat intelligence snippet to accompany governance narrative.
- validation_status: A short indicator of validation status for governance controls (e.g., 'Validated', 'Awaiting Evidence').
- cost_of_inaction_summary: Condensed section describing the cost of inaction, derived from MonetaryCostGBP if present.
- compliance_gap_details: Detailed gaps against compliance standards with remediation guidance.
- remediation_summary: Summary of remediation actions and owners.

-Template wiring guidance
- Governance placeholders mapping
- The VCISO Word template planet_it_vciso_template.docx now includes governance placeholders to support the partnership governance narrative. Add the following placeholders as merge fields or Jinja2 tags if not already present:
- {{ partnership_details }}
- {{ partnership_links }}
- {{ microsoft_healthchecks_summary }}
- {{ threat_intelligence_context }}
- {{ validation_status }}
- {{ cost_of_inaction_summary }}
- {{ compliance_gap_details }}
- {{ remediation_summary }}
- If rendering fails due to missing fields, guard the template context with default values in export.py.
- For multi-valued fields like partnership_links, render as a bullet list in Word if supported, else join with semicolons.
27 | - Ensure planet_it_vciso_template.docx contains the above placeholders as merge fields or Jinja2 tags (e.g., {{ partnership_details }}, {{ partnership_links }}).
28 | - If rendering fails due to missing fields, guard the template context with default values in export.py.
29 | - For multi-valued fields like partnership_links, render as a bullet list in the Word template if supported, else join with semicolons.
30 | - GBP cost narrative integration: If MonetaryCostGBP is provided, populate cost_of_inaction_summary with a clearly formatted GBP amount (e.g., The estimated cost of inactivity is £1,234,567.89 over the forecast period.). Always format GBP with a leading £ and two decimals.
31 | - Threat intelligence integration: threat_intelligence_context should render as a narrative snippet in governance outputs rather than remaining empty.
32 | - Governance narrative rendering: partnership_links should render as bullets in Word-enabled renderers; otherwise, a safe semicolon-delimited string should be produced.

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
