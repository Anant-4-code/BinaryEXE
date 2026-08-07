from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect
from sqlalchemy import text

from app.config import get_settings
from app.core.database import Base, engine
from app.models.models import (  # noqa: F401
    User, Prescription, Medicine, DoctorNote,
    XrayScan, XrayDetection, XrayAIReport, XrayVerification,
    DoctorProfile, ReceptionistProfile, PatientProfile, AuditLog,
    NotificationPreference, RefillRequest, DoctorAvailability, Appointment,
    MessageThread, ThreadMessage, VitalsLog, LabDocument, CaregiverLink,
)

from app.routers import upload, workspace, calendar, notifications, export, dashboard, receptionist, doctor, speech, xray, patient



settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def init_db() -> None:
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    # Create all tables that don't exist yet
    Base.metadata.create_all(bind=engine)

    if not existing_tables:
        return

    # Lightweight schema migration for SQLite (keeps project runnable without a migration tool).
    try:
        cols = [c.get("name") for c in inspector.get_columns("prescriptions")]
        if "caption" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE prescriptions ADD COLUMN caption TEXT"))
        if "export_overrides_json" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE prescriptions ADD COLUMN export_overrides_json TEXT"))
        if "verified_by" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE prescriptions ADD COLUMN verified_by INTEGER"))
        if "verified_at" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE prescriptions ADD COLUMN verified_at DATETIME"))
        if "reject_reason" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE prescriptions ADD COLUMN reject_reason TEXT"))
    except Exception:
        pass

    try:
        user_cols = [c.get("name") for c in inspector.get_columns("users")]
        if "role" not in user_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(50) DEFAULT 'patient'"))
        if "name" not in user_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN name VARCHAR(255)"))
        if "phone" not in user_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(50)"))
        if "is_active" not in user_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1"))
        if "mfa_enabled" not in user_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN mfa_enabled BOOLEAN DEFAULT 0"))
    except Exception:
        pass


    # Base.metadata.create_all handles table creation for all models.


static_dir = settings.static_dir
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

uploads_dir = settings.uploads_dir
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

# Base uploads directory creation


app.include_router(dashboard.router)
app.include_router(upload.router)
app.include_router(workspace.router)
app.include_router(calendar.router)
app.include_router(notifications.router)
app.include_router(export.router)
app.include_router(receptionist.router)
app.include_router(doctor.router)
app.include_router(speech.router)
app.include_router(xray.router)
app.include_router(patient.router)



@app.on_event("startup")
async def on_startup():
    init_db()
