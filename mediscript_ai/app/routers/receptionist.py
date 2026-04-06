"""
Receptionist router — search patients, forward to doctor queue, recent activity.
"""
import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.database import get_db
from app.models.models import ForwardQueue, Prescription, User

router = APIRouter(prefix="/receptionist", tags=["receptionist"])
settings = get_settings()
templates = Jinja2Templates(directory=str(settings.base_dir / "app" / "templates"))

# Demo doctor accounts
DEMO_DOCTORS = [
    {"id": 9001, "name": "Dr. Priya Sharma", "specialization": "General Physician"},
    {"id": 9002, "name": "Dr. Rahul Mehta", "specialization": "Cardiologist"},
    {"id": 9003, "name": "Dr. Anita Verma", "specialization": "Paediatrician"},
]


def _get_patient_name(prescription: Prescription) -> str:
    if prescription.patient_details_json:
        try:
            data = json.loads(prescription.patient_details_json)
            name = (data.get("name") or "").strip()
            if name:
                return name
        except Exception:
            pass
    return prescription.title or f"Patient #{prescription.user_id}"


def _get_patient_phone(prescription: Prescription) -> str:
    if prescription.patient_details_json:
        try:
            data = json.loads(prescription.patient_details_json)
            return (data.get("phone") or data.get("contact") or "").strip()
        except Exception:
            pass
    return ""


def _build_card(p: Prescription) -> dict:
    patient_name = _get_patient_name(p)
    fq = p.forward_queues[-1] if p.forward_queues else None
    return {
        "id": p.id,
        "patient_name": patient_name,
        "patient_id": f"RX-{p.id:04d}",
        "last_prescription": p.title,
        "status": p.status,
        "created_at": p.created_at.strftime("%d %b %Y") if p.created_at else "",
        "phone": _get_patient_phone(p),
        "forwarded": fq is not None,
    }


@router.get("", response_class=HTMLResponse)
def receptionist_panel(request: Request, db: Session = Depends(get_db)) -> Any:
    # Recent 5 forward actions
    recent = (
        db.query(ForwardQueue)
        .order_by(ForwardQueue.forwarded_at.desc())
        .limit(5)
        .all()
    )
    activity = []
    for fq in recent:
        p_name = _get_patient_name(fq.prescription)
        doc_name = next((d["name"] for d in DEMO_DOCTORS if d["id"] == fq.doctor_id), "Any Doctor")
        activity.append({
            "patient_name": p_name,
            "doctor_name": doc_name,
            "time": fq.forwarded_at.strftime("%d %b %Y, %H:%M") if fq.forwarded_at else "",
            "priority": fq.priority,
        })

    return templates.TemplateResponse(
        "receptionist.html",
        {
            "request": request,
            "title": "Receptionist Panel",
            "doctors": DEMO_DOCTORS,
            "recent_activity": activity,
        },
    )


@router.get("/search")
def search_patients(
    q: str = "",
    db: Session = Depends(get_db),
) -> Any:
    q = q.strip()
    if not q:
        return JSONResponse({"results": []})

    prescriptions = db.query(Prescription).all()
    results = []
    for p in prescriptions:
        patient_name = _get_patient_name(p).lower()
        phone = _get_patient_phone(p)
        rx_id = f"RX-{p.id:04d}"
        if (
            q.lower() in patient_name
            or q.lower() in rx_id.lower()
            or (phone and q in phone)
        ):
            results.append(_build_card(p))
        if len(results) >= 20:
            break

    return JSONResponse({"results": results})


@router.post("/forward")
async def forward_to_doctor(request: Request, db: Session = Depends(get_db)) -> Any:
    form = await request.form()
    prescription_id = int(form.get("prescription_id") or 0)
    doctor_id = form.get("doctor_id") or None
    priority = form.get("priority") or "normal"
    note = (form.get("note") or "").strip()

    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        return JSONResponse({"error": "Prescription not found"}, status_code=404)

    fq = ForwardQueue(
        prescription_id=prescription_id,
        forwarded_by=1,  # demo: receptionist user id placeholder
        doctor_id=int(doctor_id) if doctor_id else None,
        priority=priority,
        note=note or None,
        status="pending",
        forwarded_at=datetime.utcnow(),
    )
    db.add(fq)

    # Update prescription status
    prescription.status = "forwarded"
    db.commit()

    return JSONResponse({"success": True, "message": f"Forwarded to doctor queue with {priority} priority."})


@router.get("/activity")
def recent_activity(db: Session = Depends(get_db)) -> Any:
    recent = (
        db.query(ForwardQueue)
        .order_by(ForwardQueue.forwarded_at.desc())
        .limit(5)
        .all()
    )
    activity = []
    for fq in recent:
        p_name = _get_patient_name(fq.prescription)
        doc_name = next((d["name"] for d in DEMO_DOCTORS if d["id"] == fq.doctor_id), "Any Doctor")
        activity.append({
            "patient_name": p_name,
            "doctor_name": doc_name,
            "time": fq.forwarded_at.strftime("%d %b %Y, %H:%M") if fq.forwarded_at else "",
            "priority": fq.priority,
            "prescription_id": fq.prescription_id,
        })
    return JSONResponse({"activity": activity})
