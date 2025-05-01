#!/bin/bash
# Script to reset the database and volumes if authentication fails

echo "This script will reset your database and volumes to fix authentication issues"
echo "WARNING: This will delete all existing data in your database!"
read -p "Are you sure you want to continue? (y/N) " -n 1 -r
echo    # Move to a new line

if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Operation cancelled."
    exit 1
fi

echo "Stopping all containers..."
docker-compose down

echo "Removing postgres volume..."
docker volume rm enrichment_postgres_data

echo "Starting fresh containers..."
docker-compose up -d

echo "Database reset complete. The API should now be able to connect to the database."
echo "Check the logs to confirm with: docker-compose logs -f"
