from datetime import datetime, date, time

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text, Time, Float
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    prescriptions = relationship("Prescription", back_populates="user")


class PrescriptionStatusEnum(str):
    NEEDS_REVIEW = "needs_review"
    ACTIVE = "active"
    COMPLETED = "completed"


class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    caption = Column(Text, nullable=True)
    raw_text = Column(Text, nullable=True)
    image_path = Column(String(512), nullable=True)
    confidence_score = Column(Float, default=0.0)
    status = Column(String(50), default=PrescriptionStatusEnum.NEEDS_REVIEW)
    created_at = Column(DateTime, default=datetime.utcnow)
    # AI-extracted patient and doctor details (JSON strings)
    patient_details_json = Column(Text, nullable=True)
    doctor_details_json = Column(Text, nullable=True)
    # Transliterated prescription by language: {"hindi": "...", "tamil": "..."}
    transliterated_json = Column(Text, nullable=True)
    export_overrides_json = Column(Text, nullable=True)

    user = relationship("User", back_populates="prescriptions")
    medicines = relationship("Medicine", back_populates="prescription", cascade="all, delete-orphan")
    doses = relationship("Dose", back_populates="prescription", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="prescription", cascade="all, delete-orphan")


class Medicine(Base):
    __tablename__ = "medicines"

    id = Column(Integer, primary_key=True, index=True)
    prescription_id = Column(Integer, ForeignKey("prescriptions.id"), nullable=False)

    original_name = Column(String(255), nullable=False)
    normalized_name = Column(String(255), nullable=False)
    dose = Column(String(255), nullable=True)
    frequency = Column(String(50), nullable=True)
    duration_days = Column(Integer, nullable=True)
    instructions = Column(Text, nullable=True)
    confidence = Column(Float, default=0.0)
    # AI-generated explanation (uses, side effects, etc.)
    explanation = Column(Text, nullable=True)
    # Age group or range who can consume (e.g. "Adults and children 12 years and older")
    age_range = Column(String(255), nullable=True)

    prescription = relationship("Prescription", back_populates="medicines")
    doses = relationship("Dose", back_populates="medicine", cascade="all, delete-orphan")


class Dose(Base):
    __tablename__ = "doses"

    id = Column(Integer, primary_key=True, index=True)
    prescription_id = Column(Integer, ForeignKey("prescriptions.id"), nullable=False)
    medicine_id = Column(Integer, ForeignKey("medicines.id"), nullable=False)

    date = Column(Date, nullable=False)
    time = Column(Time, nullable=False)
    taken = Column(Boolean, default=False)
    taken_at = Column(DateTime, nullable=True)

    prescription = relationship("Prescription", back_populates="doses")
    medicine = relationship("Medicine", back_populates="doses")


class NotificationTypeEnum(str):
    UPCOMING = "upcoming"
    MISSED = "missed"
    COMPLETED = "completed"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    prescription_id = Column(Integer, ForeignKey("prescriptions.id"), nullable=False)
    dose_id = Column(Integer, ForeignKey("doses.id"), nullable=True)

    type = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    scheduled_for = Column(DateTime, nullable=False)
    sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    prescription = relationship("Prescription", back_populates="notifications")

