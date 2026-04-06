import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.speech_service import synthesize_speech, transcribe_audio
from app.services.assistant_service import parse_assistant_intent

router = APIRouter(prefix="/speech", tags=["speech"])

class SynthesizeRequest(BaseModel):
    text: str
    language: str = 'en'

class IntentRequest(BaseModel):
    text: str
    url: str


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Accepts an audio file upload and returns transcription.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
        
    try:
        content = await file.read()
        transcription = transcribe_audio(content, file.filename)
        return {"text": transcription}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/synthesize")
def synthesize(req: SynthesizeRequest, db: Session = Depends(get_db)):
    """
    Accepts text and returns a streaming WAV audio response to play.
    """
    orig_text = req.text.strip()
    if not orig_text:
        raise HTTPException(status_code=400, detail="Empty text provided")
        
    try:
        audio_bytes = synthesize_speech(orig_text, language=req.language)
        if not audio_bytes:
            raise HTTPException(status_code=500, detail="Failed to synthesize speech")
            
        def iterfile():
            yield audio_bytes
            
        return StreamingResponse(iterfile(), media_type="audio/wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/assistant_intent")
async def assistant_intent(req: IntentRequest):
    """
    Accepts transcribed voice command text and current viewing context, 
    then returns the parsed LLM intent JSON for autonomous execution.
    """
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Empty text provided")
        
    try:
        intent = await parse_assistant_intent(req.text, req.url)
        return intent
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
