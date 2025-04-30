from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from typing import Dict, Any, List
from datetime import datetime
import requests
import pandas as pd
import logging
import time
from app.database import get_db, AEDModel, AEDReportModel, SessionLocal
from app.models import AED, AEDWithDistance, AEDReportCreate, AEDReport
from app.utils import headers, url
from app.services.aed_service import update_aed_database

router = APIRouter()

logger = logging.getLogger("aed_api")

@router.post("/refresh", response_model=Dict[str, Any])
async def refresh_data(
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Download and update AED data from the official source
    
    This endpoint requires admin privileges and will refresh all AED data in the system
    by importing the latest data from the Hong Kong Fire Services Department.
    
    Note: This operation is resource-intensive and should be rate limited.
    """
    
    # Create a background task to refresh data
    def _refresh_data_task():
        # The actual data refresh is handled by the service module
        result = update_aed_database(request.state.request_id)
        logger.info(f"Background refresh task completed with status: {result['status']}")
        
    # Start the background task
    background_tasks.add_task(_refresh_data_task)
        
    return {
        "status": "accepted",
        "message": "AED data refresh has been scheduled",
        "request_id": request.state.request_id,
        "timestamp": datetime.now().isoformat()
    }

@router.get("/", response_model=Dict[str, Any])
async def get_all_aeds(
    request: Request,
    skip: int = 0, 
    limit: int = 50, 
    sort_by: str = "id",
    order: str = "asc",
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

@router.get("/nearby", response_model=Dict[str, Any])
async def get_nearby_aeds(
    request: Request,
    lat: float, 
    lng: float, 
    radius: float = 1.0, 
    limit: int = 50,
    public_only: bool = True,
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
            status_code=400,
            detail="Radius must be greater than zero"
        )
        
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
            status_code=500,
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

@router.get("/sorted-by-location", response_model=List[AEDWithDistance])
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

@router.post("/{aed_id}/report", response_model=Dict[str, Any])
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
            status_code=404, 
            detail="AED not found"
        )
    
    # Create report with current timestamp
    current_time = datetime.now().isoformat()
    
    # Validate report type
    valid_report_types = ["damaged", "missing", "incorrect_info", "other"]
    if report.report_type not in valid_report_types:
        raise HTTPException(
            status_code=400,
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

@router.get("/{aed_id}/reports", response_model=Dict[str, Any])
async def get_aed_reports(
    request: Request,
    aed_id: int, 
    skip: int = 0,
    limit: int = 20,
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
            status_code=404, 
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
