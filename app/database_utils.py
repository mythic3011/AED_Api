"""
Database utility functions for error handling and connection management.

This module provides functions for handling database errors, connection retrying,
and session management to improve the resilience of database operations.
"""

import time
import logging
import functools
import re
from typing import Callable, Any, TypeVar, cast, Dict, List, Union, Optional
try:
    from sqlalchemy.exc import OperationalError, DatabaseError, SQLAlchemyError, InvalidRequestError
    from sqlalchemy.orm import Session
    from sqlalchemy import text
except ImportError:
    # For type checking and IDE support without the actual imports
    OperationalError = Exception
    DatabaseError = Exception
    SQLAlchemyError = Exception
    InvalidRequestError = Exception
    Session = object

logger = logging.getLogger("aed_api")

# Type variable for function return type
T = TypeVar('T')

# Common error messages and patterns
INVALID_INPUT_SYNTAX = "invalid input syntax"
SYNTAX_ERROR = "syntax error"
CONNECTION_CLOSED = "server closed the connection unexpectedly"
DATABASE_NOT_EXIST = "does not exist"
SQL_INJECTION_CHARS = ["'", "\"", ";", "--", "/*", "*/", "=", " OR ", " AND ", " UNION ", " SELECT ", " DROP ", " DELETE ", "\\"]

class DatabaseError(Exception):
    """Base exception for database errors"""
    pass

class ConnectionError(DatabaseError):
    """Exception for database connection errors"""
    pass

class QueryError(DatabaseError):
    """Exception for database query errors"""
    pass

class SQLInjectionError(QueryError):
    """Exception for potential SQL injection attempts"""
    def __init__(self, message=None, param_name=None, value=None):
        self.param_name = param_name
        self.value = value
        if message is None:
            if param_name:
                message = f"Potential SQL injection detected in parameter '{param_name}'"
            else:
                message = "Potential SQL injection detected"
        
        super().__init__(message)


def with_db_retry(
    max_retries: int = 3, 
    retry_interval: int = 2,
    exponential_backoff: bool = True
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to add retry logic for database operations
    
    Args:
        max_retries: Maximum number of retry attempts
        retry_interval: Base interval between retries (in seconds)
        exponential_backoff: If True, use exponential backoff for retries
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            retry_count = 0
            last_error = None
            
            while retry_count <= max_retries:
                try:
                    return func(*args, **kwargs)
                    
                except (OperationalError, DatabaseError) as e:
                    retry_count += 1
                    last_error = e
                    error_msg = str(e)
                    
                    # Log the error with appropriate level
                    if retry_count <= max_retries:
                        logger.warning(
                            f"Database operation failed (attempt {retry_count}/{max_retries}): {error_msg}"
                        )
                        
                        # Calculate wait time with optional exponential backoff
                        if exponential_backoff:
                            wait_time = retry_interval * (2 ** (retry_count - 1))
                        else:
                            wait_time = retry_interval
                            
                        logger.info(f"Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        # Log as error on final attempt
                        logger.error(
                            f"Database operation failed after {max_retries} attempts: {error_msg}"
                        )
                
            # If we get here, all retries have failed
            if isinstance(last_error, OperationalError):
                if "does not exist" in str(last_error):
                    raise ConnectionError(f"Database does not exist or is not properly set up. Please check your configuration.")
                else:
                    raise ConnectionError(f"Database connection error after {max_retries} attempts: {str(last_error)}")
            else:
                raise QueryError(f"Database query failed after {max_retries} attempts: {str(last_error)}")
                
        return cast(Callable[..., T], wrapper)
    return decorator


def check_db_connection(db: Session) -> bool:
    """
    Test if database connection is working
    
    Args:
        db: SQLAlchemy Session
        
    Returns:
        True if connection is working, False otherwise
    """
    try:
        db.execute(text("SELECT 1")).fetchone()
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {str(e)}")
        return False


def get_db_info(db: Session) -> dict:
    """
    Get database information
    
    Args:
        db: SQLAlchemy Session
        
    Returns:
        Dictionary with database information or error details
    """
    try:
        # Check connection
        result = db.execute(text("SELECT version()")).fetchone()
        version = result[0] if result else "Unknown"
        
        # Get PostGIS version if available
        try:
            postgis_result = db.execute(text("SELECT PostGIS_version()")).fetchone()
            postgis_version = postgis_result[0] if postgis_result else "Not installed"
        except:
            postgis_version = "Not installed or unavailable"
        
        return {
            "status": "connected",
            "version": version,
            "postgis_version": postgis_version
        }
        
    except SQLAlchemyError as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "error_message": str(e)
        }


def format_db_error(error: Exception) -> str:
    """
    Format a database error into a user-friendly message
    
    Args:
        error: The caught exception
        
    Returns:
        User-friendly error message
    """
    error_str = str(error)
    
    if isinstance(error, OperationalError):
        if "does not exist" in error_str:
            return "The database does not exist or has not been properly set up."
        elif "could not connect" in error_str or "connection" in error_str.lower():
            return "Could not connect to the database server. Please try again later."
        elif "timeout" in error_str.lower():
            return "Database connection timed out. Please try again later."
        elif "syntax error" in error_str.lower() or "invalid input syntax" in error_str.lower():
            return "Invalid parameter format in database query. Please check your input."
        elif "server closed the connection unexpectedly" in error_str:
            return "The database server closed the connection unexpectedly. Please try again later."
        else:
            return "A database operational error occurred. Please try again later."
    elif isinstance(error, DatabaseError):
        if "invalid input syntax" in error_str:
            return "Invalid parameter format. Please check your input values."
        elif "violates" in error_str and "constraint" in error_str:
            return "The operation could not be completed due to data constraints."
        else:
            return "A database error occurred while processing your request."
    elif isinstance(error, InvalidRequestError):
        return "Invalid database request. Please check your input parameters."
    else:
        return "An unexpected error occurred while accessing the database."


def validate_coordinate(value: Any, param_name: str) -> float:
    """
    Validate and sanitize a coordinate value
    
    Args:
        value: The value to validate
        param_name: The parameter name for error messages
        
    Returns:
        Validated float value
    
    Raises:
        ValueError: If the value is not a valid coordinate
    """
    # Check for None or empty values first
    if value is None:
        raise ValueError(f"{param_name} cannot be null or empty.")
        
    # Handle different input types
    if isinstance(value, (int, float)):
        # Direct numeric value
        float_val = float(value)
    elif isinstance(value, str):
        # First check for SQL injection attempts or invalid characters
        if any(char in value for char in ["'", "\"", ";", "--", "/*", "*/", "\\"]):
            raise ValueError(f"Invalid characters in {param_name}. Single quotes and special SQL characters are not allowed.")
            
        # String that should be convertible to float
        if not value or not re.match(r'^-?\d+(\.\d+)?$', value):
            raise ValueError(f"Invalid {param_name} format. Must be a valid number.")
            
        try:
            float_val = float(value)
        except ValueError:
            raise ValueError(f"Could not convert {param_name} to a number.")
    else:
        raise ValueError(f"Invalid {param_name} type. Must be a number.")
    
    # Check coordinate bounds
    if param_name == "latitude" and (float_val < -90 or float_val > 90):
        raise ValueError(f"Invalid latitude. Must be between -90 and 90.")
    elif param_name == "longitude" and (float_val < -180 or float_val > 180):
        raise ValueError(f"Invalid longitude. Must be between -180 and 180.")
    
    return float_val


def validate_numeric_param(value: Any, param_name: str, min_value: Optional[float] = None, 
                          max_value: Optional[float] = None) -> float:
    """
    Validate and sanitize a numeric parameter
    
    Args:
        value: The value to validate
        param_name: The parameter name for error messages
        min_value: Optional minimum allowed value
        max_value: Optional maximum allowed value
        
    Returns:
        Validated float value
    
    Raises:
        ValueError: If the value is not a valid number or out of range
    """
    # Check for None values
    if value is None:
        raise ValueError(f"{param_name} cannot be null.")
        
    # Handle different input types
    if isinstance(value, (int, float)):
        float_val = float(value)
    elif isinstance(value, str):
        # Check for potentially harmful characters
        if any(char in value for char in SQL_INJECTION_CHARS):
            raise ValueError(f"Invalid characters in {param_name}. Single quotes and special SQL characters are not allowed.")
            
        # Validate numeric format
        if not value or not re.match(r'^-?\d+(\.\d+)?$', value):
            raise ValueError(f"Invalid {param_name} format. Must be a valid number.")
        
        try:
            float_val = float(value)
        except ValueError:
            raise ValueError(f"Could not convert {param_name} to a number.")
    else:
        raise ValueError(f"Invalid {param_name} type. Must be a number.")
    
    # Validate range
    if min_value is not None and float_val < min_value:
        raise ValueError(f"{param_name} must be at least {min_value}.")
    
    if max_value is not None and float_val > max_value:
        raise ValueError(f"{param_name} must be at most {max_value}.")
    
    return float_val


def sanitize_parameters(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize and validate query parameters
    
    Args:
        params: Dictionary of parameters
        
    Returns:
        Dictionary with sanitized parameters
    
    Raises:
        ValueError: If any parameter is invalid
    """
    sanitized = {}
    
    for key, value in params.items():
        # Handle specific parameter types
        if key in ("lat", "latitude"):
            sanitized[key] = validate_coordinate(value, "latitude")
        elif key in ("lng", "longitude"):
            sanitized[key] = validate_coordinate(value, "longitude")
        elif key in ("radius", "distance"):
            sanitized[key] = validate_numeric_param(value, key, 0.01)
        elif key in ("limit", "skip", "offset"):
            # Convert to int and ensure positive
            try:
                int_val = int(value)
                if int_val < 0:
                    raise ValueError(f"{key} must be a positive integer.")
                sanitized[key] = int_val
            except (ValueError, TypeError):
                raise ValueError(f"Invalid {key}. Must be a positive integer.")
        elif isinstance(value, (int, float, bool, str)):
            # Pass through other primitive types
            sanitized[key] = value
        elif value is None:
            # Handle None values
            sanitized[key] = None
        else:
            # Reject complex objects that might be used for injection
            raise ValueError(f"Unsupported parameter type for {key}.")
    
    return sanitized


def detect_sql_injection(value: Any) -> bool:
    """
    Detect potential SQL injection attempts in a value
    
    Args:
        value: The value to check
        
    Returns:
        True if SQL injection is detected, False otherwise
    """
    if not isinstance(value, str):
        return False
    
    # Convert to lowercase for case-insensitive matching
    value_lower = value.lower()
    
    # Check for common SQL injection patterns
    for pattern in SQL_INJECTION_CHARS:
        if pattern.lower() in value_lower:
            return True
    
    # Check for more complex patterns with regular expressions
    suspicious_patterns = [
        r"(\%27)|(\')|(\-\-)|(\%23)|(#)",  # Basic SQL injection chars
        r"((\%3D)|(=))[^\n]*((\%27)|(\')|(\-\-)|(\%3B)|(\;))",  # = followed by quotes or comments
        r"\w*((\%27)|(\'))((\%6F)|o|(\%4F))((\%72)|r|(\%52))",  # 'OR pattern
        r"((\%27)|(\'))union",  # 'union
        r"exec(\s|\+)+(s|x)p\w+",  # exec sp
        r"insert|update|delete|select|create|drop|alter|truncate",  # Direct SQL commands
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, value_lower):
            return True
    
    return False


def sanitize_sql_value(value: Any, param_name: str = None) -> Any:
    """
    Sanitize a value for SQL to prevent SQL injection
    
    Args:
        value: The value to sanitize
        param_name: Optional parameter name for better error messages
        
    Returns:
        Sanitized value
        
    Raises:
        SQLInjectionError: If the value appears to be a SQL injection attempt
    """
    # Check for None first
    if value is None:
        return None
        
    # Different handling based on type
    if isinstance(value, (int, float, bool)):
        # Numeric and boolean values are safe
        return value
    elif isinstance(value, str):
        # Check for SQL injection in string
        if detect_sql_injection(value):
            logger.warning(f"Potential SQL injection attempt detected in '{param_name}': {value}")
            raise SQLInjectionError(
                message="Invalid input containing unsafe SQL characters", 
                param_name=param_name,
                value=value
            )
            
        # For strings, we'll just validate but actual sanitization happens via SQLAlchemy parameters
        return value
    else:
        # Reject complex types for safety
        raise ValueError(f"Unsupported parameter type: {type(value).__name__}")


def escape_sql_quotes(value: str) -> str:
    """
    Escape single quotes in a string for SQL safety
    
    Args:
        value: String to escape
        
    Returns:
        String with escaped quotes
    """
    if not isinstance(value, str):
        return value
        
    # Replace single quotes with double quotes for SQL safety
    return value.replace("'", "''")


def execute_spatial_query(
    db: Session,
    query_str: str,
    params: Dict[str, Any],
    max_retries: int = 3
) -> List[Any]:
    """
    Execute a spatial query with proper error handling and retries
    
    Args:
        db: Database session
        query_str: SQL query string
        params: Query parameters
        max_retries: Maximum number of retry attempts
        
    Returns:
        Query results
        
    Raises:
        HTTPException: When the query fails after retries or due to invalid parameters
    """
    # Import HTTPException here to avoid circular imports
    try:
        from fastapi import HTTPException
    except ImportError:
        # Create fallback exception for testing without FastAPI
        class HTTPException(Exception):
            def __init__(self, status_code=500, detail="Internal Server Error"):
                self.status_code = status_code
                self.detail = detail
                super().__init__(f"HTTP {status_code}: {detail}")
    
    # Validate and sanitize parameters to catch issues before hitting the database
    try:
        sanitized_params = {}
        for key, value in params.items():
            try:
                # First check for SQL injection attempts
                try:
                    sanitize_sql_value(value)
                except SQLInjectionError:
                    raise ValueError(f"Invalid characters detected in {key} parameter.")
                
                # Then apply type-specific validation
                if key == "lat" or key == "latitude":
                    sanitized_params[key] = validate_coordinate(value, "latitude")
                elif key == "lng" or key == "longitude":
                    sanitized_params[key] = validate_coordinate(value, "longitude")
                elif key == "radius":
                    sanitized_params[key] = validate_numeric_param(value, "radius", 0.01, 100.0)
                elif key == "limit":
                    sanitized_params[key] = validate_numeric_param(value, "limit", 1, 1000)
                else:
                    # For other parameters, still ensure they're safe
                    if isinstance(value, (int, float, bool)) or value is None:
                        sanitized_params[key] = value
                    elif isinstance(value, str):
                        # Simple strings get passed through but we'll check for SQL injection
                        sanitized_params[key] = value
                    else:
                        raise ValueError(f"Unsupported parameter type for {key}.")
            except ValueError as param_error:
                # Convert individual parameter errors to user-friendly message
                raise ValueError(f"Parameter '{key}': {str(param_error)}")
                
    except ValueError as e:
        # Parameter validation failed
        logger.warning(f"Parameter validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    
    # Connection retry loop
    retry_count = 0
    last_error = None
    
    while retry_count <= max_retries:
        try:
            # Test connection before executing query
            db.execute(text("SELECT 1")).fetchone()
            
            # Execute the actual query with sanitized parameters
            result = db.execute(text(query_str), sanitized_params).fetchall()
            return result
            
        except (OperationalError, DatabaseError) as e:
            retry_count += 1
            last_error = e
            error_str = str(e)
            logger.error(f"Database error in spatial query: {error_str}")
            
            # Check for syntax errors that likely indicate parameter issues
            if SYNTAX_ERROR in error_str.lower() or INVALID_INPUT_SYNTAX in error_str.lower():
                logger.error(f"SQL syntax error with parameters: {sanitized_params}")
                raise HTTPException(
                    status_code=400,
                    detail="Invalid parameter format. Please check your input values."
                )
            
            # Only retry for connection issues
            if CONNECTION_CLOSED in error_str or "connection" in error_str.lower():
                if retry_count <= max_retries:
                    wait_time = 2 ** (retry_count - 1)  # 1s, 2s, 4s
                    logger.info(f"Retrying database query in {wait_time}s (attempt {retry_count}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
            
            # If we've run out of retries or it's not a connection issue
            user_friendly_error = format_db_error(e)
            status_code = 503 if "connection" in error_str.lower() else 500
            raise HTTPException(status_code=status_code, detail=user_friendly_error)
                
        except Exception as e:
            # Handle non-database errors
            logger.error(f"Non-database error in spatial query: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="An unexpected error occurred while processing your request."
            )
    
    # This should never be reached, but just in case
    if last_error:
        raise HTTPException(
            status_code=503,
            detail="Database service unavailable. Please try again later."
        )
        
    return []
