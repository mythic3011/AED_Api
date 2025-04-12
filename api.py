import requests
import pandas as pd
import os
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union
from fastapi import FastAPI, HTTPException, Depends, Request, Response, status, Security, BackgroundTasks
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, text, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel, Field, EmailStr, validator, constr
from sqlalchemy.sql.expression import cast
from sqlalchemy.types import Numeric
from math import radians
from geoalchemy2 import Geography, Geometry

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
    swagger_ui_parameters={"persistAuthorization": True},
)

# Set up CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
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
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error", "request_id": request_id}
        )

# Database setup - PostgreSQL
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost/aed_db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Enable PostGIS extension
def setup_postgis():
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))

# Create PostGIS extension before other operations
setup_postgis()

# SQLAlchemy models
class AEDModel(Base):
    __tablename__ = "aeds"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    address = Column(String)
    location_detail = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    public_use = Column(Boolean)
    allowed_operators = Column(String)
    access_persons = Column(String)
    category = Column(String)
    service_hours = Column(String)  # Explicitly using String to avoid type issues
    brand = Column(String)
    model = Column(String)
    remark = Column(String)
    is_flagged = Column(Boolean, default=False, server_default="false")  # Flag for AEDs with reported issues
    flag_reason = Column(String, nullable=True)  # Reason for flagging
    flagged_at = Column(String, nullable=True)  # When it was flagged (ISO format)
    geo_point = Column(Geography(geometry_type='POINT', srid=4326))

class AEDReportModel(Base):
    __tablename__ = "aed_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    aed_id = Column(Integer)
    report_type = Column(String)  # damaged, missing, incorrect_info, other
    description = Column(String)
    reporter_name = Column(String)
    reporter_email = Column(String)
    reporter_phone = Column(String)
    created_at = Column(String)  # Store as ISO format string
    status = Column(String, default="pending")  # pending, investigating, resolved

Base.metadata.create_all(bind=engine)

# Pydantic models
class AED(BaseModel):
    id: Optional[int] = None
    name: str
    address: str
    location_detail: str
    latitude: float
    longitude: float
    public_use: bool
    allowed_operators: str
    access_persons: str
    category: str
    service_hours: Optional[str] = ""
    brand: str
    model: str
    remark: str
    is_flagged: bool = False
    flag_reason: Optional[str] = None
    flagged_at: Optional[str] = None
    
    class Config:
        orm_mode = True

class AEDWithDistance(AED):
    distance_km: float
    distance_display: str = ""  # Human readable distance (e.g., "~500 m" or "~2.5 km")
    
    @validator('distance_display', always=True)
    def format_distance(cls, v, values):
        distance = values.get('distance_km', 0)
        # Format distance for display
        if distance < 1:
            # Show in meters if less than 1km
            meters = int(distance * 1000)
            return f"~{meters} m"
        else:
            # Show in km with 1 decimal place if more than 1km
            return f"~{distance:.1f} km"

class AEDReportCreate(BaseModel):
    aed_id: int
    report_type: str  # damaged, missing, incorrect_info, other
    description: str
    reporter_name: Optional[str] = None
    reporter_email: Optional[str] = None
    reporter_phone: Optional[str] = None

class AEDReport(AEDReportCreate):
    id: int
    created_at: str
    status: str = "pending"
    
    class Config:
        orm_mode = True

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Headers for download
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"
}

url = "https://es.hkfsd.gov.hk/aed_api/export_aed.php?lang=EN"

@app.post("/api/v1/aeds/refresh", response_model=Dict[str, Any])
async def refresh_data(
    background_tasks: BackgroundTasks,
    request: Request,
    api_key: dict = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """
    Download and update AED data from the official source
    
    This endpoint requires admin privileges and will refresh all AED data in the system
    by importing the latest data from the Hong Kong Fire Services Department.
    
    Note: This operation is resource-intensive and should be rate limited.
    """
    
    # Check for admin privileges - Uncomment when ready to enforce this restriction
    # if api_key["tier"] != "premium":
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="This operation requires premium API access"
    #     )
    
    # Create a background task to refresh data
    def _refresh_data_task():
        logger.info(f"Starting background data refresh task (RequestID: {request.state.request_id})")
        _db = SessionLocal()
        
        try:
            # Step 1: Download data from source
            logger.info("Downloading AED data from source...")
            try:
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()  # Raise exception for HTTP errors
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to download data: {str(e)}")
                return
                
            # Step 2: Ensure schema compatibility
            logger.info("Ensuring database schema compatibility...")
            try:
                with _db.begin():
                    _db.execute(text("ALTER TABLE aeds ALTER COLUMN service_hours TYPE VARCHAR;"))
                logger.info("Successfully altered service_hours column to VARCHAR type")
            except Exception as schema_error:
                logger.warning(f"Schema adjustment note: {str(schema_error)}")
            
            # Step 3: Parse CSV data
            logger.info("Parsing CSV data...")
            try:
                df = pd.read_csv(
                    pd.io.common.StringIO(response.text),
                    encoding='utf-8',
                    on_bad_lines='warn',
                    low_memory=False
                )
            except Exception as e:
                logger.error(f"Error parsing CSV data: {str(e)}")
                return
                
            logger.info(f"CSV parsed successfully. Found {len(df)} rows and {len(df.columns)} columns")
            logger.info(f"Columns: {', '.join(df.columns)}")
            
            # Step 4: Map columns
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
            
            # Find matching columns for each field
            column_matches = {}
            for field, possible_columns in column_map.items():
                for col in possible_columns:
                    if col in df.columns:
                        column_matches[field] = col
                        break
            
            # Verify we have all required fields
            required_field_groups = ["name", "address", "lat", "lng"]
            missing_fields = [field for field in required_field_groups if field not in column_matches]
            if missing_fields:
                logger.error(f"Missing required fields in CSV: {', '.join(missing_fields)}")
                logger.error(f"Available columns: {', '.join(df.columns)}")
                return
                
            logger.info(f"Column mapping established successfully: {column_matches}")
            
            # Step 5: Create backup count
            count_before = _db.query(func.count(AEDModel.id)).scalar()
            logger.info(f"Current record count before refresh: {count_before}")
            
            # Step 6: Begin transaction and clear existing data
            _db.begin()
            try:
                _db.query(AEDModel).delete()
                logger.info("Existing AED data cleared")
                
                # Step 7: Process and insert data in batches
                batch_size = 100
                aeds_to_add = []
                success_count = 0
                error_count = 0
                skipped_rows = 0
                
                def safe_get(row, field, default=None):
                    col = column_matches.get(field)
                    if col is None:
                        return default
                    val = row[col]
                    return default if pd.isna(val) else val
                
                for index, row in df.iterrows():
                    try:
                        # Extract and validate coordinates
                        try:
                            lat_col = column_matches.get("lat")
                            lng_col = column_matches.get("lng")
                            lat = float(row[lat_col]) if pd.notna(row[lat_col]) else 0.0
                            lng = float(row[lng_col]) if pd.notna(row[lng_col]) else 0.0
                            
                            # Basic validation
                            if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                                logger.warning(f"Invalid coordinates at row {index}: lat={lat}, lng={lng}")
                                skipped_rows += 1
                                continue
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Error parsing coordinates at row {index}: {str(e)}")
                            skipped_rows += 1
                            continue
                        
                        # Handle service hours field
                        service_hours = safe_get(row, "service_hours")
                        if pd.isna(service_hours):
                            service_hours = ""
                        else:
                            service_hours = str(service_hours)
                        
                        # Parse boolean fields safely
                        public_use_val = safe_get(row, "public_use", "No")
                        if isinstance(public_use_val, str):
                            public_use = public_use_val.lower() in ["yes", "true", "1"]
                        else:
                            public_use = bool(public_use_val)
                        
                        # Create AED model
                        aed = AEDModel(
                            name=safe_get(row, "name", "Unknown"),
                            address=safe_get(row, "address", ""),
                            location_detail=safe_get(row, "location_detail", ""),
                            latitude=lat,
                            longitude=lng,
                            public_use=public_use,
                            allowed_operators=safe_get(row, "allowed_operators", ""),
                            access_persons=safe_get(row, "access_persons", ""),
                            category=safe_get(row, "category", ""),
                            service_hours=service_hours,
                            brand=safe_get(row, "brand", ""),
                            model=safe_get(row, "model", ""),
                            remark=safe_get(row, "remark", ""),
                            geo_point=f'POINT({lng} {lat})'
                        )
                        
                        # Add to batch
                        aeds_to_add.append(aed)
                        success_count += 1
                        
                        # Commit in batches
                        if len(aeds_to_add) >= batch_size:
                            _db.add_all(aeds_to_add)
                            _db.flush()
                            aeds_to_add = []
                            logger.info(f"Processed {success_count} AEDs so far...")
                        
                    except Exception as row_error:
                        error_count += 1
                        logger.warning(f"Error processing row {index}: {str(row_error)}")
                        continue
                
                # Add any remaining AEDs in the final batch
                if aeds_to_add:
                    _db.add_all(aeds_to_add)
                    _db.flush()
                
                # Commit the transaction
                _db.commit()
                
                # Step 8: Log results
                count_after = _db.query(func.count(AEDModel.id)).scalar()
                logger.info(f"Data refresh complete. Records before: {count_before}, after: {count_after}")
                logger.info(f"Import summary: {success_count} successful, {error_count} errors, {skipped_rows} skipped")
                
            except Exception as transaction_error:
                _db.rollback()
                logger.error(f"Transaction failed: {str(transaction_error)}")
                
        except Exception as e:
            logger.error(f"Unhandled error in background refresh task: {str(e)}")
        finally:
            _db.close()

    # Start the background task
    background_tasks.add_task(_refresh_data_task)
        
    return {
        "status": "accepted",
        "message": "AED data refresh has been scheduled",
        "request_id": request.state.request_id,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/v1/aeds", response_model=Dict[str, Any])
async def get_all_aeds(
    request: Request,
    skip: int = 0, 
    limit: int = 50, 
    sort_by: str = "id",
    order: str = "asc",
    api_key: dict = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """
    Get all AEDs with pagination, sorting and filtering options
    
    Parameters:
    - skip: Number of records to skip (for pagination)
    - limit: Maximum number of records to return
    - sort_by: Field to sort by (id, name, address)
    - order: Sort order (asc or desc)
    
    Returns a paginated list of AEDs with metadata about the total count
    and pagination links.
    """
    # Apply rate limiting based on API tier
    if limit > 100 and api_key["tier"] == "basic":
        limit = 100
    elif limit > 500 and api_key["tier"] == "standard":
        limit = 500
        
    # Validate sort parameters
    valid_sort_fields = ["id", "name", "address", "category"]
    if sort_by not in valid_sort_fields:
        sort_by = "id"
        
    valid_orders = ["asc", "desc"]
    if order not in valid_orders:
        order = "asc"
    
    # Build query with sorting
    query = db.query(AEDModel)
    
    # Get total count before pagination
    total_count = query.count()
    
    # Apply sorting
    if order == "asc":
        query = query.order_by(getattr(AEDModel, sort_by).asc())
    else:
        query = query.order_by(getattr(AEDModel, sort_by).desc())
    
    # Apply pagination
    aeds = query.offset(skip).limit(limit).all()
    
    # Build pagination links
    base_url = str(request.url).split("?")[0]
    
    # Calculate pagination metadata
    next_page = skip + limit if skip + limit < total_count else None
    prev_page = skip - limit if skip - limit >= 0 else None
    
    # Prepare pagination links
    pagination = {
        "total": total_count,
        "limit": limit,
        "offset": skip,
        "next": f"{base_url}?skip={next_page}&limit={limit}&sort_by={sort_by}&order={order}" if next_page is not None else None,
        "prev": f"{base_url}?skip={prev_page}&limit={limit}&sort_by={sort_by}&order={order}" if prev_page is not None else None
    }
    
    # Convert SQLAlchemy model objects to Pydantic models for proper JSON serialization
    aeds_data = []
    for aed in aeds:
        # Handle the geo_point field which can't be directly serialized
        aed_dict = {
            "id": aed.id,
            "name": aed.name,
            "address": aed.address,
            "location_detail": aed.location_detail,
            "latitude": aed.latitude,
            "longitude": aed.longitude,
            "public_use": aed.public_use,
            "allowed_operators": aed.allowed_operators,
            "access_persons": aed.access_persons,
            "category": aed.category,
            "service_hours": aed.service_hours,
            "brand": aed.brand,
            "model": aed.model,
            "remark": aed.remark,
            "is_flagged": aed.is_flagged,
            "flag_reason": aed.flag_reason,
            "flagged_at": aed.flagged_at
        }
        aeds_data.append(AED(**aed_dict))
    
    # Return structured response with metadata
    return {
        "data": aeds_data,
        "pagination": pagination,
        "metadata": {
            "request_id": request.state.request_id,
            "timestamp": datetime.now().isoformat()
        }
    }

@app.get("/api/v1/aeds/nearby", response_model=Dict[str, Any])
async def get_nearby_aeds(
    request: Request,
    lat: float, 
    lng: float, 
    radius: float = 1.0, 
    limit: int = 50,
    public_only: bool = True,
    api_key: dict = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """
    Find AEDs within specified radius (kilometers) of given coordinates
    
    Parameters:
    - lat: Latitude of search center point
    - lng: Longitude of search center point
    - radius: Search radius in kilometers (default: 1.0)
    - limit: Maximum number of results to return
    - public_only: If true, returns only publicly accessible AEDs
    
    Returns a list of AEDs sorted by distance from the specified coordinates,
    with distance information included for each AED.
    """
    # Validate parameters
    if radius <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Radius must be greater than zero"
        )
        
    if radius > 50 and api_key["tier"] == "basic":
        radius = 50
        
    # Apply rate limiting based on API tier
    if limit > 100 and api_key["tier"] == "basic":
        limit = 100
    elif limit > 500 and api_key["tier"] == "standard":
        limit = 500
        
    # Build the SQL query with optional public_only filter
    query_str = """
        SELECT 
            id, name, address, location_detail, latitude, longitude, 
            public_use, allowed_operators, access_persons, category, 
            service_hours, brand, model, remark,
            ST_Distance(
                geo_point::geography,
                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
            )/1000 AS distance_km
        FROM aeds
        WHERE ST_DWithin(
            geo_point::geography,
            ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
            :radius * 1000
        )
    """
    
    # Add public_only filter if requested
    if public_only:
        query_str += " AND public_use = true"
        
    query_str += " ORDER BY distance_km LIMIT :limit"
    
    # Execute query
    try:
        result = db.execute(
            text(query_str), 
            {"lat": lat, "lng": lng, "radius": radius, "limit": limit}
        ).fetchall()
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error querying database for nearby AEDs"
        )
    
    # Process results
    aeds_with_distance = []
    for row in result:
        aed_dict = {
            "id": row.id,
            "name": row.name,
            "address": row.address,
            "location_detail": row.location_detail,
            "latitude": row.latitude,
            "longitude": row.longitude,
            "public_use": row.public_use,
            "allowed_operators": row.allowed_operators,
            "access_persons": row.access_persons,
            "category": row.category,
            "service_hours": row.service_hours,
            "brand": row.brand,
            "model": row.model,
            "remark": row.remark,
            "distance_km": row.distance_km
        }
        aeds_with_distance.append(AEDWithDistance(**aed_dict))
    
    return {
        "data": aeds_with_distance,
        "metadata": {
            "request_id": request.state.request_id,
            "timestamp": datetime.now().isoformat(),
            "search": {
                "latitude": lat,
                "longitude": lng,
                "radius_km": radius,
                "limit": limit,
                "public_only": public_only,
                "results_found": len(aeds_with_distance)
            }
        }
    }

@app.get("/api/v1/aeds/sorted-by-location", response_model=List[AEDWithDistance])
async def get_aeds_sorted_by_location(lat: float, lng: float, limit: int = 100, db: Session = Depends(get_db)):
    """Find all AEDs sorted by distance from the given coordinates"""
    query = text("""
        SELECT 
            id, name, address, location_detail, latitude, longitude, 
            public_use, allowed_operators, access_persons, category, 
            service_hours, brand, model, remark,
            ST_Distance(
                geo_point::geography,
                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
            )/1000 AS distance_km
        FROM aeds
        ORDER BY distance_km
        LIMIT :limit
    """)
    
    result = db.execute(query, {"lat": lat, "lng": lng, "limit": limit}).fetchall()
    
    aeds_with_distance = []
    for row in result:
        aed_dict = {
            "id": row.id,
            "name": row.name,
            "address": row.address,
            "location_detail": row.location_detail,
            "latitude": row.latitude,
            "longitude": row.longitude,
            "public_use": row.public_use,
            "allowed_operators": row.allowed_operators,
            "access_persons": row.access_persons,
            "category": row.category,
            "service_hours": row.service_hours,
            "brand": row.brand,
            "model": row.model,
            "remark": row.remark,
            "distance_km": row.distance_km
        }
        aeds_with_distance.append(AEDWithDistance(**aed_dict))
    
    return aeds_with_distance

@app.post("/api/v1/aeds/{aed_id}/report", response_model=Dict[str, Any])
async def report_aed_issue(
    request: Request,
    aed_id: int, 
    report: AEDReportCreate, 
    db: Session = Depends(get_db)
):
    """
    Report an issue with an AED (damaged, missing, incorrect info)
    
    This endpoint allows users to report problems with specific AEDs.
    When an AED is reported, it will be flagged in the system to indicate
    potential issues that need to be addressed.
    
    Parameters:
    - aed_id: ID of the AED being reported
    - report: Report details including type and description
    
    Returns the created report and updates the AED's flagged status.
    """
    # Check if the AED exists
    aed = db.query(AEDModel).filter(AEDModel.id == aed_id).first()
    if not aed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="AED not found"
        )
    
    # Create report with current timestamp
    current_time = datetime.now().isoformat()
    
    # Validate report type
    valid_report_types = ["damaged", "missing", "incorrect_info", "other"]
    if report.report_type not in valid_report_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid report type. Must be one of: {', '.join(valid_report_types)}"
        )
    
    # Create the report
    db_report = AEDReportModel(
        aed_id=aed_id,
        report_type=report.report_type,
        description=report.description,
        reporter_name=report.reporter_name,
        reporter_email=report.reporter_email,
        reporter_phone=report.reporter_phone,
        created_at=current_time,
        status="pending"
    )
    
    # Flag the AED as having an issue
    aed.is_flagged = True
    aed.flag_reason = report.report_type
    aed.flagged_at = current_time
    
    # Save changes
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    
    # Log the report
    logger.info(f"AED {aed_id} reported as {report.report_type} by {report.reporter_name or 'anonymous'}")
    
    return {
        "report": db_report,
        "aed_flagged": True,
        "message": f"Thank you for reporting this AED issue. Reference ID: {db_report.id}",
        "request_id": request.state.request_id,
        "timestamp": current_time
    }

@app.get("/api/v1/aeds/{aed_id}/reports", response_model=Dict[str, Any])
async def get_aed_reports(
    request: Request,
    aed_id: int, 
    skip: int = 0,
    limit: int = 20,
    api_key: dict = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """
    Get all reports for a specific AED
    
    This endpoint returns all the reports that have been submitted 
    for a specific AED, sorted by creation date.
    
    Parameters:
    - aed_id: ID of the AED
    - skip: Number of reports to skip (pagination)
    - limit: Maximum number of reports to return
    
    Returns a list of reports for the specified AED.
    """
    # Check if the AED exists
    aed = db.query(AEDModel).filter(AEDModel.id == aed_id).first()
    if not aed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="AED not found"
        )
    
    # Count total reports for this AED
    total_count = db.query(func.count(AEDReportModel.id)).filter(
        AEDReportModel.aed_id == aed_id
    ).scalar()
    
    # Get reports with pagination
    reports = db.query(AEDReportModel).filter(
        AEDReportModel.aed_id == aed_id
    ).order_by(AEDReportModel.created_at.desc()).offset(skip).limit(limit).all()
    
    # Build pagination metadata
    next_page = skip + limit if skip + limit < total_count else None
    prev_page = skip - limit if skip - limit >= 0 else None
    
    # Base URL for pagination links
    base_url = str(request.url).split("?")[0]
    
    return {
        "data": reports,
        "pagination": {
            "total": total_count,
            "limit": limit,
            "offset": skip,
            "next": f"{base_url}?skip={next_page}&limit={limit}" if next_page is not None else None,
            "prev": f"{base_url}?skip={prev_page}&limit={limit}" if prev_page is not None else None
        },
        "metadata": {
            "request_id": request.state.request_id,
            "timestamp": datetime.now().isoformat(),
            "aed_info": {
                "id": aed.id,
                "name": aed.name,
                "is_flagged": aed.is_flagged,
                "flag_reason": aed.flag_reason
            }
        }
    }

@app.get("/api/v1/reports", response_model=Dict[str, Any])
async def get_all_reports(
    request: Request,
    skip: int = 0, 
    limit: int = 50, 
    status: Optional[str] = None,
    report_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    api_key: dict = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """
    Get all AED reports with filtering and pagination
    
    This endpoint returns all AED reports with optional filtering by:
    - status (pending, investigating, resolved)
    - report_type (damaged, missing, incorrect_info, other)
    - date range (start_date, end_date in ISO format)
    
    Parameters:
    - skip: Number of reports to skip (pagination)
    - limit: Maximum number of reports to return
    - status: Filter by report status
    - report_type: Filter by report type
    - start_date: Filter reports created on or after this date (ISO format)
    - end_date: Filter reports created before this date (ISO format)
    
    Note: This endpoint requires admin access for complete report access.
    """
    # Check for proper permissions
    if api_key["tier"] == "basic" and limit > 20:
        limit = 20
    elif api_key["tier"] == "standard" and limit > 100:
        limit = 100
        
    if api_key["tier"] == "basic":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires standard or premium API access"
        )
    
    # Build query with filters
    query = db.query(AEDReportModel)
    
    # Apply filters
    if status:
        valid_statuses = ["pending", "investigating", "resolved"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        query = query.filter(AEDReportModel.status == status)
        
    if report_type:
        valid_types = ["damaged", "missing", "incorrect_info", "other"]
        if report_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid report type. Must be one of: {', '.join(valid_types)}"
            )
        query = query.filter(AEDReportModel.report_type == report_type)
        
    if start_date:
        try:
            start = datetime.fromisoformat(start_date)
            query = query.filter(AEDReportModel.created_at >= start.isoformat())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"
            )
            
    if end_date:
        try:
            end = datetime.fromisoformat(end_date)
            query = query.filter(AEDReportModel.created_at <= end.isoformat())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"
            )
    
    # Get total count before pagination
    total_count = query.count()
    
    # Apply sorting and pagination
    reports = query.order_by(AEDReportModel.created_at.desc()).offset(skip).limit(limit).all()
    
    # Build pagination metadata
    next_page = skip + limit if skip + limit < total_count else None
    prev_page = skip - limit if skip - limit >= 0 else None
    
    # Base URL for pagination links
    base_url = str(request.url).split("?")[0]
    
    # Prepare filter parameters for pagination links
    filter_params = []
    if status:
        filter_params.append(f"status={status}")
    if report_type:
        filter_params.append(f"report_type={report_type}")
    if start_date:
        filter_params.append(f"start_date={start_date}")
    if end_date:
        filter_params.append(f"end_date={end_date}")
        
    filter_str = "&".join(filter_params)
    if filter_str:
        filter_str = "&" + filter_str
    
    return {
        "data": reports,
        "pagination": {
            "total": total_count,
            "limit": limit,
            "offset": skip,
            "next": f"{base_url}?skip={next_page}&limit={limit}{filter_str}" if next_page is not None else None,
            "prev": f"{base_url}?skip={prev_page}&limit={limit}{filter_str}" if prev_page is not None else None
        },
        "metadata": {
            "request_id": request.state.request_id,
            "timestamp": datetime.now().isoformat(),
            "filters_applied": {
                "status": status,
                "report_type": report_type,
                "start_date": start_date,
                "end_date": end_date
            }
        }
    }

# Startup event to load data automatically when the app starts
@app.on_event("startup")
async def startup_event():
    """Load AED data when the application starts"""
    db = SessionLocal()
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)