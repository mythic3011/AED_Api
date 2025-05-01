#!/bin/bash
set -e

# Function to check if database is available
check_database() {
  echo "Checking database connection..."
  python -c "
import sys
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
import os

# Get DB connection details
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'postgres')
DB_HOST = os.environ.get('DB_HOST', 'db')
DB_NAME = os.environ.get('DB_NAME', 'aed_db')

DATABASE_URL = os.environ.get('DATABASE_URL', f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}')

try:
    engine = create_engine(DATABASE_URL)
    connection = engine.connect()
    connection.close()
    print('Database connection successful')
    sys.exit(0)
except OperationalError as e:
    error_str = str(e)
    
    # Check for specific errors and provide helpful messages
    if 'does not exist' in error_str:
        print('ERROR: Database does not exist')
        sys.exit(2)
    elif 'could not connect' in error_str or 'connection' in error_str.lower():
        print('ERROR: Could not connect to database server')
        sys.exit(1)
    else:
        print(f'ERROR: Database error - {error_str}')
        sys.exit(3)
except Exception as e:
    print(f'ERROR: Unexpected error - {str(e)}')
    sys.exit(4)
"
  return $?
}

# Function to create database if it doesn't exist
setup_database() {
  echo "Setting up database..."
  PGPASSWORD=$POSTGRES_SUPERUSER_PASSWORD psql -h $DB_HOST -U $POSTGRES_SUPERUSER -c "CREATE DATABASE $DB_NAME;"
  PGPASSWORD=$POSTGRES_SUPERUSER_PASSWORD psql -h $DB_HOST -U $POSTGRES_SUPERUSER -d $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS postgis;"
  echo "Database $DB_NAME created successfully"
}

# Maximum number of retries
MAX_RETRIES=5
RETRY_COUNTER=0

# Check if database exists, retry with exponential backoff if connection fails
while [ $RETRY_COUNTER -lt $MAX_RETRIES ]; do
  check_database
  RESULT=$?
  
  if [ $RESULT -eq 0 ]; then
    echo "Database is ready."
    break
  elif [ $RESULT -eq 2 ]; then
    echo "Database does not exist. Setting up..."
    setup_database
    # Verify setup was successful
    check_database
    if [ $? -ne 0 ]; then
      echo "Failed to create database. Exiting."
      exit 1
    fi
    break
  elif [ $RESULT -eq 1 ]; then
    # Connection error, retry with backoff
    RETRY_COUNTER=$((RETRY_COUNTER+1))
    SLEEP_TIME=$((2**RETRY_COUNTER))
    echo "Connection failed. Retrying in $SLEEP_TIME seconds (attempt $RETRY_COUNTER/$MAX_RETRIES)"
    sleep $SLEEP_TIME
  else
    # Other errors, exit
    echo "Database setup failed with error $RESULT. Exiting."
    exit 1
  fi
done

if [ $RETRY_COUNTER -eq $MAX_RETRIES ]; then
  echo "Failed to connect to database after $MAX_RETRIES attempts. Exiting."
  exit 1
fi

# Start the application
echo "Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 ${@}
