# Database Error Handling

This document describes the database error handling approach implemented in the AED Location API project.

## Overview

Database errors can occur for various reasons, including:

- Connection issues (server not available, network problems)
- Database does not exist
- Connection closed unexpectedly
- Invalid input syntax (often caused by SQL injection attempts)
- Constraint violations
- Other PostgreSQL-specific errors

Our approach focuses on:

1. **Preventing errors** with robust parameter validation
2. **Detecting errors early** with connection testing
3. **Handling errors gracefully** to provide helpful feedback
4. **Retrying operations** when appropriate
5. **Logging** for diagnosability

## Key Components

### Database Utils Module

The `app/database_utils.py` module provides:

- **Parameter validation functions** to sanitize inputs:

  - `validate_coordinate()` - Ensures latitude/longitude are valid
  - `validate_numeric_param()` - Validates numeric parameters
  - `sanitize_parameters()` - Validates a map of parameters

- **SQL injection protection**:

  - `detect_sql_injection()` - Checks for SQL injection patterns
  - `sanitize_sql_value()` - Ensures values are safe for SQL

- **Error formatting**:

  - `format_db_error()` - Converts technical error messages to user-friendly ones

- **Query execution with retries**:

  - `execute_spatial_query()` - Handles PostGIS queries with appropriate error handling

- **Retry decorator**:
  - `with_db_retry()` - Adds retry functionality to any database operation

### Exception Handling

The application implements exception handlers for different database errors:

- **OperationalError** - Connection issues, syntax errors
- **DatabaseError** - General database problems
- **SQLInjectionError** - Detected injection attempts
- **ConnectionError** - Custom error for connection problems
- **QueryError** - Custom error for query issues

### Database Connection Management

The `get_db()` dependency:

- Tests connections before providing them to endpoints
- Tracks connection errors to inform endpoints
- Ensures connection cleanup even on errors

## Error Response Structure

Error responses follow this structure:

```json
{
  "detail": "User-friendly error message",
  "type": "error_type",
  "request_id": "unique-request-id"
}
```

HTTP status codes are used meaningfully:

- **400** - Bad Request (invalid parameters)
- **503** - Service Unavailable (database connection issues)
- **500** - Internal Server Error (unexpected errors)

## Retry Strategy

The retry strategy follows these principles:

1. Only retry for connection issues
2. Use exponential backoff (1s, 2s, 4s)
3. Limited to 3 attempts by default
4. Don't retry for input validation or syntax errors

## Implementation Guidelines

When implementing new database operations:

1. Use the `execute_spatial_query()` function for spatial queries
2. Use `validate_coordinate()` and `validate_numeric_param()` for input validation
3. Apply the `with_db_retry()` decorator to functions that perform database operations
4. Catch database exceptions and use `format_db_error()` to provide user-friendly messages
5. For complex operations, consider database transactions with try/except/finally

## Example Usage

Here's how to use these utilities in a route function:

```python
@router.get("/example", response_model=Dict[str, Any])
async def example_function(
    request: Request,
    lat: float,
    lng: float,
    db: Session = Depends(get_db)
):
    from app.database_utils import execute_spatial_query

    try:
        # Build query
        query_str = """
            SELECT * FROM table
            WHERE ST_DWithin(
                geo_point::geography,
                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                1000
            )
        """

        # Params will be validated and sanitized
        params = {"lat": lat, "lng": lng}

        # Execute with retry logic and error handling
        result = execute_spatial_query(db, query_str, params)

        # Process results...
        return {"data": result}

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Unexpected error")
```
