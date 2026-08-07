"""
X-Ray Fracture Analysis Router
═══════════════════════════════
Endpoints:
  GET  /doctor/xray                  → landing / upload page
  POST /doctor/xray/upload           → upload & store xray
  POST /doctor/xray/detect/{uuid}    → run YOLOv7 + save detections
  POST /doctor/xray/explain/{uuid}   → generate AI explanation
  GET  /doctor/xray/result/{uuid}    → full result page
  POST /doctor/xray/verify/{uuid}    → doctor verify/reject/edit
  GET  /doctor/xray/history          → all scans list
"""
from __future__ import annotations

import base64
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.database import get_db
from app.models.models import (
    XrayScan, XrayDetection, XrayAIReport, XrayVerification, User
)

logger = logging.getLogger(__name__)

settings  = get_settings()
from app.core.deps import require_role

router    = APIRouter(prefix="/doctor/xray", tags=["xray"], dependencies=[Depends(require_role("doctor"))])
templates = Jinja2Templates(directory=str(settings.base_dir / "app" / "templates"))

DEMO_DOCTOR = {"id": 9001, "name": "Dr. Priya Sharma", "specialization": "General Physician"}

_XRAY_DIR = settings.uploads_dir / "xrays"
_ANN_DIR  = settings.uploads_dir / "xrays" / "annotated"
_HEAT_DIR = settings.uploads_dir / "xrays" / "heatmaps"

for _d in (_XRAY_DIR, _ANN_DIR, _HEAT_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# ─── helpers ─────────────────────────────────────────────────────────────────

def _scan_or_404(scan_uuid: str, db: Session) -> XrayScan:
    scan = db.query(XrayScan).filter(XrayScan.scan_uuid == scan_uuid).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


def _to_view(scan: XrayScan) -> dict:
    """Convert ORM scan → template-friendly dict."""
    detections = []
    for d in scan.detections:
        bbox = json.loads(d.bbox_json) if d.bbox_json else []
        detections.append({
            "id":            d.id,
            "label":         d.label,
            "label_display": d.label_display or d.label,
            "confidence":    d.confidence,
            "confidence_pct": f"{d.confidence:.0%}",
            "bbox":          bbox,
            "class_id":      d.class_id,
        })

    report = scan.ai_reports[-1] if scan.ai_reports else None
    verification = scan.verifications[-1] if scan.verifications else None

    ann_url  = f"/uploads/xrays/annotated/{Path(report.annotated_path).name}" if report and report.annotated_path else None
    heat_url = f"/uploads/xrays/heatmaps/{Path(report.heatmap_path).name}"   if report and report.heatmap_path   else None
    orig_url = f"/uploads/xrays/{Path(scan.image_path).name}"

    return {
        "scan_uuid":    scan.scan_uuid,
        "filename":     scan.filename or "xray.png",
        "uploaded_at":  scan.uploaded_at.strftime("%d %b %Y, %H:%M") if scan.uploaded_at else "",
        "status":       scan.status,
        "notes":        scan.notes or "",
        "detections":   detections,
        "has_fracture": report.has_fracture if report else False,
        "explanation":  report.explanation if report else None,
        "annotated_url": ann_url,
        "heatmap_url":   heat_url,
        "orig_url":      orig_url,
        "verification":  {
            "status":   verification.status,
            "doctor":   verification.doctor_name or "Unknown",
            "remarks":  verification.remarks or "",
            "edited":   verification.edited_explanation or "",
            "at":       verification.verified_at.strftime("%d %b %Y, %H:%M") if verification.verified_at else "",
        } if verification else None,
    }


# ─── Landing page ────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
def xray_landing(request: Request, db: Session = Depends(get_db)) -> Any:
    recent = (
        db.query(XrayScan)
        .order_by(XrayScan.uploaded_at.desc())
        .limit(5)
        .all()
    )
    recent_list = []
    for s in recent:
        rep = s.ai_reports[-1] if s.ai_reports else None
        ver = s.verifications[-1] if s.verifications else None
        recent_list.append({
            "scan_uuid":   s.scan_uuid,
            "filename":    s.filename or "xray.png",
            "uploaded_at": s.uploaded_at.strftime("%d %b %Y") if s.uploaded_at else "",
            "status":      s.status,
            "has_fracture": rep.has_fracture if rep else False,
            "verified":    ver.status if ver else None,
            "finding_count": len(s.detections),
        })

    return templates.TemplateResponse(
        "doctor_xray.html",
        {
            "request": request,
            "title": "AI Fracture Analysis",
            "doctor": DEMO_DOCTOR,
            "active_nav": "xray",
            "page": "upload",
            "recent_scans": recent_list,
        },
    )


# ─── Upload ──────────────────────────────────────────────────────────────────

@router.post("/upload")
async def xray_upload(
    request: Request,
    file: UploadFile = File(...),
    patient_notes: str = Form(""),
    db: Session = Depends(get_db),
) -> Any:
    ext = Path(file.filename or "scan.png").suffix.lower() or ".png"
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}:
        raise HTTPException(status_code=400, detail="Unsupported image format")

    scan_id = uuid.uuid4().hex
    dest    = _XRAY_DIR / f"{scan_id}{ext}"
    content = await file.read()
    dest.write_bytes(content)

    scan = XrayScan(
        scan_uuid  = scan_id,
        image_path = str(dest),
        filename   = file.filename or f"xray{ext}",
        notes      = patient_notes.strip() or None,
        status     = "uploaded",
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    logger.info(f"X-ray uploaded scan_uuid={scan_id}, size={len(content)} bytes")
    return JSONResponse({"scan_uuid": scan_id, "filename": scan.filename})


# ─── Detect ──────────────────────────────────────────────────────────────────

@router.post("/detect/{scan_uuid}")
async def xray_detect(
    scan_uuid: str,
    threshold: float = 0.30,
    db: Session = Depends(get_db),
) -> Any:
    scan = _scan_or_404(scan_uuid, db)
    img_bytes = Path(scan.image_path).read_bytes()

    scan.status = "processing"
    db.commit()

    try:
        from app.services.fracture_service import run_fracture_detection

        result = run_fracture_detection(img_bytes, threshold=threshold)

        # Persist detections
        db.query(XrayDetection).filter(XrayDetection.scan_id == scan.id).delete()
        for det in result["detections"]:
            db.add(XrayDetection(
                scan_id       = scan.id,
                label         = det["label"],
                label_display = det["label_display"],
                confidence    = det["confidence"],
                bbox_json     = json.dumps(det["bbox"]),
                class_id      = det["class_id"],
            ))

        # Save annotated / heatmap images
        ann_path  = None
        heat_path = None
        if result.get("annotated_b64"):
            ann_path = str(_ANN_DIR / f"{scan_uuid}_annotated.png")
            Path(ann_path).write_bytes(base64.b64decode(result["annotated_b64"]))
        if result.get("heatmap_b64"):
            heat_path = str(_HEAT_DIR / f"{scan_uuid}_heatmap.png")
            Path(heat_path).write_bytes(base64.b64decode(result["heatmap_b64"]))

        # Upsert AI report (detection + images, no explanation yet)
        existing = db.query(XrayAIReport).filter(XrayAIReport.scan_id == scan.id).first()
        if existing:
            existing.has_fracture   = result["has_fracture"]
            existing.annotated_path = ann_path
            existing.heatmap_path   = heat_path
            existing.explanation    = existing.explanation or ""
        else:
            db.add(XrayAIReport(
                scan_id        = scan.id,
                explanation    = "",
                annotated_path = ann_path,
                heatmap_path   = heat_path,
                has_fracture   = result["has_fracture"],
            ))

        scan.status = "detected"
        db.commit()

        return JSONResponse({
            "success":   True,
            "scan_uuid": scan_uuid,
            "summary":   result["summary"],
            "has_fracture": result["has_fracture"],
            "model_available": result["model_available"],
            "inference_ms": result.get("inference_ms", 0),
            "detection_count": len(result["detections"]),
        })

    except Exception as exc:
        scan.status = "error"
        db.commit()
        logger.error(f"Detection failed for {scan_uuid}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Explain ─────────────────────────────────────────────────────────────────

@router.post("/explain/{scan_uuid}")
async def xray_explain(scan_uuid: str, db: Session = Depends(get_db)) -> Any:
    scan = _scan_or_404(scan_uuid, db)

    detections = [
        {
            "label":         d.label,
            "label_display": d.label_display or d.label,
            "confidence":    d.confidence,
            "bbox":          json.loads(d.bbox_json) if d.bbox_json else [],
        }
        for d in scan.detections
    ]

    # Provide original image as base64 for multimodal
    img_b64 = None
    try:
        img_b64 = base64.b64encode(Path(scan.image_path).read_bytes()).decode()
    except Exception:
        pass

    try:
        from app.services.fracture_service import get_ai_explanation
        logger.info(f"Generating Sanjivini AI report for scan {scan_uuid}…")
        explanation = await get_ai_explanation(detections, image_b64=img_b64)
        logger.info(f"AI report ready for scan {scan_uuid}")
    except Exception as exc:
        logger.error(f"AI explanation failed: {exc}")
        explanation = "AI explanation unavailable. Please review detection results manually."

    report = db.query(XrayAIReport).filter(XrayAIReport.scan_id == scan.id).first()
    if report:
        report.explanation = explanation
    else:
        db.add(XrayAIReport(
            scan_id     = scan.id,
            explanation = explanation,
            has_fracture = any(d["label"] == "fracture" for d in detections),
        ))

    scan.status = "done"
    db.commit()

    return JSONResponse({"success": True, "explanation": explanation})


# ─── Result page ─────────────────────────────────────────────────────────────

@router.get("/result/{scan_uuid}", response_class=HTMLResponse)
def xray_result(request: Request, scan_uuid: str, db: Session = Depends(get_db)) -> Any:
    scan = _scan_or_404(scan_uuid, db)
    view = _to_view(scan)

    return templates.TemplateResponse(
        "doctor_xray.html",
        {
            "request":    request,
            "title":      "Fracture Analysis Result",
            "doctor":     DEMO_DOCTOR,
            "active_nav": "xray",
            "page":       "result",
            "scan":       view,
        },
    )


# ─── Verify ──────────────────────────────────────────────────────────────────

@router.post("/verify/{scan_uuid}")
async def xray_verify(
    request: Request,
    scan_uuid: str,
    db: Session = Depends(get_db),
) -> Any:
    form   = await request.form()
    status  = (form.get("status") or "").strip()
    remarks = (form.get("remarks") or "").strip()
    edited  = (form.get("edited_explanation") or "").strip()

    if status not in ("approved", "rejected", "modified"):
        raise HTTPException(status_code=400, detail="Invalid status")

    scan = _scan_or_404(scan_uuid, db)

    verif = XrayVerification(
        scan_id            = scan.id,
        doctor_name        = DEMO_DOCTOR["name"],
        status             = status,
        remarks            = remarks or None,
        edited_explanation = edited or None,
        verified_at        = datetime.utcnow(),
    )
    db.add(verif)

    # If doctor edited, update the AI report explanation
    if edited:
        rep = db.query(XrayAIReport).filter(XrayAIReport.scan_id == scan.id).first()
        if rep:
            rep.explanation = edited

    scan.status = "verified" if status == "approved" else ("rejected" if status == "rejected" else "done")
    db.commit()

    return JSONResponse({"success": True, "status": status})


# ─── History ─────────────────────────────────────────────────────────────────

@router.get("/history", response_class=HTMLResponse)
def xray_history(request: Request, db: Session = Depends(get_db)) -> Any:
    scans = db.query(XrayScan).order_by(XrayScan.uploaded_at.desc()).all()
    scan_list = []
    for s in scans:
        rep = s.ai_reports[-1] if s.ai_reports else None
        ver = s.verifications[-1] if s.verifications else None
        scan_list.append({
            "scan_uuid":   s.scan_uuid,
            "filename":    s.filename or "xray.png",
            "uploaded_at": s.uploaded_at.strftime("%d %b %Y, %H:%M") if s.uploaded_at else "",
            "status":      s.status,
            "has_fracture": rep.has_fracture if rep else False,
            "finding_count": len(s.detections),
            "verified":    ver.status if ver else None,
            "doctor":      ver.doctor_name if ver else "",
        })

    return templates.TemplateResponse(
        "doctor_xray.html",
        {
            "request": request,
            "title": "X-Ray Scan History",
            "doctor": DEMO_DOCTOR,
            "active_nav": "xray",
            "page": "history",
            "scan_list": scan_list,
        },
    )


# ─── AI Chat endpoint ─────────────────────────────────────────────────────────

@router.post("/chat")
async def xray_chat(request: Request) -> Any:
    """Lightweight chat endpoint for the result-page AI assistant."""
    try:
        body = await request.json()
        question = (body.get("question") or "").strip()
        context  = (body.get("context")  or "").strip()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if not question:
        return JSONResponse({"answer": "Please ask a specific question about the X-ray."})

    from app.config import get_settings as _gs
    _settings = _gs()
    # Use Kimi K2.5 key for chat if available, otherwise fall back
    api_key = _settings.nvidia_kimi_api_key or _settings.nvidia_qwen_api_key or _settings.nvidia_api_key

    system_msg = (
        "You are an expert radiologist AI assistant. "
        "Answer the doctor's question about the X-ray findings concisely and professionally. "
        "Keep answers under 150 words. "
        + (f"Context from analysis: {context}" if context else "")
    )

    if not api_key:
        return JSONResponse({
            "answer": (
                "AI chat requires an NVIDIA API key. "
                "Please review the clinical report above for findings."
            )
        })

    import httpx as _httpx
    try:
        async with _httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "moonshotai/kimi-k2.5",
                    "messages": [
                        {"role": "system", "content": system_msg},
                        {"role": "user",   "content": question},
                    ],
                    "max_tokens": 512,
                    "temperature": 1.00,
                    "top_p": 0.95,
                    "chat_template_kwargs": {"thinking": False},
                },
            )
            r.raise_for_status()
            answer = r.json()["choices"][0]["message"]["content"].strip()
            return JSONResponse({"answer": answer})
    except Exception as exc:
        logger.error(f"Chat API failed: {exc}")
        return JSONResponse({"answer": "Chat service temporarily unavailable. Please review the report above."})
