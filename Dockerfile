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

# Make all scripts executable
RUN chmod +x *.sh

# Install gunicorn and uvicorn explicitly to ensure they're available
RUN pip install --no-cache-dir fastapi-cache2 gunicorn uvicorn

# Use our universal start script that handles all cases
CMD ["./universal_start.sh"]

# Expose the API port
EXPOSE 8000
