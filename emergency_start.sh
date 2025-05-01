#!/bin/bash
# Emergency fallback script to install required packages and start the API server

echo "🚨 EMERGENCY FALLBACK SCRIPT 🚨"
echo "This script is used when normal startup methods fail."
echo "It will install required packages and start the API server."

# Install required packages
echo "📦 Installing required packages..."
pip install --no-cache-dir gunicorn uvicorn fastapi

# Check PostgreSQL connection
echo "🔄 Checking PostgreSQL connection..."

# Get database connection parameters from environment variables
DB_HOST="${DB_HOST:-db}"
DB_NAME="${DB_NAME:-aed_db}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-postgres}"

# Configure PostgreSQL client authentication
export PGHOST=$DB_HOST
export PGUSER=$DB_USER
export PGPASSWORD=$DB_PASSWORD
export PGDATABASE=$DB_NAME

# Test the connection
echo "Testing PostgreSQL connection..."
if psql -c "SELECT 1" >/dev/null 2>&1; then
    echo "✅ PostgreSQL connection successful!"
else
    echo "⚠️ PostgreSQL connection failed. The API may not work correctly."
fi

# Clear PostgreSQL environment variables to avoid leaking credentials
unset PGPASSWORD

# Install any potentially missing packages
pip install fastapi uvicorn gunicorn SQLAlchemy psycopg2-binary geoalchemy2 pydantic

# Start the server
echo "🚀 Starting API server..."
echo "Trying gunicorn first..."

# Set default port
PORT=${PORT:-8000}

# Try starting with gunicorn
if command -v gunicorn &> /dev/null; then
    echo "Using gunicorn..."
    # First attempt with standard settings
    gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT || {
        echo "Basic gunicorn startup failed, trying simplified configuration..."
        # Try simpler settings without worker class
        gunicorn app.main:app -w 1 -b 0.0.0.0:$PORT || {
            echo "Simplified gunicorn startup failed, falling back to uvicorn..."
            if command -v uvicorn &> /dev/null; then
                uvicorn app.main:app --host 0.0.0.0 --port $PORT
            else
                echo "❌ All server startup methods failed!"
                exit 1
            fi
        }
    }
elif command -v uvicorn &> /dev/null; then
    echo "Gunicorn not found, using uvicorn..."
    uvicorn app.main:app --host 0.0.0.0 --port $PORT
else
    echo "❌ Neither gunicorn nor uvicorn is available."
    echo "Installing uvicorn as last resort..."
    pip install --no-cache-dir uvicorn
    
    if command -v uvicorn &> /dev/null; then
        echo "Starting with freshly installed uvicorn..."
        uvicorn app.main:app --host 0.0.0.0 --port $PORT
    else
        echo "❌ Failed to install and start any server. Cannot continue."
        exit 1
    fi
fi
