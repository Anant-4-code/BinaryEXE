import asyncio
import json
from app.services.gemma_service import call_gemma_extract_patient_doctor

sample_text = """
Dr. Arun Kumar, MBBS, MD
Cardiologist
City Heart Clinic
123 Health Ave, Mumbai
Phone: 9876543210

Name: John Doe
Age: 45 yrs    Sex: Male
C/O: Chest pain, breathless
Dx: Hypertension

Rx
Tab Telmisartan 40mg
"""

async def test():
    result = await call_gemma_extract_patient_doctor(sample_text)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(test())
