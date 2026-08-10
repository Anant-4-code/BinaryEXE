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


@router.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)) -> Any:
    prescriptions: List[Prescription] = (
        db.query(Prescription).order_by(Prescription.created_at.desc()).limit(20).all()
    )
    return templates.TemplateResponse(
        request,
        "home.html",
        {"prescriptions": prescriptions},
    )

