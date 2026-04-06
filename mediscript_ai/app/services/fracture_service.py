"""
Fracture Analysis Service
────────────────────────
Pipeline:
  1. YOLOv7 ONNX  → structured bone-finding detections
  2. Kimi K2.5    → deep multimodal clinical report (thinking mode + X-ray image)
  3. Fallback     → Qwen VL → Qwen-7B → rule-based (offline)
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
import numpy as np

logger = logging.getLogger(__name__)

# ─── Model paths ────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
ONNX_MODEL_PATH = Path(
    os.environ.get(
        "YOLO_FRACTURE_MODEL_PATH",
        str(_HERE.parent.parent / "yolov7-p6-bonefracture.onnx"),
    )
)

# ─── Class map ───────────────────────────────────────────────────────────────
ID2NAMES: Dict[int, str] = {
    0: "boneanomaly",
    1: "bonelesion",
    2: "foreignbody",
    3: "fracture",
    4: "metal",
    5: "periostealreaction",
    6: "pronatorsign",
    7: "softtissue",
    8: "text",
}

CLINICAL_LABELS = {
    "boneanomaly":        "Bone Anomaly",
    "bonelesion":         "Bone Lesion",
    "foreignbody":        "Foreign Body",
    "fracture":           "Fracture",
    "metal":              "Metal Implant",
    "periostealreaction": "Periosteal Reaction",
    "pronatorsign":       "Pronator Sign",
    "softtissue":         "Soft Tissue Finding",
    "text":               "Annotation Text",
}

PALETTE = [
    (255, 99,  72),   # 0 - red-orange
    (255, 175, 51),   # 1 - amber
    (33,  182, 168),  # 2 - teal
    (255, 59,  59),   # 3 - fracture = red
    (120, 119, 198),  # 4 - purple
    (255, 209, 102),  # 5 - yellow
    (52,  199, 89),   # 6 - green
    (90,  200, 250),  # 7 - sky
    (175, 82,  222),  # 8 - violet
]

_ort_session = None  # lazy singleton


def _get_session():
    global _ort_session
    if _ort_session is not None:
        return _ort_session
    try:
        import onnxruntime as ort
        if not ONNX_MODEL_PATH.exists():
            raise FileNotFoundError(f"ONNX model not found at {ONNX_MODEL_PATH}")
        providers = (
            ["CUDAExecutionProvider"]
            if "CUDAExecutionProvider" in ort.get_available_providers()
            else ["CPUExecutionProvider"]
        )
        _ort_session = ort.InferenceSession(str(ONNX_MODEL_PATH), providers=providers)
        logger.info(f"YOLOv7 ONNX model loaded from {ONNX_MODEL_PATH}")
        return _ort_session
    except Exception as exc:
        logger.error(f"Failed to load ONNX model: {exc}")
        raise


# ─── Preprocessing ───────────────────────────────────────────────────────────
_MODEL_W, _MODEL_H = 640, 640


def _preprocess(img_bytes: bytes) -> Tuple[np.ndarray, int, int]:
    """Return (model_input_float32, orig_W, orig_H)."""
    from PIL import Image as PILImage, ImageOps

    img = PILImage.open(io.BytesIO(img_bytes)).convert("RGB")
    # 1. Enhance low-contrast X-rays
    img = ImageOps.autocontrast(img)
    
    orig_w, orig_h = img.size
    
    # 2. Letterbox padding to maintain aspect ratio
    scale = min(_MODEL_W / orig_w, _MODEL_H / orig_h)
    new_w, new_h = int(orig_w * scale), int(orig_h * scale)
    img_resized = img.resize((new_w, new_h), PILImage.BILINEAR)
    
    padded = PILImage.new("RGB", (_MODEL_W, _MODEL_H), (114, 114, 114))  # Neutral gray padding matches YOLO pre-train
    pad_w = (_MODEL_W - new_w) // 2
    pad_h = (_MODEL_H - new_h) // 2
    padded.paste(img_resized, (pad_w, pad_h))
    
    arr = np.array(padded, dtype=np.float32) / 255.0   # H×W×C
    arr = arr.transpose(2, 0, 1)                             # C×H×W
    arr = np.expand_dims(arr, axis=0)                        # 1×C×H×W
    return arr, orig_w, orig_h


# ─── Post-process ────────────────────────────────────────────────────────────

def _postprocess(
    raw_output: np.ndarray,
    orig_w: int,
    orig_h: int,
    threshold: float = 0.15,
) -> List[Dict[str, Any]]:
    """Convert raw ONNX output → list of detection dicts."""
    detections = []
    scale = min(_MODEL_W / orig_w, _MODEL_H / orig_h)
    new_w, new_h = int(orig_w * scale), int(orig_h * scale)
    pad_w = (_MODEL_W - new_w) // 2
    pad_h = (_MODEL_H - new_h) // 2

    for row in raw_output:
        x1, y1, x2, y2, score, cls_id = row[:6]
        if score < threshold:
            continue
        cls_id = int(cls_id)
        
        # Remove padding offset and scale back to original map dims
        bbox_x1 = max(0, int((x1 - pad_w) / scale))
        bbox_y1 = max(0, int((y1 - pad_h) / scale))
        bbox_x2 = min(orig_w, int((x2 - pad_w) / scale))
        bbox_y2 = min(orig_h, int((y2 - pad_h) / scale))
        
        detections.append(
            {
                "label":         ID2NAMES.get(cls_id, f"class_{cls_id}"),
                "label_display": CLINICAL_LABELS.get(ID2NAMES.get(cls_id, ""), ID2NAMES.get(cls_id, "")),
                "confidence":    float(round(score, 4)),
                "bbox":          [bbox_x1, bbox_y1, bbox_x2, bbox_y2],
                "class_id": cls_id,
            }
        )
    return detections


# ─── Draw annotated image ─────────────────────────────────────────────────────

def _draw_annotated(img_bytes: bytes, detections: List[Dict]) -> bytes:
    """Return PNG bytes with bounding boxes drawn."""
    from PIL import Image as PILImage, ImageDraw, ImageFont

    img = PILImage.open(io.BytesIO(img_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except Exception:
        font = ImageFont.load_default()

    for det in detections:
        x1, y1, x2, y2 = det["bbox"]
        color = PALETTE[det["class_id"] % len(PALETTE)]
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
        label_txt = f"{det['label_display']} {det['confidence']:.0%}"
        bbox_text = draw.textbbox((x1, y1), label_txt, font=font)
        tw = bbox_text[2] - bbox_text[0]
        th = bbox_text[3] - bbox_text[1]
        draw.rectangle([x1 - 1, y1 - th - 8, x1 + tw + 4, y1], fill=color)
        draw.text((x1 + 2, y1 - th - 4), label_txt, fill=(255, 255, 255), font=font)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _draw_heatmap(img_bytes: bytes, detections: List[Dict]) -> bytes:
    """Return PNG bytes with Gaussian heatmap overlay for pathological regions."""
    from PIL import Image as PILImage
    import math

    img = PILImage.open(io.BytesIO(img_bytes)).convert("RGBA")
    W, H = img.size
    heat = PILImage.new("RGBA", (W, H), (0, 0, 0, 0))
    pixels = heat.load()

    for det in detections:
        if det["label"] not in ("fracture", "boneanomaly", "bonelesion", "periostealreaction"):
            continue
        x1, y1, x2, y2 = det["bbox"]
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        rx = max((x2 - x1) / 2, 1)
        ry = max((y2 - y1) / 2, 1)
        conf = det["confidence"]

        x_lo = max(0, x1 - int(rx * 0.5))
        x_hi = min(W - 1, x2 + int(rx * 0.5))
        y_lo = max(0, y1 - int(ry * 0.5))
        y_hi = min(H - 1, y2 + int(ry * 0.5))

        for px in range(x_lo, x_hi + 1):
            for py in range(y_lo, y_hi + 1):
                dx = (px - cx) / rx
                dy = (py - cy) / ry
                g = math.exp(-0.5 * (dx * dx + dy * dy))
                alpha = int(g * conf * 180)
                if alpha <= 0:
                    continue
                r, g2, b, a = pixels[px, py]
                nr = min(255, r + int(255 * g * conf))
                ng = max(0, g2 - int(80 * g * conf))
                nb = max(0, b - int(100 * g * conf))
                na = min(255, a + alpha)
                pixels[px, py] = (nr, ng, nb, na)

    result = PILImage.alpha_composite(img, heat).convert("RGB")
    buf = io.BytesIO()
    result.save(buf, format="PNG")
    return buf.getvalue()


# ─── Main YOLO inference ──────────────────────────────────────────────────────

def run_fracture_detection(
    img_bytes: bytes,
    threshold: float = 0.30,
) -> Dict[str, Any]:
    """
    Run YOLOv7 inference on raw image bytes.

    Returns:
        {
          "detections": [...],
          "annotated_b64": "<png_base64>",
          "heatmap_b64":   "<png_base64>",
          "summary": {...},
          "has_fracture": bool,
          "model_available": bool,
        }
    """
    model_available = ONNX_MODEL_PATH.exists()

    if not model_available:
        logger.warning("ONNX model missing — returning mock detections for demo.")
        return _mock_result()

    try:
        session = _get_session()
        arr, orig_w, orig_h = _preprocess(img_bytes)

        t0 = time.perf_counter()
        input_name  = session.get_inputs()[0].name
        output_name = session.get_outputs()[0].name
        raw = session.run([output_name], {input_name: arr})[0][:, :6]
        elapsed = time.perf_counter() - t0
        logger.info(f"YOLOv7 inference done in {elapsed:.3f}s, raw detections={len(raw)}")

        detections = _postprocess(raw, orig_w, orig_h, threshold)

        annotated_bytes = _draw_annotated(img_bytes, detections)
        heatmap_bytes   = _draw_heatmap(img_bytes, detections)

        annotated_b64 = base64.b64encode(annotated_bytes).decode()
        heatmap_b64   = base64.b64encode(heatmap_bytes).decode()

        has_fracture = any(d["label"] == "fracture" for d in detections)
        summary = _build_summary(detections)

        return {
            "detections":      detections,
            "annotated_b64":   annotated_b64,
            "heatmap_b64":     heatmap_b64,
            "summary":         summary,
            "has_fracture":    has_fracture,
            "model_available": True,
            "inference_ms":    int(elapsed * 1000),
        }

    except Exception as exc:
        logger.error(f"Fracture detection failed: {exc}", exc_info=True)
        raise


def _build_summary(detections: List[Dict]) -> Dict[str, Any]:
    if not detections:
        return {
            "finding_count":  0,
            "top_finding":    "No significant findings",
            "max_confidence": 0.0,
            "finding_labels": [],
        }
    by_conf = sorted(detections, key=lambda d: d["confidence"], reverse=True)
    labels = list({d["label_display"] for d in detections})
    return {
        "finding_count":  len(detections),
        "top_finding":    by_conf[0]["label_display"],
        "max_confidence": by_conf[0]["confidence"],
        "finding_labels": labels,
    }


def _mock_result() -> Dict[str, Any]:
    """Fallback when model file is missing (demo / CI environments)."""
    return {
        "detections": [
            {
                "label": "fracture",
                "label_display": "Fracture",
                "confidence": 0.87,
                "bbox": [120, 80, 280, 220],
                "class_id": 3,
            }
        ],
        "annotated_b64":  "",
        "heatmap_b64":    "",
        "summary": {
            "finding_count":  1,
            "top_finding":    "Fracture",
            "max_confidence": 0.87,
            "finding_labels": ["Fracture"],
        },
        "has_fracture":    True,
        "model_available": False,
        "inference_ms":    0,
    }


# ─── Kimi K2.5 clinical report prompt ────────────────────────────────────────

KIMI_SYSTEM_PROMPT = """\
You are an elite radiologist AI powered by Sanjivini AI providing clinical decision support.
You have been given:
  A) The raw X-ray image to visually inspect.
  B) Structured YOLO object-detection findings (bounding boxes, labels, confidence scores).

⚠️ CRITICAL DIRECTIVE: The YOLO object detection model is a preliminary screen and may miss subtle fractures (false negatives) or hallucinate (false positives). You MUST perform your own independent visual analysis of the raw X-ray. 
- If YOLO missed a fracture that you clearly see, you MUST report it. 
- If YOLO hallucinated a fracture that does not exist, you MUST override it and clarify the absence of pathology.

Your task is to synthesise BOTH your independent visual inspection and the YOLO sources to produce a **comprehensive, accurate, doctor-ready clinical report**.

Format your response with these exact sections using markdown:

## 🩻 Clinical Findings
Describe each finding based on your OWN visual observation of the X-ray, comparing it against the provided YOLO detections. Note the location, severity, and appearance. If you detected a fracture YOLO missed, clearly state "Independent AI Analysis identified a fracture..."

## 🧬 Medical Context
Explain the clinical significance of the findings. Mention differential diagnoses where appropriate.

## 🔬 YOLO Detection Summary
List each detected finding as a table:
| Finding | Confidence | Location (bbox) | Clinical Significance |
|---------|------------|-----------------|-----------------------|

## 💊 Recommended Actions
Provide numbered priority-ordered clinical recommendations (immobilisation, specialist referral, further imaging, etc.).

## ⚠️ Severity Assessment
State: **Mild / Moderate / Severe** with a one-sentence justification based on findings and confidence.

## 📋 Report Conclusion
A concise 2–3 sentence summary suitable for the patient record."""


def _build_kimi_user_prompt(detections: List[Dict], has_fracture: bool) -> str:
    """Build the structured YOLO findings block for Kimi's user message."""
    if not detections:
        findings_block = "No pathological findings detected by YOLO object detection."
    else:
        rows = []
        for d in detections:
            b = d["bbox"]
            rows.append(
                f"  - {d['label_display']}: confidence={d['confidence']:.1%}, "
                f"bbox=[({b[0]},{b[1]}) → ({b[2]},{b[3]})]"
            )
        findings_block = "\n".join(rows)

    fracture_note = (
        "\n⚠️ IMPORTANT: At least one FRACTURE has been detected by YOLO. "
        "Pay special attention to fracture patterns, displacement, and urgent care requirements. Verify if this detection is accurate."
        if has_fracture else 
        "\n⚠️ IMPORTANT: YOLO detected NO fractures. However, you MUST independently scan the entire bone structure in the provided X-ray image to ensure no subtle fractures were missed."
    )

    return (
        f"YOLO Structural Detection Results:\n{findings_block}{fracture_note}\n\n"
        "Please analyse the X-ray image independently, cross-check against the YOLO findings, and generate "
        "the full structured clinical report identifying any missed pathology."
    )


# ─── Kimi K2.5 API call (primary) ────────────────────────────────────────────

async def _call_kimi(
    api_key: str,
    detections: List[Dict],
    image_b64: Optional[str],
    has_fracture: bool,
) -> str:
    """Call Kimi K2.5 with thinking mode + optional X-ray image."""
    user_text = _build_kimi_user_prompt(detections, has_fracture)

    # Build user message — multimodal if image is available
    if image_b64:
        user_content = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
            },
            {"type": "text", "text": user_text},
        ]
    else:
        user_content = user_text

    messages = [
        {"role": "system", "content": KIMI_SYSTEM_PROMPT},
        {"role": "user",   "content": user_content},
    ]

    # Instant mode: no extended reasoning → fast response (~5-10s vs 60s+)
    payload = {
        "model": "moonshotai/kimi-k2.5",
        "messages": messages,
        "max_tokens": 1500,
        "temperature": 0.6,   # recommended for instant mode
        "top_p": 0.95,
        "stream": False,
        "chat_template_kwargs": {"thinking": False},  # instant = no chain-of-thought
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    choice = data["choices"][0]["message"]
    report_text = choice.get("content", "").strip()
    return report_text


# ─── Qwen VL fallback ────────────────────────────────────────────────────────

FRACTURE_SYSTEM_PROMPT = KIMI_SYSTEM_PROMPT  # reuse same prompt for fallback models


async def _call_qwen_vl(
    api_key: str,
    detections: List[Dict],
    image_b64: Optional[str],
    has_fracture: bool,
) -> str:
    user_text = _build_kimi_user_prompt(detections, has_fracture)

    if image_b64:
        user_content = [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
            {"type": "text", "text": user_text},
        ]
    else:
        user_content = user_text

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "qwen/qwen2.5-vl-72b-instruct",
                "messages": [
                    {"role": "system", "content": FRACTURE_SYSTEM_PROMPT},
                    {"role": "user",   "content": user_content},
                ],
                "max_tokens": 2048,
                "temperature": 0.3,
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()


async def _call_qwen_text(api_key: str, detections: List[Dict], has_fracture: bool) -> str:
    user_text = _build_kimi_user_prompt(detections, has_fracture)

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "qwen/qwen2-7b-instruct",
                "messages": [
                    {"role": "system", "content": FRACTURE_SYSTEM_PROMPT},
                    {"role": "user",   "content": user_text},
                ],
                "max_tokens": 1024,
                "temperature": 0.3,
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()


# ─── Public entry point ───────────────────────────────────────────────────────

async def get_ai_explanation(
    detections: List[Dict],
    image_b64: Optional[str] = None,
) -> str:
    """
    Generate a clinical AI report using:
      1. Kimi K2.5  (thinking mode + vision)  — primary
      2. Qwen VL 72B (vision)                 — fallback
      3. Qwen 7B  (text-only)                 — fallback
      4. Rule-based template                  — offline fallback
    """
    from app.config import get_settings
    settings = get_settings()

    has_fracture = any(d.get("label") == "fracture" for d in detections)

    if not detections:
        return (
            "## 🩻 Clinical Findings\n\nNo significant pathology detected in this X-ray. "
            "The image appears within normal limits for the examined region.\n\n"
            "## ⚠️ Disclaimer\nThis is an AI-assisted analysis (YOLO v7 + Sanjivini AI). "
            "Final diagnosis must be made by a qualified physician."
        )

    # ── 1. Sanjivini AI (primary) ─────────────────────────────────────────────
    kimi_key = settings.nvidia_kimi_api_key or settings.nvidia_api_key
    if kimi_key:
        try:
            logger.info("Calling Sanjivini AI for clinical report generation…")
            report = await _call_kimi(kimi_key, detections, image_b64, has_fracture)
            if report:
                logger.info("✅ Sanjivini AI report generated successfully.")
                return report
        except Exception as exc:
            logger.warning(f"Sanjivini AI failed: {exc} — trying Qwen VL fallback.")

    # ── 2. Qwen VL 72B (fallback) ───────────────────────────────────────────
    qwen_key = settings.nvidia_qwen_api_key or settings.nvidia_api_key
    if qwen_key:
        try:
            logger.info("Calling Qwen VL 72B as fallback…")
            report = await _call_qwen_vl(qwen_key, detections, image_b64, has_fracture)
            if report:
                logger.info("✅ Qwen VL report generated.")
                return report
        except Exception as exc:
            logger.warning(f"Qwen VL failed: {exc} — trying Qwen 7B.")

        try:
            logger.info("Calling Qwen 7B text-only as final API fallback…")
            report = await _call_qwen_text(qwen_key, detections, has_fracture)
            if report:
                return report
        except Exception as exc:
            logger.error(f"Qwen 7B also failed: {exc}")

    # ── 3. Rule-based (offline) ─────────────────────────────────────────────
    logger.warning("All AI APIs failed — using rule-based explanation.")
    return _rule_based_explanation(detections)


# ─── Rule-based offline fallback ─────────────────────────────────────────────

def _rule_based_explanation(detections: List[Dict]) -> str:
    labels = [d["label_display"] for d in detections]
    confs  = [d["confidence"] for d in detections]
    has_fx = any(d["label"] == "fracture" for d in detections)
    max_conf = max(confs) if confs else 0.0
    severity = "Mild" if max_conf < 0.6 else "Moderate" if max_conf < 0.85 else "Severe"
    findings_str = ", ".join(set(labels))

    det_table = "\n".join(
        f"| {d['label_display']} | {d['confidence']:.0%} | "
        f"({d['bbox'][0]},{d['bbox'][1]})→({d['bbox'][2]},{d['bbox'][3]}) | — |"
        for d in detections
    )

    return "\n".join([
        f"## 🩻 Clinical Findings\n\nDetected: {findings_str}. "
        f"{len(detections)} finding(s) with max confidence {max_conf:.0%}.",
        "",
        "## 🧬 Medical Context\n\n"
        + (
            "Fractures detected may represent traumatic injury, stress fracture, or pathological "
            "fracture. Clinical correlation with patient history and physical exam is essential."
            if has_fx else
            "Identified findings may represent incidental or clinically significant pathology. "
            "Correlation with clinical presentation is recommended."
        ),
        "",
        "## 🔬 YOLO Detection Summary\n\n"
        "| Finding | Confidence | Location (bbox) | Clinical Significance |\n"
        "|---------|-----------|-----------------|----------------------|\n"
        + det_table,
        "",
        "## 💊 Recommended Actions\n\n"
        + (
            "1. Immobilise the affected region immediately\n"
            "2. Orthopedic / specialist consultation\n"
            "3. Further imaging (CT scan) if fracture pattern is complex\n"
            "4. Adequate pain management"
            if has_fx else
            "1. Correlate clinically with patient symptoms\n"
            "2. Consider follow-up imaging if indicated\n"
            "3. Specialist referral if pathology is suspected"
        ),
        "",
        f"## ⚠️ Severity Assessment\n\n**{severity}** — based on detection confidence of {max_conf:.0%}.",
        "",
        "## 📋 Report Conclusion\n\n"
        f"AI analysis identified {len(detections)} finding(s) including {findings_str}. "
        "Clinical review by the attending physician is strongly recommended. "
        "This summary was generated using rule-based logic as AI APIs were unavailable.",
        "",
        "## ⚠️ Disclaimer\nThis report is generated by an AI system (YOLO v7 + rule-based engine). "
        "It is **NOT a substitute** for evaluation by a qualified physician. "
        "Final diagnosis and treatment must be determined by a licensed medical professional.",
    ])
