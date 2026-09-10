# 🪐 Planet IT Strategic Advisory Platform

## Overview
The **Planet IT Strategic Advisory Platform** is an AI-powered, enterprise-grade consulting engine built to generate highly customised, compliance-aligned security assessments and tactical threat simulations.

Designed for security consultants, the platform leverages advanced Large Language Models (LLMs) to analyse a client's environment. It instantly generates boardroom-ready strategic deliverables aligned to the **Planet IT Cyber Resiliency Matrix**: Cybersecurity Maturity Assessments in Microsoft Word (`.docx`) and Tactical Threat Simulation Reports in PDF.

---

## 🚀 Core Capabilities

### 1. vCISO Strategic Assessment Engine
* **Planet IT Resiliency Matrix Mapping:** Evaluates the client's estate across 9 security domains (including Security Validation & Testing) and strictly maps them to:
  1. **Pillar 1: Reactive Cybersecurity** (Foundational Hygiene)
  2. **Pillar 2: Proactive Cybersecurity** (Active Managed Defence)
  3. **Pillar 3: Adaptive Cybersecurity** (Adaptive Governance & Resilience)
* **The Capability Mismatch Rule:** Mathematically penalises maturity scores to Pillar 1 if advanced enterprise tools (e.g., MDR) are present but foundational hygiene (e.g., Automated Patching, Enforced MFA, Immutable Backups) is absent.
* **C-Level Contextual Intelligence:** Generates comprehensive, multi-paragraph Executive Summaries and deep, flowing "Cost of Inaction" analyses directly referencing client-specific threat landscapes, Crown Jewels, insurance status, and downtime tolerances (RTO).
* **Compliance & GRC Mapping:** Aligns security gaps directly to target frameworks (e.g., ISO 27001, Cyber Essentials Plus, PCI DSS, NIST CSF) and dynamically calculates an overall Security Culture Tier.

### 2. Tactical Threat Simulator
- **Single-Pass Scenario Generation:** Utilises highly optimised prompt framing to simultaneously generate a realistic strategic breach narrative and a detailed SOC Incident Case Log (with PIDs, cmdlines, and MITRE references).

### 3. Enterprise Export Pipeline
- **Dynamic Radar Charts:** Renders publication-quality polar area charts using `matplotlib`, hard-capped to a maximum radius of 3 (representing the Three-Pillar Cyber Resiliency Matrix).
- **Structured Word Doc Rendering:** Uses `docxtpl` to inject AI-generated assessments and recommendations into pre-formatted templates:
  - `planet_it_maturity_assessment_template.docx` (auto-fallback to `planet_it_maturity_assessment_template_v2.docx` where required)
  - `planet_it_threat_scenario_template.docx`
- **Threat Simulator PDF Export:** Uses `fpdf` to render a publication-ready Tactical Threat Simulation Report.

---

### Deliverables and assets
The core deliverables produced by the platform are:
- Word document: Cybersecurity Maturity Assessment (`planet_it_maturity_assessment_template.docx`)
- Word document: Tactical Threat Scenario (`planet_it_threat_scenario_template.docx`)
- PDF: Tactical Threat Simulation Report
- Radar visuals: Matplotlib charts embedded in reports

Asset templates present in the repository:
- `planet_it_maturity_assessment_template.docx`
- `planet_it_maturity_assessment_template_v2.docx`
- `planet_it_threat_scenario_template.docx`
- `planet_it_master_template.pptx` (currently unused)

### Consultation evidence model (new)
The consultation model now captures shared evidence groups to minimise duplication across domains:
- Business Services, Critical Assets & Sensitive Data (CAP)
- Business Service Resilience (service-specific RTO/RPO, dependency mapping, recovery priorities)
- Information Protection & Data Governance (classification, external sharing, DLP, retention)
- Identity Governance & Privileged Access (lifecycle, deprovisioning, access reviews, PIM/PAM, break‑glass, service/shared accounts, legacy auth)
- SaaS, Application & Shadow IT Governance (inventory, critical platforms, SSO/MFA coverage, offboarding, recovery responsibility, shadow IT, OAuth app governance)
- Asset, Configuration & Exposure Assurance (asset inventory, external attack surface, vulnerability remediation, secure configuration, change assurance, unsupported technology)
- Monitoring, Telemetry & Response Coverage (coverage, log sources, retention, escalation, response authority, detection testing, reporting cadence)
- Supplier Risk & Third‑Party Access (supplier assurance maturity and third‑party access model, MFA, review cadence, contractual requirements, notification, exit, concentration risk)
- Recovery Assurance (restore testing, immutability, administrative separation, service recovery testing, evidence, ownership)
- Incident Response Assurance (roles, business/technical authority, tabletop status, OOB comms, crisis comms, regulatory readiness, supplier coordination, lessons learned)

Assurance Status:
- Default and per‑section assurance statuses drive consultative wording: Confirmed, Reported (unverified), Requires supplier confirmation, Unknown (rendered as “Not established during consultation”), and Not applicable (neutral; not scored as weak).

Unknown vs None:
- Unknown means “not established during consultation”; None means “control absent”. Recommendations and scoring treat Unknown with reduced confidence, not as confirmed absence.

Conditional modules appear only when relevant:
- OT & IoT Security; Business Process & Payment Fraud; Application & API Security; Acquisition & Integration Assurance.

Profile migration & compatibility:
- Legacy profiles are migrated to include a minimal CAP using critical_infra; new structured sections are optional and backwards compatible. Import/export round‑trips preserve nested dictionaries and lists.

### Domain coverage (updated)
The Planet IT Cyber Resiliency Matrix now covers the following 15 standard domains:
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
- Supplier & Third-Party Security
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

### Environment variables (quick reference)
Cloud (Azure OpenAI) mode:
- AZURE_OPENAI_API_KEY
- AZURE_OPENAI_ENDPOINT
- AZURE_OPENAI_DEPLOYMENT
- AZURE_OPENAI_API_VERSION

### Docker & Secrets notes
- After code changes, rebuild Docker images to ensure changes are incorporated:
  ```bash
  docker-compose up --build
  ```
- Secrets management:
  - Store sensitive credentials in environment-specific secret files (e.g., `.streamlit/secrets.toml`) and avoid committing secrets to version control. For local development, you can copy an example like `secrets.example.toml` and rename it to `secrets.toml`, then populate values. In production, configure environment variables via your deployment platform.

### Azure LLM Engine (Cloud-only)
* **Azure OpenAI Only:** The application exclusively uses Azure OpenAI with strict API configurations (`max_completion_tokens`) and resilient timeouts (`300s`).
* **Structured & Free-Text Modes:** Supports Pydantic-validated structured outputs and free-text generation, with retry and optional streaming.

---

## 🛠️ Architecture & File Structure

The application maintains a strictly targeted, modular architecture:

* `app.py`: Streamlit frontend layout, user input telemetry, security culture calculation, and workflow state routing.
* `core.py`: Azure OpenAI client, exponential backoff, `max_completion_tokens` usage, and 300s timeout for resilience; structured JSON schema completions.
* `prompts.py`: Strict, typed Pydantic schema models (`MaturityReport`, `DomainAssessment`, `RoadmapPhase`, `RadarChartData`) and master consulting system personas.
* `catalog.py`: The unified Planet IT security solution portfolio, vendor alignment logic, and corporate value propositions.
* `data.py`: Static knowledge base holding attack vectors, static OSINT simulation maps, and Cyber Resiliency Matrix parameters.
* `export.py`: Document generation for Word (docxtpl) and PDF (fpdf), plus custom Matplotlib radar generation (radius hard-capped at 3).

---

## ⚙️ Setup & Execution

### 1. Configure Streamlit Secrets
Create a `.streamlit/secrets.toml` file in the project root containing your API credentials and environment options:

```toml
# --- Azure OpenAI Configuration (Cloud Mode) ---
AZURE_OPENAI_API_KEY = "your_azure_api_key_here"
AZURE_OPENAI_ENDPOINT = "https://your-endpoint.openai.azure.com/"
AZURE_OPENAI_DEPLOYMENT = "gpt-4o"
AZURE_OPENAI_API_VERSION = "2024-02-15-preview"
```

### 2. Local Python Environment
To run the application locally outside of a container:
```bash
# Install dependencies
pip install -r requirements.txt

# Run Streamlit
streamlit run app.py
```

### 3. Docker Container Deployment
The application is fully containerised with a multi-architecture (`amd64`/`arm64`) build. Since files are copied during build time, you **must rebuild the image** after modifying python files on disk:

```bash
# Build and run the service
docker-compose up --build
```
