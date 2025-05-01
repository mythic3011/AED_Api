#!/bin/bash
# Test script to verify AED report management endpoints

echo "Running AED Report API tests..."

# Setup API URL
API_URL="http://localhost:8000/api/v1"

# Test submission with valid data (should succeed)
echo -e "\n===== Testing Report Creation with Valid Data ====="
REPORT_ID=$(curl -s -X POST \
  "$API_URL/reports/" \
  -H "Content-Type: application/json" \
  -d '{
    "aed_id": 1,
    "report_type": "missing",
    "description": "The AED unit appears to be missing from its marked location",
    "reporter_name": "Test User",
    "reporter_email": "test@example.com",
    "reporter_phone": "123-456-7890"
  }' | grep -o '"id":[0-9]*' | cut -d':' -f2)

if [ -z "$REPORT_ID" ]; then
  echo "❌ FAILED: Could not create report"
  exit 1
else
  echo "✅ PASSED: Successfully created report with ID: $REPORT_ID"
fi

# Test submission with invalid report type (should fail)
echo -e "\n===== Testing Report Creation with Invalid Type ====="
STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST \
  "$API_URL/reports/" \
  -H "Content-Type: application/json" \
  -d '{
    "aed_id": 1,
    "report_type": "invalid_type_here",
    "description": "This should fail validation"
  }')

if [ "$STATUS_CODE" -eq 422 ] || [ "$STATUS_CODE" -eq 400 ]; then
  echo "✅ PASSED: Server correctly rejected invalid report type with status $STATUS_CODE"
else
  echo "❌ FAILED: Server did not reject invalid report type. Got status $STATUS_CODE"
fi

# Test fetching the report by ID
echo -e "\n===== Testing Report Retrieval ====="
if [ -n "$REPORT_ID" ]; then
  STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X GET \
    "$API_URL/reports/$REPORT_ID")
    
  if [ "$STATUS_CODE" -eq 200 ]; then
    echo "✅ PASSED: Successfully retrieved report with ID: $REPORT_ID"
  else
    echo "❌ FAILED: Could not retrieve report. Got status $STATUS_CODE"
  fi
fi

# Test updating report status
echo -e "\n===== Testing Report Status Update ====="
if [ -n "$REPORT_ID" ]; then
  STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X PUT \
    "$API_URL/reports/$REPORT_ID/status" \
    -H "Content-Type: application/json" \
    -d '{"status": "investigating"}')
    
  if [ "$STATUS_CODE" -eq 200 ]; then
    echo "✅ PASSED: Successfully updated report status"
  else
    echo "❌ FAILED: Failed to update report status. Got status $STATUS_CODE"
  fi
fi

# Test fetching report statistics
echo -e "\n===== Testing Report Statistics ====="
STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X GET \
  "$API_URL/reports/stats")
  
if [ "$STATUS_CODE" -eq 200 ]; then
  echo "✅ PASSED: Successfully retrieved report statistics"
else
  echo "❌ FAILED: Failed to retrieve report statistics. Got status $STATUS_CODE"
fi

# Test fetching all reports
echo -e "\n===== Testing Report Listing ====="
STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X GET \
  "$API_URL/reports/")
  
if [ "$STATUS_CODE" -eq 200 ]; then
  echo "✅ PASSED: Successfully retrieved report listing"
else
  echo "❌ FAILED: Failed to retrieve report listing. Got status $STATUS_CODE"
fi

# Test cleanup - delete the test report
echo -e "\n===== Testing Report Deletion ====="
if [ -n "$REPORT_ID" ]; then
  STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X DELETE \
    "$API_URL/reports/$REPORT_ID")
    
  if [ "$STATUS_CODE" -eq 204 ]; then
    echo "✅ PASSED: Successfully deleted report"
  else
    echo "❌ FAILED: Failed to delete report. Got status $STATUS_CODE"
  fi
fi

echo -e "\n===== All Tests Completed ====="
