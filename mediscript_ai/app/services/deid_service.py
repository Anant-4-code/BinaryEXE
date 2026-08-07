import re
import json
from typing import Dict, Any, Tuple


class DeidService:
    """
    De-identification Layer for PHI/PII Protection (HIPAA & India DPDP Act 2023 compliant).
    Scrubs identifiable fields before sending payloads to external Vision/LLM APIs (Gemini / NVIDIA NIM).
    """

    # Regex patterns for scrubbing PII in free text
    PHONE_REGEX = re.compile(r'(\+?\d{1,3}[-.\s]?)?(\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{3,4}')
    EMAIL_REGEX = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
    AADHAAR_PAN_REGEX = re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b|\b\d{4}\s?\d{4}\s?\d{4}\b')

    @classmethod
    def scrub_text(cls, text: str) -> str:
        """Scrubs obvious PII tokens from unstructured free-text."""
        if not text:
            return ""
        scrubbed = cls.EMAIL_REGEX.sub("[EMAIL_REDACTED]", text)
        scrubbed = cls.AADHAAR_PAN_REGEX.sub("[GOVT_ID_REDACTED]", scrubbed)
        scrubbed = cls.PHONE_REGEX.sub("[PHONE_REDACTED]", scrubbed)
        return scrubbed

    @classmethod
    def prepare_deidentified_payload(
        cls,
        patient_details: Dict[str, Any],
        clinical_data: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """
        Takes raw patient details and clinical findings.
        Returns:
            - De-identified payload safe for external AI calls.
            - Re-identification mapping dictionary retained server-side only.
        """
        pseudonym_id = f"ANON-PATIENT-{abs(hash(str(patient_details.get('name', '')) + str(patient_details.get('phone', '')))) % 1000000:06d}"
        
        reid_map = {
            "pseudonym_id": pseudonym_id,
            "real_name": str(patient_details.get("name", "")),
            "real_phone": str(patient_details.get("phone", "")),
            "real_email": str(patient_details.get("email", "")),
            "real_address": str(patient_details.get("address", "")),
        }

        deidentified_patient = {
            "patient_code": pseudonym_id,
            "age": patient_details.get("age", "Unknown"),
            "gender": patient_details.get("gender", "Unknown"),
            "condition": cls.scrub_text(str(patient_details.get("disease_or_condition", ""))),
        }

        # Scrub free text in clinical data if present
        scrubbed_clinical = {}
        for k, v in clinical_data.items():
            if isinstance(v, str):
                scrubbed_clinical[k] = cls.scrub_text(v)
            elif isinstance(v, dict):
                scrubbed_clinical[k] = json.loads(cls.scrub_text(json.dumps(v)))
            else:
                scrubbed_clinical[k] = v

        payload = {
            "patient": deidentified_patient,
            "clinical": scrubbed_clinical
        }

        return payload, reid_map

    @classmethod
    def reattach_patient_identity(cls, ai_generated_text: str, reid_map: Dict[str, str]) -> str:
        """Re-attaches real patient identity server-side prior to displaying to authorized doctor."""
        if not ai_generated_text:
            return ""
        
        result = ai_generated_text
        if reid_map.get("pseudonym_id"):
            result = result.replace(reid_map["pseudonym_id"], reid_map.get("real_name") or "Patient")
        return result
