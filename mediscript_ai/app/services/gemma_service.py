import json
from typing import List

import httpx

from app.config import get_settings
from app.schemas.schemas import GemmaMedicine, ExtractionResult


settings = get_settings()

LLM_EXTRACTION_PROMPT = """You are a medical prescription extraction assistant.
Extract medicines and related details from the following text.

Text:
{raw_text}

Return strict JSON only, no explanations:
[
  {{
    "medicine": "",
    "dose": "",
    "frequency": "",
    "duration": "",
    "instructions": ""
  }}
]
"""


async def call_gemma(raw_text: str) -> ExtractionResult:
    """
    Call a local Ollama model (llama3.2:3b) to extract medicines in strict JSON.
    """
    prompt = LLM_EXTRACTION_PROMPT.format(raw_text=raw_text)

    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
    }

    async with httpx.AsyncClient(base_url=settings.ollama_base_url, timeout=120) as client:
        response = await client.post("/api/generate", json=payload)
        response.raise_for_status()
        data = response.json()
        content = (data.get("response") or "").strip()

    try:
        parsed = json.loads(content)
        medicines: List[GemmaMedicine] = [GemmaMedicine(**item) for item in parsed]
        json_success = 1.0
    except Exception:
        medicines = []
        json_success = 0.0

    return ExtractionResult(medicines=medicines, json_parse_success=json_success)

