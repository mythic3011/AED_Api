"""
AED Data Service Module

This module provides services for managing AED data, including functions
to download, parse, update and validate AED information from external sources.
"""

import logging
import pandas as pd 
import requests
from sqlalchemy import func, text
from sqlalchemy.orm import Session
from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime

from app.database import AEDModel, SessionLocal
from app.utils import url, headers

logger = logging.getLogger("aed_api")

def download_and_parse_data() -> Optional[pd.DataFrame]:
    """
    Downloads AED data from the official source and parses it.
    
    Returns:
        DataFrame with the parsed data or None if the operation failed
    """
    # Download data from source
    logger.info("Downloading AED data from source...")
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        logger.info(f"Successfully downloaded data: {len(response.content)} bytes")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download data: {str(e)}")
        return None
            
    # Parse CSV data
    logger.info("Parsing CSV data...")
    try:
        df = pd.read_csv(
            pd.io.common.StringIO(response.text),
            encoding='utf-8',
            on_bad_lines='skip',
            low_memory=False
        )
        logger.info(f"CSV parsed successfully. Found {len(df)} rows and {len(df.columns)} columns")
        return df
    except Exception as e:
        logger.error(f"Error parsing CSV data: {str(e)}")
        return None

def map_csv_columns(df: pd.DataFrame) -> Optional[Dict[str, str]]:
    """
    Maps columns from the CSV file to database fields.
    
    Args:
        df: DataFrame containing the CSV data
        
    Returns:
        Dictionary mapping database fields to CSV column names or None if mapping failed
    """
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
    required_fields = ["name", "address", "lat", "lng"]
    missing_fields = [field for field in required_fields if field not in column_matches]
    
    if missing_fields:
        logger.error(f"Missing required fields in CSV: {', '.join(missing_fields)}")
        logger.error(f"Available columns: {', '.join(df.columns)}")
        return None
        
    logger.info(f"Column mapping established: {column_matches}")
    return column_matches

def prepare_database_schema(db: Session) -> bool:
    """
    Ensures the database schema is ready for the data import.
    
    Args:
        db: SQLAlchemy session
        
    Returns:
        True if the schema is ready, False otherwise
    """
    try:
        db.execute(text("ALTER TABLE aeds ALTER COLUMN service_hours TYPE VARCHAR;"))
        logger.info("Successfully altered service_hours column to VARCHAR type")
        return True
    except Exception as schema_error:
        logger.warning(f"Schema adjustment note: {str(schema_error)}")
        # Continue anyway as this might be just a warning that the column is already VARCHAR
        return True

def process_coordinates(row: pd.Series, column_matches: Dict[str, str], index: int) -> Optional[Tuple[float, float]]:
    """
    Extracts and validates coordinates from a row.
    
    Args:
        row: DataFrame row
        column_matches: Column mapping dictionary
        index: Row index for logging
        
    Returns:
        Tuple of (latitude, longitude) or None if invalid
    """
    try:
        lat_col = column_matches.get("lat")
        lng_col = column_matches.get("lng")
        
        if lat_col is None or lng_col is None:
            logger.warning(f"Missing coordinate columns at row {index}")
            return None
            
        lat = float(row[lat_col]) if pd.notna(row[lat_col]) else 0.0
        lng = float(row[lng_col]) if pd.notna(row[lng_col]) else 0.0
        
        # Basic validation
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            logger.warning(f"Invalid coordinates at row {index}: lat={lat}, lng={lng}")
            return None
            
        return lat, lng
        
    except (ValueError, TypeError) as e:
        logger.warning(f"Error parsing coordinates at row {index}: {str(e)}")
        return None

def safe_get_value(row: pd.Series, field: str, column_matches: Dict[str, str], default: Any = None) -> Any:
    """
    Safely retrieves a value from a DataFrame row.
    
    Args:
        row: DataFrame row
        field: Field name to retrieve
        column_matches: Column mapping dictionary
        default: Default value if the field is not found or is NaN
        
    Returns:
        The field value or the default value
    """
    col = column_matches.get(field)
    if col is None:
        return default
    val = row[col]
    return default if pd.isna(val) else val

def process_and_insert_data(db: Session, df: pd.DataFrame, column_matches: Dict[str, str]) -> Dict[str, int]:
    """
    Processes and inserts AED data into the database.
    
    Args:
        db: SQLAlchemy session
        df: DataFrame with the data
        column_matches: Column mapping dictionary
        
    Returns:
        Dictionary with success, error and skipped counts
    """
    batch_size = 100
    aeds_to_add = []
    success_count = 0
    error_count = 0
    skipped_rows = 0
    
    # Process each row
    for index, row in df.iterrows():
        try:
            # Process coordinates
            coordinates = process_coordinates(row, column_matches, index)
            if coordinates is None:
                skipped_rows += 1
                continue
                
            lat, lng = coordinates
            
            # Handle service hours field
            service_hours = safe_get_value(row, "service_hours", column_matches, "")
            if not pd.isna(service_hours):
                service_hours = str(service_hours)
            
            # Parse boolean fields safely
            public_use_val = safe_get_value(row, "public_use", column_matches, "No")
            if isinstance(public_use_val, str):
                public_use = public_use_val.lower() in ["yes", "true", "1"]
            else:
                public_use = bool(public_use_val)
            
            # Create AED model with proper geo_point
            # The geo_point needs special handling as a PostGIS point
            aed = AEDModel(
                name=safe_get_value(row, "name", column_matches, "Unknown"),
                address=safe_get_value(row, "address", column_matches, ""),
                location_detail=safe_get_value(row, "location_detail", column_matches, ""),
                latitude=lat,
                longitude=lng,
                public_use=public_use,
                allowed_operators=safe_get_value(row, "allowed_operators", column_matches, ""),
                access_persons=safe_get_value(row, "access_persons", column_matches, ""),
                category=safe_get_value(row, "category", column_matches, ""),
                service_hours=service_hours,
                brand=safe_get_value(row, "brand", column_matches, ""),
                model=safe_get_value(row, "model", column_matches, ""),
                remark=safe_get_value(row, "remark", column_matches, ""),
                geo_point=f'POINT({lng} {lat})'
            )
            
            # Add to batch
            aeds_to_add.append(aed)
            success_count += 1
            
            # Commit in batches
            if len(aeds_to_add) >= batch_size:
                db.add_all(aeds_to_add)
                db.flush()
                aeds_to_add = []
                logger.info(f"Processed {success_count} AEDs so far...")
                
        except Exception as row_error:
            error_count += 1
            logger.warning(f"Error processing row {index}: {str(row_error)}")
            continue
    
    # Add any remaining AEDs in the final batch
    if aeds_to_add:
        db.add_all(aeds_to_add)
        db.flush()
        
    return {
        "success": success_count,
        "errors": error_count,
        "skipped": skipped_rows
    }

def update_aed_database(request_id: str) -> Dict[str, Any]:
    """
    Main function to update the AED database from the external source.
    
    Args:
        request_id: The ID of the request for logging
        
    Returns:
        Dictionary with the result of the operation
    """
    logger.info(f"Starting AED data refresh task (RequestID: {request_id})")
    db = SessionLocal()
    result = {
        "status": "failed",
        "message": "Unknown error occurred",
        "details": {}
    }
    
    try:
        # Step 1: Download and parse data
        df = download_and_parse_data()
        if df is None:
            result["message"] = "Failed to download or parse data"
            return result
            
        # Step 2: Map columns and validate
        column_matches = map_csv_columns(df)
        if not column_matches:
            result["message"] = "Failed to map CSV columns to database fields"
            return result
        
        # Step 3: Ensure database schema is compatible
        if not prepare_database_schema(db):
            result["message"] = "Failed to prepare database schema"
            return result
        
        # Step 4: Get record count for reporting
        count_before = db.query(func.count(AEDModel.id)).scalar()
        
        # Step 5: Begin transaction and clear existing data
        transaction = db.begin()
        try:
            # Delete existing records
            db.query(AEDModel).delete()
            logger.info("Existing AED data cleared")
            
            # Process and insert new data
            process_result = process_and_insert_data(db, df, column_matches)
            
            # Commit the transaction
            transaction.commit()
            
            # Log results
            count_after = db.query(func.count(AEDModel.id)).scalar()
            
            result["status"] = "success"
            result["message"] = "AED data refresh completed successfully"
            result["details"] = {
                "records_before": count_before,
                "records_after": count_after,
                "processed": process_result
            }
            
            logger.info(f"Data refresh complete. Records before: {count_before}, after: {count_after}")
            logger.info(f"Import summary: {process_result['success']} successful, " + 
                      f"{process_result['errors']} errors, {process_result['skipped']} skipped")
            
        except Exception as transaction_error:
            transaction.rollback()
            error_msg = str(transaction_error)
            logger.error(f"Transaction failed: {error_msg}")
            result["message"] = f"Database transaction failed: {error_msg}"
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unhandled error in refresh task: {error_msg}")
        result["message"] = f"Unhandled error: {error_msg}"
    finally:
        db.close()
    
    return result
