"""
Data Correction Service - Validates and corrects extracted medicine data using Ollama.
Fixes OCR/LLM errors like:
- Incorrect medicine names
- Missing durations
- Wrong frequencies
- Incomplete dose information
"""

import json
import logging
from typing import Any, Dict, List

import httpx

from app.config import get_settings
from app.schemas.schemas import GemmaMedicine

logger = logging.getLogger(__name__)
settings = get_settings()

# ============================================================================
# CORRECTION PROMPTS - Use Ollama to verify and fix extracted data
# ============================================================================

VERIFY_MEDICINE_PROMPT = """You are a medical data correction expert. Review this medicine data extracted from a prescription.
Correct any errors in medicine names, doses, frequencies, and durations.

Extracted data:
{extracted_json}

Common corrections:
- Fix misspelled medicine names (e.g., Hijenae → Hijama or similar)
- Complete missing durations (if "— days" or blank, infer from context or default to 7 days)
- Validate frequencies (OD=once daily, BD=twice daily, TDS=thrice daily, QID=4 times daily)
- Validate doses (must have quantity and unit like mg, ml, tabs, etc.)
- Remove invalid age ranges (should be adult, pediatric, etc., not numbers like "10-24 years")

Return ONLY corrected JSON, no explanations:
[
  {{
    "medicine": "Correct Medicine Name",
    "dose": "correct dose with unit",
    "frequency": "frequency",
    "duration": "7 days",
    "instructions": "instructions or empty",
    "age_range": "adult/pediatric/other"
  }}
]"""

IDENTIFY_MISSPELLED_MEDICINE = """Review this medicine name from a prescription: "{medicine_name}"

Is this name:
1. Correct as-is?
2. Misspelled? If so, what's the correct name?

Return ONLY JSON:
{{
  "original": "{medicine_name}",
  "is_valid": true/false,
  "corrected_name": "corrected name or same as original if valid",
  "confidence": 0.0-1.0
}}"""

INFER_DURATION_PROMPT = """A medicine prescription has incomplete duration: "{medicine_name}" - "{dose}" - "{frequency}"

What's a reasonable duration for this medicine? (typically 5-14 days for common medicines)

Return ONLY JSON:
{{
  "medicine": "{medicine_name}",
  "inferred_duration": "7 days",
  "reasoning": "short explanation"
}}"""


# ============================================================================
# OLLAMA CALLS FOR CORRECTION
# ============================================================================

async def _call_ollama_correction(prompt: str, temperature: float = 0.1) -> str:
    """Call Ollama for data correction with very low temperature for accuracy."""
    payload = {
        "model": "llama3.2:3b",
        "prompt": prompt,
        "stream": False,
        "temperature": temperature,  # Very low for precise correction
        "num_predict": 500,
    }
    
    try:
        async with httpx.AsyncClient(
            base_url="http://localhost:11434",
            timeout=60.0
        ) as client:
            response = await client.post("/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return (data.get("response") or "").strip()
    except Exception as e:
        logger.error(f"Correction request failed: {e}")
        raise


# ============================================================================
# INDIVIDUAL CORRECTION FUNCTIONS
# ============================================================================

async def correct_medicine_name(medicine_name: str) -> str:
    """Verify and correct a single medicine name."""
    if not medicine_name or not medicine_name.strip():
        return medicine_name
    
    prompt = IDENTIFY_MISSPELLED_MEDICINE.format(medicine_name=medicine_name)
    
    try:
        response = await _call_ollama_correction(prompt, temperature=0.1)
        
        # Parse JSON
        json_match = response
        if "```json" in response:
            json_match = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            json_match = response.split("```")[1].split("```")[0].strip()
        
        data = json.loads(json_match)
        corrected = data.get("corrected_name", medicine_name)
        confidence = data.get("confidence", 0.0)
        
        # Only use correction if confident
        if confidence > 0.7 and corrected != medicine_name:
            logger.info(f"Corrected medicine: {medicine_name} → {corrected} (confidence: {confidence})")
            return corrected
        
        return medicine_name
    
    except Exception as e:
        logger.warning(f"Could not correct medicine name: {e}")
        return medicine_name


async def infer_missing_duration(medicine_name: str, dose: str, frequency: str) -> str:
    """Infer duration if it's missing or invalid."""
    # Check if duration is missing or placeholder
    if not medicine_name or not dose or not frequency:
        return "7 days"  # Default
    
    prompt = INFER_DURATION_PROMPT.format(
        medicine_name=medicine_name,
        dose=dose,
        frequency=frequency
    )
    
    try:
        response = await _call_ollama_correction(prompt, temperature=0.1)
        
        # Parse JSON
        json_match = response
        if "```json" in response:
            json_match = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            json_match = response.split("```")[1].split("```")[0].strip()
        
        data = json.loads(json_match)
        inferred = data.get("inferred_duration", "7 days")
        
        logger.info(f"Inferred duration: {medicine_name} → {inferred}")
        return inferred
    
    except Exception as e:
        logger.warning(f"Could not infer duration: {e}")
        return "7 days"  # Default


async def validate_and_correct_dose(dose: str) -> str:
    """Ensure dose has both quantity and unit."""
    if not dose or not dose.strip():
        return ""
    
    dose = dose.strip()
    
    # Already looks valid (has number + unit)
    if any(char.isdigit() for char in dose):
        return dose
    
    # If no numbers, it's incomplete
    return ""


async def normalize_frequency(frequency: str) -> str:
    """Normalize frequency to standard terms."""
    if not frequency:
        return "once daily"
    
    freq_lower = frequency.lower().strip()
    
    # Common mappings
    mappings = {
        "od": "once daily",
        "once daily": "once daily",
        "bd": "twice daily",
        "twice daily": "twice daily",
        "tds": "thrice daily",
        "thrice daily": "thrice daily",
        "3 times daily": "thrice daily",
        "qid": "4 times daily",
        "4 times daily": "4 times daily",
    }
    
    for key, value in mappings.items():
        if key in freq_lower:
            return value
    
    return frequency  # Return as-is if no mapping found


async def normalize_age_range(age_range: str) -> str:
    """Normalize age range to standard categories or keep as numeric."""
    if not age_range or not age_range.strip():
        return ""
    
    age_lower = age_range.lower().strip()
    
    # If it's a numeric range (e.g. 10-24 years), keep it
    if any(char.isdigit() for char in age_lower) and "year" in age_lower:
        return age_range.strip()
    
    # Standard categories
    if "pediatric" in age_lower or "child" in age_lower or "baby" in age_lower:
        return "Pediatric"
    elif "adult" in age_lower or "senior" in age_lower:
        return "Adult"
    elif "elder" in age_lower or "geriatric" in age_lower:
        return "Geriatric"
    
    return age_range.strip()


async def correct_medicines_batch(medicines: List[GemmaMedicine]) -> List[GemmaMedicine]:
    """
    Correct a batch of medicines. Now more CONSERVATIVE.
    Only fixes obvious errors, preserves specialized numeric formats like age ranges.
    """
    if not medicines:
        return []
    
    logger.info(f"Correcting {len(medicines)} medicines (Conservative Mode)")
    
    corrected_medicines = []
    
    for med in medicines:
        try:
            # Normalize but don't over-correct with multiple LLM calls per field
            # This reduces latency and hallucination risk
            
            # 1. Simple normalization for frequency
            corrected_frequency = await normalize_frequency(med.frequency)
            
            # 2. Simple normalization for age range (preserves numbers)
            corrected_age_range = await normalize_age_range(med.age_range)
            
            # Only use LLM for the name if it's very messy/unlikely
            # For now, we trust the primary extraction more than separate tiny calls
            
            corrected_med = GemmaMedicine(
                medicine=(med.medicine or "").strip().title(),
                dose=(med.dose or "").strip(),
                frequency=corrected_frequency,
                duration=(med.duration or "").strip(),
                instructions=(med.instructions or "").strip(),
                age_range=corrected_age_range,
            )
            
            corrected_medicines.append(corrected_med)
            
        except Exception as e:
            logger.error(f"Error correcting {med.medicine}: {e}")
            corrected_medicines.append(med)
            
    return corrected_medicines


async def correct_medicines_with_ollama(medicines_json: str) -> List[Dict[str, Any]]:
    """
    Comprehensive correction using Ollama to verify entire batch.
    Sends all medicines to Ollama for complete verification.
    """
    if not medicines_json or not medicines_json.strip():
        return []
    
    prompt = VERIFY_MEDICINE_PROMPT.format(extracted_json=medicines_json)
    
    try:
        response = await _call_ollama_correction(prompt, temperature=0.1)
        
        # Parse JSON response
        json_match = response
        if "```json" in response:
            json_match = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            json_match = response.split("```")[1].split("```")[0].strip()
        
        corrected_list = json.loads(json_match)
        
        if not isinstance(corrected_list, list):
            corrected_list = [corrected_list]
        
        logger.info(f"Ollama correction complete: {len(corrected_list)} medicines verified")
        return corrected_list
    
    except json.JSONDecodeError as e:
        logger.error(f"Could not parse Ollama correction response: {e}")
        return []
    except Exception as e:
        logger.error(f"Ollama correction failed: {e}")
        return []
