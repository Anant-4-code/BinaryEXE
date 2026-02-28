from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.export_service import generate_prescription_pdf


router = APIRouter(prefix="/export", tags=["export"])


@router.get("/prescription/{prescription_id}")
def export_prescription_pdf(
    prescription_id: int,
    language: Optional[str] = Query(None, description="Language for transliterated PDF (english, hindi, tamil, etc.)"),
    db: Session = Depends(get_db),
):
    """Generate and download prescription PDF. Use ?language=hindi (etc.) for transliterated content."""
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

