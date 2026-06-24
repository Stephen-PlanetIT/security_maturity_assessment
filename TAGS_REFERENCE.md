# TAGS_REFERENCE

| Tag/Field name | Data Type | Source Module | Schema Path | Description | Default/Constraints | Template Mapping | Example Value | Notes |
|---|---|---|---|---|---|---|---|---|
| MonetaryCostGBP | MonetaryCostGBP (object with amount_gbp, source, rationale) | prompts.py / data.py | MaturityReport.monetary_cost_of_inaction | Annual cost of inaction to be used in governance narratives | Cap at GBP 1,000,000; 2 decimals | monetary_cost_of_inaction | 12000.00 | GBP cost of inaction baseline; cross-walk from risk model |
| GapRemediationPlan | RemediationPlan (string or list) | prompts.py | MaturityReport.gap_remediation_plan | Plan to remediate gaps identified in assessment | Optional text; if present, render as bullet list | gap_remediation_plan | Implement MFA hardening + automated patching by Q4 | Used in governance narrative sections |
| ComplianceSection | ComplianceSection (string) | prompts.py | MaturityReport.compliance_section | Summary of compliance posture and gaps | Optional | compliance_section | ISO 27001 aligned; gaps identified | References ISO/NIST controls |
| DomainAssessment | DomainAssessment[] | prompts.py / data.py | MaturityReport.domain_assessments | Per-domain maturity and gaps | Must be complete per domain; min 1 | domain_assessments | Endpoint & IAM maturity across domains | See DomainAssessment schema |
| RoadmapPhase | RoadmapPhase[] | prompts.py / data.py | MaturityReport.phased_roadmap | Phased implementation milestones | Min 1 per phase | phased_roadmap | Phase 1: Reactive → Phase 3: Adaptive | Link to business value delivered |
| MaturityReportPlaceholder | Placeholder field | prompts.py | MaturityReport (misc.) | Placeholder to be extended with governance data | Optional | maturity_placeholder | N/A | Placeholder for future governance fields |
| RadarChartData.iam | int | prompts.py / data.py | MaturityReport.radar_chart_data.iam | Score 1-3 mapped to IAM controls; governance gating requires 1 if missing automatic patching or MFA | 1-3 | radar_chart_data.iam | 2 | Governance gating example |
| RadarChartData.endpoint | int | prompts.py / data.py | MaturityReport.radar_chart_data.endpoint | Endpoint security maturity score | 1-3 | radar_chart_data.endpoint | 2 | Governance gating example |
| RadarChartData.network | int | prompts.py / data.py | MaturityReport.radar_chart_data.network | Network/perimeter score; gating rules apply | 1-3 | radar_chart_data.network | 2 | Governance gating example |
| RadarChartData.email | int | prompts.py / data.py | MaturityReport.radar_chart_data.email | Email security maturity score | 1-3 | radar_chart_data.email | 2 | Governance gating example |
| RadarChartData.cloud | int | prompts.py / data.py | MaturityReport.radar_chart_data.cloud | Cloud security maturity score | 1-3 | radar_chart_data.cloud | 2 | Governance gating example |
| RadarChartData.secops | int | prompts.py / data.py | MaturityReport.radar_chart_data.secops | SecOps maturity score | 1-3 | radar_chart_data.secops | 2 | Governance gating example |
| RadarChartData.testing | int | prompts.py / data.py | MaturityReport.radar_chart_data.testing | Security testing maturity score | 1-3 | radar_chart_data.testing | 2 | Governance gating example |
| RadarChartData.culture | int | prompts.py / data.py | MaturityReport.radar_chart_data.culture | Culture and training maturity | 1-3 | radar_chart_data.culture | 2 | Governance gating example |
| RadarChartData.grc | int | prompts.py / data.py | MaturityReport.radar_chart_data.grc | Governance, Risk & Compliance maturity | 1-3 | radar_chart_data.grc | 2 | Governance gating example |
| partnership_details | string | prompts.py | MaturityReport.partnership_details | Governance narrative for partnership engagement | Optional | partnership_details | Joint governance narrative | Governance narrative block |
| | partnership_links | List[str] | prompts.py | MaturityReport.partnership_links | Governance resource URLs | Optional | partnership_links | https://planet-it.example.com/governance | Governance links |
| RadarChartData.iam | int | prompts.py / data.py | MaturityReport.radar_chart_data.iam | Score 1-3. STRICT RULE: Must be exactly 1 if MFA Enforcement is 'None' or 'Privileged Accounts Only'. | 1-3 | radar_chart_data.iam | 2 | Governance gating example |
| RadarChartData.endpoint | int | prompts.py / data.py | MaturityReport.radar_chart_data.endpoint | Endpoint security maturity score | 1-3 | radar_chart_data.endpoint | 2 | Governance gating example |
| RadarChartData.network | int | prompts.py / data.py | MaturityReport.radar_chart_data.network | Network/perimeter score; gating rules apply | 1-3 | radar_chart_data.network | 2 | Governance gating example |
| RadarChartData.email | int | prompts.py / data.py | MaturityReport.radar_chart_data.email | Email security maturity score | 1-3 | radar_chart_data.email | 2 | Governance gating example |
| RadarChartData.cloud | int | prompts.py / data.py | MaturityReport.radar_chart_data.cloud | Cloud security maturity score | 1-3 | radar_chart_data.cloud | 2 | Governance gating example |
| RadarChartData.secops | int | prompts.py / data.py | MaturityReport.radar_chart_data.secops | SecOps maturity score | 1-3 | radar_chart_data.secops | 2 | Governance gating example |
| RadarChartData.testing | int | prompts.py / data.py | MaturityReport.radar_chart_data.testing | Security testing maturity score | 1-3 | radar_chart_data.testing | 2 | Governance gating example |
| RadarChartData.culture | int | prompts.py / data.py | MaturityReport.radar_chart_data.culture | Culture and training maturity | 1-3 | radar_chart_data.culture | 2 | Governance gating example |
| RadarChartData.grc | int | prompts.py / data.py | MaturityReport.radar_chart_data.grc | Governance, Risk & Compliance maturity | 1-3 | radar_chart_data.grc | 2 | Governance gating example |
| partnership_details | string | prompts.py | MaturityReport.partnership_details | Governance narrative for partnership engagement | Optional | partnership_details | Joint governance narrative | Governance narrative block |
| partnership_links | List[str] | prompts.py | MaturityReport.partnership_links | Governance resource URLs | Optional | partnership_links | https://planet-it.example.com/governance | Governance links |

## Change Log
- Initial skeleton with representative entries and governance notes.

## Governance notes
- This catalogue supports Fully Managed vs Co-Managed governance with URLs defined in data.py as FULLY_MANAGED_URL and CO_MANAGED_URL.

## Additional RadarChart and governance fields (sample expansion)
- RadarChartData.iam | int | prompts.py / data.py | MaturityReport.radar_chart_data.iam | Score 1-3 mapping to IAM controls; must reflect governance rules | 1-3 | radar_chart_data.iam | 2 | Sector governance gating
- RadarChartData.endpoint | int | prompts.py / data.py | MaturityReport.radar_chart_data.endpoint | Endpoint security maturity score; gating rules apply | 1-3 | radar_chart_data.endpoint | 2 | Endpoint hygiene gating
- RadarChartData.network | int | prompts.py / data.py | MaturityReport.radar_chart_data.network | Network/perimeter score; gating rules apply | 1-3 | radar_chart_data.network | 2 | Network controls gating
- RadarChartData.email | int | prompts.py / data.py | MaturityReport.radar_chart_data.email | Email security maturity score | 1-3 | radar_chart_data.email | 2 | Email protection gating
- RadarChartData.cloud | int | prompts.py / data.py | MaturityReport.radar_chart_data.cloud | Cloud security maturity score | 1-3 | radar_chart_data.cloud | 2 | Cloud apps governance gating
- RadarChartData.secops | int | prompts.py / data.py | MaturityReport.radar_chart_data.secops | SecOps maturity score | 1-3 | radar_chart_data.secops | 2 | Security operations gating
- RadarChartData.testing | int | prompts.py / data.py | MaturityReport.radar_chart_data.testing | Security testing maturity score | 1-3 | radar_chart_data.testing | 2 | Testing maturity gating
- RadarChartData.culture | int | prompts.py / data.py | MaturityReport.radar_chart_data.culture | Culture and training maturity | 1-3 | radar_chart_data.culture | 2 | Culture & training gating
- RadarChartData.grc | int | prompts.py / data.py | MaturityReport.radar_chart_data.grc | Governance, Risk & Compliance maturity | 1-3 | radar_chart_data.grc | 2 | GRC gating
- partnership_details | string | prompts.py | MaturityReport.partnership_details | Governance narrative for partnership engagement | Optional | partnership_details | Joint governance narrative | Governance narrative block
- partnership_links | List[str] | prompts.py | MaturityReport.partnership_links | Governance resource URLs | Optional | partnership_links | https://planet-it.example.com/governance | Governance links

## Change Log
- Initial skeleton with representative entries and governance notes.

## Governance notes
- This catalogue supports Fully Managed vs Co-Managed governance with URLs defined in data.py as FULLY_MANAGED_URL and CO_MANAGED_URL.

## Additional RadarChart and governance fields (sample expansion)
- RadarChartData.iam | int | prompts.py / data.py | MaturityReport.radar_chart_data.iam | Score 1-3 mapping to IAM controls; must reflect governance rules | 1-3 | radar_chart_data.iam | 2 | Sector governance gating
- RadarChartData.endpoint | int | prompts.py / data.py | MaturityReport.radar_chart_data.endpoint | Endpoint security maturity score; gating rules apply | 1-3 | radar_chart_data.endpoint | 2 | Endpoint hygiene gating
- RadarChartData.network | int | prompts.py / data.py | MaturityReport.radar_chart_data.network | Network/perimeter score; gating rules apply | 1-3 | radar_chart_data.network | 2 | Network controls gating
- RadarChartData.email | int | prompts.py / data.py | MaturityReport.radar_chart_data.email | Email security maturity score | 1-3 | radar_chart_data.email | 2 | Email protection gating
- RadarChartData.cloud | int | prompts.py / data.py | MaturityReport.radar_chart_data.cloud | Cloud security maturity score | 1-3 | radar_chart_data.cloud | 2 | Cloud apps governance gating
- RadarChartData.secops | int | prompts.py / data.py | MaturityReport.radar_chart_data.secops | SecOps maturity score | 1-3 | radar_chart_data.secops | 2 | Security operations gating
- RadarChartData.testing | int | prompts.py / data.py | MaturityReport.radar_chart_data.testing | Security testing maturity score | 1-3 | radar_chart_data.testing | 2 | Testing maturity gating
- RadarChartData.culture | int | prompts.py / data.py | MaturityReport.radar_chart_data.culture | Culture and training maturity | 1-3 | radar_chart_data.culture | 2 | Culture & training gating
- RadarChartData.grc | int | prompts.py / data.py | MaturityReport.radar_chart_data.grc | Governance, Risk & Compliance maturity | 1-3 | radar_chart_data.grc | 2 | GRC gating
- partnership_details | string | prompts.py | MaturityReport.partnership_details | Governance narrative for partnership engagement | Optional | partnership_details | Joint governance narrative | Governance narrative block
- partnership_links | List[str] | prompts.py | MaturityReport.partnership_links | Governance resource URLs | Optional | partnership_links | https://planet-it.example.com/governance | Governance links
