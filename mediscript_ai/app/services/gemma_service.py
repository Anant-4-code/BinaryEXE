import json
from typing import Any, Dict, List

import httpx

from app.config import get_settings
from app.schemas.schemas import GemmaMedicine, ExtractionResult
from app.services.deid_service import DeidService


settings = get_settings()


LLM_EXTRACTION_PROMPT = """You are a medical prescription extraction assistant. Your task is to accurately extract medicine data from the provided OCR text.

CRITICAL: 
- Be FAITHFUL to the source text. 
- Do NOT invent medicines that are not mentioned. 
- If a value is unclear, use an empty string or "Unknown".
- Output ONLY strict JSON. No conversational text.

Frequency Format: Use people-friendly terms (e.g., "once daily", "twice daily", "thrice daily", "four times daily", "as needed").
Age Range Format: Use exact numeric range from the text if possible (e.g., "10-24 years", "10-47 years", "18-65 years"). If not found, use "Adult" or empty string.

Text to Extract:
---
{raw_text}
---

Output Format:
[
  {{
    "medicine": "Medicine Name",
    "dose": "Dose (e.g. 500mg)",
    "frequency": "Frequency",
    "duration": "Duration (e.g. 5 days)",
    "instructions": "Special instructions (e.g. post meals)",
    "age_range": "10-24 years"
  }}
]
"""

LLM_PATIENT_DOCTOR_PROMPT = """You are a specialist clinical data extraction AI. Your task is to carefully read a medical prescription OCR text and extract patient and doctor identity fields.

== PRESCRIPTION LAYOUT AWARENESS ==
Medical prescriptions typically have:
- TOP SECTION (letterhead): Doctor's name, qualifications, clinic/hospital name, address, phone. Sometimes a registration/license number.
- MIDDLE SECTION: Patient name (often prefixed with "Name:", "Patient:", "Pt:"), Age (often "Age:", "A/E:"), Gender ("Sex:", "M/F"), Chief complaint ("C/O:", "Complaints:", "D/X:", "Dx:", "Diagnosis:")
- BOTTOM SECTION: Doctor signature, registration number, date, stamp.

== MEDICAL ABBREVIATION GUIDE ==
- "C/O" or "c/o" = Complaints or Chief Complaint → maps to disease_or_condition
- "D/X", "Dx", "Diag." = Diagnosis → maps to disease_or_condition
- "P/H" = Past History
- "H/O" = History of
- "Rx" = Prescription (ignore — it marks the start of the medicine list)
- "M/F", "Sex: M", "Gender: F" = Male or Female → maps to gender
- "A/E", "Age/E" = Age → maps to age
- "Dr.", "DR." = Doctor prefix → strip and include as part of the name
- "MBBS", "MD", "MS", "DNB", "FCPS", "DM", "MCh", "BDS", "MDS" = Medical qualifications → maps to qualification

== EXTRACTION RULES ==
1. PATIENT NAME: Look for "Name:", "Patient:", "Pt:", "Mr.", "Mrs.", "Ms." followed by text. Extract the full name.
2. AGE: Extract exactly — could be "25 yrs", "25Y", "10-24 years", "Infant", "5 months". Preserve units.
3. GENDER: Normalize to "Male", "Female", or "Other".
4. DISEASE/CONDITION: Look for D/X, Dx, C/O, Diagnosis, Chief Complaint. If multiple, join with comma.
5. DOCTOR NAME: Usually at the top line of the letterhead. Include "Dr." prefix.
6. QUALIFICATION: Extract all degree abbreviations after the doctor's name.
7. SPECIALIZATION: Look for specialty words like "Dermatologist", "Pediatrician", "MBBS", "General Physician", "Cardiologist", etc. If derived from qualification only, infer it.
8. CLINIC/HOSPITAL: The facility name, often on the second line of the letterhead or stamped at bottom.
9. PHONE: Any 10-digit number near doctor section or patient section.
10. ADDRESS: Multi-line text near clinic name or near patient name.

== OUTPUT RULES ==
- If a field is not found, output ""  (empty string). Do NOT guess or hallucinate values.
- Do NOT output "Unknown", "N/A", "Not mentioned", or similar placeholders — use "" instead.
- Output ONLY a valid JSON object. No explanations, no markdown, no conversational text.

Text to analyze:
---
{raw_text}
---

Required JSON Output (match these exact keys):
{{
  "patient": {{
    "name": "",
    "age": "",
    "gender": "",
    "address": "",
    "phone": "",
    "disease_or_condition": "",
    "medicines_summary": "",
    "other": ""
  }},
  "doctor": {{
    "name": "",
    "qualification": "",
    "specialization": "",
    "clinic_hospital": "",
    "address": "",
    "phone": "",
    "other": ""
  }}
}}"""


def _clean_llm_json_response(content: str) -> str:
    """
    Robustly extract a JSON object from an LLM response that may contain:
    - Markdown code fences (```json ... ```)
    - Conversational preamble ('Here is the extracted data: {...}')
    - Trailing explanations after the JSON
    """
    text = content.strip()
    # 1. Strip markdown fences
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0].strip()

    # 2. Find the outermost JSON object
    start = text.find("{")
    if start == -1:
        return text
    # Walk backwards from the last } to find a complete JSON object
    end = text.rfind("}")
    if end == -1:
        return text
    return text[start:end + 1].strip()


def _normalize_extracted_identities(data: dict) -> dict:
    """
    Post-process extracted identities to:
    - Replace placeholder strings with empty strings
    - Normalize gender to Male/Female/Other
    - Strip leading/trailing whitespace from all values
    """
    PLACEHOLDER_VALUES = {
        "unknown", "n/a", "not mentioned", "not available", "not found",
        "not provided", "none", "null", "na", "-", "—", "N/A", "Unknown",
        "Not mentioned", "Not available"
    }

    def clean_value(v):
        if not isinstance(v, str):
            return str(v).strip() if v is not None else ""
        v = v.strip()
        if v.lower() in {p.lower() for p in PLACEHOLDER_VALUES}:
            return ""
        return v

    def normalize_gender(g: str) -> str:
        g_lower = g.lower().strip()
        if g_lower in {"m", "male", "man", "boy"}:
            return "Male"
        if g_lower in {"f", "female", "woman", "girl"}:
            return "Female"
        if g_lower:
            return g.strip()
        return ""

    patient = data.get("patient") or {}
    doctor = data.get("doctor") or {}

    cleaned_patient = {k: clean_value(v) for k, v in patient.items()}
    cleaned_doctor = {k: clean_value(v) for k, v in doctor.items()}

    if "gender" in cleaned_patient:
        cleaned_patient["gender"] = normalize_gender(cleaned_patient["gender"])

    return {"patient": cleaned_patient, "doctor": cleaned_doctor}

LLM_MEDICINE_EXPLAIN_PROMPT = """You are a clinical pharmacology assistant. Explain this medication to the patient in simple terms.

Medicine: {medicine_name}
Parameters: Dose {dose}, Frequency {frequency}, Duration {duration}, Instructions {instructions}

Structure your response:
1. Purpose: What is this medicine for?
2. Patient Profile: Mention the suitable age range (e.g., "Suitable for 10-24 years" or as per clinical guidelines).
3. Schedule: How and when to take it.
4. Caution: One critical safety warning.

MAXIMUM 500 CHARACTERS. Be professional yet accessible."""

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
    Uses a high-fidelity clinical extraction prompt with abbreviation awareness.
    """
    import logging as _log
    _logger = _log.getLogger(__name__)

    prompt = LLM_PATIENT_DOCTOR_PROMPT.format(raw_text=raw_text)
    try:
        content = await _call_ollama(prompt)
    except Exception as e:
        _logger.error(f"Ollama call failed for patient/doctor extraction: {e}")
        return {"patient": {}, "doctor": {}}

    try:
        # Use the robust JSON cleaner
        cleaned = _clean_llm_json_response(content)
        parsed = json.loads(cleaned)

        # Normalize values — strip placeholders, fix gender, etc.
        normalized = _normalize_extracted_identities(parsed)
        patient = normalized.get("patient") or {}
        doctor = normalized.get("doctor") or {}

        _logger.info(
            f"Clinical identities extracted — Patient: '{patient.get('name', '')}', "
            f"Doctor: '{doctor.get('name', '')}', "
            f"Condition: '{patient.get('disease_or_condition', '')}'"
        )
        return {"patient": patient, "doctor": doctor}

    except json.JSONDecodeError as e:
        _logger.error(f"JSON parse failed for patient/doctor. Raw snippet: '{content[:300]}' | Error: {e}")
        return {"patient": {}, "doctor": {}}
    except Exception as e:
        _logger.error(f"Unexpected error during identity extraction: {e}")
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


LLM_CLINICAL_TTS_PROMPT = """You are a clinical AI assistant named Sanjivini AI. Your job is to create a comprehensive, conversational audio script to be read aloud to the patient or doctor.

Context Data:
{context_data}

Instructions for the script:
1. Start with a warm, professional greeting (e.g., "Hello, this is Sanjivini AI with a detailed overview for patient [Name].")
2. Mention the diagnosis or chief complaint clearly comprehensively.
3. List ALL the prescribed medicines conversationally. For EVERY medicine, mention its name, dose, how to take it, and clearly articulate its explanation (its purpose and any side effects or precautions) as provided in the context data.
4. Add a brief piece of advice or encouragement based on the overall condition.
5. Do not limit the length. Speak normally, avoiding asterisks, bold text, or lists since this will be read by a TTS system.

Script:"""

async def call_gemma_clinical_tts_script(context_data: str, target_lang: str = "en") -> str:
    """Generate a conversational TTS script from patient and medicine data using Ollama."""
    lang_name_map = {
        'hi': 'Hindi', 'mr': 'Marathi', 'kn': 'Kannada', 'gu': 'Gujarati',
        'pa': 'Punjabi', 'bn': 'Bengali', 'ta': 'Tamil', 'te': 'Telugu',
        'ml': 'Malayalam', 'or': 'Odia', 'sa': 'Sanskrit', 'en': 'English'
    }
    target_name = lang_name_map.get(target_lang.lower(), target_lang.title())
    
    lang_instruction = ""
    if target_lang and target_lang.lower() != "en":
        # Inject instruction at the top of the prompt for maximum attention
        lang_instruction = f"SYSTEM: THE ENTIRE RESPONSE MUST BE WRITTEN IN THE {target_name.upper()} LANGUAGE SCRIPT. DO NOT USE ANY ENGLISH CHARACTERS OR WORDS.\n\n"
    
    prompt = lang_instruction + LLM_CLINICAL_TTS_PROMPT.format(context_data=context_data)
    
    # Also append a final reminder in case the model forgets
    if target_lang.lower() != "en":
        prompt += f"\n\nREMINDER: Write everything above in {target_name} script strictly."
    
    response = await _call_ollama(prompt)
    
    # Clean up any markdown characters the LLM might have used by mistake
    cleaned = response.replace("*", "").replace("#", "").replace("_", "")
    return cleaned.strip()

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

