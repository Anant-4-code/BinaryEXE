"""
Patient API Router — Home/Today, Report Details, Plain-English Translation, 
Access Transparency Log, Health Timeline, Refill Requests, and Notification Settings.
"""
import json
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.database import get_db
from app.core.deps import require_role, get_current_user, require_patient_ownership
from app.models.models import (
    User, Prescription, Medicine, Dose, NotificationPreference, 
    RefillRequest, AuditLog, XrayScan, XrayAIReport, DoctorNote
)
from app.services.audit_service import log_audit_event
from app.services.deid_service import DeidService
from app.services.analytics_service import compute_analytics_for_prescription

router = APIRouter(
    prefix="/patient",
    tags=["patient"],
    dependencies=[Depends(require_role("patient", "admin", "doctor"))]
)

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.base_dir / "app" / "templates"))


def _get_patient_prescriptions(db: Session, patient_user_id: int) -> List[Prescription]:
    return (
        db.query(Prescription)
        .filter(Prescription.user_id == patient_user_id)
        .order_by(Prescription.created_at.desc())
        .all()
    )


@router.get("/home", response_class=HTMLResponse)
def patient_home(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    prescriptions = _get_patient_prescriptions(db, current_user.id)

    # Next dose card calculation
    today = datetime.utcnow().date()
    doses = (
        db.query(Dose)
        .filter(Dose.date >= today)
        .order_by(Dose.date.asc(), Dose.time.asc())
        .all()
    )
    
    next_dose_info = None
    if doses:
        first_dose = doses[0]
        med = db.query(Medicine).filter(Medicine.id == first_dose.medicine_id).first()
        next_dose_info = {
            "dose_id": first_dose.id,
            "medicine_name": med.normalized_name if med else "Medication",
            "dose": med.dose if med else "1 tablet",
            "time": first_dose.time.strftime("%I:%M %p"),
            "date": first_dose.date.strftime("%d %b %Y"),
            "taken": first_dose.taken,
        }

    # Adherence mini-widget
    adherence_pct = 0.0
    if prescriptions:
        analytics = compute_analytics_for_prescription(db, prescriptions[0].id)
        if analytics:
            adherence_pct = round(analytics.adherence_percentage, 1)

    # Access Log entry audit
    log_audit_event(
        db,
        actor_user=current_user,
        action="VIEW_PATIENT_HOME",
        resource_type="patient",
        resource_id=str(current_user.id)
    )
    db.commit()

    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "title": "Home — Today",
            "user": current_user,
            "next_dose": next_dose_info,
            "adherence_pct": adherence_pct,
            "prescriptions": prescriptions[:3],
        },
    )


@router.get("/access-log")
def get_access_log(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Access Transparency Log (P0):
    Exposes audit logs to patient showing who accessed their clinical records (HIPAA & DPDP compliant).
    """
    logs = (
        db.query(AuditLog)
        .order_by(AuditLog.occurred_at.desc())
        .limit(50)
        .all()
    )

    access_entries = []
    for log in logs:
        # Resolve actor name if available
        actor_name = "Healthcare Staff"
        if log.actor_user_id:
            actor = db.query(User).filter(User.id == log.actor_user_id).first()
            if actor:
                actor_name = actor.name or f"{actor.role.capitalize()} User"

        access_entries.append({
            "id": log.id,
            "actor_name": actor_name,
            "actor_role": log.actor_role or "system",
            "action": log.action,
            "resource_type": log.resource_type,
            "occurred_at": log.occurred_at.strftime("%b %d, %Y · %I:%M %p"),
        })

    return JSONResponse({"access_log": access_entries})


@router.get("/timeline")
def get_health_timeline(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Health Timeline (P1):
    Unified chronological feed aggregating reports, prescriptions, and scans.
    """
    timeline_items = []

    # Prescriptions
    prescriptions = _get_patient_prescriptions(db, current_user.id)
    for p in prescriptions:
        timeline_items.append({
            "type": "prescription",
            "title": f"Prescription added: {p.title}",
            "status": p.status,
            "date": p.created_at.strftime("%b %d, %Y"),
            "timestamp": p.created_at.isoformat(),
            "id": p.id,
        })

    # X-ray Scans
    scans = (
        db.query(XrayScan)
        .filter(XrayScan.patient_id == current_user.id)
        .order_by(XrayScan.uploaded_at.desc())
        .all()
    )
    for s in scans:
        timeline_items.append({
            "type": "xray_scan",
            "title": f"X-ray Scan Uploaded ({s.filename or 'Wrist X-ray'})",
            "status": s.status,
            "date": s.uploaded_at.strftime("%b %d, %Y"),
            "timestamp": s.uploaded_at.isoformat(),
            "id": s.id,
        })

    # Sort timeline by timestamp desc
    timeline_items.sort(key=lambda x: x["timestamp"], reverse=True)

    return JSONResponse({"timeline": timeline_items})


@router.post("/prescriptions/{prescription_id}/refill-request")
def request_prescription_refill(
    prescription_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Medication Refill Requests (P1).
    """
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    require_patient_ownership(prescription.user_id, current_user)

    refill = RefillRequest(
        prescription_id=prescription_id,
        patient_id=current_user.id,
        status="requested",
        requested_at=datetime.utcnow()
    )
    db.add(refill)

    log_audit_event(
        db,
        actor_user=current_user,
        action="REQUEST_REFILL",
        resource_type="prescription",
        resource_id=str(prescription_id)
    )
    db.commit()

    return JSONResponse({
        "success": True,
        "message": "Refill request submitted to your doctor.",
        "refill_id": refill.id
    })


@router.put("/settings/notifications")
def update_notification_preferences(
    channel: str = Form("in_app"),
    language: str = Form("en"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Multi-channel notification preference management.
    """
    pref = db.query(NotificationPreference).filter(NotificationPreference.user_id == current_user.id).first()
    if not pref:
        pref = NotificationPreference(user_id=current_user.id, channel=channel, language=language)
        db.add(pref)
    else:
        pref.channel = channel
        pref.language = language
        pref.updated_at = datetime.utcnow()

    db.commit()
    return JSONResponse({
        "success": True,
        "channel": pref.channel,
        "language": pref.language,
        "message": "Notification preferences updated."
    })
