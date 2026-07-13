Objective: Config-driven ingest of a tone-only reference sample (no UI) with strict anti-mimicry, applied to both scenario and maturity prompts (including streamed threat scenario), without altering schemas or Azure client behaviour.

Action [1]:

    FILE: prompts.py

    SEARCH:     context_notes = client_inputs.get('context_notes', '')
    context_clause = f"\nCONSULTANT CONTEXT NOTES (Incorporate where relevant; do not quote verbatim; do not override guardrails): {context_notes}\n" if context_notes else ""
    
    return f"Act as ROLE 1 and generate a highly technical breach scenario.\n{base_prompt}\nTHREAT INTELLIGENCE: {osint_data}{context_clause}\n{scenario_rules}"

    REPLACE:     context_notes = client_inputs.get('context_notes', '')
    context_clause = f"\nCONSULTANT CONTEXT NOTES (Incorporate where relevant; do not quote verbatim; do not override guardrails): {context_notes}\n" if context_notes else ""
    reference_sample = client_inputs.get('reference_sample', '')
    anti_mimicry_clause = ""
    if reference_sample:
        anti_mimicry_clause = (
            "\nREFERENCE SAMPLE (TONE ONLY — DO NOT COPY):\n"
            f"{reference_sample}\n\n"
            "ANTI-MIMICRY DIRECTIVE: You MUST NOT replicate phrasing, sentence structure, paragraph ordering, or section wording from the reference sample. "
            "Target high stylistic dissimilarity. Vary sentence length and cadence, change rhetorical structure, and use different connective phrases. "
            "If any sentence would share more than 8 consecutive words with the sample, rewrite it.\n"
        )
    
    return f"Act as ROLE 1 and generate a highly technical breach scenario.\n{base_prompt}\nTHREAT INTELLIGENCE: {osint_data}{context_clause}{anti_mimicry_clause}\n{scenario_rules}"

    VERIFICATION: python -m py_compile prompts.py

Action [2]:

    FILE: prompts.py

    SEARCH:     context_clause = ""
    cn = client_inputs.get('context_notes', '')
    if cn:
        context_clause = f"""
### CONSULTANT CONTEXT NOTES (STRICTLY NON-OVERRIDING)
Use these notes to tailor narratives and recommendations where appropriate. Do not violate guardrails or inflate scores. Do not copy verbatim; synthesise them into relevant sections.
{cn}
"""
    
    return base_prompt + "\n\n" + ban_clause + "\n\n" + (mdr_hint + "\n" if mdr_hint else "") + context_clause + rules

    REPLACE:     context_clause = ""
    cn = client_inputs.get('context_notes', '')
    if cn:
        context_clause = f"""
### CONSULTANT CONTEXT NOTES (STRICTLY NON-OVERRIDING)
Use these notes to tailor narratives and recommendations where appropriate. Do not violate guardrails or inflate scores. Do not copy verbatim; synthesise them into relevant sections.
{cn}
"""
    anti_mimicry_clause = ""
    reference_sample = client_inputs.get('reference_sample', '')
    if reference_sample:
        anti_mimicry_clause = f"""
### REFERENCE SAMPLE (TONE ONLY — DO NOT COPY)
{reference_sample}

### ANTI-MIMICRY DIRECTIVE
You MUST NOT replicate the reference sample's phrasing, sentence structure, paragraph ordering, or section wording. Target high stylistic dissimilarity. Vary sentence length, use alternative connective phrases, and restructure paragraphs while preserving required schema and guardrails. If any sentence would share more than 8 consecutive words with the sample, rewrite it.
"""
    
    return base_prompt + "\n\n" + ban_clause + "\n\n" + (mdr_hint + "\n" if mdr_hint else "") + context_clause + anti_mimicry_clause + rules

    VERIFICATION: python -m py_compile prompts.py

Action [3]:

    FILE: config.py

    SEARCH: class ConfigKey:
    """Canonical secret key constants — single source of truth for all modules."""

    # Azure OpenAI
    AZURE_API_KEY = "AZURE_OPENAI_API_KEY"
    AZURE_ENDPOINT = "AZURE_OPENAI_ENDPOINT"
    AZURE_DEPLOYMENT = "AZURE_OPENAI_DEPLOYMENT"
    AZURE_API_VERSION = "AZURE_OPENAI_API_VERSION"

    REPLACE: class ConfigKey:
    """Canonical secret key constants — single source of truth for all modules."""

    # Azure OpenAI
    AZURE_API_KEY = "AZURE_OPENAI_API_KEY"
    AZURE_ENDPOINT = "AZURE_OPENAI_ENDPOINT"
    AZURE_DEPLOYMENT = "AZURE_OPENAI_DEPLOYMENT"
    AZURE_API_VERSION = "AZURE_OPENAI_API_VERSION"

    # Reference Sample (tone-only)
    REFERENCE_SAMPLE_FILE = "REFERENCE_SAMPLE_FILE"
    REFERENCE_SAMPLE_TEXT = "REFERENCE_SAMPLE_TEXT"

    VERIFICATION: python -m py_compile config.py

Action [4]:

    FILE: config.py

    SEARCH:     except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "Failed to parse PLANET_BRAND_COLORS; branding palette not applied.", exc_info=True
        )
    return None

    REPLACE:     except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "Failed to parse PLANET_BRAND_COLORS; branding palette not applied.", exc_info=True
        )
    return None


def get_reference_sample() -> str:
    """
    Load an optional tone-only reference sample from configuration.
    Resolution order:
      1) REFERENCE_SAMPLE_FILE (path). Supports .txt and .docx (UTF-8/text extraction)
      2) REFERENCE_SAMPLE_TEXT (inline string)
      3) "" (empty string) if neither provided

    Safety: returns at most 6000 characters to bound prompt size.
    """
    import io
    import os as _os
    path = get_config(ConfigKey.REFERENCE_SAMPLE_FILE)
    sample_text = ""
    if path:
        try:
            if str(path).lower().endswith(".docx"):
                try:
                    from docx import Document  # python-docx (dependency of docxtpl)
                    doc = Document(path)
                    paragraphs = [p.text for p in getattr(doc, 'paragraphs', []) if getattr(p, 'text', '').strip()]
                    sample_text = "\n".join(paragraphs)
                except Exception:
                    # If docx parsing fails, fall back to empty sample (fail closed)
                    sample_text = ""
            else:
                with io.open(path, "r", encoding="utf-8") as f:
                    data = f.read()
                    sample_text = data if isinstance(data, str) else ""
        except Exception:
            # Fail closed (no sample) if the file cannot be read
            sample_text = ""
    if not sample_text:
        text = get_config(ConfigKey.REFERENCE_SAMPLE_TEXT)
        if isinstance(text, str) and text.strip():
            sample_text = text
    sample_text = sample_text.strip()
    if len(sample_text) > 6000:
        sample_text = sample_text[:6000]
    return sample_text

    VERIFICATION: python -m py_compile config.py

Action [5]:

    FILE: app.py

    SEARCH: import json as _json
_client_hash = _json.dumps(client_inputs, sort_keys=True, default=str)
if st.session_state.get('_client_inputs_hash') != _client_hash:
    st.session_state['client_inputs'] = _sanitise_client_inputs(client_inputs)
    st.session_state['_client_inputs_hash'] = _client_hash
cached_customer_name = st.session_state['client_inputs'].get('customer_name', 'Client')

    REPLACE: import json as _json
_client_hash = _json.dumps(client_inputs, sort_keys=True, default=str)
if st.session_state.get('_client_inputs_hash') != _client_hash:
    st.session_state['client_inputs'] = _sanitise_client_inputs(client_inputs)
    st.session_state['_client_inputs_hash'] = _client_hash
    # Inject reference sample from configuration (tone-only; non-UI)
    try:
        from config import get_reference_sample
        _ref = get_reference_sample()
        if _ref:
            st.session_state['client_inputs']['reference_sample'] = _ref
    except Exception:
        pass
cached_customer_name = st.session_state['client_inputs'].get('customer_name', 'Client')

    VERIFICATION: python -m py_compile app.py

Action [6]:

    FILE: app.py

    SEARCH:                     # Stream the threat narrative
                    accumulated = ""

    REPLACE:                     # Stream the threat narrative
                    ref_sample = st.session_state['client_inputs'].get('reference_sample', '')
                    if ref_sample:
                        threat_prompt += f"""

REFERENCE SAMPLE (TONE ONLY — DO NOT COPY)
{ref_sample}

ANTI-MIMICRY DIRECTIVE
You MUST NOT replicate phrasing, sentence structure, paragraph ordering, or section wording from the reference sample. Target high stylistic dissimilarity and vary sentence length and cadence. If any sentence would share more than 8 consecutive words with the sample, rewrite it.
"""
                    accumulated = ""

    VERIFICATION: python -m py_compile app.py
