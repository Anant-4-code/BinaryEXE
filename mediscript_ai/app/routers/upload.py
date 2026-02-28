from pathlib import Path
from typing import Any
import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.database import get_db
from app.models.models import Prescription, PrescriptionStatusEnum
from app.schemas.schemas import OCRResult
from app.services.handwriting_service import run_handwriting_model


router = APIRouter(prefix="/upload", tags=["upload"])
settings = get_settings()


@router.post("/", response_class=RedirectResponse)
async def upload_prescription(
    file: UploadFile = File(...),
    title: str = Form("Prescription"),
    caption: str = Form(""),
    db: Session = Depends(get_db),
) -> Any:
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are supported")

    uploads_dir = settings.uploads_dir
    uploads_dir.mkdir(parents=True, exist_ok=True)

    file_path = uploads_dir / file.filename
    with open(file_path, "wb") as f:
        f.write(await file.read())

    try:
        ocr_result: OCRResult = run_handwriting_model(file_path)
    except ValueError as e:
        if file_path.exists():
            try:
                file_path.unlink()
            except OSError:
                pass
        raise HTTPException(status_code=400, detail=str(e))

    prescription = Prescription(
        user_id=1,
        title=(title or "Prescription").strip(),
        caption=(caption or "").strip() or None,
        raw_text=ocr_result.raw_text,
        image_path=str(file_path),
        confidence_score=ocr_result.ocr_reliability * 100.0,
        status=PrescriptionStatusEnum.NEEDS_REVIEW,
    )
    db.add(prescription)
    db.commit()
    db.refresh(prescription)

    return RedirectResponse(url=f"/workspace/{prescription.id}/refresh-all", status_code=303)


@router.post("/{prescription_id}/update-meta")
async def update_prescription_meta(
    prescription_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Update prescription title and caption (from dashboard)."""
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")
    form = await request.form()
    title = (form.get("title") or "").strip()
    if title:
        prescription.title = title
    caption = (form.get("caption") or "").strip()
    prescription.caption = caption if caption else None
    db.commit()
    return RedirectResponse(url="/", status_code=303)


def _delete_prescription_core(db: Session, prescription_id: int) -> None:
    """Internal helper to delete a prescription and its image file."""
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    # Delete the image file if it exists
    if prescription.image_path and os.path.exists(prescription.image_path):
        try:
            os.remove(prescription.image_path)
        except Exception as e:
            print(f"Error deleting file: {e}")

    # Delete from database (cascade will delete medicines, doses, and notifications)
    db.delete(prescription)
    db.commit()


@router.delete("/{prescription_id}")
async def delete_prescription(
    prescription_id: int,
    db: Session = Depends(get_db),
) -> Any:
    """API delete endpoint (JSON response)."""
    _delete_prescription_core(db, prescription_id)

    return JSONResponse(
        status_code=200,
        content={"message": "Prescription deleted successfully", "prescription_id": prescription_id}
    )


@router.post("/{prescription_id}/delete")
async def delete_prescription_form(
    prescription_id: int,
    db: Session = Depends(get_db),
) -> Any:
    """
    Delete endpoint intended for HTML forms.
    After deletion, redirect back to the dashboard.
    """
    _delete_prescription_core(db, prescription_id)
    return RedirectResponse(url="/", status_code=303)

