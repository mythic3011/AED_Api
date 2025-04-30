from pydantic import BaseModel, Field, validator
from typing import Optional, List

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
