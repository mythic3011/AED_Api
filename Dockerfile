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

# Install packages one by one to better handle dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir numpy==1.24.3 && \
    pip install --no-cache-dir pandas==2.0.1 && \
    pip install --no-cache-dir fastapi==0.95.1 && \
    pip install --no-cache-dir uvicorn==0.22.0 && \
    pip install --no-cache-dir sqlalchemy==2.0.12 && \
    pip install --no-cache-dir requests==2.29.0 && \
    pip install --no-cache-dir geoalchemy2==0.13.0 && \
    pip install --no-cache-dir psycopg2-binary==2.9.6

# Install zeabur CLI tool
RUN curl -fsSL https://cli.zeabur.com/install.sh | sh

# Copy application code
COPY . .

# Set environment variables
ENV DATABASE_URL=postgresql://postgres:postgres@localhost/aed_db
ENV POSTGRES_DB=aed_db
ENV POSTGRES_USER=postgres 
ENV POSTGRES_PASSWORD=postgres

# Start PostgreSQL and FastAPI application
CMD ["sh", "start.sh"]

# Expose the API port
EXPOSE 8000

# Add zeabur deployment script
COPY zeabur_deploy.sh /app/zeabur_deploy.sh
RUN chmod +x /app/zeabur_deploy.sh
