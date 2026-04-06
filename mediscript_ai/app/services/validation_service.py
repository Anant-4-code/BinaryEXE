from dataclasses import dataclass
from typing import Dict, List, Tuple

from rapidfuzz import process, fuzz

from app.schemas.schemas import GemmaMedicine


DRUG_DICTIONARY = {
    "paracetamol": ["pcm", "parac", "crocin"],
    "amoxicillin": ["amox", "amoxil"],
}

FREQUENCY_MAP: Dict[str, int] = {
    "od": 1,
    "bd": 2,
    "tds": 3,
    "qid": 4,
    "once daily": 1,
    "twice daily": 2,
    "three times daily": 3,
    "four times daily": 4,
    "q4h": 6,
    "q6h": 4,
    "hs": 1,
}

# People-friendly display names for frequency (no medical abbreviations)
FREQUENCY_DISPLAY: Dict[str, str] = {
    "od": "Once daily",
    "bd": "Twice daily",
    "bid": "Twice daily",
    "tds": "Three times daily",
    "tid": "Three times daily",
    "qid": "Four times daily",
    "q4h": "Every 4 hours",
    "q6h": "Every 6 hours",
    "hs": "At bedtime",
    "prn": "As needed",
    "sos": "If necessary",
    "once daily": "Once daily",
    "twice daily": "Twice daily",
    "three times daily": "Three times daily",
    "four times daily": "Four times daily",
}


@dataclass
class ValidatedMedicine:
    original_name: str
    normalized_name: str
    dose: str
    frequency: str
    frequency_per_day: int
    duration_days: int
    instructions: str
    confidence: float
    drug_match_success: float
    age_range: str = ""


def normalize_drug_name(name: str) -> Tuple[str, float]:
    name_lower = name.lower().strip()

    for canonical, aliases in DRUG_DICTIONARY.items():
        if name_lower == canonical:
            return canonical.title(), 1.0
        if name_lower in aliases:
            return canonical.title(), 0.9

    all_names = list(DRUG_DICTIONARY.keys()) + [a for aliases in DRUG_DICTIONARY.values() for a in aliases]
    best, score, _ = process.extractOne(name_lower, all_names, scorer=fuzz.WRatio)
    if score >= 80:
        for canonical, aliases in DRUG_DICTIONARY.items():
            if best == canonical or best in aliases:
                return canonical.title(), score / 100.0

    return name, 0.5


def parse_duration(duration: str) -> int:
    if not duration:
        return 0
    tokens = duration.lower().split()
    for token in tokens:
        if token.isdigit():
            return int(token)
    return 0


def map_frequency(freq: str) -> Tuple[str, int]:
    """Map frequency abbreviation to people-friendly string and times per day."""
    if not freq:
        return "", 0
    key = freq.lower().strip()
    per_day = FREQUENCY_MAP.get(key, 0)
    display = FREQUENCY_DISPLAY.get(key)
    if display:
        return display, per_day
    # Unknown abbreviation: return as-is but try to make it readable
    return freq.strip(), per_day


def validate_medicines(gemma_medicines: List[GemmaMedicine], ocr_reliability: float, json_parse_success: float) -> Tuple[List[ValidatedMedicine], float]:
    validated: List[ValidatedMedicine] = []
    total_drug_match = 0.0

    for item in gemma_medicines:
        normalized_name, drug_score = normalize_drug_name(item.medicine)
        freq_str, per_day = map_frequency(item.frequency)
        duration_days = parse_duration(item.duration)

        medicine_confidence = (
            ocr_reliability * 0.4 +
            json_parse_success * 0.3 +
            drug_score * 0.3
        ) * 100.0

        age_range = getattr(item, "age_range", None) or ""
        validated.append(
            ValidatedMedicine(
                original_name=item.medicine,
                normalized_name=normalized_name,
                dose=item.dose,
                frequency=freq_str,
                frequency_per_day=per_day,
                duration_days=duration_days,
                instructions=item.instructions,
                confidence=medicine_confidence,
                drug_match_success=drug_score * 100.0,
                age_range=(age_range or "").strip(),
            )
        )
        total_drug_match += drug_score

    if gemma_medicines:
        avg_drug_match = total_drug_match / len(gemma_medicines)
    else:
        avg_drug_match = 0.0

    final_confidence = (
        ocr_reliability * 0.4 +
        json_parse_success * 0.3 +
        avg_drug_match * 0.3
    ) * 100.0

    return validated, final_confidence

