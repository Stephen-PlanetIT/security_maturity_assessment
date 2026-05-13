# app.py
import streamlit as st

st.set_page_config(page_title="Planet IT Strategic Advisory Platform", page_icon="🪐", layout="wide")

st.title("🪐 Planet IT Advisory Platform")
st.markdown("### Welcome to the Strategic Engine")
st.write("This platform generates highly customised, multi-vendor strategic roadmaps and threat simulations. Select a module from the sidebar navigation menu to begin.")

st.divider()

col1, col2 = st.columns(2)
with col1:
    st.info("**🌐 Unified Enterprise Audit**\n\nA holistic assessment covering GRC, Financial Cyber Risk, Security Architecture, and IT Operations. Generates board-level tear-sheets and technical deployment roadmaps utilising the Sophos, N-able, Mimecast, and Fortinet ecosystems.")
with col2:
    st.error("**🔥 Threat Simulator**\n\nGenerate tactical breach narratives, chronological attack timelines, and mock Planet IT Managed SOC incident response logs tailored to a specific client's vulnerabilities.")

st.divider()
st.caption("Powered by Azure OpenAI & The Planet IT Truth Engine")