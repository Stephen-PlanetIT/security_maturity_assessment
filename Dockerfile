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
# (This safely ingests app.py, core.py, data.py, export.py, prompts.py, and catalog.py)
COPY *.py ./

# Copy the core Planet IT branding templates
COPY planet_it_master_template.pptx .
COPY planet_it_vciso_template.docx .

# Expose the standard Streamlit port
EXPOSE 8501

# Healthcheck to ensure the container is routing correctly
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Instruct the container to run Streamlit on boot
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]