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
    pip install --no-cache-dir -r requirements.txt

# Install zeabur CLI tool
RUN curl -fsSL https://cli.zeabur.com/install.sh | sh

# Copy application code
COPY . .

# Set environment variables
ENV DATABASE_URL=postgresql://postgres:postgres@db/aed_db
ENV POSTGRES_DB=aed_db
ENV POSTGRES_USER=postgres 
ENV POSTGRES_PASSWORD=postgres
ENV SUPERUSER_DATABASE_URL=postgresql://postgres:postgres@db/aed_db

# Start PostgreSQL and FastAPI application
CMD ["sh", "start.sh"]

# Expose the API port
EXPOSE 8000
