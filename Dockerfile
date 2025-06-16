FROM mcr.microsoft.com/devcontainers/python:1-3.11-bullseye

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    vim \
    gcc \
    g++ \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js and npm
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
    apt-get install -y nodejs

# Install Google Cloud CLI
RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | \
    tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | \
    gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg && \
    apt-get update && \
    apt-get install -y google-cloud-cli

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .
COPY src/retrieval_service/requirements.txt ./retrieval-requirements.txt
COPY src/frontend_service/requirements.txt ./frontend-requirements.txt
COPY src/scrapers/requirements.txt ./scraper-requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r retrieval-requirements.txt
RUN pip install --no-cache-dir -r frontend-requirements.txt
RUN pip install --no-cache-dir -r scraper-requirements.txt

# Set environment variables
ENV PYTHONPATH=/app
ENV PATH="${PATH}:/home/vscode/.local/bin"

COPY . .
CMD ["python", "-m", "src.retrieval_service.main"]