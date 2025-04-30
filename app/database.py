import os
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, text, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from geoalchemy2 import Geography

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
engine = create_engine(DATABASE_URL)
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
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
