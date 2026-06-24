import streamlit as st
from openai import AzureOpenAI
import time
from config import get_config, ConfigKey

class LLMEngine:
    @staticmethod
    def get_client():
        # Azure OpenAI is the sole supported provider going forward
        try:
            return AzureOpenAI(
                api_key=get_config(ConfigKey.AZURE_API_KEY), 
                api_version=get_config(ConfigKey.AZURE_API_VERSION, "2024-02-15-preview"), 
                azure_endpoint=get_config(ConfigKey.AZURE_ENDPOINT),
                timeout=60.0 
            )
        except Exception as e:
            st.error(f"🚨 Client Initialization Error: {e}")
            return None

    @staticmethod
    def _build_extra_params(client):
        """Return fixed extra_params for Azure-only OpenAI calls"""
        return {
            "max_completion_tokens": 8192,
            "temperature": 0.6
        }

    @staticmethod
    def generate_structured_report(client, deployment, system_persona, user_prompt, response_model):
        if not client: 
            return None
            
        try:
            extra_params = LLMEngine._build_extra_params(client)
                
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
                        st.error(f"Generation failed after {max_retries} attempts: {e}")
                        return None
                    time.sleep(2 ** attempt)
                    
        except Exception as e:
            st.error(f"LLM Generation Error: {e}")
            return None

    @staticmethod
    def generate_text_report(client, deployment, system_persona, user_prompt, temperature=0.7):
        """Generate a free-text (non-structured) response, passing provider-specific params."""
        if not client:
            return None

        try:
            extra_params = LLMEngine._build_extra_params(client)
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
                        st.error(f"Text generation failed after {max_retries} attempts: {e}")
                        return None
                    time.sleep(2 ** attempt)

        except Exception as e:
            st.error(f"LLM Text Generation Error: {e}")
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
                extra_params = LLMEngine._build_extra_params(client)
                extra_params["temperature"] = temperature
                extra_params["stream"] = True

                # Remove max_completion_tokens from extra_params for streaming if present
                # (streaming handles this differently)
                extra_params.pop("max_completion_tokens", None)

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
                    yield f"\n\n[Streaming error after {max_retries} attempts: {e}]"
                    return
                import time
                time.sleep(2 ** attempt)
                continue
