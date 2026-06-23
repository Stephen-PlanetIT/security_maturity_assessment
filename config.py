"""
config.py — Provider-agnostic secrets layer.

Supports two runtime modes:
  1. Local development: reads from Streamlit's st.secrets (backed by .streamlit/secrets.toml)
  2. Azure Container Apps: reads from os.environ (injected via ACA secretrefs)

Usage:
    from config import get_config, validate_config, ConfigKey

    api_key = get_config(ConfigKey.AZURE_API_KEY)
    validate_config("azure")
"""

import os
from typing import Optional
import streamlit as st


class ConfigKey:
    """Canonical secret key constants — single source of truth for all modules."""

    # Azure OpenAI
    AZURE_API_KEY = "AZURE_OPENAI_API_KEY"
    AZURE_ENDPOINT = "AZURE_OPENAI_ENDPOINT"
    AZURE_DEPLOYMENT = "AZURE_OPENAI_DEPLOYMENT"
    AZURE_API_VERSION = "AZURE_OPENAI_API_VERSION"

    # Ollama (local)
    OLLAMA_BASE_URL = "OLLAMA_BASE_URL"
    OLLAMA_MODEL = "OLLAMA_MODEL"
    OLLAMA_KEEP_ALIVE = "OLLAMA_KEEP_ALIVE_DURATION"


def get_config(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Retrieve a configuration value.

    Resolution order:
      1. st.secrets (local .streamlit/secrets.toml)
      2. os.environ (ACA / container runtime)
      3. default (fallback)

    Returns None only if the key is absent in all sources and no default is given.
    """
    # 1. Try st.secrets (local .streamlit/secrets.toml)
    #    Note: st.secrets.get() raises StreamlitSecretNotFoundError if no TOML
    #    file exists at all, so we must catch broadly here.
    try:
        value = st.secrets.get(key)
        if value is not None:
            return value
    except Exception:
        pass  # No secrets file — fall through to os.environ

    # 2. Try os.environ (ACA / container runtime)
    value = os.environ.get(key)
    if value is not None:
        return value

    # 3. Fallback default
    return default


def validate_config(provider: str) -> None:
    """
    Fail-fast validation that all required secrets are present.

    Args:
        provider: "azure" or "ollama"

    Raises:
        ValueError: with a descriptive message listing every missing key.
    """
    if provider == "ollama":
        required = [
            ConfigKey.OLLAMA_BASE_URL,
            ConfigKey.OLLAMA_MODEL,
        ]
    else:
        required = [
            ConfigKey.AZURE_API_KEY,
            ConfigKey.AZURE_ENDPOINT,
            ConfigKey.AZURE_DEPLOYMENT,
        ]

    missing = [key for key in required if get_config(key) is None]

    if missing:
        source_hint = (
            "Set them in .streamlit/secrets.toml (local) "
            "or as environment variables (Azure Container Apps)."
        )
        raise ValueError(
            f"Missing required configuration keys for provider '{provider}': "
            f"{', '.join(missing)}. {source_hint}"
        )