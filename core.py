import streamlit as st
from openai import AzureOpenAI, OpenAI
import time
from config import get_config, ConfigKey

class LLMEngine:
    @staticmethod
    def get_client(provider_choice="azure"):
        provider = provider_choice.lower()
        
        try:
            if "ollama" in provider or "local" in provider:
                base_url = get_config(ConfigKey.OLLAMA_BASE_URL, "http://host.docker.internal:11434/v1")
                return OpenAI(
                    base_url=base_url,
                    api_key="ollama",
                    timeout=360.0  # Slightly longer timeout for heavy local generation
                )
            else:
                return AzureOpenAI(
                    api_key=get_config(ConfigKey.AZURE_API_KEY), 
                    api_version=get_config(ConfigKey.AZURE_API_VERSION, "2024-02-15-preview"), 
                    azure_endpoint=get_config(ConfigKey.AZURE_ENDPOINT),
                    timeout=180.0 
                )
        except Exception as e:
            st.error(f"🚨 Client Initialization Error: {e}")
            return None

    @staticmethod
    def _build_extra_params(client):
        """Build the extra_params dict based on provider type."""
        extra_params = {}
        if "ollama" in str(client.base_url).lower():
            keep_alive = get_config(ConfigKey.OLLAMA_KEEP_ALIVE, "24h")
            extra_params["extra_body"] = {
                "keep_alive": keep_alive,
                "options": {
                    "num_ctx": 16384,    
                    "num_predict": 8192,   
                    "temperature": 0.6,
                    "top_p": 0.9           
                }
            }
        else:
            extra_params["max_completion_tokens"] = 8192
            extra_params["temperature"] = 0.6
        return extra_params

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
        """
        if not client:
            yield "Error: LLM client not initialised."
            return

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

        except Exception as e:
            yield f"\n\n[Streaming Error: {e}]"