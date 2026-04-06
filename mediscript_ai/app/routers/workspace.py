import asyncio
import json
import logging
from typing import Any
from pathlib import Path

from datetime import date, datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.database import get_db
from app.models.models import Medicine, Prescription, PrescriptionStatusEnum, User
from app.schemas.schemas import GemmaMedicine
from app.services.analytics_service import compute_analytics_for_prescription
from app.services.translation_service import translate_prescription
from app.services.calendar_service import generate_schedule_for_prescription
from app.services.gemma_service import (
    call_gemma,
    call_gemma_explain_medicine,
    call_gemma_extract_patient_doctor,
    call_gemma_clinical_tts_script,
)
from app.services.correction_service import correct_medicines_batch
from app.services.validation_service import validate_medicines
from app.utils import format_frequency


router = APIRouter(prefix="/workspace", tags=["workspace"])
settings = get_settings()
templates = Jinja2Templates(directory=str(settings.base_dir / "app" / "templates"))
templates.env.filters["format_frequency"] = format_frequency
logger = logging.getLogger(__name__)

PATIENT_KEYS = ["name", "age", "gender", "address", "phone", "disease_or_condition", "medicines_summary", "other"]
DOCTOR_KEYS = ["name", "qualification", "specialization", "clinic_hospital", "address", "phone", "other"]


async def _run_all_extractions_core(prescription_id: int, db: Session) -> None:
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription or not prescription.raw_text:
        raise HTTPException(status_code=404, detail="Prescription text not found")

    logger.info(f"Running AI extraction for prescription {prescription_id}")
    extraction = await call_gemma(prescription.raw_text)
    logger.info(f"AI Extraction Results: {len(extraction.medicines)} medicines found. Parse success: {extraction.json_parse_success}")
    
    gemma_meds = extraction.medicines or []

    # ✅ CORRECTION LAYER: Fix spelling, complete missing data, normalize formats
    logger.info(f"Processing {len(gemma_meds)} medicines through correction layer")
    corrected_meds = await correct_medicines_batch(gemma_meds)
    
    validated, final_conf = validate_medicines(
        gemma_medicines=[GemmaMedicine(**m.dict()) for m in corrected_meds],
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
            age_range=item.age_range or None,
        )
        db.add(med)

    # 5. Extract Patient/Doctor Identities
    try:
        identities = await call_gemma_extract_patient_doctor(prescription.raw_text)
        if identities.get("patient"):
            prescription.patient_details_json = json.dumps(identities["patient"])
        if identities.get("doctor"):
            prescription.doctor_details_json = json.dumps(identities["doctor"])
        print(f"Extracted identities for {prescription.id}")
    except Exception as e:
        print(f"Identity extraction error for {prescription.id}: {e}")

    # 6. Generate Initial Explanations for Documentation Engine
    logger.info(f"Generating initial explanations for {len(validated)} medicines")
    for med in prescription.medicines:
        try:
            explanation = await call_gemma_explain_medicine(
                medicine_name=med.normalized_name or med.original_name,
                dose=med.dose or "",
                frequency=med.frequency or "",
                duration=str(med.duration_days) if med.duration_days else "",
                instructions=med.instructions or "",
            )
            med.explanation = (explanation or "").strip()[:500]
        except Exception as e:
            logger.error(f"Failed to generate initial explanation for {med.normalized_name}: {e}")

    prescription.confidence_score = final_conf
    db.commit()


@router.get("/{prescription_id}", response_class=HTMLResponse)
async def workspace_view(
    request: Request,
    prescription_id: int,
    tab: str = Query("overview"),
    saved: int = Query(0),
    error: str = Query(""),
    db: Session = Depends(get_db),
) -> Any:
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    analytics = compute_analytics_for_prescription(db, prescription_id)

    patient_details = {}
    doctor_details = {}
    transliterated = None  # {language, label, patient, doctor, medicines, full} or None
    if prescription.patient_details_json:
        try:
            patient_details = json.loads(prescription.patient_details_json)
        except (json.JSONDecodeError, TypeError):
            pass
    if prescription.doctor_details_json:
        try:
            doctor_details = json.loads(prescription.doctor_details_json)
        except (json.JSONDecodeError, TypeError):
            pass
    if prescription.transliterated_json:
        try:
            t = json.loads(prescription.transliterated_json)
            if t and t.get("language"):
                transliterated = t
        except (json.JSONDecodeError, TypeError):
            pass

    verifier_name = None
    if prescription.verified_by:
        verifier = db.query(User).filter(User.id == prescription.verified_by).first()
        if verifier:
            verifier_name = verifier.name or verifier.email

    export_overrides = {}
    if prescription.export_overrides_json:
        try:
            export_overrides = json.loads(prescription.export_overrides_json) or {}
        except (json.JSONDecodeError, TypeError):
            export_overrides = {}

    def _dict_to_lines(dct: dict) -> str:
        lines = []
        for k, v in (dct or {}).items():
            if v and str(v).strip():
                key = str(k).replace("_", " ").title()
                lines.append(f"{key}: {v}")
        return "\n".join(lines)

    export_defaults = {
        "date": prescription.created_at.strftime("%d-%m-%Y") if prescription.created_at else "",
        "time": prescription.created_at.strftime("%H:%M") if prescription.created_at else "",
        "patient_text": _dict_to_lines(patient_details),
        "doctor_text": _dict_to_lines(doctor_details),
        "instructions_text": "",
    }

    instr_lines = []
    for i, m in enumerate(prescription.medicines or [], 1):
        name = m.normalized_name or m.original_name or f"Medicine {i}"
        inst = (m.instructions or "").strip()
        expl = (m.explanation or "").strip()
        msg = inst
        if expl:
            msg = (msg + " | " if msg else "") + expl
        if msg:
            trimmed = msg[:200]
            instr_lines.append(f"{i}. {name}: {trimmed}")
    export_defaults["instructions_text"] = "\n".join(instr_lines)

    image_url = None
    if prescription.image_path:
        try:
            image_url = f"/uploads/{Path(prescription.image_path).name}"
        except Exception:
            image_url = None

    return templates.TemplateResponse(
        "workspace.html",
        {
            "request": request,
            "prescription": prescription,
            "tab": tab,
            "saved": saved,
            "error": error,
            "analytics": analytics,
            "patient_details": patient_details,
            "doctor_details": doctor_details,
            "transliterated": transliterated,
            "image_url": image_url,
            "export_overrides": export_overrides,
            "export_defaults": export_defaults,
            "patient_keys": PATIENT_KEYS,
            "doctor_keys": DOCTOR_KEYS,
            "verifier_name": verifier_name,
            "transliteration_languages": [
                ("english", "English"),
                ("hindi", "Hindi"),
                ("marathi", "Marathi"),
                ("kannada", "Kannada"),
                ("gujarati", "Gujarati"),
                ("punjabi", "Punjabi"),
                ("bengali", "Bengali"),
                ("tamil", "Tamil"),
                ("telugu", "Telugu"),
                ("malayalam", "Malayalam"),
                ("odia", "Odia"),
                ("sanskrit", "Sanskrit"),
            ],
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

    if prescription.status == PrescriptionStatusEnum.VERIFIED:
        raise HTTPException(status_code=400, detail="Cannot modify a verified prescription")

    extraction = await call_gemma(prescription.raw_text)
    gemma_meds = extraction.medicines or []

    # ✅ CORRECTION LAYER: Fix spelling, complete missing data, normalize formats
    logger.info(f"Correcting {len(gemma_meds)} extracted medicines")
    corrected_meds = await correct_medicines_batch(gemma_meds)

    validated, final_conf = validate_medicines(
        gemma_medicines=[GemmaMedicine(**m.dict()) for m in corrected_meds],
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
            age_range=item.age_range or None,
        )
        db.add(med)

    prescription.confidence_score = final_conf
    db.commit()

    return RedirectResponse(url=f"/workspace/{prescription_id}?tab=overview", status_code=303)


@router.get("/{prescription_id}/refresh-all")
async def refresh_all_extractions_get(
    prescription_id: int,
    db: Session = Depends(get_db),
) -> Any:
    await _run_all_extractions_core(prescription_id, db)
    return RedirectResponse(url=f"/workspace/{prescription_id}?tab=overview", status_code=303)


@router.post("/{prescription_id}/refresh-all")
async def refresh_all_extractions_post(
    prescription_id: int,
    db: Session = Depends(get_db),
) -> Any:
    await _run_all_extractions_core(prescription_id, db)
    return RedirectResponse(url=f"/workspace/{prescription_id}?tab=overview", status_code=303)


@router.post("/{prescription_id}/extract-patient-doctor")
async def run_extract_patient_doctor(
    prescription_id: int,
    db: Session = Depends(get_db),
) -> Any:
    """Extract patient and doctor details from OCR text using AI."""
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription or not prescription.raw_text:
        raise HTTPException(status_code=404, detail="Prescription text not found")

    if prescription.status == PrescriptionStatusEnum.VERIFIED:
        raise HTTPException(status_code=400, detail="Cannot modify a verified prescription")

    result = await call_gemma_extract_patient_doctor(prescription.raw_text)
    prescription.patient_details_json = json.dumps(result.get("patient") or {})
    prescription.doctor_details_json = json.dumps(result.get("doctor") or {})
    db.commit()

    return RedirectResponse(url=f"/workspace/{prescription_id}?tab=overview", status_code=303)


@router.post("/{prescription_id}/update-patient-doctor")
async def update_patient_doctor(
    prescription_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Save or update patient and doctor details from user form (edit/enter)."""
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    form = await request.form()
    patient = {k: (form.get(f"patient_{k}") or "").strip() for k in PATIENT_KEYS}
    doctor = {k: (form.get(f"doctor_{k}") or "").strip() for k in DOCTOR_KEYS}

    prescription.patient_details_json = json.dumps(patient)
    prescription.doctor_details_json = json.dumps(doctor)
    db.commit()

    return RedirectResponse(url=f"/workspace/{prescription_id}?tab=overview", status_code=303)


@router.post("/{prescription_id}/update-meta")
async def update_prescription_meta(
    prescription_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Update prescription title and caption."""
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
    return RedirectResponse(url=f"/workspace/{prescription_id}?tab=overview", status_code=303)


@router.post("/{prescription_id}/update-export-overrides")
async def update_export_overrides(
    prescription_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Persist editable fields used by PDF export (patient/doctor blocks, date/time, instructions)."""
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    form = await request.form()
    overrides = {
        "date": (form.get("export_date") or "").strip(),
        "time": (form.get("export_time") or "").strip(),
        "instructions_text": (form.get("export_instructions_text") or "").strip(),
    }

    patient = {
        "full_name": (form.get("patient_full_name") or "").strip(),
        "age": (form.get("patient_age") or "").strip(),
        "gender": (form.get("patient_gender") or "").strip(),
        "patient_id": (form.get("patient_patient_id") or "").strip(),
        "contact": (form.get("patient_contact") or "").strip(),
        "address": (form.get("patient_address") or "").strip(),
        "allergies": (form.get("patient_allergies") or "").strip(),
    }
    doctor = {
        "name": (form.get("doctor_name") or "").strip(),
        "specialization": (form.get("doctor_specialization") or "").strip(),
        "license": (form.get("doctor_license") or "").strip(),
        "clinic": (form.get("doctor_clinic") or "").strip(),
        "contact": (form.get("doctor_contact") or "").strip(),
        "signature_status": (form.get("doctor_signature_status") or "").strip(),
    }

    patient_clean = {k: v for k, v in patient.items() if v}
    doctor_clean = {k: v for k, v in doctor.items() if v}
    if patient_clean:
        overrides["patient"] = patient_clean
    if doctor_clean:
        overrides["doctor"] = doctor_clean

    # Backward compatibility if old textareas still submit from older pages
    patient_text = (form.get("export_patient_text") or "").strip()
    doctor_text = (form.get("export_doctor_text") or "").strip()
    if patient_text and "patient" not in overrides:
        overrides["patient_text"] = patient_text
    if doctor_text and "doctor" not in overrides:
        overrides["doctor_text"] = doctor_text

    # Normalize empties to missing keys
    cleaned = {k: v for k, v in overrides.items() if v}
    prescription.export_overrides_json = json.dumps(cleaned) if cleaned else None
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save export details: {e}")

    return RedirectResponse(url=f"/workspace/{prescription_id}?tab=export&saved=1", status_code=303)


@router.post("/{prescription_id}/refresh-export-overrides")
async def refresh_export_overrides(
    prescription_id: int,
    db: Session = Depends(get_db),
) -> Any:
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    patient_details = {}
    doctor_details = {}
    if prescription.patient_details_json:
        try:
            patient_details = json.loads(prescription.patient_details_json) or {}
        except (json.JSONDecodeError, TypeError):
            patient_details = {}
    if prescription.doctor_details_json:
        try:
            doctor_details = json.loads(prescription.doctor_details_json) or {}
        except (json.JSONDecodeError, TypeError):
            doctor_details = {}

    created = prescription.created_at
    date_str = created.strftime("%d-%m-%Y") if created else ""
    time_str = created.strftime("%H:%M") if created else ""

    patient = {
        "full_name": (patient_details.get("full_name") or patient_details.get("name") or "").strip(),
        "age": str(patient_details.get("age") or "").strip(),
        "gender": str(patient_details.get("gender") or "").strip(),
        "patient_id": str(patient_details.get("patient_id") or "").strip(),
        "contact": str(patient_details.get("contact") or patient_details.get("phone") or "").strip(),
        "address": str(patient_details.get("address") or "").strip(),
        "allergies": str(patient_details.get("allergies") or "").strip(),
    }
    doctor = {
        "name": (doctor_details.get("doctor_name") or doctor_details.get("name") or "").strip(),
        "specialization": str(doctor_details.get("specialization") or "").strip(),
        "license": str(doctor_details.get("registration_number") or doctor_details.get("license_number") or "").strip(),
        "clinic": str(doctor_details.get("clinic") or doctor_details.get("clinic_hospital") or "").strip(),
        "contact": str(doctor_details.get("contact") or doctor_details.get("phone") or "").strip(),
        "signature_status": str(doctor_details.get("digital_signature_status") or "").strip(),
    }

    instr_lines = []
    for i, m in enumerate(prescription.medicines or [], 1):
        name = m.normalized_name or m.original_name or f"Medicine {i}"
        inst = (m.instructions or "").strip()
        expl = (m.explanation or "").strip()
        msg = inst
        if expl:
            msg = (msg + " | " if msg else "") + expl
        if msg:
            instr_lines.append(f"{i}. {name}: {msg[:200]}")
        else:
            dose = (m.dose or "").strip()
            freq = (m.frequency or "").strip()
            dur = f"{m.duration_days} days" if m.duration_days else ""
            parts = [p for p in [dose, freq, dur] if p]
            if parts:
                instr_lines.append(f"{i}. {name}: {' | '.join(parts)[:200]}")

    overrides = {
        "date": date_str,
        "time": time_str,
        "instructions_text": "\n".join(instr_lines),
        "patient": {k: v for k, v in patient.items() if v},
        "doctor": {k: v for k, v in doctor.items() if v},
    }
    cleaned = {k: v for k, v in overrides.items() if v}
    prescription.export_overrides_json = json.dumps(cleaned) if cleaned else None
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to refresh export details: {e}")

    return RedirectResponse(url=f"/workspace/{prescription_id}?tab=export&saved=1", status_code=303)


@router.post("/{prescription_id}/convert-export-data")
async def convert_export_data(
    prescription_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    form = await request.form()
    lang = (form.get("language") or "").strip().lower()
    if not lang or lang == "english":
        return JSONResponse({
            "patient_text": (form.get("patient_text") or ""),
            "doctor_text": (form.get("doctor_text") or ""),
            "instructions_text": (form.get("instructions_text") or ""),
        })

    patient_text = (form.get("patient_text") or "").strip()
    doctor_text = (form.get("doctor_text") or "").strip()
    instructions_text = (form.get("instructions_text") or "").strip()

    translated = translate_prescription(patient_text, doctor_text, instructions_text, lang)
    return JSONResponse({
        "patient_text": translated.get("patient", ""),
        "doctor_text": translated.get("doctor", ""),
        "instructions_text": translated.get("medicines", ""),
    })


@router.post("/{prescription_id}/medicine/{medicine_id}/update")
async def update_medicine(
    prescription_id: int,
    medicine_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Update a single medicine's structured data (name, dose, frequency, etc.)."""
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    if prescription.status == PrescriptionStatusEnum.VERIFIED:
        raise HTTPException(status_code=400, detail="Cannot modify a verified prescription")

    medicine = db.query(Medicine).filter(
        Medicine.id == medicine_id,
        Medicine.prescription_id == prescription_id,
    ).first()
    if not medicine:
        raise HTTPException(status_code=404, detail="Medicine not found")
    form = await request.form()
    name = (form.get("name") or "").strip()
    if name:
        medicine.original_name = name
        medicine.normalized_name = name
    for field in ("dose", "frequency", "instructions", "age_range"):
        val = (form.get(field) or "").strip()
        setattr(medicine, field, val if val else None)
    duration = form.get("duration_days")
    if duration is not None and duration != "":
        try:
            medicine.duration_days = int(duration)
        except ValueError:
            pass
    db.commit()
    return RedirectResponse(url=f"/workspace/{prescription_id}?tab=overview", status_code=303)


@router.post("/{prescription_id}/medicine/{medicine_id}/explain")
async def run_explain_medicine(
    prescription_id: int,
    medicine_id: int,
    db: Session = Depends(get_db),
) -> Any:
    """Generate AI explanation for a medicine and save it."""
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    medicine = db.query(Medicine).filter(
        Medicine.id == medicine_id,
        Medicine.prescription_id == prescription_id,
    ).first()
    if not medicine:
        raise HTTPException(status_code=404, detail="Medicine not found")

    explanation = await call_gemma_explain_medicine(
        medicine_name=medicine.normalized_name or medicine.original_name,
        dose=medicine.dose or "",
        frequency=medicine.frequency or "",
        duration=str(medicine.duration_days) if medicine.duration_days else "",
        instructions=medicine.instructions or "",
    )
    medicine.explanation = (explanation or "").strip()[:500]
    db.commit()

    return RedirectResponse(url=f"/workspace/{prescription_id}?tab=overview", status_code=303)


@router.post("/{prescription_id}/explain-all-medicines")
async def run_explain_all_medicines(
    prescription_id: int,
    db: Session = Depends(get_db),
) -> Any:
    """Generate AI explanations for all medicines in the prescription."""
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    print(f"Generating explanations for {len(prescription.medicines)} medicines...")
    for medicine in prescription.medicines:
        try:
            explanation = await call_gemma_explain_medicine(
                medicine_name=medicine.normalized_name or medicine.original_name,
                dose=medicine.dose or "",
                frequency=medicine.frequency or "",
                duration=str(medicine.duration_days) if medicine.duration_days else "",
                instructions=medicine.instructions or "",
            )
            medicine.explanation = (explanation or "").strip()[:500]
            print(f"Explained {medicine.normalized_name}")
        except Exception as e:
            print(f"Failed to explain {medicine.normalized_name}: {e}")

    db.commit()
    return RedirectResponse(url=f"/workspace/{prescription_id}?tab=overview", status_code=303)


TRANSLITERATION_LANGUAGES = [
    ("english", "English"),
    ("hindi", "Hindi"),
    ("marathi", "Marathi"),
    ("kannada", "Kannada"),
    ("gujarati", "Gujarati"),
    ("punjabi", "Punjabi"),
    ("bengali", "Bengali"),
    ("tamil", "Tamil"),
    ("telugu", "Telugu"),
    ("malayalam", "Malayalam"),
    ("odia", "Odia"),
    ("sanskrit", "Sanskrit"),
]


def _build_prescription_sections(prescription, patient_details: dict, doctor_details: dict):
    """Build patient, doctor, medicines text sections separately for translation."""
    p_lines = []
    for k, v in (patient_details or {}).items():
        if v and str(v).strip():
            p_lines.append(f"{k.replace('_', ' ').title()}: {v}")
    patient_text = "\n".join(p_lines) if p_lines else ""

    d_lines = []
    for k, v in (doctor_details or {}).items():
        if v and str(v).strip():
            d_lines.append(f"{k.replace('_', ' ').title()}: {v}")
    doctor_text = "\n".join(d_lines) if d_lines else ""

    med_lines = []
    for i, m in enumerate(prescription.medicines or [], 1):
        name = m.normalized_name or m.original_name
        dose = m.dose or "—"
        freq = format_frequency(m.frequency)
        dur = f"{m.duration_days} days" if m.duration_days else "—"
        age_range = m.age_range or "Consult doctor for exact age range"
        inst = m.instructions or "Doctor's instructions: —"
        expl = (m.explanation or "Explanation: —")[:300]
        med_lines.append(f"{i}. {name}\n   Dose: {dose} | Frequency: {freq} | Duration: {dur} | Age range: {age_range}\n   {inst}\n   {expl}")
    medicines_text = "\n\n".join(med_lines) if med_lines else ""

    if not patient_text and not doctor_text and not medicines_text and prescription.raw_text:
        return "", "", prescription.raw_text
    return patient_text, doctor_text, medicines_text


@router.post("/{prescription_id}/transliterate")
async def run_transliterate(
    prescription_id: int,
    language: str = Form(...),
    db: Session = Depends(get_db),
) -> Any:
    """Transliterate full prescription (patient, doctor, medicines) into selected language. One language at a time."""
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    lang_key = language.lower().strip()
    valid_keys = [k for k, _ in TRANSLITERATION_LANGUAGES]
    if lang_key not in valid_keys:
        raise HTTPException(status_code=400, detail=f"Invalid language. Choose from: {valid_keys}")

    patient_details = {}
    doctor_details = {}
    if prescription.patient_details_json:
        try:
            patient_details = json.loads(prescription.patient_details_json)
        except (json.JSONDecodeError, TypeError):
            pass
    if prescription.doctor_details_json:
        try:
            doctor_details = json.loads(prescription.doctor_details_json)
        except (json.JSONDecodeError, TypeError):
            pass

    patient_text, doctor_text, medicines_text = _build_prescription_sections(
        prescription, patient_details, doctor_details
    )
    if not patient_text and not doctor_text and not medicines_text:
        raise HTTPException(status_code=400, detail="No data to transliterate. Run AI Extraction and Patient/Doctor extraction first.")

    lang_label = next((lbl for k, lbl in TRANSLITERATION_LANGUAGES if k == lang_key), lang_key.title())
    result = await asyncio.to_thread(
        translate_prescription, patient_text, doctor_text, medicines_text, lang_key
    )

    # Store only one language at a time
    transliterated = {
        "language": lang_key,
        "label": lang_label,
        "patient": result.get("patient", ""),
        "doctor": result.get("doctor", ""),
        "medicines": result.get("medicines", ""),
        "full": result.get("full", ""),
    }
    prescription.transliterated_json = json.dumps(transliterated)
    db.commit()

    return RedirectResponse(url=f"/workspace/{prescription_id}?tab=transliteration", status_code=303)


@router.post("/{prescription_id}/confirm")
async def confirm_prescription(
    prescription_id: int,
    start_date: str = Form(""),
    db: Session = Depends(get_db),
) -> Any:
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    if not prescription.medicines:
        return RedirectResponse(
            url=f"/workspace/{prescription_id}?tab=overview&error=Run%20AI%20Extraction%20first%20to%20extract%20medicines%20before%20activating%20the%20schedule",
            status_code=303,
        )

    # Clear future schedule entries (preserve history)
    today = date.today()
    for d in list(prescription.doses or []):
        if d.date and d.date >= today and not d.taken:
            db.delete(d)
    db.commit()

    parsed_start: date | None = None
    if start_date and str(start_date).strip():
        try:
            parsed_start = date.fromisoformat(str(start_date).strip())
        except ValueError:
            parsed_start = None

    generate_schedule_for_prescription(db, prescription, start_date=parsed_start)
    prescription.status = PrescriptionStatusEnum.ACTIVE
    db.commit()

    return RedirectResponse(url=f"/workspace/{prescription_id}?tab=calendar", status_code=303)


@router.post("/{prescription_id}/verify")
async def verify_prescription_workspace(
    prescription_id: int,
    db: Session = Depends(get_db),
) -> Any:
    """Clinically verify a prescription by a doctor."""
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    # In current demo mode, we use the hardcoded DEMO_DOCTOR ID from doctor.py
    # or a generic doctor ID (e.g. 9001).
    prescription.status = PrescriptionStatusEnum.VERIFIED
    prescription.verified_by = 9001  # Hardcoded for clinical demo flow
    prescription.verified_at = datetime.utcnow()
    
    # Also update any forward queue items as verified
    for fq in prescription.forward_queues:
        if fq.status == "pending":
            fq.status = "verified"
            fq.reviewed_at = datetime.utcnow()


@router.post("/{prescription_id}/chat")
async def workspace_chat(
    prescription_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    # Check prescription exists
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")
        
    try:
        body = await request.json()
        question = (body.get("question") or "").strip()
        context  = (body.get("context")  or "").strip()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if not question:
        return JSONResponse({"answer": "Please ask a specific question about your prescription."})

    from app.config import get_settings as _gs
    _settings = _gs()
    api_key = _settings.nvidia_qwen_api_key or _settings.nvidia_api_key

    system_msg = (
        "You are 'Sanjivini AI', an elite patient-facing medical assistant. "
        "Your goal is to provide exceptionally clear, structured, and helpful guidance based on the patient's prescription. "
        "Format your answers like a high-end AI: "
        "- Use markdown bullet points for lists of instructions or medications. "
        "- Use markdown tables for dosing schedules, timing, or comparisons. "
        "- Use bold text for critical warnings or medicine names. "
        "- Maintain a professional yet empathetic tone. "
        "IMPORTANT: You are an AI, NOT a substitute for professional medical advice. Always advise consulting the doctor for definitive changes. "
        + (f"\nClinical Context: {context}" if context else "")
    )

    if not api_key:
        return JSONResponse({"answer": "NVIDIA API Key missing. Please check your configuration."})

    import httpx as _httpx
    try:
        async with _httpx.AsyncClient(timeout=45.0) as client:
            r = await client.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "qwen/qwen2-7b-instruct",
                    "messages": [
                        {"role": "system", "content": system_msg},
                        {"role": "user",   "content": question},
                    ],
                    "max_tokens": 1024,
                    "temperature": 0.3,
                },
            )
            r.raise_for_status()
            answer = r.json()["choices"][0]["message"]["content"].strip()
            return JSONResponse({"answer": answer})
    except Exception as exc:
        logger.error(f"Workspace Chat API failed: {exc}")
        return JSONResponse({"answer": "Sanjivini AI service temporarily unavailable. Please refer to your clinical overview."})

@router.post("/{prescription_id}/generate-tts-script")
async def workspace_generate_tts_script(
    prescription_id: int,
    request: Request,
    db: Session = Depends(get_db)
) -> Any:
    """Generate a conversational TTS script dynamically using Gemma/Ollama."""
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")
        
    try:
        body = await request.json()
        context_data = body.get("context_data", "")
        target_lang = body.get("target_lang", "en")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if not context_data:
        raise HTTPException(status_code=400, detail="Missing context_data")

    try:
        script = await call_gemma_clinical_tts_script(context_data, target_lang=target_lang)
        return JSONResponse({"script": script})
    except Exception as exc:
        logger.error(f"Failed to generate TTS script: {exc}")
        raise HTTPException(status_code=500, detail="Failed to generate voice script.")

