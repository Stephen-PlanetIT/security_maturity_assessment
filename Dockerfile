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