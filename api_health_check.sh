#!/bin/bash
# Health check script for the AED API

# Default endpoint to check
HEALTH_ENDPOINT=${HEALTH_ENDPOINT:-"http://localhost:8000/api/v1/health"}

# Function to check if the API is responding
check_api() {
  # Try to access the health check endpoint
  response=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_ENDPOINT)
  
  if [ "$response" == "200" ]; then
    echo "✅ API is healthy (status 200)"
    exit 0
  else
    echo "❌ API health check failed with status: $response"
    # Try the root endpoint
    root_response=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/")
    
    if [ "$root_response" == "200" ] || [ "$root_response" == "307" ]; then
      echo "✅ API root endpoint is responding (status $root_response)"
      exit 0
    else
      echo "❌ API root endpoint check failed with status: $root_response"
      exit 1
    fi
  fi
}

# Run the API check
check_api
