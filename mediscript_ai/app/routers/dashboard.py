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
    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "prescriptions": prescriptions,
        },
    )

