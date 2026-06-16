import streamlit as st
from openai import AzureOpenAI, OpenAI
import time

class LLMEngine:
    @staticmethod
    def get_client(provider_choice="azure"):
        provider = provider_choice.lower()
        
        try:
            if "ollama" in provider or "local" in provider:
                base_url = st.secrets.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434/v1")
                return OpenAI(
                    base_url=base_url,
                    api_key="ollama",
                    timeout=90.0  # Slightly longer timeout for heavy local generation
                )
            else:
                return AzureOpenAI(
                    api_key=st.secrets["AZURE_OPENAI_API_KEY"], 
                    api_version=st.secrets.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"), 
                    azure_endpoint=st.secrets["AZURE_OPENAI_ENDPOINT"],
                    timeout=60.0 
                )
        except Exception as e:
            st.error(f"🚨 Client Initialization Error: {e}")
            return None

    @staticmethod
    def generate_structured_report(client, deployment, system_persona, user_prompt, response_model):
        if not client: 
            return None
            
        try:
            extra_params = {}
            if "ollama" in str(client.base_url).lower():
                extra_params["extra_body"] = {
                    "options": {
                        "num_ctx": 16384,    
                        "num_predict": 8192,   
                        "temperature": 0.6,  # Kept at 0.6 to prevent JSON drift
                        "top_p": 0.9           
                    }
                }
            else:
                extra_params["max_completion_tokens"] = 8192
                extra_params["temperature"] = 0.6
                
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