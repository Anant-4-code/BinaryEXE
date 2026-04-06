from datetime import datetime, date, time

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text, Time, Float
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    role = Column(String(50), default="patient")  # patient | receptionist | doctor
    created_at = Column(DateTime, default=datetime.utcnow)

    prescriptions = relationship("Prescription", back_populates="user", foreign_keys="Prescription.user_id")
    forward_actions = relationship("ForwardQueue", back_populates="forwarded_by_user", foreign_keys="ForwardQueue.forwarded_by")
    doctor_verifications = relationship("ForwardQueue", back_populates="doctor_user", foreign_keys="ForwardQueue.doctor_id")
    doctor_notes = relationship("DoctorNote", back_populates="doctor")


class PrescriptionStatusEnum(str):
    NEEDS_REVIEW = "needs_review"
    ACTIVE = "active"
    COMPLETED = "completed"
    FORWARDED = "forwarded"
    VERIFIED = "verified"
    REJECTED = "rejected"
    DRAFT = "draft"


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
    # Doctor verification fields
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    reject_reason = Column(Text, nullable=True)

    user = relationship("User", back_populates="prescriptions", foreign_keys=[user_id])
    verifier = relationship("User", foreign_keys=[verified_by])
    medicines = relationship("Medicine", back_populates="prescription", cascade="all, delete-orphan")
    doses = relationship("Dose", back_populates="prescription", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="prescription", cascade="all, delete-orphan")
    forward_queues = relationship("ForwardQueue", back_populates="prescription", cascade="all, delete-orphan")
    doctor_notes = relationship("DoctorNote", back_populates="prescription", cascade="all, delete-orphan")


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


class ForwardQueue(Base):
    """Tracks when a receptionist forwards a prescription to a doctor's queue."""
    __tablename__ = "forward_queue"

    id = Column(Integer, primary_key=True, index=True)
    prescription_id = Column(Integer, ForeignKey("prescriptions.id"), nullable=False)
    forwarded_by = Column(Integer, ForeignKey("users.id"), nullable=False)   # receptionist user id
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True)       # assigned doctor (optional)
    priority = Column(String(20), default="normal")                          # normal | urgent
    note = Column(Text, nullable=True)
    status = Column(String(30), default="pending")                           # pending | reviewed | verified | rejected
    forwarded_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)

    prescription = relationship("Prescription", back_populates="forward_queues")
    forwarded_by_user = relationship("User", back_populates="forward_actions", foreign_keys=[forwarded_by])
    doctor_user = relationship("User", back_populates="doctor_verifications", foreign_keys=[doctor_id])


class DoctorNote(Base):
    """Doctor notes on a prescription."""
    __tablename__ = "doctor_notes"

    id = Column(Integer, primary_key=True, index=True)
    prescription_id = Column(Integer, ForeignKey("prescriptions.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    note = Column(Text, nullable=False)
    warning = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    prescription = relationship("Prescription", back_populates="doctor_notes")
    doctor = relationship("User", back_populates="doctor_notes")


# ═══════════════════════════════════════════════════════════════════════════
# AI FRACTURE ANALYSIS  (YOLOv7 + Qwen)
# ═══════════════════════════════════════════════════════════════════════════

class XrayScan(Base):
    """One X-ray upload session linked to a patient."""
    __tablename__ = "xray_scans"

    id           = Column(Integer, primary_key=True, index=True)
    patient_id   = Column(Integer, ForeignKey("users.id"), nullable=True)
    scan_uuid    = Column(String(64), unique=True, nullable=False, index=True)
    image_path   = Column(String(512), nullable=False)
    filename     = Column(String(255), nullable=True)
    uploaded_at  = Column(DateTime, default=datetime.utcnow)
    status       = Column(String(30), default="uploaded")   # uploaded | processing | done | error
    notes        = Column(Text, nullable=True)

    detections    = relationship("XrayDetection",    back_populates="scan", cascade="all, delete-orphan")
    ai_reports    = relationship("XrayAIReport",     back_populates="scan", cascade="all, delete-orphan")
    verifications = relationship("XrayVerification", back_populates="scan", cascade="all, delete-orphan")


class XrayDetection(Base):
    """Individual YOLO detection within a scan."""
    __tablename__ = "xray_detections"

    id            = Column(Integer, primary_key=True, index=True)
    scan_id       = Column(Integer, ForeignKey("xray_scans.id"), nullable=False)
    label         = Column(String(100), nullable=False)
    label_display = Column(String(100), nullable=True)
    confidence    = Column(Float, nullable=False)
    bbox_json     = Column(Text, nullable=True)
    class_id      = Column(Integer, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)

    scan = relationship("XrayScan", back_populates="detections")


class XrayAIReport(Base):
    """AI-generated clinical explanation for a scan."""
    __tablename__ = "xray_ai_reports"

    id             = Column(Integer, primary_key=True, index=True)
    scan_id        = Column(Integer, ForeignKey("xray_scans.id"), nullable=False)
    explanation    = Column(Text, nullable=False)
    annotated_path = Column(String(512), nullable=True)
    heatmap_path   = Column(String(512), nullable=True)
    has_fracture   = Column(Boolean, default=False)
    model_version  = Column(String(64), default="yolov7-p6")
    created_at     = Column(DateTime, default=datetime.utcnow)

    scan = relationship("XrayScan", back_populates="ai_reports")


class XrayVerification(Base):
    """Doctor verification / override of AI findings."""
    __tablename__ = "xray_verifications"

    id                 = Column(Integer, primary_key=True, index=True)
    scan_id            = Column(Integer, ForeignKey("xray_scans.id"), nullable=False)
    doctor_id          = Column(Integer, ForeignKey("users.id"), nullable=True)
    doctor_name        = Column(String(255), nullable=True)
    status             = Column(String(30), nullable=False)   # approved | rejected | modified
    remarks            = Column(Text, nullable=True)
    edited_explanation = Column(Text, nullable=True)
    verified_at        = Column(DateTime, default=datetime.utcnow)

    scan = relationship("XrayScan", back_populates="verifications")
