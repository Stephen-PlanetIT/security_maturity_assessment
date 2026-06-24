# Execution Plan: Azure-Only LLM Support
## Overview
Eliminate all code paths, configuration keys, UI controls, and documentation that reference the Ollama (Azure OpenAI) provider. Standardise on Azure OpenAI only.

---

## 1. core.py
1. Ensure only Azure OpenAI is used. Remove any references to Ollama / local models.
2. Remove `from openai import AzureOpenAI, OpenAI`; keep only:
```python
from openai import AzureOpenAI
```
3. Replace or simplify `LLMEngine.get_client` to return an AzureOpenAI client configured with Azure secrets (no local provider branches).
4. In `_build_extra_params`, remove any Ollama-specific branches; keep a fixed payload suitable for Azure (e.g. `{"max_completion_tokens": 8192, "temperature": 0.6}`).
5. Delete any code or comments containing `"ollama"` or `"local"`.

---

## 2. config.py
1. In `ConfigKey`, delete any Ollama-specific keys (no changes required beyond documentation).
2. Ensure `validate_config()` only validates Azure keys; remove any provider-conditional branches for `ollama`.
3. Update all internal calls to `validate_config()` to call without a provider argument.

---

## 3. app.py
1. Remove UI controls and logic related to selecting an LLM provider; Azure is the only provider.
2. In `validate_platform_config()`, call `validate_config()` without arguments.
3. Ensure function `get_optimal_deployment_name()` returns the Azure deployment (e.g., `gpt-4o`).
4. Replace any calls to `LLMEngine.get_client(provider_flag)` with `LLMEngine.get_client()`.
5. Remove any runtime branches or checks for Ollama / Local provider.
6. Remove unused Ollama imports.

---

- All references to Ollama or Local LLM have been removed; documentation now references only Azure OpenAI.

---

---

## 5. Verification Steps (Act Mode)
1. **Syntax check**:  
   `python -c "import core, config, app; print('OK')"`
2. **Runtime test**:  
   `streamlit run app.py` — confirm no UI selector and app initialises without errors.
3. **Functionality test**:  
   Generate a report; ensure Azure model calls succeed and no references to local LLM remain.

---

- core.py  
- config.py  
- app.py  
- README.md