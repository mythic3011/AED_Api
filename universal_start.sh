#!/bin/bash
# Universal API server startup script

set -e  # Exit on any error

echo "🚀 AED API - Universal Startup Script 🚀"
echo "========================================"

# 1. Environment Setup
echo "Setting up environment..."
export PORT=${PORT:-8000}
export GUNICORN_WORKERS=${GUNICORN_WORKERS:-4}
export GUNICORN_TIMEOUT=${GUNICORN_TIMEOUT:-120}

# 2. Database Connection Check
echo "Checking database connection..."
DB_HOST="${DB_HOST:-db}"
DB_NAME="${DB_NAME:-aed_db}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-postgres}"

# Export for PostgreSQL client
export PGHOST=$DB_HOST
export PGDATABASE=$DB_NAME
export PGUSER=$DB_USER
export PGPASSWORD=$DB_PASSWORD

# Function to check database connection
check_db() {
    echo "Testing PostgreSQL connection..."
    psql -c "SELECT 1" >/dev/null 2>&1
    return $?
}

# Try to connect to the database with retry
MAX_RETRIES=10
for i in $(seq 1 $MAX_RETRIES); do
    if check_db; then
        echo "✅ Successfully connected to PostgreSQL!"
        
        # Check for PostGIS extension
        if psql -c "SELECT extname FROM pg_extension WHERE extname='postgis'" | grep -q postgis; then
            echo "✅ PostGIS extension is installed."
        else
            echo "Creating PostGIS extension..."
            psql -c "CREATE EXTENSION IF NOT EXISTS postgis"
            if [ $? -eq 0 ]; then
                echo "✅ PostGIS extension created!"
            else
                echo "⚠️ Failed to create PostGIS extension!"
            fi
        fi
        
        db_connected=true
        break
    else
        echo "⚠️ Database connection attempt $i failed. Retrying in 5 seconds..."
        sleep 5
    fi
done

if [ -z "$db_connected" ]; then
    echo "⚠️ Could not establish database connection after $MAX_RETRIES attempts."
    echo "The application will start anyway, but may not function correctly."
fi

# Clear password
unset PGPASSWORD

# 3. Server Start
echo "Starting API server..."

# Function to try gunicorn with various configurations
start_with_gunicorn() {
    echo "Attempting to start with gunicorn..."
    
    # Try standard configuration
    if command -v gunicorn >/dev/null 2>&1; then
        if gunicorn app.main:app -w $GUNICORN_WORKERS -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT --timeout $GUNICORN_TIMEOUT; then
            return 0
        fi
        
        echo "⚠️ Standard gunicorn configuration failed, trying simple configuration..."
        # Try simple configuration
        if gunicorn app.main:app -b 0.0.0.0:$PORT; then
            return 0
        fi
    else
        echo "⚠️ Gunicorn not found in PATH"
    fi
    
    return 1
}

# Function to start with uvicorn
start_with_uvicorn() {
    echo "Attempting to start with uvicorn..."
    uvicorn app.main:app --host 0.0.0.0 --port $PORT
    return $?
}

# Try to start the server with different methods
if command -v gunicorn &>/dev/null; then
    start_with_gunicorn || start_with_uvicorn
elif command -v uvicorn &>/dev/null; then
    else
    echo "⚠️ Neither gunicorn nor uvicorn found. Installing requirements..."
    pip install -r requirements.txt
    
    # Try again after installing
    if command -v gunicorn &>/dev/null; then
        start_with_gunicorn || start_with_uvicorn
    elif command -v uvicorn &>/dev/null; then
        start_with_uvicorn
    else
        echo "❌ Failed to start server after installing requirements. Exiting."
        exit 1
    fi
fi

echo "❌ All server startup methods failed."
exit 1
