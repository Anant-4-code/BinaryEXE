import json
from typing import Any, List

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.database import get_db
from app.models.models import Prescription


router = APIRouter(tags=["dashboard"])
settings = get_settings()
templates = Jinja2Templates(directory=str(settings.base_dir / "app" / "templates"))


SAMPLE_EMAIL = "anantrai0809@gmail.com"
SAMPLE_PASSWORD = "Anantrai"

# Role-based demo credentials
ROLE_CREDENTIALS = {
    "patient": {"email": "anantrai0809@gmail.com", "password": "Anantrai", "redirect": "/dashboard"},
    "receptionist": {"email": "receptionist@sanjeevani.com", "password": "Receptionist1", "redirect": "/receptionist"},
    "doctor": {"email": "doctor@sanjeevani.com", "password": "Doctor1", "redirect": "/doctor/queue"},
}


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


@router.get("/login", response_class=HTMLResponse)
def login_get(request: Request) -> Any:
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "hide_header": True,
            "title": "Sign in",
            "error": None,
            "email": "",
        },
    )


@router.get("/signup", response_class=HTMLResponse)
def signup_get(request: Request) -> Any:
    return templates.TemplateResponse(
        "signup.html",
        {
            "request": request,
            "hide_header": True,
            "title": "Sign up",
            "error": None,
            "email": "",
            "name": "",
        },
    )


@router.get("/role-login", response_class=HTMLResponse)
def role_login_get(request: Request, role: str = "patient") -> Any:
    role = role if role in ("patient", "receptionist", "doctor") else "patient"
    return templates.TemplateResponse(
        "role_login.html",
        {
            "request": request,
            "hide_header": True,
            "title": f"Sign in — {role.title()}",
            "role": role,
            "error": None,
            "email": "",
        },
    )


@router.post("/role-login", response_class=HTMLResponse)
async def role_login_post(request: Request) -> Any:
    form = await request.form()
    role = (form.get("role") or "patient").strip()
    email = (form.get("email") or "").strip()
    password = (form.get("password") or "").strip()

    creds = ROLE_CREDENTIALS.get(role)
    if creds and email.lower() == creds["email"].lower() and password == creds["password"]:
        return RedirectResponse(url=creds["redirect"], status_code=303)

    return templates.TemplateResponse(
        "role_login.html",
        {
            "request": request,
            "hide_header": True,
            "title": f"Sign in — {role.title()}",
            "role": role,
            "error": "Invalid credentials. Please check and try again.",
            "email": email,
        },
        status_code=400,
    )


@router.post("/login", response_class=HTMLResponse)
async def login_post(request: Request) -> Any:
    form = await request.form()
    email = (form.get("email") or "").strip()
    password = (form.get("password") or "").strip()

    if not email.lower().endswith(".com"):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "hide_header": True,
                "title": "Sign in",
                "error": "Please enter a valid email address.",
                "email": email,
            },
            status_code=400,
        )

    if email.lower() != SAMPLE_EMAIL.lower() or password != SAMPLE_PASSWORD:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "hide_header": True,
                "title": "Sign in",
                "error": "Invalid email or password.",
                "email": email,
            },
            status_code=400,
        )

    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/signup", response_class=HTMLResponse)
async def signup_post(request: Request) -> Any:
    form = await request.form()
    name = (form.get("name") or "").strip()
    email = (form.get("email") or "").strip()

    if email.lower() == SAMPLE_EMAIL.lower():
        return templates.TemplateResponse(
            "signup.html",
            {
                "request": request,
                "hide_header": True,
                "title": "Sign up",
                "error": "Account already exists. Please sign in.",
                "email": email,
                "name": name,
            },
            status_code=400,
        )

    if not name:
        return templates.TemplateResponse(
            "signup.html",
            {
                "request": request,
                "hide_header": True,
                "title": "Sign up",
                "error": "Please enter a valid name.",
                "email": email,
                "name": name,
            },
            status_code=400,
        )

    if not email.lower().endswith(".com"):
        return templates.TemplateResponse(
            "signup.html",
            {
                "request": request,
                "hide_header": True,
                "title": "Sign up",
                "error": "Please enter a valid email address.",
                "email": email,
                "name": name,
            },
            status_code=400,
        )

    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/dashboard", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)) -> Any:
    prescriptions: List[Prescription] = (
        db.query(Prescription).order_by(Prescription.created_at.desc()).limit(20).all()
    )
    # Attach display names for dashboard cards
    for p in prescriptions:
        p.patient_name, p.disease_name = _patient_info(p)
    stats = {
        "total_prescriptions": len(prescriptions),
        "doses_due_today": sum(len(p.medicines) for p in prescriptions if p.medicines),
        "adherence_pct": "85",
    }
    
    upcoming_doses = []
    
    notifications = [
        {"type": "upcoming", "message": "Upcoming dose reminder", "scheduled_for": "Today, 6:00 PM"}
    ]

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "prescriptions": prescriptions,
            "stats": stats,
            "username": "Patient",
            "upcoming_doses": upcoming_doses,
            "notifications": notifications,
        },
    )

