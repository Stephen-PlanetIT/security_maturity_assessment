# core.py
import streamlit as st
from openai import AzureOpenAI

class LLMEngine:
    @staticmethod
    def get_client():
        try:
            return AzureOpenAI(
                api_key=st.secrets["AZURE_OPENAI_API_KEY"], 
                api_version=st.secrets.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"), 
                azure_endpoint=st.secrets["AZURE_OPENAI_ENDPOINT"]
            )
        except Exception as e:
            st.error(f"🚨 API Credentials missing or invalid. Check secrets.toml or .env. Error: {e}")
            return None

    @staticmethod
    def generate_structured_report(client, deployment, system_persona, user_prompt, response_model):
        if not client: return None
        try:
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