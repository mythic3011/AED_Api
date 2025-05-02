#!/bin/bash
# Health check script for the AED API

# Default endpoint to check
HEALTH_ENDPOINT=${HEALTH_ENDPOINT:-"http://localhost:8000/api/v1/health"}

# Function to check if the Redis service is available
check_redis() {
  # Check if redis-cli is available
  if command -v redis-cli &> /dev/null; then
    # Try to ping the Redis server
    REDIS_HOST=${REDIS_HOST:-"redis"}
    REDIS_PORT=${REDIS_PORT:-"6379"}
    
    if redis-cli -h $REDIS_HOST -p $REDIS_PORT ping | grep -q "PONG"; then
      echo "✅ Redis is responding (PONG)"
      return 0
    else
      echo "❌ Redis health check failed"
      return 1
    fi
  else
    echo "⚠️ redis-cli not found, skipping Redis health check"
    return 0  # Return success even if we can't check Redis
  fi
}

# Function to check if the API is responding
check_api() {
  # Try to access the health check endpoint
  response=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_ENDPOINT)
  
  if [ "$response" == "200" ]; then
    echo "✅ API is healthy (status 200)"
    return 0
  else
    echo "❌ API health check failed with status: $response"
    # Try the root endpoint
    root_response=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/")
    
    if [ "$root_response" == "200" ] || [ "$root_response" == "307" ]; then
      echo "✅ API root endpoint is responding (status $root_response)"
      return 0
    else
      echo "❌ API root endpoint check failed with status: $root_response"
      return 1
    fi
  fi
}

# Run the health checks
check_api
API_STATUS=$?

# For Docker health checks, we only care about the API status
# Redis is optional for the app to function
exit $API_STATUS
