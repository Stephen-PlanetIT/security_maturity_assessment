__all__ = ["LLMEngine"]
import streamlit as st
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
            # Detect common placeholder values
            if not endpoint or "your-resource-name" in endpoint or "<your-resource-name>" in endpoint:
                raise ValueError("Azure OpenAI endpoint appears to be a placeholder. Please set AZURE_OPENAI_ENDPOINT to your real resource URL.")
            if not api_key or "REDACTED" in str(api_key):
                raise ValueError("Azure OpenAI API key appears to be placeholder or redacted. Please set AZURE_OPENAI_API_KEY to your actual key.")
            return AzureOpenAI(
                api_key=api_key, 
                api_version=get_config(ConfigKey.AZURE_API_VERSION, "2024-02-15-preview"), 
                azure_endpoint=endpoint,
                timeout=300.0 
            )
        except Exception as e:
            _logger.error("Client initialisation failed: %s", e, exc_info=True)
            st.error("🚨 Unable to initialise the advisory engine. Please check the configuration and try again.")
            return None

    @staticmethod
    def _build_extra_params(streaming=False):
        """Build the extra_params dict for Azure OpenAI.

        When streaming, max_completion_tokens is omitted as the streaming
        protocol handles token limits differently.
        """
        extra_params = {
            "temperature": 0.6
        }
        if not streaming:
            extra_params["max_completion_tokens"] = 8192
        return extra_params

    @staticmethod
    def generate_structured_report(client, deployment, system_persona, user_prompt, response_model):
        if not client: 
            return None
            
        try:
            extra_params = LLMEngine._build_extra_params()
                
            # Exponential Backoff Retry Logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = client.beta.chat.completions.parse(
                        model=deployment, 
                        messages=[
                            {"role": "system", "content": system_persona}, 
                            {"role": "user", "content": user_prompt}
                        ],
                        response_format=response_model, 
                        **extra_params
                    )
                    return response.choices[0].message.parsed
                except Exception as e:
                    if attempt == max_retries - 1:
                        _logger.error("Structured generation exhausted retries (%d attempts): %s", max_retries, e, exc_info=True)
                        st.error("Report generation failed after multiple attempts. Please try again.")
                        return None
                    time.sleep((2 ** attempt) + random.random())
                    
        except Exception as e:
            _logger.error("LLM structured generation error: %s", e, exc_info=True)
            st.error("An error occurred during report generation. Please try again.")
            return None

    @staticmethod
    def generate_text_report(client, deployment, system_persona, user_prompt, temperature=0.7):
        """Generate a free-text (non-structured) response, passing provider-specific params."""
        if not client:
            return None

        try:
            extra_params = LLMEngine._build_extra_params()
            extra_params["temperature"] = temperature

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
                    time.sleep(2 ** attempt)

        except Exception as e:
            _logger.error("LLM text generation error: %s", e, exc_info=True)
            st.error("An error occurred during text generation. Please try again.")
            return None

    @staticmethod
    def generate_text_report_streaming(client, deployment, system_persona, user_prompt, temperature=0.7):
        """
        Generate a free-text response with streaming support.
        Yields tokens as they arrive from the API.
        Implements retry logic with exponential backoff for transient failures.
        """
        if not client:
            yield "Error: LLM client not initialised."
            return

        max_retries = 3
        for attempt in range(max_retries):
            try:
                extra_params = LLMEngine._build_extra_params(streaming=True)
                extra_params["temperature"] = temperature
                extra_params["stream"] = True

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
                return  # Success — exit generator

            except Exception as e:
                if attempt == max_retries - 1:
                    _logger.error("Streaming generation exhausted retries (%d attempts): %s", max_retries, e, exc_info=True)
                    yield "\n\n[An error occurred during streaming. Please try again.]"
                    return
                time.sleep((2 ** attempt) + random.random())
                continue
