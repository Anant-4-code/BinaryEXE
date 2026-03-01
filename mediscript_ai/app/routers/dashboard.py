import json
from typing import Any, List

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.database import get_db
from app.models.models import Prescription


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
        "landing.html",
        {
            "request": request,
            "hide_header": True,
            "title": "Sanjeevani AI",
        },
    )


@router.get("/dashboard", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)) -> Any:
    prescriptions: List[Prescription] = (
        db.query(Prescription).order_by(Prescription.created_at.desc()).limit(20).all()
    )
    # Attach display names for dashboard cards
    for p in prescriptions:
        p.patient_name, p.disease_name = _patient_info(p)
    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "prescriptions": prescriptions,
        },
    )

