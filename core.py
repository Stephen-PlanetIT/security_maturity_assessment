__all__ = ["LLMEngine"]
import streamlit as st
import openai
from openai import AzureOpenAI
import time
import random
import logging
from config import get_config, ConfigKey

_logger = logging.getLogger(__name__)


class LLMEngine:
    @staticmethod
    def get_client():
        try:
            # Pre-flight credential validation to surface misconfig quickly
            endpoint = get_config(ConfigKey.AZURE_ENDPOINT)
            api_key = get_config(ConfigKey.AZURE_API_KEY)
            if not endpoint or "your-resource-name" in endpoint or "<your-resource-name>" in endpoint:
                raise ValueError("Azure OpenAI endpoint placeholder. Please set AZURE_OPENAI_ENDPOINT to your real resource URL.")
            if not api_key or "REDACTED" in str(api_key):
                raise ValueError("Azure OpenAI API key placeholder.")
            # Configurable timeout for resilience; default 300s; bounded to 0-600s
            timeout_sec = 300.0
            try:
                timeout_raw = get_config("AZURE_CLIENT_TIMEOUT_SEC", 300.0)
                timeout_sec = float(timeout_raw)
                if timeout_sec <= 0 or timeout_sec > 600:
                    timeout_sec = 300.0
            except Exception:
                timeout_sec = 300.0
            return AzureOpenAI(
                api_key=api_key,
                api_version=get_config(ConfigKey.AZURE_API_VERSION, "2024-02-15-preview"),
                azure_endpoint=endpoint,
                timeout=timeout_sec
            )
        except Exception as e:
            _logger.error("Client initialisation failed: %s", e, exc_info=True)
            st.error("🚨 Unable to initialise the advisory engine. Please check the configuration and try again.")
            return None

    @staticmethod
    def _build_extra_params(streaming: bool = False):
        """Build the extra_params dict for Azure OpenAI.

        When streaming, max_completion_tokens is omitted as the streaming
        protocol handles token limits differently.
        """
        try:
            temp_raw = get_config("AZURE_TEMPERATURE", 0.6)
            temperature = float(temp_raw)
            if temperature < 0.0 or temperature > 1.0:
                temperature = 0.6
        except Exception:
            temperature = 0.6

        extra_params = {
            "temperature": temperature
        }
        if not streaming:
            try:
                mct_raw = get_config("AZURE_MAX_COMPLETION_TOKENS", 8192)
                mct = int(mct_raw)
                if mct <= 0 or mct > 8192:
                    mct = 8192
            except Exception:
                mct = 8192
            extra_params["max_completion_tokens"] = mct
        return extra_params

    @staticmethod
    def _count_tokens(model: str, text: str) -> int:
        """Approximate token count using tiktoken if available; fallback to len(text)//4."""
        try:
            import tiktoken  # type: ignore
            enc = tiktoken.encoding_for_model(model) if hasattr(tiktoken, "encoding_for_model") else tiktoken.get_encoding("p50k_base")
            return len(enc.encode(text or ""))
        except Exception:
            return max(1, int(len(text or "") / 4))

    @staticmethod
    def _debug_prompt_metrics(model: str, system_persona: str, user_prompt: str, streaming: bool = False):
        """Emit prompt metrics when LLM_DEBUG is enabled via config/secrets."""
        try:
            dbg = str(get_config("LLM_DEBUG", "false")).strip().lower() in ("1","true","yes","on")
        except Exception:
            dbg = False
        if not dbg:
            return
        try:
            sys_toks = LLMEngine._count_tokens(model, system_persona)
            usr_toks = LLMEngine._count_tokens(model, user_prompt)
            total = sys_toks + usr_toks
            mode = "STREAM" if streaming else "STRUCTURED"
            mct = None if streaming else LLMEngine._build_extra_params().get("max_completion_tokens")
            msg = f"LLM DEBUG [{mode}] — system={sys_toks} toks, user={usr_toks} toks, total={total} toks, max_completion_tokens={mct}"
            _logger.info(msg)
            try:
                st.caption(msg)
            except Exception:
                pass
        except Exception:
            _logger.debug("LLM DEBUG: metrics calculation failed", exc_info=True)

    @staticmethod
    def generate_structured_report(client, deployment, system_persona, user_prompt, response_model):
        if not client:
            return None
        try:
            extra_params = LLMEngine._build_extra_params()
            LLMEngine._debug_prompt_metrics(deployment, system_persona, user_prompt, streaming=False)
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Use the beta parse path for structured outputs backed by Pydantic models
                    response = client.beta.chat.completions.parse(
                        model=deployment,
                        messages=[
                            {"role": "system", "content": system_persona},
                            {"role": "user", "content": user_prompt}
                        ],
                        response_format=response_model,
                        **extra_params
                    )
                    # The beta.parse path returns a parsed BaseModel directly when the
                    # response_model is a Pydantic model class.
                    # If available, prefer the parsed attribute; otherwise fall back to content.
                    if hasattr(response.choices[0].message, "parsed"):
                        return response.choices[0].message.parsed
                    return getattr(response.choices[0].message, "content", None)
                except Exception as e:
                    if attempt == max_retries - 1:
                        _logger.error("Structured generation exhausted retries (%d attempts): %s", max_retries, e, exc_info=True)
                        st.error("Report generation failed after multiple attempts. Please try again.")
                        return None
                    time.sleep((2 ** attempt))
        except Exception as e:
            _logger.error("LLM structured generation error: %s", e, exc_info=True)
            st.error("An error occurred during report generation. Please try again.")
            return None

    @staticmethod
    def generate_text_report(client, deployment, system_persona, user_prompt, temperature=0.7):
        if not client:
            return None
        try:
            extra_params = LLMEngine._build_extra_params()
            extra_params["temperature"] = temperature
            LLMEngine._debug_prompt_metrics(deployment, system_persona, user_prompt, streaming=False)
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = client.chat.completions.create(
                        model=deployment,
                        messages=[
                            {"role": "system", "content": system_persona},
                            {"role": "user", "content": user_prompt}
                        ],
                        **extra_params
                    )
                    return response.choices[0].message.content
                except Exception as e:
                    if attempt == max_retries - 1:
                        _logger.error("Text generation exhausted retries (%d attempts): %s", max_retries, e, exc_info=True)
                        st.error("Text generation failed after multiple attempts. Please try again.")
                        return None
                    time.sleep((2 ** attempt))
        except Exception as e:
            _logger.error("LLM text generation error: %s", e, exc_info=True)
            st.error("An error occurred during text generation. Please try again.")
            return None

    @staticmethod
    def generate_text_report_streaming(client, deployment, system_persona, user_prompt, temperature=0.7):
        if not client:
            yield "Error: LLM client not initialised."
            return
        max_retries = 3
        for attempt in range(max_retries):
            try:
                extra_params = LLMEngine._build_extra_params(streaming=True)
                extra_params["temperature"] = temperature
                extra_params["stream"] = True
                LLMEngine._debug_prompt_metrics(deployment, system_persona, user_prompt, streaming=True)
                response = client.chat.completions.create(
                    model=deployment,
                    messages=[
                        {"role": "system", "content": system_persona},
                        {"role": "user", "content": user_prompt}
                    ],
                    **extra_params
                )
                for chunk in response:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if delta and delta.content:
                            yield delta.content
                return
            except Exception as e:
                if attempt == max_retries - 1:
                    _logger.error("Streaming generation exhausted retries (%d attempts): %s", max_retries, e, exc_info=True)
                    yield "\n\n[An error occurred during streaming. Please try again.]"
                    return
                time.sleep((2 ** attempt) + random.random())