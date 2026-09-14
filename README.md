# 🪐 Planet IT Strategic Advisory Platform

## Overview
The **Planet IT Strategic Advisory Platform** is an AI‑powered, enterprise‑grade consulting engine that generates highly customised, compliance‑aligned security assessments and tactical threat simulations.

Designed for security consultants, the platform leverages Azure OpenAI to analyse a client’s environment and instantly produce boardroom‑ready strategic deliverables aligned to the **Planet IT Cyber Resiliency Matrix**: Cybersecurity Maturity Assessments in Microsoft Word (`.docx`), Tactical Threat Simulation Reports in PDF, and optional presentation decks in PowerPoint (`.pptx`).

---

## 🚀 Core Capabilities

### 1. vCISO Strategic Assessment Engine
- Planet IT Resiliency Matrix Mapping: Evaluates the client’s estate across 15 security domains (with conditional domains rendered only when applicable) and strictly maps them to:
  1. Pillar 1: Reactive Cybersecurity (Foundational Hygiene)
  2. Pillar 2: Proactive Cybersecurity (Active Managed Defence)
  3. Pillar 3: Adaptive Cybersecurity (Adaptive Governance & Resilience)
- The Capability Mismatch Rule: Penalises maturity scores to Pillar 1 if advanced enterprise tools (e.g., MDR) are present but foundational hygiene (Automated Patching, Enforced MFA, Immutable Backups) is absent.
- C‑Level Contextual Intelligence: Generates multi‑paragraph Executive Summaries and flowing “Cost of Inaction” analyses that reference client‑specific threat landscapes, crown jewels, insurance status, and downtime tolerances (RTO).
- Compliance & GRC Mapping: Aligns security gaps to target frameworks (e.g., ISO 27001, Cyber Essentials Plus, PCI DSS, NIST CSF) and dynamically calculates an overall Security Culture Tier.

### 2. Tactical Threat Simulator
- Single‑Pass Scenario Generation: Utilises optimised prompt framing to simultaneously generate a realistic strategic breach narrative and a detailed SOC Incident Case Log (with PIDs, cmdlines, and MITRE references).

### 3. Enterprise Export Pipeline
- Dynamic Radar Charts: Publication‑quality polar charts via `matplotlib`, hard‑capped at a maximum radius of 3 (representing the Three‑Pillar Cyber Resiliency Matrix).
- Structured Word Doc Rendering: `docxtpl` injects AI‑generated assessments and recommendations into templates:
  - `planet_it_maturity_assessment_template.docx` (auto‑fallback to `planet_it_maturity_assessment_template_v2.docx` where required)
  - `planet_it_threat_scenario_template.docx`
  - `planet_it_tabletop_report_template.docx`
- Threat Simulator PDF Export: `fpdf` renders publication‑ready Tactical Threat Simulation Reports.
- Presentation Deck Export: `python‑pptx` renders slides aligned to `planet_it_master_template.pptx`.

---

### Deliverables and assets

Primary deliverables:
- DOCX: Cybersecurity Maturity Assessment (`planet_it_maturity_assessment_template*.docx`)
- DOCX: Tactical Threat Scenario (`planet_it_threat_scenario_template.docx`)
- DOCX: Tabletop Exercise Report (`planet_it_tabletop_report_template.docx`)
- PDF: Tactical Threat Simulation Report
- PPTX: Presentation Deck (`planet_it_master_template.pptx`)
- PNG: Radar visuals (also embedded in documents)

Asset templates present in the repository:
- `planet_it_maturity_assessment_template.docx`
- `planet_it_maturity_assessment_template_v2.docx`
- `planet_it_threat_scenario_template.docx`
- `planet_it_tabletop_report_template.docx`
- `planet_it_master_template.pptx`

### Consultation evidence model

The consultation model captures shared evidence groups to minimise duplication across domains:
- Business Services, Critical Assets & Sensitive Data (CAP)
- Business Service Resilience (service‑specific RTO/RPO, dependency mapping, recovery priorities)
- Information Protection & Data Governance (classification, external sharing, DLP, retention)
- Identity Governance & Privileged Access (lifecycle, de‑provisioning, access reviews, PIM/PAM, break‑glass, service/shared accounts, legacy auth)
- SaaS, Application & Shadow IT Governance (inventory, critical platforms, SSO/MFA coverage, offboarding, recovery responsibility, shadow IT, OAuth app governance)
- Asset, Configuration & Exposure Assurance (asset inventory, external attack surface, vulnerability remediation, secure configuration, change assurance, unsupported technology)
- Monitoring, Telemetry & Response Coverage (coverage, log sources, retention, escalation, response authority, detection testing, reporting cadence)
- Supplier Risk & Third‑Party Access (supplier assurance maturity and third‑party access model, MFA, review cadence, contractual requirements, notification, exit, concentration risk)
- Recovery Assurance (restore testing, immutability, administrative separation, service recovery testing, evidence, ownership)
- Incident Response Assurance (roles, business/technical authority, tabletop status, OOB comms, crisis comms, regulatory readiness, supplier coordination, lessons learned)

Assurance Status:
- Confirmed, Reported (unverified), Requires supplier confirmation, Unknown (rendered as “Not established during consultation”), Not applicable (neutral; not scored as weak).

Unknown vs None:
- Unknown means “not established during consultation”; None means “control absent”. Recommendations and scoring treat Unknown with reduced confidence, not as confirmed absence.

Conditional modules appear only when relevant:
- OT & IoT Security; Business Process & Payment Fraud; Application & API Security; Acquisition & Integration Assurance.

Profile migration & compatibility:
- Legacy profiles are migrated to include a minimal CAP using critical_infra; new structured sections are optional and backwards compatible. Import/export round‑trips preserve nested dictionaries and lists.

### Domain coverage

The Planet IT Cyber Resiliency Matrix covers the following 15 standard domains:
- Identity & Access Management
- Privileged Access & Identity Governance
- Endpoint & Device Security
- Network & Remote Access Security
- Email & Collaboration Security
- Cloud & Infrastructure Security
- SaaS & Application Governance
- Data Security & Information Protection
- Security Operations & Response
- Security Validation & Testing
- Supplier & Third‑Party Security
- Operational Resilience & Backup
- Security Culture & Awareness
- Governance, Risk & Compliance
- AI Governance & Security

Conditional domains (rendered only when applicable):
- OT & IoT Security
- Business Process & Payment Fraud
- Application & API Security
- Acquisition & Integration Assurance

### Recommendation behaviour (capability‑led, evidence‑led)
- Unknown evidence → recommend validation/assessment; do not auto‑procure.
- Existing control with weak assurance → configuration review, coverage validation, testing, governance.
- Confirmed absence → proportionate remediation.
- Mature control → acknowledge; recommend maintenance or no further action.
- Vendor suggestions respect the ban list and portfolio; Planet IT positioning remains consultative.

### Evidence in prompts & exports
- Prompts include structured evidence summaries and assurance rules; conditional domains only when applicable.
- Exports render Unknown as “Not established during consultation” and exclude or clearly indicate Not applicable fields. Tables remain left‑aligned and long text wraps correctly.

---

## 🧭 Multi‑Page Streamlit Workflow

The application is a multi‑page Streamlit app. Navigation is unified under `app.py` as the single router, with dedicated pages under `pages/` only where page‑specific UI is substantial:

- `app.py`: Authoritative router and UI host for the vCISO Maturity Assessment and Tactical Threat Simulator workflows.
- `pages/01_Maturity_Relay.py`: Redirect stub (preserves bookmarks) → sets workflow to Maturity and redirects to `app.py`.
- `pages/02_Threats_Relay.py`: Redirect stub (preserves bookmarks) → sets workflow to Threats and redirects to `app.py`.
- `pages/03_Tabletop_Designer.py`: Dedicated Tabletop Designer and artefact generator.
- `pages/04_Live_Facilitation.py`: Live facilitation support for exercise execution.
- `pages/05_After_Action_Review.py`: Captures outcomes and generates AAR reports.
- `ui_shared_sections.py`: Shared UI components and sections used across pages.

These modules leverage shared engines (`core.py`, `prompts.py`) and knowledge (`data.py`, `catalog.py`) while writing outputs via `export.py`.

---

## 🛠️ Architecture & File Structure

Core modules:
- `app.py`: Streamlit multi‑page router, input sanitisation, workflow state routing.
- `core.py`: Azure OpenAI client; exponential backoff; `max_completion_tokens`; 300s timeout; structured JSON completions.
- `prompts.py`: Strict Pydantic schema models (`MaturityReport`, `DomainAssessment`, `RoadmapPhase`, `RadarChartData`) and consulting personas.
- `consultation_schema.py` and `consultation_helpers.py`: Consultation evidence model, assurance statuses, normalisers/builders.
- `scenario_selection.py`: Scenario tagging and selection logic.
- `risk.py`: Risk scoring and helper utilities.
- `catalog.py`: Planet IT solution portfolio and vendor alignment.
- `data.py`: Static knowledge base: attack vectors, simulated OSINT, maturity framework, domains, solution map.
- `export.py`: Document rendering for DOCX (`docxtpl`), PDF (`fpdf`), PPTX (`python‑pptx`), and radar charts (radius hard‑capped at 3).

Quality and tools:
- `tests/`: Unit and smoke tests (export, prompts build, MDR decision assist, migration, sanitisation, scenarios, derived maturity, tabletop custom).
- `quality_pipeline.py`: Quality gates orchestration.
- `tools/`: Template utilities, tag catalogue generation, verification scripts.

Infrastructure:
- `Dockerfile`: Multi‑stage container build.
- `docker-compose.yml`: Local orchestration (watchtower optional).
- `.streamlit/secrets.toml`: Development secrets; production uses environment variables.
- `config.py`: All settings via `os.getenv` with validation; no hardcoded values.

---

## ⚙️ Setup & Execution

### 1. Configure Streamlit Secrets (development)
Create `.streamlit/secrets.toml` with Azure OpenAI settings:

```toml
AZURE_OPENAI_API_KEY = "your_azure_api_key_here"
AZURE_OPENAI_ENDPOINT = "https://your-endpoint.openai.azure.com/"
AZURE_OPENAI_DEPLOYMENT = "gpt-4o"
AZURE_OPENAI_API_VERSION = "2024-02-15-preview"
```

### 2. Local Python Environment
```bash
pip install -r requirements.txt
streamlit run app.py
```

### 3. Docker Container Deployment
Files are copied at build time; rebuild after code changes:
```bash
docker-compose up --build
```

---

## 🔐 Azure LLM Engine (Cloud‑only)
- Azure OpenAI only, with `max_completion_tokens` and resilient timeouts (300s).
- Structured (Pydantic‑validated) and free‑text modes supported; retries and optional streaming included.

---

## ✅ Security & Visualisation Constraints (non‑negotiable)
- Capability Mismatch: Advanced tools (MDR) without foundational hygiene (Automated Patching, Enforced MFA, Immutable Backups) → maturity penalised to Pillar 1.
- Radar Charts: Radius hard‑capped at 3; no auto‑scaling or 5/10‑point conversions.
- Configuration: All settings via `config.py` and environment variables; no hardcoded secrets, keys, or URIs.
