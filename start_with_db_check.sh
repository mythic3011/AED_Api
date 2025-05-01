#!/bin/bash
# Script to check database connectivity before starting the application

echo "Checking database connectivity..."

MAX_RETRIES=30
RETRY_INTERVAL=5
RETRY_COUNT=0

# Source environment variables if they exist
if [ -f .env ]; then
    echo "Loading environment variables from .env"
    source .env
fi

# Get database connection parameters from environment variables
DB_HOST="${DB_HOST:-db}"
DB_NAME="${DB_NAME:-aed_db}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-postgres}"

# Log connection parameters (without credentials)
echo "Will connect to PostgreSQL at $DB_HOST/$DB_NAME as $DB_USER"

# Function to check if PostgreSQL is ready
check_postgres() {
    # Export password to avoid showing it in process list
    export PGPASSWORD=$DB_PASSWORD
    psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT 1" >/dev/null 2>&1
    local result=$?
    unset PGPASSWORD
    return $result
}

# Wait for PostgreSQL to be ready
while ! check_postgres; do
    RETRY_COUNT=$((RETRY_COUNT+1))
    
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "Failed to connect to PostgreSQL after $MAX_RETRIES attempts. Giving up."
        echo "Please check your database configuration and ensure PostgreSQL is running."
        exit 1
    fi
    
    echo "PostgreSQL is not ready yet. Waiting $RETRY_INTERVAL seconds... (Attempt $RETRY_COUNT/$MAX_RETRIES)"
    sleep $RETRY_INTERVAL
done

echo "Successfully connected to PostgreSQL. Starting application..."

# Start the application with gunicorn
exec gunicorn app.main:app -w ${GUNICORN_WORKERS:-4} -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${PORT:-8000} --timeout ${GUNICORN_TIMEOUT:-120}
