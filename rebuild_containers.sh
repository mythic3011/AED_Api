#!/bin/bash
# Script to rebuild Docker containers with latest changes

echo "🔄 Rebuilding and restarting Docker containers..."

# Stop running containers
echo "Stopping running containers..."
docker-compose down

# Build the containers with no cache to ensure fresh dependencies
echo "Building containers..."
docker-compose build --no-cache

# Start the containers
echo "Starting containers..."
docker-compose up -d

# Show logs
echo "✅ Containers rebuilt and started. Showing logs..."
docker-compose logs -f
