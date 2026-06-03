# 🪐 Planet IT Strategic Advisory Platform

## Overview
The **Planet IT Strategic Advisory Platform** is an AI-powered, enterprise-grade consulting engine built to generate highly customised, compliance-aligned security assessments and tactical threat simulations. 

Designed for security consultants, the platform leverages advanced Large Language Models (LLMs) and a proprietary bifurcated logic schema to analyse a client's environment. It instantly generates boardroom-ready Executive Summaries (PDF) and deep Technical Deployment Roadmaps (PPTX), aligned to the **Planet IT Cyber Resiliency Matrix**.

## 🚀 Core Capabilities

### 1. vCISO Strategic Assessment Engine
* **Planet IT Resiliency Matrix Mapping:** Evaluates the client's estate against 9 security domains (including Security Validation & Testing) and strictly maps them to Phase 1 (Reactive), Phase 2 (Proactive), or Phase 3 (Adaptive).
* **Bifurcated Deliverables:** Automatically splits LLM generation into two distinct streams: a high-level, risk-focused Executive Summary (PDF) and a deep, engineering-focused Deployment Roadmap (PPTX).
* **Compliance & GRC Mapping:** Maps gaps to major frameworks (ISO27001, NIS2, DORA) and calculates an internal Security Culture Tier.

### 2. Tactical Threat Simulator
* **Single-Pass Generation:** Utilises a highly optimised LLM call to simultaneously generate a strategic breach narrative and a highly technical SOC Investigation Log.
* **Stack-Specific Attacks:** Modifies the attack vector and OSINT data based on the client's exact firewall, endpoint, and identity providers.

### 3. Enterprise Export Engine
* **Memory-Safe PDF Generation:** Uses a hardened FPDF pipeline with full-page justification and sanitised Markdown rendering.
* **Dynamic Radar Charts:** Generates accurately scaled, 3-phase Matplotlib radar charts dynamically mapped to the assessment domains.
* **Master Template Injection:** Actively reads a local `planet_it_master_template.pptx` file and seamlessly injects AI-generated content into pre-branded corporate slides.

### 4. Dual LLM Inference Engine (Hybrid Cloud/Local)
* **Dynamic UI Provider Routing:** A built-in sidebar toggle allows you to seamlessly switch between enterprise-grade Azure OpenAI (`gpt-4o`) for rapid generation, or local on-device inference via Ollama (e.g., `deepseek-r1:32b`) for zero-cost, private execution without restarting the application.

---

## 🛠️ Architecture & File Structure

The application follows a modular, scalable architecture:

* `app.py`: The core Streamlit application, UI dashboard, and LLM routing logic.
* `prompts.py`: Houses the Pydantic schemas and the Planet IT Master Persona guardrails.
* `export.py`: The document generation engine (PDF creation, Matplotlib charting, PPTX injection).
* `data.py`: The static knowledge base containing OSINT data, threat vectors, the Cyber Resiliency Matrix, and the authorised Planet IT/Sophos solution map.
* `planet_it_master_template.pptx`: The visual anchor; a blank, branded corporate deck used for PPTX injection.
* `docker-compose.yml` & `Dockerfile`: Multi-architecture (`amd64`/`arm64`) containerisation setup ensuring the app runs flawlessly on both Intel and Apple Silicon hardware.

---

## ⚙️ Configuration & Secrets

The platform requires a `.streamlit/secrets.toml` file in the root directory to house your API credentials and local endpoint configurations. You must define both Azure and Ollama parameters here. 

Create `.streamlit/secrets.toml` with the following format:

```toml
# --- Azure OpenAI Configuration (For Cloud Mode) ---
AZURE_OPENAI_API_KEY = "your_azure_api_key_here"
AZURE_OPENAI_ENDPOINT = "[https://your-endpoint.openai.azure.com/](https://your-endpoint.openai.azure.com/)"
AZURE_OPENAI_DEPLOYMENT = "gpt-4o"
AZURE_OPENAI_API_VERSION = "2024-02-15-preview"

# --- Ollama Configuration (For Local Mode) ---
# Use host.docker.internal if running the app in Docker. Use localhost if running locally via Python.
OLLAMA_BASE_URL = "[http://host.docker.internal:11434/v1](http://host.docker.internal:11434/v1)"
OLLAMA_MODEL = "deepseek-r1:32b" # e.g., deepseek-r1:32b or qwen2.5:32b