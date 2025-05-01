#!/bin/bash
# Script to fix PostgreSQL authentication issues

echo "This will attempt to fix PostgreSQL authentication issues by resetting the password"

# Step 1: Restart the database container
echo "Step 1: Restarting PostgreSQL container..."
docker-compose restart db
sleep 5

# Step 2: Copy the reset script into the container
echo "Step 2: Copying reset script to container..."
docker cp reset_postgres_password.sh aed-postgres:/tmp/reset_postgres_password.sh
docker exec aed-postgres chmod +x /tmp/reset_postgres_password.sh

# Step 3: Execute the reset script inside the container
echo "Step 3: Resetting PostgreSQL password..."
docker exec -e POSTGRES_PASSWORD=postgres aed-postgres /tmp/reset_postgres_password.sh

# Step 4: Restart the API container
echo "Step 4: Restarting API container..."
docker-compose restart api

echo "Done! Check the logs with: docker-compose logs -f"
