"""
Doctor router — priority queue, patient list, prescription review, verify/reject, create, analytics.
"""
import json
from datetime import datetime
from typing import Any, List

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.database import get_db
from app.models.models import (
    DoctorNote, ForwardQueue, Medicine, Prescription, PrescriptionStatusEnum, User
)
from app.services.analytics_service import compute_analytics_for_prescription

from app.core.deps import require_role

router = APIRouter(prefix="/doctor", tags=["doctor"], dependencies=[Depends(require_role("doctor"))])
settings = get_settings()
templates = Jinja2Templates(directory=str(settings.base_dir / "app" / "templates"))

DEMO_DOCTOR = {"id": 9001, "name": "Dr. Priya Sharma", "specialization": "General Physician"}


def _patient_name(prescription: Prescription) -> str:
    if prescription.patient_details_json:
        try:
            data = json.loads(prescription.patient_details_json)
            name = (data.get("name") or "").strip()
            if name:
                return name
        except Exception:
            pass
    return prescription.title or f"Patient #{prescription.user_id}"


def _patient_phone(prescription: Prescription) -> str:
    if prescription.patient_details_json:
        try:
            data = json.loads(prescription.patient_details_json)
            return (data.get("phone") or data.get("contact") or "").strip()
        except Exception:
            pass
    return ""


def _adherence(db: Session, prescription_id: int) -> float:
    try:
        analytics = compute_analytics_for_prescription(db, prescription_id)
        return analytics.adherence_percentage if analytics else 0.0
    except Exception:
        return 0.0


@router.get("", response_class=HTMLResponse)
def doctor_root(request: Request):
    return RedirectResponse(url="/doctor/queue")


@router.get("/queue", response_class=HTMLResponse)
def doctor_queue(request: Request, filter: str = "all", db: Session = Depends(get_db)) -> Any:
    fqs = (
        db.query(ForwardQueue)
        .order_by(ForwardQueue.forwarded_at.desc())
        .all()
    )

    queue_items = []
    for fq in fqs:
        p = fq.prescription
        if filter == "urgent" and fq.priority != "urgent":
            continue
        if filter == "pending" and fq.status == "verified":
            continue
        queue_items.append({
            "fq_id": fq.id,
            "prescription_id": p.id,
            "patient_name": _patient_name(p),
            "rx_id": f"RX-{p.id:04d}",
            "forwarded_by": "Receptionist",
            "forwarded_at": fq.forwarded_at.strftime("%d %b %Y, %H:%M") if fq.forwarded_at else "",
            "priority": fq.priority,
            "status": fq.status,
            "note": fq.note or "",
        })

    # Urgent goes first
    queue_items.sort(key=lambda x: (x["priority"] != "urgent", x["status"] == "verified"))

    return templates.TemplateResponse(
        request,
        "doctor_queue.html",
        {
            "title": "Priority Queue",
            "doctor": DEMO_DOCTOR,
            "queue_items": queue_items,
            "current_filter": filter,
        },
    )


@router.get("/patients", response_class=HTMLResponse)
def doctor_patients(request: Request, db: Session = Depends(get_db)) -> Any:
    prescriptions = (
        db.query(Prescription)
        .order_by(Prescription.created_at.desc())
        .all()
    )

    # Group by "patient" (user_id)
    seen = {}
    patients = []
    for p in prescriptions:
        uid = p.user_id
        if uid not in seen:
            seen[uid] = True
            adh = _adherence(db, p.id)
            patients.append({
                "id": uid,
                "name": _patient_name(p),
                "patient_rx_id": f"RX-{p.id:04d}",
                "last_activity": p.created_at.strftime("%d %b %Y") if p.created_at else "",
                "adherence": round(adh, 1),
                "status": p.status,
                "prescription_id": p.id,
            })

    return templates.TemplateResponse(
        request,
        "doctor_patients.html",
        {
            "title": "Patients",
            "doctor": DEMO_DOCTOR,
            "patients": patients,
        },
    )


@router.get("/patient/{user_id}", response_class=HTMLResponse)
def doctor_patient_profile(request: Request, user_id: int, db: Session = Depends(get_db)) -> Any:
    prescriptions = (
        db.query(Prescription)
        .filter(Prescription.user_id == user_id)
        .order_by(Prescription.created_at.desc())
        .all()
    )
    if not prescriptions:
        raise HTTPException(status_code=404, detail="Patient not found")

    patient_name = _patient_name(prescriptions[0])

    # Merge patient details across all prescriptions (most recent wins)
    patient_details: dict = {}
    for p in reversed(prescriptions):
        if p.patient_details_json:
            try:
                d = json.loads(p.patient_details_json)
                patient_details.update(d)
            except Exception:
                pass

    rx_list = []
    for p in prescriptions:
        adh = _adherence(db, p.id)
        notes = (
            db.query(DoctorNote)
            .filter(DoctorNote.prescription_id == p.id)
            .order_by(DoctorNote.created_at.desc())
            .all()
        )
        fqs = (
            db.query(ForwardQueue)
            .filter(ForwardQueue.prescription_id == p.id)
            .order_by(ForwardQueue.forwarded_at.desc())
            .all()
        )

        # Full medicine detail
        medicines = []
        for med in p.medicines:
            medicines.append({
                "id": med.id,
                "name": med.normalized_name or med.original_name,
                "original_name": med.original_name,
                "dose": med.dose or "—",
                "frequency": med.frequency or "—",
                "duration_days": med.duration_days,
                "instructions": med.instructions or "",
                "confidence": round((med.confidence or 0) * 100, 1),
            })

        # Forward queue history
        fq_history = [{
            "priority": fq.priority,
            "status": fq.status,
            "note": fq.note or "",
            "forwarded_at": fq.forwarded_at.strftime("%d %b %Y, %H:%M") if fq.forwarded_at else "",
            "reviewed_at": fq.reviewed_at.strftime("%d %b %Y, %H:%M") if fq.reviewed_at else "",
        } for fq in fqs]

        # Dose schedule
        try:
            analytics = compute_analytics_for_prescription(db, p.id)
            schedule = {
                "total_doses": analytics.total_doses if analytics else 0,
                "taken_doses": analytics.taken_doses if analytics else 0,
                "missed_doses": analytics.missed_doses if analytics else 0,
                "adherence": round(analytics.adherence_percentage, 1) if analytics else 0.0,
            }
        except Exception:
            schedule = {"total_doses": 0, "taken_doses": 0, "missed_doses": 0, "adherence": 0.0}

        # Raw OCR text
        raw_text = getattr(p, "raw_text", "") or getattr(p, "ocr_text", "") or ""

        rx_list.append({
            "id": p.id,
            "title": p.title,
            "status": p.status,
            "created_at": p.created_at.strftime("%d %b %Y, %H:%M") if p.created_at else "",
            "created_at_short": p.created_at.strftime("%d %b %Y") if p.created_at else "",
            "adherence": round(adh, 1),
            "medicine_count": len(p.medicines),
            "notes_count": len(notes),
            "medicines": medicines,
            "doctor_notes": [{
                "note": n.note,
                "warning": n.warning or "",
                "created_at": n.created_at.strftime("%d %b %Y, %H:%M") if n.created_at else "",
            } for n in notes],
            "fq_history": fq_history,
            "schedule": schedule,
            "verified_at": p.verified_at.strftime("%d %b %Y") if p.verified_at else "",
            "reject_reason": p.reject_reason or "",
            "raw_text": raw_text,
            "image_filename": getattr(p, "image_filename", "") or "",
        })

    return templates.TemplateResponse(
        request,
        "doctor_patient_profile.html",
        {
            "title": f"Patient — {patient_name}",
            "doctor": DEMO_DOCTOR,
            "patient_name": patient_name,
            "patient_id": user_id,
            "patient_details": patient_details,
            "prescriptions": rx_list,
        },
    )


@router.get("/prescription/{prescription_id}", response_class=HTMLResponse)
def doctor_prescription(
    request: Request, prescription_id: int, saved: int = 0, db: Session = Depends(get_db)
) -> Any:
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    patient_details = {}
    if prescription.patient_details_json:
        try:
            patient_details = json.loads(prescription.patient_details_json)
        except Exception:
            pass

    doctor_notes = (
        db.query(DoctorNote)
        .filter(DoctorNote.prescription_id == prescription_id)
        .order_by(DoctorNote.created_at.desc())
        .all()
    )

    doctor_details = {}
    if prescription.doctor_details_json:
        try:
            doctor_details = json.loads(prescription.doctor_details_json)
        except Exception:
            pass

    verifier_name = None
    if prescription.verified_by and prescription.verifier:
        verifier_name = prescription.verifier.name or prescription.verifier.email

    return templates.TemplateResponse(
        request,
        "doctor_prescription.html",
        {
            "title": f"Review — {prescription.title}",
            "doctor": DEMO_DOCTOR,
            "prescription": prescription,
            "patient_details": patient_details,
            "doctor_details": doctor_details,
            "medicines": prescription.medicines,
            "doctor_notes": doctor_notes,
            "verifier_name": verifier_name,
            "saved": saved,
        },
    )


@router.post("/prescription/{prescription_id}/verify")
async def verify_prescription(
    prescription_id: int, db: Session = Depends(get_db)
) -> Any:
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    prescription.status = "verified"
    prescription.verified_by = DEMO_DOCTOR["id"]
    prescription.verified_at = datetime.utcnow()
    prescription.reject_reason = None

    # Update forward queue status
    for fq in prescription.forward_queues:
        if fq.status == "pending":
            fq.status = "verified"
            fq.reviewed_at = datetime.utcnow()

    db.commit()
    return JSONResponse({"success": True, "message": "Prescription verified successfully."})


@router.post("/prescription/{prescription_id}/reject")
async def reject_prescription(request: Request, prescription_id: int, db: Session = Depends(get_db)) -> Any:
    form = await request.form()
    reason = (form.get("reason") or "").strip()

    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    prescription.status = "rejected"
    prescription.reject_reason = reason or "Rejected by doctor."

    for fq in prescription.forward_queues:
        if fq.status == "pending":
            fq.status = "rejected"
            fq.reviewed_at = datetime.utcnow()

    db.commit()
    return JSONResponse({"success": True, "message": "Prescription rejected."})


@router.post("/prescription/{prescription_id}/note")
async def add_doctor_note(request: Request, prescription_id: int, db: Session = Depends(get_db)) -> Any:
    form = await request.form()
    note_text = (form.get("note") or "").strip()
    warning_text = (form.get("warning") or "").strip()

    if not note_text:
        raise HTTPException(status_code=400, detail="Note cannot be empty")

    note = DoctorNote(
        prescription_id=prescription_id,
        doctor_id=DEMO_DOCTOR["id"],
        note=note_text,
        warning=warning_text or None,
        created_at=datetime.utcnow(),
    )
    db.add(note)
    db.commit()

    return RedirectResponse(url=f"/doctor/prescription/{prescription_id}?saved=1", status_code=303)


@router.post("/prescription/{prescription_id}/medicine/add")
async def add_medicine(request: Request, prescription_id: int, db: Session = Depends(get_db)) -> Any:
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    form = await request.form()
    name = (form.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Medicine name required")

    med = Medicine(
        prescription_id=prescription_id,
        original_name=name,
        normalized_name=name,
        dose=(form.get("dose") or "").strip() or None,
        frequency=(form.get("frequency") or "").strip() or None,
        instructions=(form.get("instructions") or "").strip() or None,
        confidence=1.0,
    )
    dur = form.get("duration_days")
    if dur:
        try:
            med.duration_days = int(dur)
        except ValueError:
            pass
    db.add(med)
    db.commit()

    return RedirectResponse(url=f"/doctor/prescription/{prescription_id}", status_code=303)


@router.post("/prescription/{prescription_id}/medicine/{medicine_id}/update")
async def update_medicine(
    request: Request, prescription_id: int, medicine_id: int, db: Session = Depends(get_db)
) -> Any:
    med = db.query(Medicine).filter(
        Medicine.id == medicine_id, Medicine.prescription_id == prescription_id
    ).first()
    if not med:
        raise HTTPException(status_code=404, detail="Medicine not found")

    form = await request.form()
    med.normalized_name = (form.get("name") or med.normalized_name).strip()
    med.original_name = (form.get("name") or med.original_name).strip()
    med.dose = (form.get("dose") or "").strip() or None
    med.frequency = (form.get("frequency") or "").strip() or None
    med.instructions = (form.get("instructions") or "").strip() or None
    med.age_range = (form.get("age_range") or "").strip() or None

    dur = form.get("duration_days")
    if dur:
        try:
            med.duration_days = int(dur)
        except ValueError:
            pass

    db.commit()
    return RedirectResponse(url=f"/doctor/prescription/{prescription_id}", status_code=303)


@router.post("/prescription/{prescription_id}/medicine/{medicine_id}/delete")
async def delete_medicine(prescription_id: int, medicine_id: int, db: Session = Depends(get_db)) -> Any:
    med = db.query(Medicine).filter(
        Medicine.id == medicine_id, Medicine.prescription_id == prescription_id
    ).first()
    if not med:
        raise HTTPException(status_code=404, detail="Medicine not found")
    db.delete(med)
    db.commit()
    return JSONResponse({"success": True})


@router.get("/prescriptions", response_class=HTMLResponse)
def doctor_all_prescriptions(request: Request, q: str = "", db: Session = Depends(get_db)) -> Any:
    query = db.query(Prescription)
    if q:
        prescriptions = [
            p for p in query.all()
            if q.lower() in _patient_name(p).lower()
            or q.lower() in p.title.lower()
            or q.lower() in f"rx-{p.id:04d}"
        ]
    else:
        prescriptions = query.order_by(Prescription.created_at.desc()).all()

    rx_list = []
    for p in prescriptions:
        rx_list.append({
            "id": p.id,
            "title": p.title,
            "patient_name": _patient_name(p),
            "rx_id": f"RX-{p.id:04d}",
            "status": p.status,
            "created_at": p.created_at.strftime("%d %b %Y") if p.created_at else "",
            "medicine_count": len(p.medicines),
        })

    return templates.TemplateResponse(
        request,
        "doctor_prescriptions.html",
        {
            "title": "All Prescriptions",
            "doctor": DEMO_DOCTOR,
            "prescriptions": rx_list,
            "query": q,
        },
    )


@router.get("/create", response_class=HTMLResponse)
def doctor_create_get(request: Request, raw_notes: str = None, db: Session = Depends(get_db)) -> Any:
    # Get all users for patient dropdown
    users = db.query(Prescription).order_by(Prescription.created_at.desc()).all()
    patients = []
    seen = set()
    for p in users:
        if p.user_id not in seen:
            seen.add(p.user_id)
            patients.append({"id": p.user_id, "name": _patient_name(p), "prescription_id": p.id})

    return templates.TemplateResponse(
        request,
        "doctor_create.html",
        {
            "title": "Create Prescription",
            "doctor": DEMO_DOCTOR,
            "patients": patients,
            "raw_notes": raw_notes or "",
        },
    )


@router.post("/create")
async def doctor_create_post(request: Request, db: Session = Depends(get_db)) -> Any:
    form = await request.form()
    patient_id = int(form.get("patient_id") or 1)
    title = (form.get("title") or "New Prescription").strip()
    notes = (form.get("notes") or "").strip()

    prescription = Prescription(
        user_id=patient_id,
        title=title,
        status="needs_review",
        created_at=datetime.utcnow(),
    )
    db.add(prescription)
    db.flush()

    # parse medicines from form (dynamic rows: medicine_0_name, etc.)
    i = 0
    while True:
        name = (form.get(f"medicine_{i}_name") or "").strip()
        if not name:
            break
        med = Medicine(
            prescription_id=prescription.id,
            original_name=name,
            normalized_name=name,
            dose=(form.get(f"medicine_{i}_dose") or "").strip() or None,
            frequency=(form.get(f"medicine_{i}_frequency") or "").strip() or None,
            instructions=(form.get(f"medicine_{i}_instructions") or "").strip() or None,
            confidence=1.0,
        )
        dur = form.get(f"medicine_{i}_duration_days")
        if dur:
            try:
                med.duration_days = int(dur)
            except ValueError:
                pass
        db.add(med)
        i += 1

    if notes:
        note = DoctorNote(
            prescription_id=prescription.id,
            doctor_id=DEMO_DOCTOR["id"],
            note=notes,
            created_at=datetime.utcnow(),
        )
        db.add(note)

    db.commit()
    return RedirectResponse(url=f"/doctor/prescription/{prescription.id}?saved=1", status_code=303)


@router.get("/analytics", response_class=HTMLResponse)
def doctor_analytics(request: Request, db: Session = Depends(get_db)) -> Any:
    prescriptions = db.query(Prescription).all()

    total = len(prescriptions)
    verified = sum(1 for p in prescriptions if p.status == "verified")
    forwarded = sum(1 for p in prescriptions if p.status == "forwarded")
    rejected = sum(1 for p in prescriptions if p.status == "rejected")
    active = sum(1 for p in prescriptions if p.status == "active")

    adherence_vals = []
    for p in prescriptions:
        try:
            a = compute_analytics_for_prescription(db, p.id)
            if a and a.total_doses > 0:
                adherence_vals.append(a.adherence_percentage)
        except Exception:
            pass
    avg_adherence = round(sum(adherence_vals) / len(adherence_vals), 1) if adherence_vals else 0.0

    # Monthly trend mock data (last 6 months)
    month_labels = ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
    monthly_rx = [3, 5, 4, 7, 6, total]

    return templates.TemplateResponse(
        request,
        "doctor_analytics.html",
        {
            "title": "Analytics",
            "doctor": DEMO_DOCTOR,
            "stats": {
                "total": total,
                "verified": verified,
                "forwarded": forwarded,
                "rejected": rejected,
                "active": active,
                "avg_adherence": avg_adherence,
            },
            "month_labels": month_labels,
            "monthly_rx": monthly_rx,
        },
    )


@router.post("/queue/{fq_id}/mark-reviewed")
async def mark_reviewed(fq_id: int, db: Session = Depends(get_db)) -> Any:
    fq = db.query(ForwardQueue).filter(ForwardQueue.id == fq_id).first()
    if not fq:
        raise HTTPException(status_code=404, detail="Queue item not found")
    fq.status = "reviewed"
    fq.reviewed_at = datetime.utcnow()
    db.commit()
    return JSONResponse({"success": True})
