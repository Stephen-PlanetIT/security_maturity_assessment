Objective: Apply 12 security hardening fixes across config.py, app.py, prompts.py, export.py, core.py, requirements.txt, Dockerfile, and .streamlit/config.toml as directed by the security review disposition.

---

Action 1: Narrow exception handling in config.py get_config() (Point 2)

FILE: config.py

SEARCH:
    try:
        value = st.secrets.get(key)
        if value is not None:
            return value
    except Exception:
        pass  # No secrets file — fall through to os.environ

REPLACE:
    try:
        value = st.secrets.get(key)
        if value is not None:
            return value
    except (AttributeError, FileNotFoundError, ModuleNotFoundError):
        pass  # No secrets file — fall through to os.environ

---

Action 2: Validate colour hex values in get_planet_branding_palette() (Point 4)

FILE: config.py

SEARCH:
        palette = json.loads(raw) if isinstance(raw, str) else raw
        primary = palette.get("primaryColor") or palette.get("primary_color") or palette.get("primary")
        background = palette.get("backgroundColor") or palette.get("background_color") or palette.get("background")
        secondary = palette.get("secondaryBackgroundColor") or palette.get("secondary_background_color") or palette.get("secondary_background")
        text = palette.get("textColor") or palette.get("text_color") or palette.get("text")
        if primary and background and secondary and text:
            return {
                "primaryColor": primary,
                "backgroundColor": background,
                "secondaryBackgroundColor": secondary,
                "textColor": text
            }

REPLACE:
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

---

Action 3: Add prompt input sanitisation function in app.py (Point 5)

FILE: app.py

SEARCH:
from config import get_config, validate_config, ConfigKey

REPLACE:
from config import get_config, validate_config, ConfigKey
import re as _re

_SANITISE_RE = _re.compile(r'["]{3,}|\'{3,}|`{3,}|(?:\r?\n){3,}')
_SANITISE_REPLACEMENTS = [
    (_re.compile(r'["]{3,}'), '"'),
    (_re.compile(r"'{3,}"), "'"),
    (_re.compile(r'`{3,}'), '`'),
    (_re.compile(r'(?:\r?\n){3,}'), '\n\n'),
]


def _sanitise_input(value):
    """Strip prompt injection vectors from a single input string.

    Removes triple-quotes, triple-backticks, and excessive newlines that
    could be used to break out of the LLM prompt context.  Returns the
    sanitised string (or the original if it is not a string).
    """
    if not isinstance(value, str):
        return value
    sanitised = value
    for pattern, replacement in _SANITISE_REPLACEMENTS:
        sanitised = pattern.sub(replacement, sanitised)
    return sanitised.strip()


def _sanitise_client_inputs(inputs: dict) -> dict:
    """Sanitise all string values in the client_inputs dictionary."""
    return {
        k: _sanitise_input(v) if isinstance(v, str) else v
        for k, v in inputs.items()
    }

---

Action 4: Apply sanitisation to client_inputs in app.py (Point 5 cont.)

FILE: app.py

SEARCH:
st.session_state['client_inputs'] = client_inputs

REPLACE:
st.session_state['client_inputs'] = _sanitise_client_inputs(client_inputs)

---

Action 5: Add rate-limiting cooldown in app.py (Point 6)

FILE: app.py

SEARCH:
if st.session_state['workflow'] == "🔥 Tactical Threat Simulator":
    st.header("Tactical Threat Simulator")
    
    if st.button("Generate Threat Scenario", type="primary"):

REPLACE:
if st.session_state['workflow'] == "🔥 Tactical Threat Simulator":
    st.header("Tactical Threat Simulator")
    
    _now_ts = time.time()
    _cooldown = 30
    _last_gen = st.session_state.get('_last_generation_ts', 0)
    _remaining = max(0, _cooldown - int(_now_ts - _last_gen))
    if _remaining > 0:
        st.info(f"⏳ Cooldown active — generation available in {_remaining} second{'s' if _remaining != 1 else ''}.")
    
    if st.button("Generate Threat Scenario", type="primary", disabled=(_remaining > 0)):

---

Action 6: Record timestamp on threat generation start (Point 6 cont.)

FILE: app.py

SEARCH:
        st.session_state.pop(key, None)
        
        with st.spinner("Simulating Attack & MDR Response..."):

REPLACE:
        st.session_state.pop(key, None)
        st.session_state['_last_generation_ts'] = time.time()
        
        with st.spinner("Simulating Attack & MDR Response..."):

---

Action 7: Add rate-limiting cooldown for Maturity Assessment button (Point 6 cont.)

FILE: app.py

SEARCH:
elif st.session_state['workflow'] == "📈 Cybersecurity Maturity Assessment":
    st.header("Cybersecurity Maturity Assessment")
    
    if st.button("Generate Maturity Roadmap", type="primary"):

REPLACE:
elif st.session_state['workflow'] == "📈 Cybersecurity Maturity Assessment":
    st.header("Cybersecurity Maturity Assessment")
    
    _now_ts2 = time.time()
    _cooldown2 = 30
    _last_gen2 = st.session_state.get('_last_generation_ts', 0)
    _remaining2 = max(0, _cooldown2 - int(_now_ts2 - _last_gen2))
    if _remaining2 > 0:
        st.info(f"⏳ Cooldown active — generation available in {_remaining2} second{'s' if _remaining2 != 1 else ''}.")
    
    if st.button("Generate Maturity Roadmap", type="primary", disabled=(_remaining2 > 0)):

---

Action 8: Record timestamp on maturity generation start (Point 6 cont.)

FILE: app.py

SEARCH:
        with st.spinner("Compiling Cybersecurity Maturity Assessment..."):
            client = LLMEngine.get_client()
            deployment = get_config(ConfigKey.AZURE_DEPLOYMENT, "gpt-4o")

REPLACE:
        st.session_state['_last_generation_ts'] = time.time()
        with st.spinner("Compiling Cybersecurity Maturity Assessment..."):
            client = LLMEngine.get_client()
            deployment = get_config(ConfigKey.AZURE_DEPLOYMENT, "gpt-4o")

---

Action 9: Add `import time` to app.py (required for rate limiting) (Point 6 cont.)

FILE: app.py

SEARCH:
import streamlit as st
import random

REPLACE:
import streamlit as st
import random
import time

---

Action 10: Pin all dependencies in requirements.txt (Point 7)

FILE: requirements.txt

SEARCH:
streamlit
pydantic
fpdf
matplotlib
openai>=1.14.0
httpx==0.27.2
matplotlib==3.8.3
numpy==1.26.4
plotly==5.19.0
docxtpl

REPLACE:
streamlit==1.42.2
pydantic==2.10.6
fpdf==1.7.2
openai==1.75.0
httpx==0.27.2
matplotlib==3.8.3
numpy==1.26.4
plotly==5.19.0
docxtpl==0.19.1

---

Action 11: Convert Dockerfile to multi-stage build with non-root user (Point 8)

FILE: Dockerfile

SEARCH:
# Use a slim, secure Python runtime as the base image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required for matplotlib, fpdf2, and healthchecks
RUN apt-get update && apt-get install -y \
    build-essential \
    libfreetype6-dev \
    libpng-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy ALL application logic and static knowledge base
# (This safely ingests app.py, core.py, config.py, data.py, export.py, prompts.py, and catalog.py)
COPY *.py ./

# Copy the VERSION tracker file
COPY VERSION .

# Copy Streamlit theme configuration for brand-consistent Azure deployment
COPY .streamlit/config.toml .streamlit/config.toml

# Copy the core Planet IT branding templates
COPY planet_it_master_template.pptx .
COPY planet_it_maturity_assessment_template.docx .
COPY planet_it_threat_scenario_template.docx .

# Expose the standard Streamlit port
EXPOSE 8501

# Healthcheck to ensure the container is routing correctly
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Instruct the container to run Streamlit on boot
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]

REPLACE:
# ================================================================
# STAGE 1: Build stage — installs dependencies into a virtual env
# ================================================================
FROM python:3.10-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y \
    build-essential \
    libfreetype6-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ================================================================
# STAGE 2: Production stage — minimal, non-root, read-only capable
# ================================================================
FROM python:3.10-slim AS production

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r appuser && useradd -r -g appuser -d /app appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code and assets
COPY *.py ./
COPY VERSION .
COPY .streamlit/config.toml .streamlit/config.toml
COPY planet_it_master_template.pptx .
COPY planet_it_maturity_assessment_template.docx .
COPY planet_it_threat_scenario_template.docx .

# Ensure appuser owns the working directory
RUN chown -R appuser:appuser /app

# Drop to non-root user
USER appuser

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=15s \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]

---

Action 12: Wrap temp file handling in try/finally in export.py (Point 9)

FILE: export.py

SEARCH:
    tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    plt.savefig(tmpfile.name, format='png', bbox_inches='tight')
    plt.close(fig)
    
    return tmpfile.name

REPLACE:
    tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    try:
        plt.savefig(tmpfile.name, format='png', bbox_inches='tight')
    finally:
        plt.close(fig)
    
    return tmpfile.name

---

Action 13: Add temp file cleanup in create_maturity_docx with try/finally (Point 9 cont.)

FILE: export.py

SEARCH:
    chart_path = generate_radar_chart_from_values(labels, values, figsize=(4, 4))
    with open(chart_path, "rb") as f:
        chart_buffer = io.BytesIO(f.read())
    os.unlink(chart_path)

REPLACE:
    chart_path = generate_radar_chart_from_values(labels, values, figsize=(4, 4))
    try:
        with open(chart_path, "rb") as f:
            chart_buffer = io.BytesIO(f.read())
    finally:
        try:
            os.unlink(chart_path)
        except OSError:
            pass

---

Action 14: Replace generic st.error with logged errors in core.py (Point 10)

FILE: core.py

SEARCH:
__all__ = ["LLMEngine"]
import streamlit as st
from openai import AzureOpenAI
import time
import random
from config import get_config, ConfigKey

REPLACE:
__all__ = ["LLMEngine"]
import streamlit as st
from openai import AzureOpenAI
import time
import random
import logging
from config import get_config, ConfigKey

_logger = logging.getLogger(__name__)

---

Action 15: Replace st.error with generic messages + internal logging in get_client() (Point 10 cont.)

FILE: core.py

SEARCH:
        except Exception as e:
            st.error(f"🚨 Client Initialization Error: {e}")
            return None

REPLACE:
        except Exception as e:
            _logger.error("Client initialisation failed: %s", e, exc_info=True)
            st.error("🚨 Unable to initialise the advisory engine. Please check the configuration and try again.")
            return None

---

Action 16: Replace st.error with generic messages + internal logging in generate_structured_report() (Point 10 cont.)

FILE: core.py

SEARCH:
                    if attempt == max_retries - 1:
                        st.error(f"Generation failed after {max_retries} attempts: {e}")
                        return None
                    time.sleep((2 ** attempt) + random.random())
                    
        except Exception as e:
            st.error(f"LLM Generation Error: {e}")
            return None

REPLACE:
                    if attempt == max_retries - 1:
                        _logger.error("Structured generation exhausted retries (%d attempts): %s", max_retries, e, exc_info=True)
                        st.error("Report generation failed after multiple attempts. Please try again.")
                        return None
                    time.sleep((2 ** attempt) + random.random())
                    
        except Exception as e:
            _logger.error("LLM structured generation error: %s", e, exc_info=True)
            st.error("An error occurred during report generation. Please try again.")
            return None

---

Action 17: Replace st.error with generic messages + internal logging in generate_text_report() (Point 10 cont.)

FILE: core.py

SEARCH:
                    if attempt == max_retries - 1:
                        st.error(f"Text generation failed after {max_retries} attempts: {e}")
                        return None
                    time.sleep(2 ** attempt)

        except Exception as e:
            st.error(f"LLM Text Generation Error: {e}")
            return None

REPLACE:
                    if attempt == max_retries - 1:
                        _logger.error("Text generation exhausted retries (%d attempts): %s", max_retries, e, exc_info=True)
                        st.error("Text generation failed after multiple attempts. Please try again.")
                        return None
                    time.sleep(2 ** attempt)

        except Exception as e:
            _logger.error("LLM text generation error: %s", e, exc_info=True)
            st.error("An error occurred during text generation. Please try again.")
            return None

---

Action 18: Replace st.error with generic messages in generate_text_report_streaming() (Point 10 cont.)

FILE: core.py

SEARCH:
                if attempt == max_retries - 1:
                    yield f"\n\n[Streaming error after {max_retries} attempts: {e}]"
                    return

REPLACE:
                if attempt == max_retries - 1:
                    _logger.error("Streaming generation exhausted retries (%d attempts): %s", max_retries, e, exc_info=True)
                    yield "\n\n[An error occurred during streaming. Please try again.]"
                    return

---

Action 19: Replace st.error with generic messages + logging in app.py export failures (Point 10 cont.)

FILE: app.py

SEARCH:
        except Exception as e:
            st.error(f"PDF Export Failed: {e}")

REPLACE:
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("PDF export failed: %s", e, exc_info=True)
            st.error("PDF export failed. Please try regenerating the report.")

---

Action 20: Replace st.error with generic messages in Word export (Point 10 cont.)

FILE: app.py

SEARCH:
        except Exception as e:
            st.error(f"Word Export Failed: {e}")

REPLACE:
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("Word export failed: %s", e, exc_info=True)
            st.error("Word export failed. Please try regenerating the report.")

---

Action 21: Replace st.error with generic messages in maturity Word export (Point 10 cont.)

FILE: app.py

SEARCH:
        except Exception as e:
            st.error(f"Cybersecurity Maturity Assessment Word Export Failed: {e}")

REPLACE:
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("Maturity Word export failed: %s", e, exc_info=True)
            st.error("Maturity report export failed. Please try regenerating the report.")

---

Action 22: Add CSP meta tag in app.py header (Point 12)

FILE: app.py

SEARCH:
# --- UI CONFIGURATION ---
st.set_page_config(page_title="Security Use Case Generator", layout="wide")

REPLACE:
# --- UI CONFIGURATION ---
st.set_page_config(page_title="Security Use Case Generator", layout="wide")

# Inject Content Security Policy header via meta tag (static string, no user input)
_CSP_META = (
    '<meta http-equiv="Content-Security-Policy" '
    'content="default-src \'self\'; '
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "script-src 'self' 'unsafe-eval' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "connect-src 'self' https://*.azure.com https://*.openai.azure.com; "
    'frame-ancestors \'none\';">'
)
st.markdown(_CSP_META, unsafe_allow_html=True)

---

Action 23: Enable XSRF protection in .streamlit/config.toml (Point 12 cont.)

FILE: .streamlit/config.toml

SEARCH:
[theme]
primaryColor = "#23506A"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"

REPLACE:
[theme]
primaryColor = "#23506A"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"

[server]
enableXsrfProtection = true
enableCORS = false

---

Action 24: Replace ast.literal_eval with json.loads in _normalize_kd() (Point 15)

FILE: export.py

SEARCH:
def _normalize_kd(kd):
    """Normalise key_deliverables to a bullet-text string.
    - If kd is a list, render as bullet points joined by newlines.
    - If kd is a string that resembles a Python list, attempt to ast.literal_eval and render if it yields a list.
    - Otherwise, return the string value or an empty string.
    """
    if isinstance(kd, list):
        return "\n".join(f"• {str(item)}" for item in kd)
    if isinstance(kd, str):
        s = kd.strip()
        if not s:
            return ""
        try:
            parsed = ast.literal_eval(s)
            if isinstance(parsed, list):
                return "\n".join(f"• {str(item)}" for item in parsed)
        except Exception:
            pass
        return s
    return ""

REPLACE:
def _normalize_kd(kd):
    """Normalise key_deliverables to a bullet-text string.
    - If kd is a list, render as bullet points joined by newlines.
    - If kd is a string that resembles a JSON array, parse it and render if successful.
    - Otherwise, return the string value or an empty string.
    """
    if isinstance(kd, list):
        return "\n".join(f"• {str(item)}" for item in kd)
    if isinstance(kd, str):
        s = kd.strip()
        if not s:
            return ""
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return "\n".join(f"• {str(item)}" for item in parsed)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        return s
    return ""

---

Action 25: Remove unused `import ast` from export.py (Point 15 cont.)

FILE: export.py

SEARCH:
import io
import ast
import re
import textwrap

REPLACE:
import io
import json
import re
import textwrap

---

Verification commands (run after all patches):
  python -c "from config import get_config, get_planet_branding_palette; print('config OK')"
  python -c "from core import LLMEngine; print('core OK')"
  python -c "from prompts import MaturityReport, ScenarioReport; print('prompts OK')"
  python -c "from export import _normalize_kd, generate_radar_chart_from_values; print('export OK')"
  python -c "from app import _sanitise_input, _sanitise_client_inputs; print('app OK')"
  python -c "import compileall; compileall.compile_dir('.', quiet=1); print('syntax OK')"
  docker build -t sec-use-case:latest .