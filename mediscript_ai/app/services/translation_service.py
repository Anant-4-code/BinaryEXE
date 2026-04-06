"""
Translation service using deep-translator for proper Indic script output.
Returns native script (Devanagari, Telugu, Tamil, etc.) for all supported languages.
"""
from typing import Dict, Optional

from deep_translator import GoogleTranslator

# Map our language keys to Google Translate target codes
LANG_TO_GOOGLE: Dict[str, str] = {
    "english": "en",
    "hindi": "hi",
    "marathi": "mr",
    "kannada": "kn",
    "gujarati": "gu",
    "punjabi": "pa",
    "bengali": "bn",
    "tamil": "ta",
    "telugu": "te",
    "malayalam": "ml",
    "odia": "or",
    "sanskrit": "sa",
}

# Max chars per request (Google Translate limit ~5000)
CHUNK_SIZE = 4500


def _translate_chunked(text: str, target_code: str) -> str:
    """Translate text, splitting into chunks if needed."""
    if not text or not text.strip():
        return ""
    if target_code == "en":
        return text
    text = text.strip()
    if len(text) <= CHUNK_SIZE:
        try:
            return GoogleTranslator(source="en", target=target_code).translate(text) or text
        except Exception:
            return text
    parts = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        if end < len(text):
            # Try to break at sentence or newline
            last_break = max(text.rfind("\n", start, end), text.rfind(". ", start, end))
            if last_break > start:
                end = last_break + 1
        chunk = text[start:end]
        try:
            translated = GoogleTranslator(source="en", target=target_code).translate(chunk) or chunk
            parts.append(translated)
        except Exception:
            parts.append(chunk)
        start = end
    return "\n".join(parts)


def translate_prescription(
    patient_text: str,
    doctor_text: str,
    medicines_text: str,
    lang_key: str,
) -> Dict[str, str]:
    """
    Translate prescription sections to target language. Returns proper native script.
    """
    lang_key = (lang_key or "").lower().strip()
    target_code = LANG_TO_GOOGLE.get(lang_key, "hi")
    if target_code == "en":
        return {
            "patient": patient_text or "",
            "doctor": doctor_text or "",
            "medicines": medicines_text or "",
            "full": f"PATIENT:\n{patient_text or ''}\n\nDOCTOR:\n{doctor_text or ''}\n\nMEDICINES:\n{medicines_text or ''}",
        }
    patient = _translate_chunked(patient_text or "", target_code)
    doctor = _translate_chunked(doctor_text or "", target_code)
    medicines = _translate_chunked(medicines_text or "", target_code)
    full = f"PATIENT:\n{patient}\n\nDOCTOR:\n{doctor}\n\nMEDICINES:\n{medicines}"
    return {"patient": patient, "doctor": doctor, "medicines": medicines, "full": full}
