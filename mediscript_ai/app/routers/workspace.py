from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.database import get_db
from app.models.models import Medicine, Prescription, PrescriptionStatusEnum
from app.schemas.schemas import GemmaMedicine
from app.services.analytics_service import compute_analytics_for_prescription
from app.services.calendar_service import generate_schedule_for_prescription
from app.services.gemma_service import call_gemma
from app.services.validation_service import validate_medicines


router = APIRouter(prefix="/workspace", tags=["workspace"])
settings = get_settings()
templates = Jinja2Templates(directory=str(settings.base_dir / "app" / "templates"))


@router.get("/{prescription_id}", response_class=HTMLResponse)
async def workspace_view(
    request: Request,
    prescription_id: int,
    tab: str = Query("overview"),
    db: Session = Depends(get_db),
) -> Any:
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    analytics = compute_analytics_for_prescription(db, prescription_id)

    return templates.TemplateResponse(
        request,
        "workspace.html",
        {
            "prescription": prescription,
            "tab": tab,
            "analytics": analytics,
        },
    )


@router.post("/{prescription_id}/extract")
async def run_extraction(
    prescription_id: int,
    db: Session = Depends(get_db),
) -> Any:
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription or not prescription.raw_text:
        raise HTTPException(status_code=404, detail="Prescription text not found")

    extraction = await call_gemma(prescription.raw_text)
    gemma_meds = extraction.medicines or []

    validated, final_conf = validate_medicines(
        gemma_medicines=[GemmaMedicine(**m.dict()) for m in gemma_meds],
        ocr_reliability=prescription.confidence_score / 100.0,
        json_parse_success=extraction.json_parse_success,
    )

    for med in list(prescription.medicines):
        db.delete(med)

    for item in validated:
        med = Medicine(
            prescription_id=prescription.id,
            original_name=item.original_name,
            normalized_name=item.normalized_name,
            dose=item.dose,
            frequency=item.frequency,
            duration_days=item.duration_days,
            instructions=item.instructions,
            confidence=item.confidence,
        )
        db.add(med)

    prescription.confidence_score = final_conf
    db.commit()

    return RedirectResponse(url=f"/workspace/{prescription_id}?tab=overview", status_code=303)


@router.post("/{prescription_id}/confirm")
async def confirm_prescription(
    prescription_id: int,
    db: Session = Depends(get_db),
) -> Any:
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    if not prescription.medicines:
        raise HTTPException(status_code=400, detail="No medicines to schedule")

    generate_schedule_for_prescription(db, prescription)
    prescription.status = PrescriptionStatusEnum.ACTIVE
    db.commit()

    return RedirectResponse(url=f"/workspace/{prescription_id}?tab=calendar", status_code=303)

