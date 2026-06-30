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


def get_config(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Retrieve a configuration value.

    Resolution order:
      1. st.secrets (local .streamlit/secrets.toml)
      2. os.environ (ACA / container runtime)
      3. default (fallback)

    Returns None only if the key is absent in all sources and no default is given.
    """
    # Detect presence of a local secrets file to avoid noisy Streamlit warnings in containers.
    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    use_streamlit_secrets = False
    try:
        use_streamlit_secrets = os.path.exists(secrets_path)
    except Exception:
        use_streamlit_secrets = False

    # 1. Try st.secrets only if a secrets.toml exists locally
    if use_streamlit_secrets:
        try:
            value = st.secrets.get(key)
            if value is not None:
                return value
        except Exception:
            # If Streamlit raises any secrets-related exception, silently fall through to env
            pass

    # 2. Try os.environ (ACA / container runtime)
    value = os.environ.get(key)
    if value is not None:
        return value

    # 3. Fallback default
    return default


def validate_config(provider: str) -> None:
    """
    Fail-fast validation that all required Azure secrets are present.
    
    Raises:
        ValueError: with a descriptive message listing every missing or malformed key.
    """
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
            f"Missing required configuration keys: {', '.join(missing)}. {source_hint}"
        )

    # Validate endpoint URL format
    endpoint = get_config(ConfigKey.AZURE_ENDPOINT)
    if endpoint:
        if not endpoint.startswith("https://"):
            raise ValueError(
                f"AZURE_OPENAI_ENDPOINT must start with 'https://'. Got: {endpoint}"
            )
        if "/openai/deployments/" in endpoint or "?api-version=" in endpoint:
            raise ValueError(
                f"AZURE_OPENAI_ENDPOINT must be the base resource URL only (e.g. 'https://my-resource.cognitiveservices.azure.com/'), "
                f"not the full API path. Got: {endpoint}"
            )

def get_planet_branding_palette():
    """
    Load Planet branding colour palette from configuration sources.
    Resolution order:
      1) PLANET_BRAND_COLORS JSON via get_config (env or secrets)
      2) None if not provided
    Returns a dict with keys: primaryColor, backgroundColor, secondaryBackgroundColor, textColor
    If any key is missing, returns None.
    """
    import json
    raw = get_config("PLANET_BRAND_COLORS")
    if not raw:
        return None
    try:
        import re
        _COLOUR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')
        palette = json.loads(raw) if isinstance(raw, str) else raw
        primary = palette.get("primaryColor") or palette.get("primary_color") or palette.get("primary")
        background = palette.get("backgroundColor") or palette.get("background_color") or palette.get("background")
        secondary = palette.get("secondaryBackgroundColor") or palette.get("secondary_background_color") or palette.get("secondary_background")
        text = palette.get("textColor") or palette.get("text_color") or palette.get("text")
        if primary and background and secondary and text:
            if not all(_COLOUR_RE.match(str(c)) for c in [primary, background, secondary, text]):
                import logging
                logging.getLogger(__name__).warning(
                    "PLANET_BRAND_COLORS contains non-hex values; rejecting palette for safety."
                )
                return None
            return {
                "primaryColor": primary,
                "backgroundColor": background,
                "secondaryBackgroundColor": secondary,
                "textColor": text
            }
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "Failed to parse PLANET_BRAND_COLORS; branding palette not applied.", exc_info=True
        )
    return None
