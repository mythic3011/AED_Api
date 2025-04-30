from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from typing import Dict, Any
from datetime import datetime
from app.database import get_db, AEDReportModel
from app.models import AEDReport

router = APIRouter()

@router.get("/", response_model=Dict[str, Any])
async def get_all_reports(
    request: Request,
    skip: int = 0,
    limit: int = 50,
    report_type: str = None,
    status: str = None,
    db: Session = Depends(get_db)
):
    """
    Get all AED reports with filtering and pagination
    
    Parameters:
    - skip: Number of records to skip (for pagination)
    - limit: Maximum number of records to return
    - report_type: Filter by report type (optional)
    - status: Filter by report status (optional)
    
    Returns a paginated list of AED reports with metadata about the total count
    and pagination links.
    """
    # Build query with optional filters
    query = db.query(AEDReportModel)
    
    if report_type:
        query = query.filter(AEDReportModel.report_type == report_type)
    
    if status:
        query = query.filter(AEDReportModel.status == status)
    
    # Get total count before pagination
    total_count = query.count()
    
    # Apply pagination
    reports = query.offset(skip).limit(limit).all()
    
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
        "next": f"{base_url}?skip={next_page}&limit={limit}&report_type={report_type}&status={status}" if next_page is not None else None,
        "prev": f"{base_url}?skip={prev_page}&limit={limit}&report_type={report_type}&status={status}" if prev_page is not None else None
    }
    
    # Convert SQLAlchemy model objects to Pydantic models for proper JSON serialization
    reports_data = [AEDReport.from_orm(report) for report in reports]
    
    # Return structured response with metadata
    return {
        "data": reports_data,
        "pagination": pagination,
        "metadata": {
            "request_id": request.state.request_id,
            "timestamp": datetime.now().isoformat()
        }
    }
