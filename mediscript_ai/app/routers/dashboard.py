import json
from typing import Any, List
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.database import get_db
from app.models.models import Prescription, User, Notification
from app.core.deps import get_current_user
from app.services.analytics_service import compute_analytics_for_prescription
from app.services.notification_service import find_upcoming_notifications

router = APIRouter(tags=["dashboard"])
settings = get_settings()
templates = Jinja2Templates(directory=str(settings.base_dir / "app" / "templates"))


def _patient_info(prescription: Prescription) -> tuple:
    """Get (patient_name, disease_name) from prescription's patient_details_json."""
    name, disease = "", ""
    if prescription.patient_details_json:
        try:
            data = json.loads(prescription.patient_details_json)
            name = (data.get("name") or "").strip()
            disease = (data.get("disease_or_condition") or "").strip()
        except (json.JSONDecodeError, TypeError):
            pass
    return name, disease


@router.get("/", response_class=HTMLResponse)
def landing(request: Request) -> Any:
    return templates.TemplateResponse(
        request,
        "landing.html",
        {
            "hide_header": True,
            "title": "Sanjeevani AI",
        },
    )


@router.get("/login")
@router.post("/login")
@router.get("/signup")
@router.post("/signup")
@router.get("/logout")
def auth_redirect() -> Any:
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/dashboard", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Any:
    prescriptions = (
        db.query(Prescription)
        .filter(Prescription.user_id == current_user.id)
        .order_by(Prescription.created_at.desc())
        .limit(20)
        .all()
    )
    for p in prescriptions:
        p.patient_name, p.disease_name = _patient_info(p)

    summaries = [compute_analytics_for_prescription(db, p.id) for p in prescriptions]
    total_doses = sum(s.total_doses for s in summaries)
    taken_doses = sum(s.taken_doses for s in summaries)
    stats = {
        "total_prescriptions": len(prescriptions),
        "doses_due_today": sum(len(p.medicines) for p in prescriptions if p.medicines),
        "adherence_pct": round(taken_doses / total_doses * 100, 1) if total_doses else 0,
    }

    # Generate new notifications
    find_upcoming_notifications(db)

    # Fetch user's prescription notifications
    user_notifs = (
        db.query(Notification)
        .join(Prescription)
        .filter(Prescription.user_id == current_user.id)
        .order_by(Notification.scheduled_for.desc())
        .limit(5)
        .all()
    )
    
    notifications = [
        {
            "type": n.type,
            "message": n.message,
            "scheduled_for": n.scheduled_for.strftime("%I:%M %p") if n.scheduled_for else "Unknown"
        } for n in user_notifs
    ]

    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "prescriptions": prescriptions,
            "stats": stats,
            "username": current_user.name or current_user.email,
            "upcoming_doses": [],
            "notifications": notifications,
        },
    )
