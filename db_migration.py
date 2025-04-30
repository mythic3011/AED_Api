import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database connection
# Get connection parameters from environment variables with Docker-compatible defaults
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")
DB_HOST = os.environ.get("DB_HOST", "db")  # Use 'db' as default for Docker
DB_NAME = os.environ.get("DB_NAME", "aed_db")

DATABASE_URL = os.environ.get(
    "DATABASE_URL", 
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
)
engine = create_engine(DATABASE_URL)

def run_migration():
    """Run database migration to ensure all tables and columns exist"""
    logger.info("Starting database migration")
    
    # Connect to database
    with engine.begin() as conn:
        # 1. Make sure PostGIS extension is available
        logger.info("Ensuring PostGIS extension is installed")
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        
        # 2. Check if the aeds table exists
        logger.info("Checking if aeds table exists")
        result = conn.execute(text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'aeds')"))
        table_exists = result.scalar()
        
        if not table_exists:
            logger.info("Creating aeds table")
            # Create the table if it doesn't exist
            conn.execute(text("""
            CREATE TABLE aeds (
                id SERIAL PRIMARY KEY,
                name VARCHAR,
                address VARCHAR,
                location_detail VARCHAR,
                latitude FLOAT,
                longitude FLOAT,
                public_use BOOLEAN,
                allowed_operators VARCHAR,
                access_persons VARCHAR,
                category VARCHAR,
                service_hours VARCHAR,
                brand VARCHAR,
                model VARCHAR,
                remark VARCHAR,
                is_flagged BOOLEAN DEFAULT FALSE,
                flag_reason VARCHAR NULL,
                flagged_at VARCHAR NULL,
                geo_point GEOGRAPHY(POINT, 4326)
            )
            """))
            logger.info("aeds table created successfully")
        else:
            logger.info("aeds table already exists, checking columns")
            
            # 3. Check if the is_flagged column exists and add it if it doesn't
            result = conn.execute(text("SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'aeds' AND column_name = 'is_flagged')"))
            if not result.scalar():
                logger.info("Adding is_flagged column")
                conn.execute(text("ALTER TABLE aeds ADD COLUMN is_flagged BOOLEAN DEFAULT FALSE"))
                
            # 4. Check if the flag_reason column exists and add it if it doesn't
            result = conn.execute(text("SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'aeds' AND column_name = 'flag_reason')"))
            if not result.scalar():
                logger.info("Adding flag_reason column")
                conn.execute(text("ALTER TABLE aeds ADD COLUMN flag_reason VARCHAR NULL"))
                
            # 5. Check if the flagged_at column exists and add it if it doesn't
            result = conn.execute(text("SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'aeds' AND column_name = 'flagged_at')"))
            if not result.scalar():
                logger.info("Adding flagged_at column")
                conn.execute(text("ALTER TABLE aeds ADD COLUMN flagged_at VARCHAR NULL"))
                
            # 6. Check if geo_point column exists and add it if it doesn't
            result = conn.execute(text("SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'aeds' AND column_name = 'geo_point')"))
            if not result.scalar():
                logger.info("Adding geo_point column")
                try:
                    conn.execute(text("ALTER TABLE aeds ADD COLUMN geo_point GEOGRAPHY(POINT, 4326)"))
                    
                    # Update geo_point for existing records
                    conn.execute(text("UPDATE aeds SET geo_point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography"))
                except Exception as e:
                    logger.error(f"Error adding geo_point column: {e}")
        
        # 7. Check if aed_reports table exists and create it if not
        result = conn.execute(text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'aed_reports')"))
        if not result.scalar():
            logger.info("Creating aed_reports table")
            conn.execute(text("""
            CREATE TABLE aed_reports (
                id SERIAL PRIMARY KEY,
                aed_id INTEGER,
                report_type VARCHAR,
                description VARCHAR,
                reporter_name VARCHAR,
                reporter_email VARCHAR,
                reporter_phone VARCHAR,
                created_at VARCHAR,
                status VARCHAR DEFAULT 'pending'
            )
            """))
            logger.info("aed_reports table created successfully")
    
    logger.info("Database migration completed successfully")

if __name__ == "__main__":
    run_migration()
