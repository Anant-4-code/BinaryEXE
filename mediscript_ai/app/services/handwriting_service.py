from pathlib import Path
import io
import json
import http.client

from PIL import Image

# Enable AVIF support (pillow-avif-plugin)
try:
    import pillow_avif  # noqa: F401
except ImportError:
    pass

from app.config import get_settings
from app.schemas.schemas import OCRResult


settings = get_settings()


def _call_handwriting_api(image_bytes: bytes) -> str:
    """
    Low-level call to Pen-to-Print RapidAPI, same pattern as app3.py.
    """
    conn = http.client.HTTPSConnection("pen-to-print-handwriting-ocr.p.rapidapi.com")

    boundary = "----011000010111000001101001"
    payload = (
        f"--{boundary}\r\n"
        "Content-Disposition: form-data; name=\"srcImg\"; filename=\"image.jpg\"\r\n"
        "Content-Type: image/jpeg\r\n\r\n"
    ).encode("utf-8") + image_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    headers = {
        "x-rapidapi-key": settings.handwriting_rapidapi_key or "",
        "x-rapidapi-host": "pen-to-print-handwriting-ocr.p.rapidapi.com",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }

    conn.request("POST", "/recognize/", payload, headers)
    res = conn.getresponse()
    data = res.read()
    return data.decode("utf-8")


def _image_to_jpeg_bytes(image_path: Path) -> bytes:
    """Open image (including AVIF/WebP) and convert to JPEG bytes for API."""
    image = Image.open(image_path)
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")
    elif image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def run_handwriting_model(image_path: Path) -> OCRResult:
    """
    Image -> raw text using Pen-to-Print RapidAPI.
    Falls back to local pytesseract, then to dummy text.
    Converts AVIF/WebP etc. to JPEG for API compatibility.
    """
    try:
        image_bytes = _image_to_jpeg_bytes(image_path)
    except Exception as e:
        if "cannot identify" in str(e).lower():
            raise ValueError(
                "Image format not supported. Please upload a JPG or PNG image."
            ) from e
        raise

    raw_text = ""
    reliability = 0.5

    ocr_engine = (settings.ocr_engine or "auto").strip().lower()

    if ocr_engine in {"auto", "rapidapi"} and settings.handwriting_rapidapi_key:
        try:
            result = _call_handwriting_api(image_bytes)
            data = json.loads(result)
            raw_text = (data.get("value") or "").strip()
            if raw_text:
                reliability = 0.9
        except Exception:
            raw_text = ""

    if not raw_text and ocr_engine in {"auto", "tesseract"}:
        try:
            import pytesseract

            if settings.tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

            img = Image.open(image_path)
            raw_text = (pytesseract.image_to_string(img) or "").strip()
            if raw_text:
                reliability = 0.8
        except Exception:
            raw_text = ""

    if not raw_text and ocr_engine in {"auto", "dummy"}:
        raw_text = "Tab Amox 500mg three times daily x 5 days\nSyp PCM 10ml twice daily"
        reliability = 0.1

    if not raw_text:
        raise RuntimeError(
            "OCR is not working. Configure either RapidAPI (HANDWRITING_RAPIDAPI_KEY) "
            "or local Tesseract (install Tesseract + pip install pytesseract, and optionally set TESSERACT_CMD)."
        )

    return OCRResult(raw_text=raw_text, ocr_reliability=reliability)

