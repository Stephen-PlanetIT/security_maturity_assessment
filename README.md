# 🪐 Planet IT Strategic Advisory Platform

## Overview
The **Planet IT Strategic Advisory Platform** is an AI-powered, enterprise-grade consulting engine built to generate highly customised, compliance-aligned security assessments and tactical threat simulations. 

Designed for security consultants, the platform leverages advanced Large Language Models (LLMs) to analyse a client's environment. It instantly generates boardroom-ready strategic deliverables: deep Technical Deployment Roadmaps in Microsoft Word (`.docx`) and Microsoft PowerPoint (`.pptx`) formats, aligned to the **Planet IT Cyber Resiliency Matrix**.

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
- **Dynamic Radar Charts:** Renders publication-quality polar area charts using `matplotlib` strictly hard-capped to a maximum radius of 3 (representing the Three-Pillar Cyber Resiliency Matrix).
- **Structured Word Doc Rendering:** Uses `docxtpl` to inject AI-generated assessments and recommendations directly into pre-formatted, corporate-branded templates (`planet_it_vciso_template.docx`).
- **PowerPoint Master Slide Injection:** Utilises `python-pptx` to programmatically inject strategic assessment roadmaps and executive briefs into high-quality client presentations.
-
---

 ### Deliverables and assets
 The core deliverables produced by the platform are:
 - Word document: Strategic Assessment (planet_it_vciso_template.docx)
 - PowerPoint deck: Client presentation (planet_it_master_template.pptx)
 - Radar visuals: Matplotlib charts included in reports
 
 Asset templates present in the repository:
 - planet_it_master_template.pptx
 - planet_it_threat_scenario_template.docx
 - planet_it_vciso_template.docx
 
 ### Domain coverage
 The Planet IT Cyber Resiliency Matrix covers the following 9 domains:
 - Endpoint & Server Security
 - Email & Data Protection
 - Identity & Access Management (IAM)
 - Network & Cloud Perimeter
 - Security Operations & Response (SecOps)
 - Security Validation & Testing
 - Governance, Risk & Compliance (GRC)
Environment variables (quick reference)
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
  - Store sensitive credentials in environment-specific secret files (e.g., secrets.toml or .streamlit/secrets.toml) and avoid committing secrets to version control. For local development, you can copy an example like secrets.example.toml and rename it to secrets.toml, then populate values. In production, configure environment variables via your deployment platform.
### 4. Azure OpenAI Only Inference Engine
- The system now exclusively uses Azure OpenAI. The UI does not expose any local LLM option, and all prompts and exports are generated via Azure deployments with the configured max_completion_tokens and temperature settings.

---

## 🛠️ Architecture & File Structure

The application maintains a strictly targeted, modular architecture:

* `app.py`: Streamlit frontend layout, user input telemetry, security culture calculation, and workflow state routing.
* `core.py`: LLM engine client abstraction, endpoint routing, resilient exponential backoff retry loops, and structured JSON schema completions.
* `prompts.py`: Strict, typed Pydantic schema models (`MaturityReport`, `DomainAssessment`, `RoadmapPhase`, `RadarChartData`) and master consulting system personas.
* `catalog.py`: The unified Planet IT security solution portfolio, vendor alignment logic, and corporate value propositions.
* `data.py`: Static knowledge base holding attack vectors, static OSINT simulation maps, and Cyber Resiliency Matrix parameters.
* `export.py`: Document generation pipelines handling DocxTemplate renderings, python-pptx templates, and custom Matplotlib radar generation.

---

## ⚙️ Setup & Execution

### 1. Configure Streamlit Secrets
Create a `.streamlit/secrets.toml` file in the project root containing your API credentials and environment options:
```toml
# --- Azure OpenAI Configuration (For Cloud Mode) ---
AZURE_OPENAI_API_KEY = "your_azure_api_key_here"
AZURE_OPENAI_ENDPOINT = "https://your-endpoint.openai.azure.com/"
AZURE_OPENAI_DEPLOYMENT = "gpt-4o"
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
