import json
from typing import Any, Dict, List

import httpx

from app.config import get_settings
from app.schemas.schemas import GemmaMedicine, ExtractionResult


settings = get_settings()

LLM_EXTRACTION_PROMPT = """You are a medical prescription extraction assistant.
Extract medicines and related details from the following text.

Text:
{raw_text}

Return strict JSON only, no explanations. Use people-friendly frequency (e.g. "once daily", "twice daily") instead of OD, BD, TDS. Include "age_range" as exact numeric range only (e.g. "10-24 years", "10-47 years", "2-11 years", "18-65 years"). Always use format "X-Y years" with numbers and hyphen. Examples: 10-24 years, 10-47 years, 0-2 years.
[
  {{
    "medicine": "",
    "dose": "",
    "frequency": "",
    "duration": "",
    "instructions": "",
    "age_range": ""
  }}
]
"""

LLM_PATIENT_DOCTOR_PROMPT = """You are a medical prescription extraction assistant. Extract every visible detail accurately from the prescription.

Text:
{raw_text}

Return strict JSON only. Be accurate and detailed. Extract all text you see. Use empty string only if truly not present.

Patient fields:
- name: Full patient name as written
- age: Exact age or range (e.g. "34" or "10-24 years")
- gender: Male/Female/Other
- address: Full address, city, state, pin
- phone: Phone/mobile number
- disease_or_condition: Name of disease, condition, or diagnosis mentioned in the prescription
- medicines_summary: Comma-separated list of medicine names mentioned (as written on prescription)
- other: Any other patient info (weight, ID, date, etc.)

Doctor fields:
- name: Full name with title (Dr. etc.)
- qualification: Degrees (MBBS, MD, etc.)
- specialization: Specialty if mentioned
- clinic_hospital: Clinic or hospital name
- address: Full clinic/hospital address
- phone: Contact/mobile number
- other: Any other doctor or prescription notes

{{
  "patient": {{ "name": "", "age": "", "gender": "", "address": "", "phone": "", "disease_or_condition": "", "medicines_summary": "", "other": "" }},
  "doctor": {{ "name": "", "qualification": "", "specialization": "", "clinic_hospital": "", "address": "", "phone": "", "other": "" }}
}}
"""

LLM_MEDICINE_EXPLAIN_PROMPT = """You are a medical information assistant. Write a short explanation for the patient. MAXIMUM 500 CHARACTERS total.

Medicine name: {medicine_name}
Dose: {dose}
Frequency: {frequency}
Duration: {duration}
Instructions: {instructions}

Start your reply with the medicine name ("{medicine_name}: ..."). Then in 1-3 short sentences cover: what it is for, age range (use format like "10-24 years" or "10-47 years"), how to take it, and one key precaution. Use simple language. Do not exceed 500 characters."""

# Script instructions per language - explicit so the model uses native Unicode, not Latin
SCRIPT_INSTRUCTIONS = {
    "hindi": "Devanagari script (अ आ इ ई उ ऊ ए ऐ ओ औ क ख ग घ च छ ज झ ट ठ ड ढ त थ द ध न प फ ब भ म य र ल व श ष स ह). Do NOT use Latin/Roman letters.",
    "marathi": "Devanagari script (same as Hindi). Do NOT use Latin/Roman letters.",
    "kannada": "Kannada script (ಅ ಆ ಇ ಈ ಉ ಊ ಋ ಎ ಐ ಒ ಔ ಕ ಖ ಗ ಘ ಙ ಚ ಛ ಜ ಝ ಞ ಟ ಠ ಡ ಢ ಣ ತ ಥ ದ ಧ ನ ಪ ಫ ಬ ಭ ಮ ಯ ರ ಲ ವ ಶ ಷ ಸ ಹ). Do NOT use Latin/Roman letters.",
    "gujarati": "Gujarati script. Do NOT use Latin/Roman letters.",
    "punjabi": "Gurmukhi script (ਅ ਆ ਇ ਈ ਉ ਊ ਏ ਐ ਓ ਔ ਕ ਖ ਗ ਘ ਙ ਚ ਛ ਜ ਝ ਞ ਟ ਠ ਡ ਢ ਣ ਤ ਥ ਦ ਧ ਨ ਪ ਫ ਬ ਭ ਮ ਯ ਰ ਲ ਵ ਸ਼ ਸ ਹ). Do NOT use Latin/Roman letters.",
    "bengali": "Bengali script (অ আ ই ঈ উ ঊ ঋ এ ঐ ও ঔ ক খ গ ঘ ঙ চ ছ জ ঝ ঞ ট ঠ ড ঢ ণ ত থ দ ধ ন প ফ ব ভ ম য র ল শ ষ স হ). Do NOT use Latin/Roman letters.",
    "tamil": "Tamil script (அ ஆ இ ஈ உ ஊ எ ஏ ஐ ஒ ஓ ஔ க ங ச ஞ ட ண த ந ப ம ய ர ல வ ழ ள ற ன). Do NOT use Latin/Roman letters.",
    "telugu": "Telugu script (అ ఆ ఇ ఈ ఉ ఊ ఋ ఎ ఏ ఐ ఒ ఓ ఔ క ఖ గ ఘ ఙ చ ఛ జ ఝ ఞ ట ఠ డ ఢ ణ త థ ద ధ న ప ఫ బ భ మ య ర ల వ శ ష స హ). Do NOT use Latin/Roman letters.",
    "malayalam": "Malayalam script. Do NOT use Latin/Roman letters.",
    "odia": "Odia script. Do NOT use Latin/Roman letters.",
    "sanskrit": "Devanagari script (same as Hindi). Do NOT use Latin/Roman letters.",
    "english": "Keep in English (Latin script).",
}

LLM_TRANSLITERATE_PROMPT = """You are a medical transliteration expert. Your task is to TRANSLATE and WRITE the following prescription in {target_language}.

CRITICAL: You MUST write the output in the native script of {target_language}.
{script_instruction}

Do NOT output in Latin/Roman letters. Do NOT use mixed-case tricks. Output must be in the actual Unicode script shown above.

Return strict JSON only:
{{
  "patient": "patient section in {target_language} native script",
  "doctor": "doctor section in {target_language} native script",
  "medicines": "medicines section in {target_language} native script"
}}

Input (English):
---
{text}
---

Output ONLY valid JSON. No explanations. Use the native script characters."""

LLM_TRANSLITERATE_SIMPLE_PROMPT = """Translate this text into {target_language}. Write ONLY in the native script of {target_language}.
{script_instruction}
Do NOT use Latin/Roman letters. Output ONLY the translated text.

Text:
---
{text}
---"""


async def _call_ollama(prompt: str, model: str = "llama3.2:3b") -> str:
    """Call Ollama API and return the raw response text."""
    payload = {"model": model, "prompt": prompt, "stream": False}
    async with httpx.AsyncClient(base_url="http://localhost:11434", timeout=120) as client:
        response = await client.post("/api/generate", json=payload)
        response.raise_for_status()
        data = response.json()
        return (data.get("response") or "").strip()


async def call_gemma(raw_text: str) -> ExtractionResult:
    """
    Call a local Ollama model (llama3.2:3b) to extract medicines in strict JSON.
    """
    prompt = LLM_EXTRACTION_PROMPT.format(raw_text=raw_text)
    content = await _call_ollama(prompt)

    try:
        parsed = json.loads(content)
        medicines: List[GemmaMedicine] = [GemmaMedicine(**item) for item in parsed]
        json_success = 1.0
    except Exception:
        medicines = []
        json_success = 0.0

    return ExtractionResult(medicines=medicines, json_parse_success=json_success)


async def call_gemma_extract_patient_doctor(raw_text: str) -> Dict[str, Any]:
    """
    Extract patient and doctor details from prescription text using Ollama.
    Returns a dict with "patient" and "doctor" keys.
    """
    prompt = LLM_PATIENT_DOCTOR_PROMPT.format(raw_text=raw_text)
    content = await _call_ollama(prompt)

    try:
        # Try to parse JSON - model might wrap in markdown code block
        text = content.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        parsed = json.loads(text)
        patient = parsed.get("patient") or {}
        doctor = parsed.get("doctor") or {}
        return {"patient": patient, "doctor": doctor}
    except Exception:
        return {"patient": {}, "doctor": {}}


async def call_gemma_explain_medicine(
    medicine_name: str,
    dose: str = "",
    frequency: str = "",
    duration: str = "",
    instructions: str = "",
) -> str:
    """
    Generate a patient-friendly explanation of a medicine using Ollama.
    """
    prompt = LLM_MEDICINE_EXPLAIN_PROMPT.format(
        medicine_name=medicine_name,
        dose=dose or "—",
        frequency=frequency or "—",
        duration=duration or "—",
        instructions=instructions or "—",
    )
    return await _call_ollama(prompt)


def _get_script_instruction(lang_key: str) -> str:
    return SCRIPT_INSTRUCTIONS.get(lang_key.lower(), f"Use the native script of {lang_key}. Do NOT use Latin/Roman letters.")


async def call_ollama_transliterate(text: str, target_language: str, lang_key: str = "") -> str:
    """Transliterate text into target language script (simple, returns plain text)."""
    script = _get_script_instruction(lang_key or target_language)
    prompt = LLM_TRANSLITERATE_SIMPLE_PROMPT.format(text=text, target_language=target_language, script_instruction=script)
    return await _call_ollama(prompt)


async def call_ollama_transliterate_structured(text: str, target_language: str, lang_key: str = "") -> Dict[str, str]:
    """
    Transliterate full prescription (patient, doctor, medicines) into target language.
    Returns dict with keys: patient, doctor, medicines, full.
    """
    script = _get_script_instruction(lang_key or target_language)
    prompt = LLM_TRANSLITERATE_PROMPT.format(
        text=text,
        target_language=target_language,
        script_instruction=script,
    )
    content = await _call_ollama(prompt)
    try:
        text_clean = content.strip()
        if "```json" in text_clean:
            text_clean = text_clean.split("```json")[1].split("```")[0].strip()
        elif "```" in text_clean:
            text_clean = text_clean.split("```")[1].split("```")[0].strip()
        parsed = json.loads(text_clean)
        patient = (parsed.get("patient") or "").strip()
        doctor = (parsed.get("doctor") or "").strip()
        medicines = (parsed.get("medicines") or "").strip()
        full = f"PATIENT:\n{patient}\n\nDOCTOR:\n{doctor}\n\nMEDICINES:\n{medicines}"
        return {"patient": patient, "doctor": doctor, "medicines": medicines, "full": full}
    except Exception:
        simple = await call_ollama_transliterate(text, target_language, lang_key)
        return {"patient": "", "doctor": "", "medicines": simple, "full": simple}

