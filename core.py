# core.py
import streamlit as st
from openai import AzureOpenAI, OpenAI

class LLMEngine:
    @staticmethod
    def get_client(provider_choice="azure"):
        provider = provider_choice.lower()
        
        try:
            if "ollama" in provider or "local" in provider:
                base_url = st.secrets.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434/v1")
                return OpenAI(
                    base_url=base_url,
                    api_key="ollama" 
                )
            else:
                return AzureOpenAI(
                    api_key=st.secrets["AZURE_OPENAI_API_KEY"], 
                    api_version=st.secrets.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"), 
                    azure_endpoint=st.secrets["AZURE_OPENAI_ENDPOINT"]
                )
        except Exception as e:
            st.error(f"🚨 Client Initialization Error: {e}")
            return None

    @staticmethod
    def generate_structured_report(client, deployment, system_persona, user_prompt, response_model):
        if not client: return None
        try:
            # Ollama natively supports this exact parsing method
            response = client.beta.chat.completions.parse(
                model=deployment, 
                messages=[
                    {"role": "system", "content": system_persona}, 
                    {"role": "user", "content": user_prompt}
                ],
                response_format=response_model, 
                temperature=0.7
            )
            return response.choices[0].message.parsed
        except Exception as e:
            st.error(f"LLM Generation Error: {e}")
            return None