#!/bin/bash
# rebuild_docker.sh - Script to stop, fix line endings, rebuild, and restart Docker containers

echo "Stopping containers..."
docker-compose down

echo "Converting shell scripts to UNIX format..."
find . -name "*.sh" -type f -exec dos2unix {} \;

echo "Making scripts executable..."
chmod +x *.sh

echo "Rebuilding containers with no cache..."
docker-compose build --no-cache

echo "Starting containers..."
docker-compose up -d

echo "Tailing logs from aed-api container..."
docker-compose logs -f api
