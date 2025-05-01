#!/bin/bash
# Script to fix PostgreSQL password authentication issues in Docker containers

echo "🔧 PostgreSQL Authentication Fix Tool 🔧"
echo "========================================"
echo ""
echo "This script will fix the 'password authentication failed' error"
echo "for PostgreSQL in your Docker containers."
echo ""

# Function to check if Docker is running
check_docker() {
    docker info >/dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "❌ Error: Docker is not running. Please start Docker and try again."
        exit 1
    fi
}

# Check if containers are running
check_containers() {
    docker ps | grep aed-postgres >/dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "⚠️ PostgreSQL container not found or not running."
        echo "   Attempting to start containers..."
        docker-compose up -d
        sleep 5
    fi
}

# Main fix function
fix_authentication() {
    echo "🔍 Checking PostgreSQL container..."
    check_docker
    check_containers
    
    echo "🔄 Stopping all services..."
    docker-compose stop
    
    echo "🔄 Starting only the database container..."
    docker-compose up -d db
    sleep 5
    
    echo "🔧 Attempting to access PostgreSQL with default settings..."
    # Try to connect with default superuser access
    docker exec aed-postgres psql -U postgres -c "SELECT 1" >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "✅ Successfully connected to PostgreSQL!"
        echo "🔧 Resetting password..."
        
        # Reset the user password
        docker exec aed-postgres psql -U postgres -c "ALTER USER postgres WITH PASSWORD 'postgres';" >/dev/null 2>&1
        if [ $? -eq 0 ]; then
            echo "✅ Password reset successful!"
        else
            echo "❌ Failed to reset password."
        fi
    else
        echo "❌ Could not connect to PostgreSQL with default credentials."
        echo "   Attempting recovery mode connection..."
        
        # Stop the container
        docker-compose stop db
        
        # Start with custom command to allow trust authentication temporarily
        echo "🔄 Starting PostgreSQL with trust authentication..."
        docker run --rm -d \
            --name pg_temp \
            --network enrichment_aed-network \
            -e POSTGRES_PASSWORD=postgres \
            -v enrichment_postgres_data:/var/lib/postgresql/data \
            postgis/postgis:14-3.2 \
            -c hba_file=/tmp/pg_hba.conf
        
        # Create a temporary pg_hba.conf with trust auth
        docker exec pg_temp bash -c 'echo "local all postgres trust" > /tmp/pg_hba.conf'
        docker exec pg_temp bash -c 'echo "host all postgres all trust" >> /tmp/pg_hba.conf'
        
        sleep 5
        
        # Try to connect and reset password
        echo "🔧 Attempting to reset password in recovery mode..."
        docker exec pg_temp psql -U postgres -c "ALTER USER postgres WITH PASSWORD 'postgres';" >/dev/null 2>&1
        if [ $? -eq 0 ]; then
            echo "✅ Password reset successful!"
        else
            echo "❌ Failed to reset password in recovery mode."
        fi
        
        # Clean up
        docker stop pg_temp
    fi
    
    echo "🔄 Restarting all services..."
    docker-compose up -d
    
    echo "✅ Done! Authentication issues should be fixed."
    echo "   Check logs with: docker-compose logs -f"
}

# Execute the fix
fix_authentication
