import streamlit as st

st.set_page_config(page_title="Threats Relay", layout="wide")

# Preserve session and set workflow intent before switching to the main app page.
st.session_state["workflow"] = "🔥 Tactical Threat Simulator"

# Prefer programmatic navigation if available (keeps session/auth intact).
try:
    # Streamlit 1.22+ provides st.switch_page
    st.switch_page("app.py")  # type: ignore[attr-defined]
except Exception:
    # Fallback: explicit link for manual click if switch_page is unavailable.
    st.page_link("app.py", label="🔥 Switching to Threats… (click if not redirected)")