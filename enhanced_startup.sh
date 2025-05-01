#!/bin/bash
# Enhanced startup script that handles PostgreSQL authentication issues

echo "Starting AED API with enhanced database connectivity checks..."

# Source environment variables if they exist
if [ -f .env ]; then
    echo "Loading environment variables from .env"
    source .env
fi

# Get database connection parameters
DB_HOST="${DB_HOST:-db}"
DB_NAME="${DB_NAME:-aed_db}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-postgres}"

# Configure PostgreSQL client authentication
export PGHOST=$DB_HOST
export PGUSER=$DB_USER
export PGPASSWORD=$DB_PASSWORD
export PGDATABASE=$DB_NAME

echo "🔄 Checking PostgreSQL connection at $DB_HOST..."

# Connection check parameters
MAX_RETRIES=30
RETRY_INTERVAL=5
RETRY_COUNT=0

# Function to check if PostgreSQL is ready
check_postgres() {
    psql -c "SELECT 1" >/dev/null 2>&1
    return $?
}

# Wait for PostgreSQL to be ready
while ! check_postgres; do
    RETRY_COUNT=$((RETRY_COUNT+1))
    
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "❌ Failed to connect to PostgreSQL after $MAX_RETRIES attempts."
        echo "   Attempting to reset PostgreSQL authentication..."
        
        # Try to reset PostgreSQL authentication
        if [ -f ./reset_postgres_password.sh ]; then
            echo "   Running password reset script..."
            # We need to copy and run it inside the PostgreSQL container
            # But since we're inside a container ourselves, we can't use docker commands
            # Instead, we'll modify our connection approach
            
            echo "   Trying alternative connection methods..."
            # Try connection with trust authentication
            PGPASSWORD="" psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT 1" >/dev/null 2>&1
            if [ $? -eq 0 ]; then
                echo "   Connected with trust authentication, attempting to reset password..."
                PGPASSWORD="" psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "ALTER USER postgres WITH PASSWORD '$DB_PASSWORD';" >/dev/null 2>&1
                if [ $? -eq 0 ]; then
                    echo "   ✅ Password reset successful!"
                    export PGPASSWORD=$DB_PASSWORD
                    check_postgres && { echo "   ✅ Connection verified with new password!"; break; }
                fi
            fi
        fi
        
        echo "❌ Unable to establish database connection. API will likely fail."
        echo "   Please check your database configuration and ensure PostgreSQL is running."
        echo "   You may need to reset the database with ./reset_db.sh or ./fix_auth.sh"
        
        # Continue anyway - this allows the API to start and provide proper error messages
        # rather than failing completely on startup
        break
    fi
    
    echo "⏳ PostgreSQL is not ready yet. Waiting $RETRY_INTERVAL seconds... (Attempt $RETRY_COUNT/$MAX_RETRIES)"
    sleep $RETRY_INTERVAL
done

# If we successfully connected, ensure the PostGIS extension is created
if check_postgres; then
    echo "✅ Successfully connected to PostgreSQL!"
    
    # Check if PostGIS extension exists
    psql -c "SELECT extname FROM pg_extension WHERE extname='postgis';" | grep -q postgis
    if [ $? -ne 0 ]; then
        echo "🔄 Creating PostGIS extension..."
        psql -c "CREATE EXTENSION IF NOT EXISTS postgis;" >/dev/null 2>&1
        if [ $? -eq 0 ]; then
            echo "✅ PostGIS extension created successfully!"
        else
            echo "⚠️ Failed to create PostGIS extension. Spatial queries may not work correctly."
        fi
    else
        echo "✅ PostGIS extension is already installed."
    fi
fi

# Clear PostgreSQL environment variables to avoid leaking credentials
unset PGPASSWORD

echo "🚀 Starting API server..."

# Check if gunicorn is available
echo "Checking for gunicorn in PATH..."
which gunicorn || echo "gunicorn not found in PATH"
echo "Current PATH: $PATH"

# Make sure gunicorn is installed and in the PATH
echo "Installing gunicorn and ensuring it's in PATH..."
pip install --no-cache-dir gunicorn

# Find gunicorn executable location
GUNICORN_PATH=$(python -c "import sys; import os; print(os.path.join(os.path.dirname(sys.executable), 'gunicorn'))")
echo "Expected gunicorn path: $GUNICORN_PATH"

if [ -f "$GUNICORN_PATH" ]; then
    echo "✅ Found gunicorn at $GUNICORN_PATH"
    echo "Starting with gunicorn..."
    # List all available packages for debugging
    echo "Installed packages:"
    pip list | grep -E "gunicorn|uvicorn|fastapi"
    
    # Start the application with direct path to gunicorn
    exec $GUNICORN_PATH app.main:app -w ${GUNICORN_WORKERS:-4} -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${PORT:-8000} --timeout ${GUNICORN_TIMEOUT:-120}
else
    echo "⚠️ gunicorn not found at expected path, falling back to uvicorn..."
    echo "Installing uvicorn as fallback..."
    pip install --no-cache-dir uvicorn
    
    # Fallback to uvicorn if gunicorn is not available
    echo "Starting with uvicorn..."
    exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
