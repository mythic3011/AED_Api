"""
Utility routes for the AED API.
These routes provide system information, health status, and other utility functions.
"""

from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from sqlalchemy.exc import OperationalError, DatabaseError
import platform
import psutil
import os
import time
import sys
import socket
from datetime import datetime
from typing import Dict, Any, List
import logging
from app.database import get_db, AEDModel, AEDReportModel, SessionLocal, DB_HOST, DB_NAME
from app.redis_utils import is_redis_available, get_stats as redis_get_stats

router = APIRouter()
logger = logging.getLogger("aed_api")

# Store the server start time
SERVER_START_TIME = time.time()


@router.get("/health", response_model=Dict[str, Any])
async def health_check(request: Request, db: Session = Depends(get_db)):
    """
    Health check endpoint for the AED API.
    
    Returns basic health information about the API and database connection status.
    Used for monitoring and automated health checks.
    """
    # Check database connection
    db_status = "healthy"
    db_error = None
    connection_details = {}
    
    try:
        # Import the needed modules here to avoid circular imports
        from sqlalchemy.exc import OperationalError, DatabaseError
        import os
        from app.database import DB_HOST, DB_NAME
        
        # Query database version information
        result = db.execute(text("SELECT version()")).fetchone()
        db_version = result[0] if result else "Unknown"
        
        # Get connection details - safely extract info without exposing credentials
        connection_details = {
            "host": DB_HOST,
            "database": DB_NAME,
            "version": db_version
        }
        
    except (OperationalError, DatabaseError) as e:
        db_status = "unhealthy"
        db_error = f"Database connection error: {str(e)}"
        logger.error(f"Database health check failed (DB Error): {e}")
        
        # Provide useful connection troubleshooting info
        connection_details = {
            "host": DB_HOST,
            "database": DB_NAME,
            "error_type": type(e).__name__
        }
        
    except Exception as e:
        db_status = "unhealthy"
        db_error = f"Health check error: {str(e)}"
        logger.error(f"Database health check failed (General Error): {e}")
    
    # Check for Zeabur-specific environment variables
    deployment_info = {
        "platform": "development"
    }
    
    # Check if running on Zeabur
    if os.environ.get("ZEABUR_SERVICE_ID"):
        deployment_info = {
            "platform": "zeabur",
            "service_id": os.environ.get("ZEABUR_SERVICE_ID"),
            "service_name": os.environ.get("ZEABUR_SERVICE_NAME", "AED API"),
            "project_id": os.environ.get("ZEABUR_PROJECT_ID")
        }
    
    # Add retry guidance if database is unhealthy
    remediation = None
    if db_status == "unhealthy":
        remediation = {
            "suggestion": "The application will automatically attempt to reconnect to the database. If the issue persists, check database configuration and connectivity."
        }
    
    response = {
        "status": "healthy" if db_status == "healthy" else "unhealthy",
        "timestamp": datetime.now().isoformat(),
        "request_id": request.state.request_id,
        "components": {
            "api": {
                "status": "healthy",
                "uptime_seconds": int(time.time() - SERVER_START_TIME)
            },
            "database": {
                "status": db_status,
                "connection": connection_details,
                "error": db_error,
                "remediation": remediation
            }
        },
        "deployment": deployment_info
    }
    
    # Set appropriate status code
    if db_status == "unhealthy":
        # Return a 200 status still to avoid triggering alerts
        # The payload will indicate unhealthy status
        pass
    
    return response


@router.get("/info", response_model=Dict[str, Any])
async def system_info(request: Request, db: Session = Depends(get_db)):
    """
    Get detailed system information about the AED API service.
    
    Returns information about the system, database statistics, and environment.
    Useful for debugging and operational insights.
    """
    # System information
    system_info = {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "memory_usage_percent": psutil.virtual_memory().percent,
        "cpu_usage_percent": psutil.cpu_percent(interval=0.1)
    }
    
    # Database statistics
    db_stats = {}
    try:
        # Count AEDs
        aed_count = db.query(func.count(AEDModel.id)).scalar()
        db_stats["aed_count"] = aed_count
        
        # Count flagged AEDs
        flagged_aed_count = db.query(func.count(AEDModel.id)).filter(AEDModel.is_flagged == True).scalar()
        db_stats["flagged_aed_count"] = flagged_aed_count
        
        # Count reports
        report_count = db.query(func.count(AEDReportModel.id)).scalar()
        db_stats["report_count"] = report_count
        
        # Get pending reports
        pending_reports = db.query(func.count(AEDReportModel.id)).filter(AEDReportModel.status == "pending").scalar()
        db_stats["pending_reports"] = pending_reports
        
        db_stats["status"] = "healthy"
    except Exception as e:
        db_stats["status"] = "error"
        db_stats["error"] = str(e)
        logger.error(f"Error getting database stats: {e}")
    
    # Environment info
    env_info = {
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "debug_mode": os.environ.get("DEBUG", "False").lower() == "true"
    }
    
    # Redis info
    redis_info = {
        "available": is_redis_available(),
        "status": "healthy" if is_redis_available() else "unavailable"
    }
    
    if redis_info["available"]:
        redis_info.update(redis_get_stats())
    
    return {
        "timestamp": datetime.now().isoformat(),
        "request_id": request.state.request_id,
        "system": system_info,
        "database": db_stats,
        "redis": redis_info,
        "environment": env_info,
        "api_uptime_seconds": int(time.time() - SERVER_START_TIME),
        "api_uptime_human": _format_uptime(int(time.time() - SERVER_START_TIME))
    }


@router.get("/redis", response_model=Dict[str, Any])
async def get_redis_info(request: Request):
    """
    Get detailed information about Redis cache status.
    
    Returns statistics and status information for the Redis cache,
    useful for monitoring and troubleshooting.
    """
    if not is_redis_available():
        return {
            "status": "unavailable",
            "timestamp": datetime.now().isoformat(),
            "request_id": request.state.request_id,
            "message": "Redis cache is not available or not configured properly"
        }
    
    # Get Redis statistics
    stats = redis_get_stats()
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "request_id": request.state.request_id,
        "statistics": stats,
        "environment": {
            "host": os.environ.get("REDIS_HOST", "redis"),
            "port": os.environ.get("REDIS_PORT", 6379),
            "ttl": os.environ.get("CACHE_TTL", 3600)
        }
    }

@router.get("/redis/flush", response_model=Dict[str, Any])
async def flush_redis_cache(request: Request):
    """
    Flush all data from Redis cache.
    
    Clears all cached data in Redis. This endpoint is useful for debugging and
    troubleshooting when cache needs to be cleared.
    """
    from app.redis_utils import redis_client
    
    if not is_redis_available():
        return {
            "status": "error",
            "message": "Redis cache is not available",
            "request_id": request.state.request_id,
            "timestamp": datetime.now().isoformat()
        }
    
    try:
        result = redis_client.flushdb()
        success = result is True
        
        return {
            "status": "success" if success else "error",
            "message": "Redis cache successfully flushed" if success else "Failed to flush Redis cache",
            "request_id": request.state.request_id,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error flushing Redis cache: {str(e)}",
            "request_id": request.state.request_id,
            "timestamp": datetime.now().isoformat()
        }

@router.get("/stats", response_model=Dict[str, Any])
async def get_statistics(request: Request, db: Session = Depends(get_db)):
    """
    Get statistics about AEDs and reports in the system.
    
    Returns counts and aggregated statistics for AEDs and reports,
    useful for dashboards and monitoring.
    """
    stats = {}
    
    try:
        # AED statistics
        aed_stats = {}
        aed_stats["total"] = db.query(func.count(AEDModel.id)).scalar()
        
        # Count by public use status
        public_aeds = db.query(func.count(AEDModel.id)).filter(AEDModel.public_use == True).scalar()
        aed_stats["public"] = public_aeds
        aed_stats["private"] = aed_stats["total"] - public_aeds
        
        # Count by flag status
        flagged_aeds = db.query(func.count(AEDModel.id)).filter(AEDModel.is_flagged == True).scalar()
        aed_stats["flagged"] = flagged_aeds
        
        # Group by category
        category_counts = db.query(AEDModel.category, func.count(AEDModel.id).label('count')) \
                         .group_by(AEDModel.category) \
                         .all()
        aed_stats["by_category"] = {category or "Unknown": count for category, count in category_counts}
        
        # Report statistics
        report_stats = {}
        report_stats["total"] = db.query(func.count(AEDReportModel.id)).scalar()
        
        # Group by report type
        report_type_counts = db.query(AEDReportModel.report_type, func.count(AEDReportModel.id).label('count')) \
                            .group_by(AEDReportModel.report_type) \
                            .all()
        report_stats["by_type"] = {report_type: count for report_type, count in report_type_counts}
        
        # Group by status
        report_status_counts = db.query(AEDReportModel.status, func.count(AEDReportModel.id).label('count')) \
                              .group_by(AEDReportModel.status) \
                              .all()
        report_stats["by_status"] = {status: count for status, count in report_status_counts}
        
        stats["aeds"] = aed_stats
        stats["reports"] = report_stats
        
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        stats["error"] = str(e)
    
    return {
        "data": stats,
        "metadata": {
            "request_id": request.state.request_id,
            "timestamp": datetime.now().isoformat()
        }
    }


@router.get("/coverage", response_model=Dict[str, Any])
async def evaluate_aed_coverage(
    request: Request,
    lat: float, 
    lng: float, 
    radius: float = 5.0,  # 5km radius
    db: Session = Depends(get_db)
):
    """
    Evaluate AED coverage for a specific area.
    
    Parameters:
    - lat: Latitude of center point
    - lng: Longitude of center point
    - radius: Radius in kilometers (default: 5.0)
    
    Returns information about AED coverage in the specified area,
    including count, density, and distribution metrics.
    """
    try:
        # Count AEDs within the radius
        aed_count_query = text("""
            SELECT COUNT(*) AS count
            FROM aeds
            WHERE ST_DWithin(
                geo_point::geography,
                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                :radius * 1000
            )
        """)
        
        aed_count_result = db.execute(
            aed_count_query, 
            {"lat": lat, "lng": lng, "radius": radius}
        ).scalar()
        
        # Calculate area in square kilometers (approximation)
        area = 3.14159 * radius * radius
        
        # Calculate density
        density = aed_count_result / area if area > 0 else 0
        
        # Get distance statistics
        distance_stats_query = text("""
            SELECT 
                MIN(ST_Distance(
                    geo_point::geography,
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
                )/1000) AS min_distance_km,
                MAX(ST_Distance(
                    geo_point::geography,
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
                )/1000) AS max_distance_km,
                AVG(ST_Distance(
                    geo_point::geography,
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
                )/1000) AS avg_distance_km
            FROM aeds
            WHERE ST_DWithin(
                geo_point::geography,
                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                :radius * 1000
            )
        """)
        
        distance_stats = db.execute(
            distance_stats_query, 
            {"lat": lat, "lng": lng, "radius": radius}
        ).fetchone()
        
        # Count public vs private AEDs
        public_aeds_query = text("""
            SELECT COUNT(*) AS count
            FROM aeds
            WHERE ST_DWithin(
                geo_point::geography,
                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                :radius * 1000
            )
            AND public_use = true
        """)
        
        public_count = db.execute(
            public_aeds_query, 
            {"lat": lat, "lng": lng, "radius": radius}
        ).scalar()
        
        # Evaluate coverage based on density
        coverage_rating = "Unknown"
        if density >= 2.0:
            coverage_rating = "Excellent"
        elif density >= 1.0:
            coverage_rating = "Good"
        elif density >= 0.5:
            coverage_rating = "Moderate"
        elif density > 0:
            coverage_rating = "Poor"
        else:
            coverage_rating = "No Coverage"
        
        result = {
            "coordinates": {
                "latitude": lat,
                "longitude": lng
            },
            "radius_km": radius,
            "area_sq_km": round(area, 2),
            "aed_count": aed_count_result,
            "public_aeds": public_count,
            "private_aeds": aed_count_result - public_count,
            "density": {
                "aeds_per_sq_km": round(density, 3),
                "rating": coverage_rating
            },
            "distance_stats": {
                "min_distance_km": round(distance_stats.min_distance_km, 3) if distance_stats.min_distance_km else None,
                "max_distance_km": round(distance_stats.max_distance_km, 3) if distance_stats.max_distance_km else None,
                "avg_distance_km": round(distance_stats.avg_distance_km, 3) if distance_stats.avg_distance_km else None
            }
        }
        
    except Exception as e:
        logger.error(f"Error evaluating AED coverage: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error evaluating AED coverage: {str(e)}"
        )
    
    return {
        "data": result,
        "metadata": {
            "request_id": request.state.request_id,
            "timestamp": datetime.now().isoformat()
        }
    }

@router.get("/validate-geo", response_model=Dict[str, Any])
async def validate_geospatial_data(request: Request, db: Session = Depends(get_db)):
    """
    Validate geospatial data integrity in the database.
    
    Checks for invalid coordinates, missing geo_point values, and other 
    potential issues with the geospatial data.
    """
    results = {
        "issues_found": 0,
        "details": []
    }
    
    try:
        # Check for invalid coordinates (outside reasonable bounds)
        invalid_coords_query = db.query(AEDModel.id, AEDModel.name, AEDModel.latitude, AEDModel.longitude) \
                              .filter(
                                  (AEDModel.latitude < -90) | 
                                  (AEDModel.latitude > 90) | 
                                  (AEDModel.longitude < -180) | 
                                  (AEDModel.longitude > 180)
                              ).all()
        
        if invalid_coords_query:
            results["issues_found"] += len(invalid_coords_query)
            results["details"].append({
                "issue": "invalid_coordinates",
                "count": len(invalid_coords_query),
                "affected_records": [{"id": aed.id, "name": aed.name, "lat": aed.latitude, "lng": aed.longitude} 
                                   for aed in invalid_coords_query]
            })
            
        # Check for null coordinates
        null_coords_query = db.query(AEDModel.id, AEDModel.name) \
                           .filter(
                               (AEDModel.latitude.is_(None)) | 
                               (AEDModel.longitude.is_(None))
                           ).all()
        
        if null_coords_query:
            results["issues_found"] += len(null_coords_query)
            results["details"].append({
                "issue": "null_coordinates",
                "count": len(null_coords_query),
                "affected_records": [{"id": aed.id, "name": aed.name} for aed in null_coords_query]
            })
            
        # Check for records where geo_point is null but coordinates are valid
        missing_geopoint_query = text("""
            SELECT id, name, latitude, longitude
            FROM aeds
            WHERE geo_point IS NULL 
            AND latitude IS NOT NULL 
            AND longitude IS NOT NULL
        """)
        
        missing_geopoint_results = db.execute(missing_geopoint_query).fetchall()
        
        if missing_geopoint_results:
            results["issues_found"] += len(missing_geopoint_results)
            results["details"].append({
                "issue": "missing_geo_point",
                "count": len(missing_geopoint_results),
                "affected_records": [{"id": row.id, "name": row.name} for row in missing_geopoint_results]
            })
        
        # If issues were found, provide a recommendation
        if results["issues_found"] > 0:
            results["recommendation"] = "Run the /refresh endpoint to update and fix geospatial data issues"
                
    except Exception as e:
        logger.error(f"Error validating geospatial data: {e}")
        results["error"] = str(e)
    
    return {
        "data": results,
        "metadata": {
            "request_id": request.state.request_id,
            "timestamp": datetime.now().isoformat()
        }
    }


@router.get("/logs", response_model=Dict[str, Any])
async def get_recent_logs(
    request: Request,
    log_type: str = "all",
    limit: int = 100
):
    """
    Get recent log entries from the application.
    
    Parameters:
    - log_type: Type of logs to retrieve (all, error, warning, info)
    - limit: Maximum number of log entries to return
    
    Returns the most recent log entries based on the specified criteria.
    """
    try:
        # Simple in-memory log retrieval for now
        # In a production environment, this should retrieve from proper log storage
        log_level_filter = None
        
        # Set log level filter based on request
        if log_type.lower() == "error":
            log_level_filter = logging.ERROR
        elif log_type.lower() == "warning":
            log_level_filter = logging.WARNING
        elif log_type.lower() == "info":
            log_level_filter = logging.INFO
            
        # For demo, generate sample logs
        # In production, you would retrieve actual logs from a file or database
        sample_logs = [
            {"level": "INFO", "timestamp": datetime.now().isoformat(), "message": "API server started successfully"},
            {"level": "INFO", "timestamp": datetime.now().isoformat(), "message": "Database connection established"},
            {"level": "WARNING", "timestamp": datetime.now().isoformat(), "message": "Rate limiting applied to client 192.168.1.100"},
            {"level": "ERROR", "timestamp": datetime.now().isoformat(), "message": "Failed to connect to external data source"}
        ]
        
        # Filter logs based on requested type
        if log_level_filter:
            filtered_logs = [
                log for log in sample_logs 
                if log["level"] == logging.getLevelName(log_level_filter)
            ]
        else:
            filtered_logs = sample_logs
            
        # Limit the number of logs returned
        limited_logs = filtered_logs[:limit]
        
        return {
            "logs": limited_logs,
            "metadata": {
                "count": len(limited_logs),
                "log_type": log_type,
                "limit": limit,
                "request_id": request.state.request_id,
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error retrieving logs: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving logs: {str(e)}"
        )


@router.get("/zeabur-verify", response_model=Dict[str, Any])
async def zeabur_verification(request: Request):
    """
    Special endpoint to verify Zeabur deployment is working correctly.
    
    Returns information specific to Zeabur deployment, including environment
    variables and service information.
    """
    # Get Zeabur-specific environment variables
    zeabur_vars = {k: v for k, v in os.environ.items() if k.startswith("ZEABUR_")}
    
    # Get basic system information
    system_info = {
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "memory_usage_percent": psutil.virtual_memory().percent
    }
    
    # Check database configuration (without connecting)
    db_config = {
        "db_host": os.environ.get("DB_HOST"),
        "db_name": os.environ.get("DB_NAME"),
        "db_user": os.environ.get("DB_USER"),
        "has_db_password": "Yes" if os.environ.get("DB_PASSWORD") else "No",
        "connection_string_format": os.environ.get("DATABASE_URL", "").split("@")[0].split(":")[0] 
                                    if os.environ.get("DATABASE_URL") else "Not set"
    }
    
    return {
        "status": "success",
        "message": "Zeabur deployment verification",
        "timestamp": datetime.now().isoformat(),
        "request_id": request.state.request_id,
        "zeabur": {
            "detected": bool(zeabur_vars),
            "environment_variables": list(zeabur_vars.keys())
        },
        "system": system_info,
        "database_config": db_config
    }


def _format_uptime(seconds: int) -> str:
    """Format seconds into a human-readable uptime string."""
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds > 0 or not parts:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
        
    return ", ".join(parts)
