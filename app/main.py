import os
import time
import uuid
import logging
import requests
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException, Depends, Request, Security, BackgroundTasks
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, DatabaseError, SQLAlchemyError
from sqlalchemy import text, func
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache
from app.database import get_db, setup_postgis, SessionLocal, AEDModel
from app.utils import headers, url
from app.routes import aeds, reports
from app.database_utils import SQLInjectionError, ConnectionError as DBConnectionError, QueryError
from app.redis_utils import redis_client, is_redis_available

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("aed_api")

# Initialize FastAPI app
app = FastAPI(
    title="AED Location API",
    description="API to retrieve and report Automated External Defibrillator (AED) locations in Hong Kong",
    version="1.0.0",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
)

# Set up CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Simple rate limiting implementation
class RateLimiter:
    def __init__(self, requests_per_minute=60):
        self.requests_per_minute = requests_per_minute
        self.request_history = {}
        
    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        # Clean old requests
        self.clean_old_requests(now)
        
        # Check if client has history
        if client_ip not in self.request_history:
            self.request_history[client_ip] = [now]
            return True
            
        # Add request to history
        self.request_history[client_ip].append(now)
        
        # Check if limit exceeded
        return len(self.request_history[client_ip]) <= self.requests_per_minute
        
    def clean_old_requests(self, now: float):
        # Remove requests older than 1 minute
        cutoff = now - 60
        for ip, requests in list(self.request_history.items()):
            self.request_history[ip] = [r for r in requests if r > cutoff]
            if not self.request_history[ip]:
                del self.request_history[ip]

rate_limiter = RateLimiter()

# API Key security setup
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# In a real production app, these would be stored securely in a database
API_KEYS = {
    "public": {"tier": "basic", "rate_limit": 100},
    "demo_key_123": {"tier": "standard", "rate_limit": 1000},
    "premium_key_456": {"tier": "premium", "rate_limit": 5000}
}

def get_api_key(api_key: str = Security(api_key_header)) -> dict:
    if api_key in API_KEYS:
        return {"key": api_key, **API_KEYS[api_key]}
    # For demo purposes, allow access with a warning message
    return {"key": "demo", "tier": "basic", "rate_limit": 20}

# Request middleware for logging, rate limiting and versioning
@app.middleware("http")
async def api_middleware(request: Request, call_next):
    # Start timer
    start_time = time.time()
    
    # Generate request ID for tracing
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    # Extract client IP for rate limiting
    client_ip = request.client.host
    
    # Check rate limit
    if not rate_limiter.is_allowed(client_ip):
        logger.warning(f"Rate limit exceeded for {client_ip}")
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Please try again later."}
        )
    
    # Process the request
    try:
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)
        
        # Log request details
        logger.info(f"RequestID: {request_id} | Method: {request.method} | Path: {request.url.path} | Time: {process_time:.3f}s")
        
        return response
    except Exception as e:
        logger.error(f"RequestID: {request_id} | Error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id}
        )

# Create PostGIS extension before other operations
setup_postgis()

# Include routes
app.include_router(aeds.router, prefix="/api/v1/aeds", tags=["AEDs"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])
from app.routes import utils
app.include_router(utils.router, prefix="/api/v1/utils", tags=["Utilities"])

# Root redirect to API documentation
@app.get("/", include_in_schema=False)
async def root_redirect():
    """Redirect root path to API documentation"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/api/v1/docs")

@app.get("/api/v1/health", include_in_schema=True)
async def health_check(request: Request, db: Session = Depends(get_db)):
    """
    Health check endpoint for the API
    
    Returns the health status of the API, including database and Redis connectivity
    """
    # Check database connection
    db_status = "connected"
    db_error = None
    
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = "error"
        db_error = str(e)
    
    # Check Redis connection
    redis_status = "connected" if is_redis_available() else "error"
    
    # Create response
    health_data = {
        "status": "healthy" if (db_status == "connected" and redis_status == "connected") else "unhealthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "database": {
            "status": db_status,
            "error": db_error
        },
        "redis": {
            "status": redis_status
        },
        "request_id": getattr(request.state, "request_id", "unknown")
    }
    
    status_code = 200 if (db_status == "connected" and redis_status == "connected") else 503
    return JSONResponse(content=health_data, status_code=status_code)

@app.get("/api/v1", response_model=Dict[str, Any])
async def api_info(request: Request):
    """
    Get information about the API service
    
    Returns basic information about the API, including version, documentation links,
    and available endpoints.
    """
    return {
        "name": "AED Location API",
        "version": "1.0.0",
        "description": "API to retrieve and report Automated External Defibrillator (AED) locations in Hong Kong",
        "documentation": {
            "swagger_ui": f"{request.base_url}api/v1/docs",
            "redoc": f"{request.base_url}api/v1/redoc",
            "openapi_json": f"{request.base_url}api/v1/openapi.json"
        },
        "endpoints": {
            "aeds": f"{request.base_url}api/v1/aeds",
            "reports": f"{request.base_url}api/v1/reports",
            "utilities": f"{request.base_url}api/v1/utils"
        },
        "request_id": request.state.request_id,
        "timestamp": datetime.now().isoformat()
    }

# Startup event to load data automatically when the app starts
@app.on_event("startup")
async def startup_event():
    """Load AED data when the application starts and initialize Redis cache"""
    # Initialize Redis cache
    try:
        if is_redis_available():
            FastAPICache.init(
                RedisBackend(redis_client),
                prefix="aed-cache:",
                expire=int(os.environ.get("CACHE_TTL", 3600))
            )
            print("Redis cache initialized successfully")
        else:
            print("Redis server is not available. Caching will be disabled.")
    except Exception as e:
        print(f"Failed to initialize Redis cache: {str(e)}")
        
    db = SessionLocal()  # Create a new session by calling the sessionmaker
    try:
        # Check if data exists
        count = db.query(func.count(AEDModel.id)).scalar()
        
        # Only refresh if no data exists
        if count == 0:
            print("No AED data found. Loading initial data...")
            # Get the refresh_data function without FastAPI dependencies
            try:
                response = requests.get(url, headers=headers)
                if response.status_code != 200:
                    print("Failed to download initial AED data")
                    return
                
                try:
                    # Try various encodings and CSV parsing options
                    print("Attempting to parse CSV data...")
                    df = pd.read_csv(
                        pd.io.common.StringIO(response.text),
                        encoding='utf-8',
                        on_bad_lines='warn',  # Skip bad lines but warn about them
                        low_memory=False  # Better handling of mixed data types
                    )
                    
                    # Log column names for debugging
                    print(f"CSV columns found: {', '.join(df.columns)}")
                    
                    # Required column mapping with fallbacks
                    column_map = {
                        "name": ["AED Name", "Name", "AEDName", "aed_name"],
                        "address": ["AED Address", "Address", "AEDAddress", "aed_address"],
                        "location_detail": ["Detailed location of the AED installed", "Location Detail", "DetailedLocation"],
                        "lat": ["Location Google Map coordinate: latitude", "Latitude", "latitude", "lat"],
                        "lng": ["Location Google Map coordinate: longitude", "Longitude", "longitude", "lng"],
                        "public_use": ["Whether the AED can be used by anyone", "Public Use", "PublicUse"],
                        "allowed_operators": ["Person allowed to operate the AED", "Allowed Operators", "AllowedOperators"],
                        "access_persons": ["Person who has access to the AED", "Access Persons", "AccessPersons"],
                        "category": ["Ground level categories", "Category", "Categories", "ground_level_categories"],
                        "service_hours": ["Service Hour Remark", "Service Hours", "ServiceHours", "service_hour_remark"],
                        "brand": ["AED brand", "Brand", "aed_brand"],
                        "model": ["AED model", "Model", "aed_model"],
                        "remark": ["AED remark", "Remark", "aed_remark", "Remarks"]
                    }
                    
                    # Check if we have the minimum required columns
                    required_field_groups = ["name", "address", "lat", "lng"]
                    column_matches = {}
                    
                    # Find matching columns for each field
                    for field, possible_columns in column_map.items():
                        for col in possible_columns:
                            if col in df.columns:
                                column_matches[field] = col
                                break
                    
                    # Verify we have all required fields
                    missing_fields = [field for field in required_field_groups if field not in column_matches]
                    if missing_fields:
                        print(f"Missing required fields in CSV: {', '.join(missing_fields)}")
                        print(f"Available columns: {', '.join(df.columns)}")
                        return
                    
                    print(f"Column mapping: {column_matches}")
                    
                    success_count = 0
                    error_count = 0
                    skipped_rows = 0
                    
                    # Add new data
                    for index, row in df.iterrows():
                        try:
                            # Safe get with fallback for all fields
                            def safe_get(field, default=None):
                                col = column_matches.get(field)
                                if col is None:
                                    return default
                                val = row[col]
                                return default if pd.isna(val) else val
                            
                            # Get coordinates with validation
                            try:
                                lat_col = column_matches.get("lat")
                                lng_col = column_matches.get("lng")
                                lat = float(row[lat_col]) if pd.notna(row[lat_col]) else 0.0
                                lng = float(row[lng_col]) if pd.notna(row[lng_col]) else 0.0
                                
                                # Basic validation
                                if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                                    print(f"Invalid coordinates at row {index}: lat={lat}, lng={lng}")
                                    skipped_rows += 1
                                    continue
                            except (ValueError, TypeError) as e:
                                print(f"Error parsing coordinates at row {index}: {str(e)}")
                                skipped_rows += 1
                                continue
                            
                            # Handle potential NaN or invalid values in the service hours field
                            service_hours = safe_get("service_hours")
                            if pd.isna(service_hours):
                                service_hours = None
                            else:
                                # Explicitly convert to string to handle any type issues
                                service_hours = str(service_hours)
                            
                            # Parse boolean fields safely
                            public_use_val = safe_get("public_use", "No")
                            public_use = public_use_val == "Yes" if isinstance(public_use_val, str) else bool(public_use_val)
                            
                            aed = AEDModel(
                                name=safe_get("name", "Unknown"),
                                address=safe_get("address", ""),
                                location_detail=safe_get("location_detail", ""),
                                latitude=lat,
                                longitude=lng,
                                public_use=public_use,
                                allowed_operators=safe_get("allowed_operators", ""),
                                access_persons=safe_get("access_persons", ""),
                                category=safe_get("category", ""),
                                service_hours=service_hours,
                                brand=safe_get("brand", ""),
                                model=safe_get("model", ""),
                                remark=safe_get("remark", ""),
                                # Create geography point
                                geo_point=f'POINT({lng} {lat})'
                            )
                            db.add(aed)
                            success_count += 1
                            
                            # Commit in batches to improve performance
                            if success_count % 100 == 0:
                                db.commit()
                                print(f"Imported {success_count} AEDs so far...")
                                
                        except Exception as e:
                            error_count += 1
                            print(f"Error processing row {index}: {str(e)}")
                            continue
                    
                    # Final commit for any remaining records
                    db.commit()
                    print(f"Import summary: {success_count} successful, {error_count} errors, {skipped_rows} skipped")
                    
                except Exception as e:
                    db.rollback()
                    print(f"Error parsing CSV data: {str(e)}")
                
                db.commit()
                print(f"Successfully imported {len(df)} AED records on startup")
            except Exception as e:
                db.rollback()
                print(f"Error loading initial AED data: {str(e)}")
        else:
            print(f"Database already contains {count} AED records. Skipping initial data load.")
    finally:
        db.close()


# Database error handling
@app.exception_handler(OperationalError)
async def database_operational_exception_handler(request: Request, exc: OperationalError):
    """
    Handle SQLAlchemy operational errors like connection issues
    """
    error_msg = str(exc)
    logger.error(f"RequestID: {request.state.request_id} | Database OperationalError: {error_msg}")
    
    # Create user-friendly error message
    if "does not exist" in error_msg:
        detail = "The database does not exist or has not been properly set up."
        status_code = 503  # Service Unavailable
    elif "could not connect" in error_msg or "connection" in error_msg.lower():
        detail = "Could not connect to the database server. Please try again later."
        status_code = 503  # Service Unavailable
    elif "server closed the connection unexpectedly" in error_msg:
        detail = "The database connection was lost. Please try again later."
        status_code = 503  # Service Unavailable
    elif "syntax error" in error_msg.lower() or "invalid input syntax" in error_msg.lower():
        detail = "Invalid parameter format in database query. Please check your input."
        status_code = 400  # Bad Request
    else:
        detail = "A database operational error occurred. Please try again later."
        status_code = 500  # Internal Server Error
    
    return JSONResponse(
        status_code=status_code,
        content={
            "detail": detail,
            "type": "database_error",
            "request_id": request.state.request_id
        }
    )

@app.exception_handler(DatabaseError)
async def database_exception_handler(request: Request, exc: DatabaseError):
    """
    Handle general SQLAlchemy database errors
    """
    error_msg = str(exc)
    logger.error(f"RequestID: {request.state.request_id} | DatabaseError: {error_msg}")
    
    # Check for specific types of errors
    if "invalid input syntax" in error_msg:
        detail = "Invalid parameter format. Please check your input values."
        status_code = 400  # Bad Request
    elif "violates" in error_msg and "constraint" in error_msg:
        detail = "The operation could not be completed due to data constraints."
        status_code = 400  # Bad Request
    else:
        detail = "A database error occurred while processing your request."
        status_code = 500  # Internal Server Error
    
    return JSONResponse(
        status_code=status_code,
        content={
            "detail": detail,
            "type": "database_error",
            "request_id": request.state.request_id
        }
    )

@app.exception_handler(SQLInjectionError)
async def sql_injection_exception_handler(request: Request, exc: SQLInjectionError):
    """
    Handle potential SQL injection attempts
    """
    logger.warning(f"RequestID: {request.state.request_id} | SQL Injection attempt detected: {str(exc)}")
    
    return JSONResponse(
        status_code=400,
        content={
            "detail": "Invalid input with potentially unsafe characters detected.",
            "type": "security_error",
            "request_id": request.state.request_id
        }
    )

@app.exception_handler(DBConnectionError)
async def db_connection_exception_handler(request: Request, exc: DBConnectionError):
    """
    Handle custom database connection errors
    """
    logger.error(f"RequestID: {request.state.request_id} | Database ConnectionError: {str(exc)}")
    
    return JSONResponse(
        status_code=503,
        content={
            "detail": str(exc),
            "type": "connection_error",
            "request_id": request.state.request_id
        }
    )

@app.exception_handler(QueryError)
async def query_exception_handler(request: Request, exc: QueryError):
    """
    Handle custom query errors
    """
    logger.error(f"RequestID: {request.state.request_id} | QueryError: {str(exc)}")
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "type": "query_error",
            "request_id": request.state.request_id
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
