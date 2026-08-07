from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Prescription, User
from app.core.deps import get_current_user
from app.services.export_service import generate_prescription_pdf


router = APIRouter(prefix="/export", tags=["export"])


@router.get("/prescription/{prescription_id}")
def export_prescription_pdf(
    prescription_id: int,
    language: Optional[str] = Query(None, description="Language for transliterated PDF (english, hindi, tamil, etc.)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate and download prescription PDF. Use ?language=hindi (etc.) for transliterated content."""
    # Verify ownership
    prescription = db.query(Prescription).filter(
        Prescription.id == prescription_id,
        Prescription.user_id == current_user.id
    ).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    try:
        # English-only export (ignore language to avoid missing-font issues).
        pdf_bytes = generate_prescription_pdf(db, prescription_id, language=None)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="prescription_{prescription_id}.pdf"'},
    )
