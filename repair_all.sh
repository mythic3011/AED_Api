#!/bin/bash
# All-in-one script to fix all database and connectivity issues

echo "🛠️  AED API - All-in-One Repair Tool 🛠️"
echo "======================================"
echo ""
echo "This script will attempt to fix all common issues:"
echo "- Database authentication problems"
echo "- Connection issues"
echo "- Container configuration"
echo ""
echo "⚠️  Warning: This is a comprehensive fix that may restart services"
echo "   and briefly interrupt API availability."
echo ""

read -p "Continue with the fix? (y/n): " choice
if [[ ! "$choice" =~ ^[Yy]$ ]]; then
    echo "Operation canceled."
    exit 0
fi

echo ""
echo "🔍 Step 1: Checking services status..."
docker-compose ps

# Check if PostgreSQL container exists
if docker ps | grep -q "aed-postgres"; then
    echo "✅ PostgreSQL container exists and is running."
    postgres_running=true
else
    echo "⚠️ PostgreSQL container is not running."
    postgres_running=false
fi

# Check if API container exists
if docker ps | grep -q "aed-api"; then
    echo "✅ API container exists and is running."
    api_running=true
else
    echo "⚠️ API container is not running."
    api_running=false
fi

echo ""
echo "🔧 Step 2: Checking database connection..."
if $postgres_running; then
    docker exec aed-postgres pg_isready -U postgres
    if [ $? -eq 0 ]; then
        echo "✅ PostgreSQL is accepting connections."
        postgres_ready=true
    else
        echo "❌ PostgreSQL is not accepting connections."
        postgres_ready=false
    fi
else
    echo "❌ Cannot check PostgreSQL connection - container not running."
    postgres_ready=false
fi

echo ""
echo "🔧 Step 3: Attempting quick database authentication fix..."
if $postgres_running; then
    echo "   Resetting PostgreSQL password..."
    docker exec aed-postgres bash -c 'psql -U postgres -c "ALTER USER postgres WITH PASSWORD '\''postgres'\'';" 2>/dev/null || echo "Failed to reset password - likely authentication issue"'
fi

echo ""
echo "🔧 Step 4: Ensuring database configuration..."
# Ensure .env file exists with correct settings
echo "   Creating/updating .env file..."
cat > .env << EOF
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=db
DB_NAME=aed_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=aed_db
EOF
echo "✅ .env file updated."

echo ""
echo "🔄 Step 5: Restarting services..."
docker-compose down
echo "   Services stopped. Waiting a moment before restarting..."
sleep 3
docker-compose up -d
echo "✅ Services restarted."

echo ""
echo "🔍 Step 6: Checking service health after restart..."
sleep 5 # Wait for services to initialize

# Check if PostgreSQL is accepting connections
echo "   Testing PostgreSQL connection..."
docker exec aed-postgres pg_isready -U postgres
if [ $? -eq 0 ]; then
    echo "✅ PostgreSQL is now accepting connections."
else
    echo "❌ PostgreSQL is still having issues. You may need to reset the database volume."
    echo "   Run: ./reset_db.sh"
fi

# Check if API is able to connect to database
echo "   Testing API's database connection..."
echo "   This may take a moment..."
sleep 5 # Give API time to start up
curl -s http://localhost:8000/api/v1/utils/db-info | grep -q "connected"
if [ $? -eq 0 ]; then
    echo "✅ API is successfully connected to the database."
else
    echo "⚠️ API may still have issues connecting to the database."
    echo "   Check the API logs: docker-compose logs api"
fi

echo ""
echo "🎯 Repair process complete!"
echo "   You should now be able to use the API without authentication errors."
echo "   If problems persist, check logs with: docker-compose logs -f"
echo "   Or reset the database entirely with: ./reset_db.sh"
