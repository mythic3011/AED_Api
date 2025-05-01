import os
import time
import logging
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, text, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError, DatabaseError
from geoalchemy2 import Geography

logger = logging.getLogger("aed_api")

# Get DB connection details from environment variables
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")
DB_HOST = os.environ.get("DB_HOST", "db")
DB_NAME = os.environ.get("DB_NAME", "aed_db")

# Construct the database URL
DATABASE_URL = os.environ.get(
    "DATABASE_URL", 
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
)

# Configure database connection with pool settings and retry logic
def create_db_engine(url, max_retries=5, retry_interval=5):
    """Create a database engine with retry logic"""
    retry_count = 0
    last_error = None
    
    while retry_count < max_retries:
        try:
            # Create engine with connection pool settings
            engine = create_engine(
                url,
                pool_pre_ping=True,  # Check connection before use
                pool_recycle=3600,   # Recycle connections after 1 hour
                pool_size=10,        # Maximum pool size
                max_overflow=20,     # Allow up to 20 connections beyond pool_size
                pool_timeout=30,     # Wait 30 sec for available connection
            )
            
            # Test the connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                
            logger.info("Database connection established successfully")
            return engine
            
        except (OperationalError, DatabaseError) as e:
            last_error = e
            retry_count += 1
            logger.warning(f"Database connection attempt {retry_count} failed: {e}")
            
            if retry_count < max_retries:
                logger.info(f"Retrying database connection in {retry_interval} seconds...")
                time.sleep(retry_interval)
            else:
                logger.error(f"Failed to connect to database after {max_retries} attempts")
                # Still return the engine, we'll handle connection errors at runtime
                return create_engine(
                    url,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                    pool_size=10,
                    max_overflow=20,
                    pool_timeout=30,
                )
                
        except Exception as e:
            logger.error(f"Unexpected error creating database engine: {e}")
            raise

# Create the database engine with retry logic
engine = create_db_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_superuser_engine():
    postgres_superuser = os.environ.get("POSTGRES_SUPERUSER", "postgres")
    postgres_superuser_password = os.environ.get("POSTGRES_SUPERUSER_PASSWORD", "postgres")
    superuser_url = f"postgresql://{postgres_superuser}:{postgres_superuser_password}@{DB_HOST}/{DB_NAME}"
    return create_engine(superuser_url)

def setup_postgis():
    superuser_engine = get_superuser_engine()
    with superuser_engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))

setup_postgis()

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
    service_hours = Column(String)
    brand = Column(String)
    model = Column(String)
    remark = Column(String)
    is_flagged = Column(Boolean, default=False, server_default="false")
    flag_reason = Column(String, nullable=True)
    flagged_at = Column(String, nullable=True)
    geo_point = Column(Geography(geometry_type='POINT', srid=4326))

class AEDReportModel(Base):
    __tablename__ = "aed_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    aed_id = Column(Integer)
    report_type = Column(String)
    description = Column(String)
    reporter_name = Column(String)
    reporter_email = Column(String)
    reporter_phone = Column(String)
    created_at = Column(String)
    status = Column(String, default="pending")

Base.metadata.create_all(bind=engine)

def get_db():
    """
    Database session dependency for FastAPI endpoints.
    
    Creates a new database session for each request and closes it when done.
    Tests the connection before yielding to catch connectivity issues early.
    """
    db = SessionLocal()
    
    try:
        # Test connection before yielding
        try:
            # Simple query to test connection
            db.execute(text("SELECT 1"))
        except (OperationalError, DatabaseError) as e:
            # Store the error message on the session for endpoints to check
            error_message = str(e)
            logger.warning(f"Database connection check failed in get_db(): {error_message}")
            
            # Set session attribute to indicate connection issues
            # This can be checked by endpoints to provide appropriate responses
            setattr(db, "_connection_error", error_message)
            
            # We'll still yield the session rather than failing immediately
            # This allows each endpoint to decide how to handle the error
        
        yield db
    except Exception as e:
        logger.error(f"Unexpected error in database session: {str(e)}")
        raise
    finally:
        # Always ensure the session is closed
        try:
            db.close()
        except Exception as close_error:
            logger.error(f"Error closing database session: {str(close_error)}")
