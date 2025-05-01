# AED Report Management API

This documentation covers the endpoints for managing AED (Automated External Defibrillator) reports in the system.

## Report Endpoints

### List All Reports

```
GET /api/v1/reports/
```

Retrieves a paginated list of AED reports with optional filtering.

**Query Parameters:**

- `skip` (integer): Number of records to skip (for pagination). Default: 0
- `limit` (integer): Maximum number of records to return. Default: 50
- `report_type` (string): Filter by report type. Options: "damaged", "missing", "incorrect_info", "other"
- `status` (string): Filter by report status. Options: "pending", "investigating", "resolved", "rejected"

**Response:**

```json
{
  "data": [
    {
      "id": 1,
      "aed_id": 123,
      "report_type": "damaged",
      "description": "The AED unit appears to be damaged",
      "reporter_name": "Jane Doe",
      "reporter_email": "jane@example.com",
      "reporter_phone": "123-456-7890",
      "created_at": "2025-05-02T10:30:00.000Z",
      "status": "pending"
    }
    // ... more reports
  ],
  "pagination": {
    "total": 42,
    "limit": 10,
    "offset": 0,
    "next": "/api/v1/reports?skip=10&limit=10",
    "prev": null
  },
  "metadata": {
    "request_id": "uuid-here",
    "timestamp": "2025-05-02T10:30:00.000Z"
  }
}
```

### Create New Report

```
POST /api/v1/reports/
```

Creates a new AED report in the system.

**Request Body:**

```json
{
  "aed_id": 123,
  "report_type": "damaged", // Must be one of: "damaged", "missing", "incorrect_info", "other"
  "description": "The AED unit appears to be damaged",
  "reporter_name": "Jane Doe", // Optional
  "reporter_email": "jane@example.com", // Optional, must be valid email
  "reporter_phone": "123-456-7890" // Optional
}
```

**Response:**

```json
{
  "id": 1,
  "aed_id": 123,
  "report_type": "damaged",
  "description": "The AED unit appears to be damaged",
  "reporter_name": "Jane Doe",
  "reporter_email": "jane@example.com",
  "reporter_phone": "123-456-7890",
  "created_at": "2025-05-02T10:30:00.000Z",
  "status": "pending"
}
```

### Get Report by ID

```
GET /api/v1/reports/{report_id}
```

Retrieves a specific AED report by its ID.

**Path Parameters:**

- `report_id` (integer): The ID of the report to retrieve

**Response:**

```json
{
  "id": 1,
  "aed_id": 123,
  "report_type": "damaged",
  "description": "The AED unit appears to be damaged",
  "reporter_name": "Jane Doe",
  "reporter_email": "jane@example.com",
  "reporter_phone": "123-456-7890",
  "created_at": "2025-05-02T10:30:00.000Z",
  "status": "pending"
}
```

### Update Report Status

```
PUT /api/v1/reports/{report_id}/status
```

Updates the status of an existing AED report.

**Path Parameters:**

- `report_id` (integer): The ID of the report to update

**Request Body:**

```json
{
  "status": "investigating" // Must be one of: "pending", "investigating", "resolved", "rejected"
}
```

**Response:**

```json
{
  "id": 1,
  "aed_id": 123,
  "report_type": "damaged",
  "description": "The AED unit appears to be damaged",
  "reporter_name": "Jane Doe",
  "reporter_email": "jane@example.com",
  "reporter_phone": "123-456-7890",
  "created_at": "2025-05-02T10:30:00.000Z",
  "status": "investigating"
}
```

### Delete Report

```
DELETE /api/v1/reports/{report_id}
```

Deletes an AED report from the system.

**Path Parameters:**

- `report_id` (integer): The ID of the report to delete

**Response:**

- Status code 204 (No Content) if successful, with no body

### Get Report Statistics

```
GET /api/v1/reports/stats
```

Retrieves summary statistics about AED reports.

**Response:**

```json
{
  "total_reports": 42,
  "by_status": {
    "pending": 15,
    "investigating": 10,
    "resolved": 12,
    "rejected": 5
  },
  "by_type": {
    "damaged": 18,
    "missing": 7,
    "incorrect_info": 12,
    "other": 5
  },
  "metadata": {
    "request_id": "uuid-here",
    "timestamp": "2025-05-02T10:30:00.000Z"
  }
}
```

## Status Codes

- `200 OK`: The request was successful
- `201 Created`: A new resource was successfully created
- `204 No Content`: The request was successful but no response body is needed
- `400 Bad Request`: The request is malformed or contains invalid parameters
- `404 Not Found`: The requested resource was not found
- `422 Unprocessable Entity`: The request body contains invalid data
- `500 Internal Server Error`: An unexpected server error occurred
