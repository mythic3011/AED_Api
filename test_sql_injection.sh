#!/bin/bash
# Test script to verify SQL injection prevention

echo "Running SQL injection prevention tests..."

# Setup API URL
API_URL="http://localhost:8000/api/v1"

# Function to test a parameter
test_param() {
    endpoint="$1"
    param_name="$2"
    param_value="$3"
    expected_code="$4"
    
    echo -e "\n[TEST] Testing $param_name=$param_value on $endpoint"
    
    # URL encode the parameter value
    encoded_value=$(python -c "import urllib.parse; print(urllib.parse.quote('''$param_value'''))")
    
    # Make the request
    status=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL$endpoint?$param_name=$encoded_value")
    
    if [ "$status" -eq "$expected_code" ]; then
        echo "✅ PASSED: Got expected status code $status"
    else
        echo "❌ FAILED: Expected status $expected_code but got $status"
    fi
}

# 1. Test valid coordinates
echo -e "\n=============== Testing Valid Inputs ==============="
test_param "/aeds/nearby" "lat" "22.29" 200
test_param "/aeds/nearby" "lng" "114.17" 200
test_param "/aeds/nearby" "radius" "1.5" 200

# 2. Test invalid coordinates (out of bounds)
echo -e "\n=============== Testing Invalid Values ==============="
test_param "/aeds/nearby" "lat" "100" 400
test_param "/aeds/nearby" "lng" "200" 400
test_param "/aeds/nearby" "radius" "-1" 400

# 3. Test SQL injection attempts
echo -e "\n=============== Testing SQL Injection Attempts ==============="
test_param "/aeds/nearby" "lat" "22.29'; DROP TABLE aeds; --" 400
test_param "/aeds/nearby" "lng" "114.17 OR 1=1" 400
test_param "/aeds/nearby" "radius" "1.5; SELECT * FROM users" 400
test_param "/aeds/nearby" "lat" "22.29' UNION SELECT username, password FROM users --" 400

echo -e "\n=============== Test Summary ==============="
echo "All tests completed. Check results above for any failures."
