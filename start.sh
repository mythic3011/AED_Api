#!/bin/bash

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
until PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c '\q'; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 1
done

echo "PostgreSQL is up - executing migration script"

# Run the migration script
python db_migration.py

# Start the API server
echo "Starting FastAPI application..."
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
