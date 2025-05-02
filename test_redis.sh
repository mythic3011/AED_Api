#!/bin/bash
# Test Redis functionality in the AED API

echo "Testing Redis integration with AED API..."

# Make the first request to the API and time it
echo -e "\n1. First request (uncached):"
time curl -s "http://localhost:8000/api/v1/aeds?limit=5" | head -n 20

# Make a second request to the same endpoint (should be faster due to caching)
echo -e "\n2. Second request (should be cached):"
time curl -s "http://localhost:8000/api/v1/aeds?limit=5" | head -n 20

# Check Redis cache status
echo -e "\n3. Checking Redis cache status:"
curl -s "http://localhost:8000/api/v1/utils/redis" | python3 -m json.tool

echo -e "\n4. Testing nearby AEDs endpoint (first request, uncached):"
time curl -s "http://localhost:8000/api/v1/aeds/nearby?lat=22.3193&lng=114.1694&radius=1.0&limit=5" | head -n 20

echo -e "\n5. Testing nearby AEDs endpoint (second request, should be cached):"
time curl -s "http://localhost:8000/api/v1/aeds/nearby?lat=22.3193&lng=114.1694&radius=1.0&limit=5" | head -n 20

echo -e "\nTest complete! If the second requests were faster than the first ones, Redis caching is working correctly."
