import json
import logging
from typing import Dict, Any

from app.services.gemma_service import _call_ollama

logger = logging.getLogger(__name__)

ASSISTANT_PROMPT = """You are "Sanjeevani Assistant", an autonomous AI Voice Assistant for doctors.
The doctor speaks to you to navigate their platform and dictate prescriptions entirely hands-free.

Transcribed Voice Input: "{text}"
Current Screen/URL Context: "{context}"

Determine the INTENT of the doctor's voice command.
Choose ONE action from this list:
1. "NAVIGATE": Doctor wants to go to a specific page (queue, patients list, analytics, dashboard, new prescription).
2. "DRAFT_PRESCRIPTION": Doctor is dictating a prescription. Extract ALL medical details (patient info, medicines, doses, frequencies, duration).
3. "EXPLAIN": Doctor is asking you a medical question or asking you to explain something.
4. "GREETING": Doctor is saying hello or testing the mic.

Return strict JSON ONLY matching this format:
{{
   "action": "ACTION_NAME",
   "data": {{}},
   "reply": "A helpful, conversational 1-sentence reply that will be spoken aloud back to the doctor."
}}

If action is NAVIGATE, data should contain {"url": "/doctor/queue"} or similar appropriate URL.
If action is DRAFT_PRESCRIPTION, data should contain {"raw_notes": "the exact medical dictation translated to formal clinical notes"}.
"""

async def parse_assistant_intent(transcribed_text: str, current_url: str) -> Dict[str, Any]:
    """
    Passes the transcribed text to Ollama to determine the intent and reply.
    """
    prompt = ASSISTANT_PROMPT.format(text=transcribed_text, context=current_url)
    
    try:
        content = await _call_ollama(prompt, model="llama3.2:3b")
        
        # Clean up Markdown markdown fences if Llama outputs them
        text_clean = content.strip()
        if "```json" in text_clean:
            text_clean = text_clean.split("```json")[1].split("```")[0].strip()
        elif "```" in text_clean:
            text_clean = text_clean.split("```")[1].split("```")[0].strip()
            
        parsed = json.loads(text_clean)
        return parsed
    except Exception as e:
        logger.error(f"Failed to parse assistant intent: {e}")
        return {
            "action": "ERROR",
            "data": {},
            "reply": "I'm sorry doctor, but I am having trouble understanding your request right now."
        }
