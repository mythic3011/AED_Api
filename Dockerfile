FROM python:3.9-slim

WORKDIR /app

# Install system dependencies required for PostgreSQL and numeric libraries
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq-dev \
    gcc \
    g++ \
    build-essential \
    python3-dev \
    dos2unix \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Make sure the pg_config path is in the PATH environment
ENV PATH "$PATH:/usr/bin:/usr/local/bin"

# Copy requirements file
COPY requirements.txt .

# Install all packages from requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir fastapi-cache2 gunicorn uvicorn fastapi-cache2

# Install zeabur CLI tool
RUN curl -fsSL https://cli.zeabur.com/install.sh | sh

# Copy application code
COPY . .

# Set environment variables
ENV DATABASE_URL=postgresql://postgres:postgres@db/aed_db
ENV DB_NAME=aed_db
ENV DB_USER=postgres 
ENV DB_PASSWORD=postgres
ENV DB_HOST=db

# Convert Windows line endings to Unix line endings and make all scripts executable
RUN dos2unix *.sh && chmod +x *.sh

# Create a copy of the universal_start.sh script in a location that won't be shadowed by volume mounts
RUN mkdir -p /scripts && \
    cp universal_start.sh /scripts/universal_start.sh && \
    cp docker-entrypoint.sh /scripts/docker-entrypoint.sh && \
    chmod +x /scripts/*.sh

# Create a failsafe startup script in case universal_start.sh isn't accessible
RUN echo '#!/bin/bash\nset -e\necho "🚀 Failsafe API Startup 🚀"\nexport PORT=${PORT:-8000}\necho "Starting server with uvicorn on port $PORT"\nexec uvicorn app.main:app --host 0.0.0.0 --port $PORT' > /scripts/failsafe_start.sh && \
    chmod +x /scripts/failsafe_start.sh

# Install gunicorn and uvicorn explicitly to ensure they're available
RUN pip install --no-cache-dir fastapi-cache2 gunicorn uvicorn

# Use our entrypoint script with direct execution
ENTRYPOINT ["/bin/bash", "/scripts/docker-entrypoint.sh"]

# Expose the API port
EXPOSE 8000
