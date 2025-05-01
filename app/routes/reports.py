from fastapi import APIRouter, HTTPException, Depends, Request, Path, Body, Query, status
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
from app.database import get_db, AEDReportModel
from app.models import AEDReport, AEDReportCreate
from app.database_utils import SQLInjectionError, validate_numeric_param

logger = logging.getLogger("aed_api")

router = APIRouter()

@router.get("/", response_model=Dict[str, Any])
async def get_all_reports(
    request: Request,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records to return"),
    report_type: Optional[str] = Query(None, description="Filter by report type"),
    status: Optional[str] = Query(None, description="Filter by report status"),
    sort_by: Optional[str] = Query(None, description="Field to sort by"),
    sort_order: Optional[str] = Query("desc", description="Sort order (asc or desc)"),
    db: Session = Depends(get_db)
):
    """
    Get all AED reports with filtering and pagination
    
    Parameters:
    - skip: Number of records to skip (for pagination)
    - limit: Maximum number of records to return
    - report_type: Filter by report type (optional)
    - status: Filter by report status (optional)
    - sort_by: Field to sort by (optional)
    - sort_order: Sort order, "asc" or "desc" (default: "desc")
    
    Returns a paginated list of AED reports with metadata about the total count
    and pagination links.
    """
    # Build query with optional filters
    query = db.query(AEDReportModel)
    
    # Validate and apply report_type filter
    if report_type:
        valid_types = ["damaged", "missing", "incorrect_info", "other"]
        if report_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid report_type. Must be one of: {', '.join(valid_types)}"
            )
        query = query.filter(AEDReportModel.report_type == report_type)
    
    # Validate and apply status filter
    if status:
        valid_statuses = ["pending", "investigating", "resolved", "rejected"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        query = query.filter(AEDReportModel.status == status)
    
    # Apply sorting if specified
    if sort_by:
        # Validate sort field
        valid_sort_fields = ["id", "aed_id", "report_type", "created_at", "status"]
        if sort_by not in valid_sort_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid sort_by field. Must be one of: {', '.join(valid_sort_fields)}"
            )
        
        # Validate sort order
        valid_sort_orders = ["asc", "desc"]
        if sort_order not in valid_sort_orders:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid sort_order. Must be one of: {', '.join(valid_sort_orders)}"
            )
        
        # Apply sorting
        sort_field = getattr(AEDReportModel, sort_by)
        if sort_order == "desc":
            query = query.order_by(sort_field.desc())
        else:
            query = query.order_by(sort_field)
    else:
        # Default sorting by created_at (newest first)
        query = query.order_by(AEDReportModel.created_at.desc())
    
    # Get total count before pagination
    total_count = query.count()
    
    # Apply pagination
    reports = query.offset(skip).limit(limit).all()
    
    # Build pagination links
    base_url = str(request.url).split("?")[0]
    
    # Calculate pagination metadata
    next_page = skip + limit if skip + limit < total_count else None
    prev_page = skip - limit if skip - limit >= 0 else None
    
    # Construct query params for pagination links
    query_params = {
        "limit": limit,
        "sort_by": sort_by,
        "sort_order": sort_order
    }
    
    if report_type:
        query_params["report_type"] = report_type
    
    if status:
        query_params["status"] = status
        
    # Prepare next/prev pagination links with all query parameters
    next_link = None
    prev_link = None
    
    if next_page is not None:
        params = {**query_params, "skip": next_page}
        param_str = "&".join([f"{k}={v}" for k, v in params.items() if v is not None])
        next_link = f"{base_url}?{param_str}"
        
    if prev_page is not None:
        params = {**query_params, "skip": prev_page}
        param_str = "&".join([f"{k}={v}" for k, v in params.items() if v is not None])
        prev_link = f"{base_url}?{param_str}"
    
    pagination = {
        "total": total_count,
        "limit": limit,
        "offset": skip,
        "next": next_link,
        "prev": prev_link
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

@router.post("/", response_model=AEDReport, status_code=status.HTTP_201_CREATED)
async def create_report(
    request: Request,
    report: AEDReportCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new AED report
    
    Creates a new report about an AED that might be damaged, missing, or have incorrect information.
    
    Parameters:
    - report: The report data including aed_id, report_type, and description
    
    Returns the created report with its ID and metadata.
    """
    try:
        # Validate the aed_id parameter to prevent SQL injection
        try:
            validate_numeric_param(report.aed_id, "aed_id", min_value=1)
        except SQLInjectionError as e:
            # Log potential SQL injection attempt
            logger.warning(f"SQL injection attempt detected: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Invalid input format. SQL special characters are not allowed."
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
            
        # Create the new report
        new_report = AEDReportModel(
            aed_id=report.aed_id,
            report_type=report.report_type,
            description=report.description,
            reporter_name=report.reporter_name,
            reporter_email=report.reporter_email,
            reporter_phone=report.reporter_phone,
            created_at=datetime.now().isoformat(),
            status="pending"
        )
        
        db.add(new_report)
        db.commit()
        db.refresh(new_report)
        
        return AEDReport.from_orm(new_report)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create report: {str(e)}"
        )

@router.get("/{report_id}", response_model=AEDReport)
async def get_report(
    request: Request,
    report_id: int = Path(..., description="The ID of the report to retrieve", gt=0),
    db: Session = Depends(get_db)
):
    """
    Get a specific AED report by ID
    
    Parameters:
    - report_id: The ID of the report to retrieve
    
    Returns the report data if found.
    """
    try:
        # Validate the report_id parameter 
        try:
            validate_numeric_param(report_id, "report_id", min_value=1)
        except SQLInjectionError as e:
            # Log potential SQL injection attempt
            logger.warning(f"SQL injection attempt detected in report_id: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Invalid input format. SQL special characters are not allowed."
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
            
        report = db.query(AEDReportModel).filter(AEDReportModel.id == report_id).first()
        if not report:
            raise HTTPException(
                status_code=404,
                detail=f"Report with ID {report_id} not found"
            )
            
        return AEDReport.from_orm(report)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve report: {str(e)}"
        )

@router.put("/{report_id}/status", response_model=AEDReport)
async def update_report_status(
    request: Request,
    report_id: int = Path(..., description="The ID of the report to update", gt=0),
    status: str = Body(..., embed=True, description="The new status for the report"),
    db: Session = Depends(get_db)
):
    """
    Update the status of an AED report
    
    Parameters:
    - report_id: The ID of the report to update
    - status: The new status value (e.g., "pending", "investigating", "resolved", "rejected")
    
    Returns the updated report data.
    """
    try:
        # Validate the report_id parameter
        try:
            validate_numeric_param(report_id, "report_id", min_value=1)
        except (ValueError, SQLInjectionError) as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        # Validate the status
        valid_statuses = ["pending", "investigating", "resolved", "rejected"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status value. Must be one of: {', '.join(valid_statuses)}"
            )
            
        # Find the report
        report = db.query(AEDReportModel).filter(AEDReportModel.id == report_id).first()
        if not report:
            raise HTTPException(
                status_code=404,
                detail=f"Report with ID {report_id} not found"
            )
            
        # Update the status
        report.status = status
        db.commit()
        db.refresh(report)
        
        return AEDReport.from_orm(report)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update report status: {str(e)}"
        )

@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    request: Request,
    report_id: int = Path(..., description="The ID of the report to delete", gt=0),
    db: Session = Depends(get_db)
):
    """
    Delete an AED report
    
    Parameters:
    - report_id: The ID of the report to delete
    
    Returns no content on success.
    """
    try:
        # Validate the report_id parameter
        try:
            validate_numeric_param(report_id, "report_id", min_value=1)
        except (ValueError, SQLInjectionError) as e:
            raise HTTPException(status_code=400, detail=str(e))
            
        # Find the report
        report = db.query(AEDReportModel).filter(AEDReportModel.id == report_id).first()
        if not report:
            raise HTTPException(
                status_code=404,
                detail=f"Report with ID {report_id} not found"
            )
            
        # Delete the report
        db.delete(report)
        db.commit()
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete report: {str(e)}"
        )

@router.get("/stats", response_model=Dict[str, Any])
async def get_report_stats(
    request: Request,
    start_date: Optional[str] = Query(None, description="Filter by start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="Filter by end date (ISO format)"),
    db: Session = Depends(get_db)
):
    """
    Get statistics about AED reports
    
    Returns summary statistics about reports grouped by type and status.
    
    Parameters:
    - start_date: Filter reports created on or after this date (optional)
    - end_date: Filter reports created on or before this date (optional)
    """
    try:
        # Start with base query
        query = db.query(AEDReportModel)
        
        # Apply date filters if provided
        if start_date:
            try:
                # Validate date format
                datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.filter(AEDReportModel.created_at >= start_date)
            except ValueError:
                raise HTTPException(
                    status_code=400, 
                    detail="Invalid start_date format. Use ISO format (YYYY-MM-DDTHH:MM:SS.sssZ)"
                )
                
        if end_date:
            try:
                # Validate date format
                datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.filter(AEDReportModel.created_at <= end_date)
            except ValueError:
                raise HTTPException(
                    status_code=400, 
                    detail="Invalid end_date format. Use ISO format (YYYY-MM-DDTHH:MM:SS.sssZ)"
                )
        
        # Get total counts
        total_reports = query.count()
        
        # Get counts by status
        status_counts = {}
        for status_value in ["pending", "investigating", "resolved", "rejected"]:
            status_query = query.filter(AEDReportModel.status == status_value)
            status_counts[status_value] = status_query.count()
        
        # Get counts by report type
        type_counts = {}
        report_types = ["damaged", "missing", "incorrect_info", "other"]
        for report_type in report_types:
            type_query = query.filter(AEDReportModel.report_type == report_type)
            type_counts[report_type] = type_query.count()
        
        return {
            "total_reports": total_reports,
            "by_status": status_counts,
            "by_type": type_counts,
            "date_range": {
                "start_date": start_date,
                "end_date": end_date
            },
            "metadata": {
                "request_id": request.state.request_id,
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve report statistics: {str(e)}"
        )
