# 🪐 Planet IT Strategic Advisory Platform

## Overview
The **Planet IT Strategic Advisory Platform** is an AI-powered, enterprise-grade consulting engine built to generate highly customised, compliance-aligned security assessments and tactical threat simulations. 

Designed for security consultants, the platform leverages Azure OpenAI and a proprietary bifurcated logic schema to analyse a client's environment and instantly generate boardroom-ready Executive Summaries (PDF) and deep Technical Deployment Roadmaps (PPTX). The underlying technical recommendations are powered by the Sophos cybersecurity ecosystem.

## 🚀 Core Capabilities

### 1. vCISO Strategic Assessment Engine
* **Bifurcated Deliverables:** Automatically splits LLM generation into two distinct streams: a high-level, risk-focused Executive Summary (PDF) and a deep, engineering-focused Deployment Roadmap (PPTX).
* **Compliance & GRC Mapping:** Grades the client's estate against 8 security domains and maps gaps to major frameworks (ISO27001, NIS2, DORA).
* **Automated Advisory Triggers:** Dynamically recommends high-margin advisory services (e.g., Secureworks Tabletop Exercises, IR Retainers) if the client's GRC maturity or tabletop testing history is outdated.

### 2. Tactical Threat Simulator
* **Single-Pass Generation:** Utilises a highly optimised, low-latency LLM call to simultaneously generate a strategic breach narrative and a highly technical SOC Investigation Log.
* **Stack-Specific Attacks:** Modifies the attack vector and OSINT data based on the client's exact firewall, endpoint, and identity providers.
* **SOC Terminal Export:** Exports a dark-mode "Terminal Style" presentation slide to mimic a real-world managed SOC investigation.

### 3. Enterprise Export Engine
* **Master Template Injection:** PowerPoint files are no longer built from scratch. The engine actively reads a local `planet_it_master_template.pptx` file and seamlessly injects AI-generated content into pre-branded corporate slides.
* **Interactive Data Visualisation:** Replaces static images with interactive, hoverable Plotly Radar Charts in the Streamlit web dashboard.
* **Memory-Safe PDF Generation:** Uses a hardened FPDF pipeline to safely handle British currency formatting (GBP) and Unicode translation without silent data loss or memory leaks.

---

## 🛠️ Architecture & File Structure

The application follows a modular, scalable architecture:

* `app.py`: The core Streamlit application, UI dashboard, and Azure OpenAI routing logic.
* `prompts.py`: Houses the Pydantic schemas (`UnifiedEngagementReport`, `ScenarioReport`) and the Planet IT Master Persona guardrails.
* `export.py`: The document generation engine. Handles PDF creation and PPTX template injection.
* `data.py`: The static knowledge base containing OSINT data, MITRE ATT&CK vectors, maturity frameworks, and the authorised Planet IT/Sophos solution map.
* `planet_it_master_template.pptx`: The visual anchor for the application. A blank, branded corporate deck used by `export.py` for template injection.

---

## ⚙️ Installation & Setup

### Prerequisites
* Python 3.9+
* An active Azure OpenAI Endpoint and API Key.

### 1. Install Dependencies
Ensure your virtual environment is active, then install the required packages:
```bash
pip install streamlit openai pydantic fpdf2 python-pptx matplotlib numpy plotly
```

### 2. Configure Environment Variables
Create a `.streamlit/secrets.toml` file in the root directory to safely house your API credentials:
```toml
AZURE_OPENAI_API_KEY = "your_azure_api_key_here"
AZURE_OPENAI_ENDPOINT = "[https://your-endpoint.openai.azure.com/](https://your-endpoint.openai.azure.com/)"
AZURE_OPENAI_DEPLOYMENT = "your_model_deployment_name"
AZURE_OPENAI_API_VERSION = "2024-02-15-preview"
```

### 3. Prepare the Branding Template
You must place a clean, branded PowerPoint file named **`planet_it_master_template.pptx`** in the root directory. `export.py` requires this file to generate the final PPTX deliverables.

---

## 💻 Usage

To launch the application locally, run the following command in your terminal:

```bash
streamlit run app.py
```

1. Select either the **vCISO Assessment** or **Threat Simulator** from the main dashboard.
2. Fill in the client's Engagement Profile, Technology Stack, and Security Culture metrics.
3. Click **Generate** to initiate the AI analysis.
4. Review the outputs via the interactive UI tabs, and download the final PDF/PPTX deliverables.

---

### Security & Privacy Notice
Consultants must ensure they **do not** input highly sensitive Personally Identifiable Information (PII), passwords, or regulated IP data into the platform. Use generic identifiers (e.g., "Crown Jewels Database") for architectural components.