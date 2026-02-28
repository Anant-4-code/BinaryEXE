from datetime import datetime, date, time
from typing import List, Optional

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    created_at: datetime

    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MedicineBase(BaseModel):
    original_name: str
    normalized_name: str
    dose: Optional[str] = None
    frequency: Optional[str] = None
    duration_days: Optional[int] = None
    instructions: Optional[str] = None
    confidence: float
    age_range: Optional[str] = None


class MedicineCreate(MedicineBase):
    pass


class MedicineOut(MedicineBase):
    id: int

    class Config:
        orm_mode = True


class PrescriptionBase(BaseModel):
    title: str


class PrescriptionCreate(PrescriptionBase):
    raw_text: Optional[str] = None


class PrescriptionOut(PrescriptionBase):
    id: int
    raw_text: Optional[str]
    confidence_score: float
    status: str
    created_at: datetime
    medicines: List[MedicineOut] = []

    class Config:
        orm_mode = True


class DoseOut(BaseModel):
    id: int
    date: date
    time: time
    taken: bool
    taken_at: Optional[datetime]
    medicine_id: int

    class Config:
        orm_mode = True


class AnalyticsSummary(BaseModel):
    total_doses: int
    taken_doses: int
    adherence_percentage: float
    missed_doses: int
    current_streak: int


class NotificationOut(BaseModel):
    id: int
    type: str
    message: str
    scheduled_for: datetime
    sent: bool

    class Config:
        orm_mode = True


class OCRResult(BaseModel):
    raw_text: str
    ocr_reliability: float


class GemmaMedicine(BaseModel):
    medicine: str
    dose: str
    frequency: str
    duration: str
    instructions: str
    age_range: Optional[str] = ""


class ExtractionResult(BaseModel):
    medicines: List[GemmaMedicine]
    json_parse_success: float


class PatientDoctorExtraction(BaseModel):
    patient: dict
    doctor: dict

