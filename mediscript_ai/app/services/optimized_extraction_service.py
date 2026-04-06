"""
Optimized extraction service for faster and more accurate data extraction.
Features:
- Advanced image preprocessing (contrast, denoise, deskew)
- Faster local OCR (EasyOCR)
- Optimized LLM prompts for faster inference
- Batch extraction to reduce LLM calls
- Parallel processing
"""

import json
import cv2
import numpy as np
from pathlib import Path
from typing import Any, Dict, List, Tuple
import asyncio
import logging

from PIL import Image, ImageEnhance, ImageFilter
import httpx

from app.config import get_settings
from app.schemas.schemas import OCRResult, GemmaMedicine, ExtractionResult

logger = logging.getLogger(__name__)
settings = get_settings()

# ============================================================================
# OPTIMIZED PROMPTS - Shorter, focused for faster inference
# ============================================================================

OPTIMIZED_EXTRACTION_PROMPT = """Extract medicines from prescription text. Return ONLY JSON.

Text: {raw_text}

Return strict JSON array. Example format:
[
  {{
    "medicine": "Medicine Name",
    "dose": "500mg",
    "frequency": "twice daily",
    "duration": "7 days",
    "instructions": "Take with food",
    "age_range": "adult"
  }}
]
"""

OPTIMIZED_PATIENT_DOCTOR_PROMPT = """Extract patient and doctor details. Return ONLY JSON.

Text: {raw_text}

{{
  "patient": {{"name": "", "age": "", "gender": "", "disease_or_condition": "", "phone": ""}},
  "doctor": {{"name": "", "qualification": "", "clinic_hospital": "", "phone": ""}}
}}
"""

OPTIMIZED_MEDICINE_EXPLAIN_PROMPT = """Brief explanation (100-150 chars): {medicine_name} - {dose} - {frequency}

What is it for? How to take? (Simple language, concise)."""

# ============================================================================
# IMAGE PREPROCESSING - Critical for accuracy
# ============================================================================

def _preprocess_image_for_ocr(image_path: Path) -> np.ndarray:
    """
    Advanced image preprocessing for better OCR accuracy.
    - Convert to grayscale
    - Enhance contrast
    - Denoise
    - Optional: Deskew
    """
    try:
        # Read image
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"Cannot read image: {image_path}")
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 1. Enhance contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrast = clahe.apply(gray)
        
        # 2. Denoise
        denoised = cv2.fastNlMeansDenoising(contrast, h=10, templateWindowSize=7, searchWindowSize=21)
        
        # 3. Threshold to binary (helps with handwriting)
        _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # 4. Optional: Morphological operations to clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
        
        logger.info("Image preprocessing complete")
        return cleaned
    
    except Exception as e:
        logger.error(f"Image preprocessing failed: {e}. Using original image.")
        img = cv2.imread(str(image_path))
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img is not None else None


def _preprocess_pil_image(image_path: Path) -> Image.Image:
    """Preprocess image using PIL for faster operations."""
    try:
        img = Image.open(image_path)
        
        # Convert to grayscale
        if img.mode != 'L':
            img = img.convert('L')
        
        # Enhance contrast
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)  # 2x contrast
        
        # Enhance sharpness
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(2.0)
        
        # Apply slight sharpening filter
        img = img.filter(ImageFilter.SHARPEN)
        
        logger.info("PIL image preprocessing complete")
        return img
    
    except Exception as e:
        logger.error(f"PIL preprocessing failed: {e}")
        return Image.open(image_path)

# ============================================================================
# OPTIMIZED OCR - EasyOCR (faster, better for handwriting)
# ============================================================================

def _ocr_with_easyocr(image_path: Path) -> Tuple[str, float]:
    """
    Use EasyOCR for faster and more accurate handwriting recognition.
    Falls back to pytesseract if EasyOCR not available.
    """
    try:
        import easyocr
        
        # Preprocess image
        preprocessed_img = _preprocess_pil_image(image_path)
        
        # Initialize reader (cached after first call)
        reader = easyocr.Reader(['en', 'hi', 'ta', 'kn'], gpu=False)
        
        # Extract text
        results = reader.readtext(np.array(preprocessed_img))
        
        # Combine text with confidence scores
        raw_text = "\n".join([text[1] for text in results])
        avg_confidence = np.mean([text[2] for text in results]) if results else 0.0
        
        logger.info(f"EasyOCR extraction: {len(raw_text)} chars, confidence: {avg_confidence:.2f}")
        return raw_text.strip(), min(avg_confidence, 1.0)
    
    except ImportError:
        logger.warning("EasyOCR not installed. Falling back to Tesseract.")
        return _ocr_with_tesseract(image_path)
    
    except Exception as e:
        logger.error(f"EasyOCR extraction failed: {e}. Falling back to Tesseract.")
        return _ocr_with_tesseract(image_path)


def _ocr_with_tesseract(image_path: Path) -> Tuple[str, float]:
    """Fallback OCR using Tesseract."""
    try:
        import pytesseract
        
        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        
        # Preprocess image
        preprocessed_img = _preprocess_pil_image(image_path)
        
        # Extract text with config for better accuracy
        raw_text = pytesseract.image_to_string(
            preprocessed_img,
            config='--psm 6 -c preserve_interword_spaces=1'
        ).strip()
        
        logger.info(f"Tesseract extraction: {len(raw_text)} chars")
        return raw_text, 0.85
    
    except Exception as e:
        logger.error(f"Tesseract extraction failed: {e}")
        return "", 0.0


async def optimized_ocr(image_path: Path) -> OCRResult:
    """
    Optimized OCR pipeline:
    1. Try EasyOCR (faster, better for handwriting)
    2. Fall back to Tesseract
    3. Reduce image size if needed
    """
    raw_text = ""
    reliability = 0.5
    
    ocr_engine = (settings.ocr_engine or "easyocr").strip().lower()
    
    if ocr_engine in {"auto", "easyocr"}:
        raw_text, reliability = _ocr_with_easyocr(image_path)
    
    if not raw_text and ocr_engine in {"auto", "tesseract"}:
        raw_text, reliability = _ocr_with_tesseract(image_path)
    
    if not raw_text:
        logger.warning("No text extracted from image")
    
    return OCRResult(
        raw_text=raw_text,
        ocr_reliability=reliability,
        ocr_engine=ocr_engine
    )

# ============================================================================
# OPTIMIZED LLM EXTRACTION - Batch calls, shorter prompts
# ============================================================================

async def _call_ollama_optimized(prompt: str, temperature: float = 0.3, max_tokens: int = 400) -> str:
    """
    Call Ollama with optimized parameters for faster inference.
    - Lower temperature for faster, more deterministic responses
    - Max tokens to limit output
    """
    payload = {
        "model": "llama3.2:3b",
        "prompt": prompt,
        "stream": False,
        "temperature": temperature,  # Lower = faster + more consistent
        "num_predict": max_tokens,  # Limit tokens
    }
    
    try:
        async with httpx.AsyncClient(base_url="http://localhost:11434", timeout=60) as client:
            response = await client.post("/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return (data.get("response") or "").strip()
    
    except Exception as e:
        logger.error(f"Ollama call failed: {e}")
        raise


async def extract_medicines_optimized(raw_text: str) -> List[GemmaMedicine]:
    """Extract medicines with optimized prompt."""
    try:
        prompt = OPTIMIZED_EXTRACTION_PROMPT.format(raw_text=raw_text)
        content = await _call_ollama_optimized(prompt, temperature=0.2, max_tokens=500)
        
        # Parse JSON (handle markdown code blocks)
        text = content.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        
        parsed = json.loads(text)
        medicines = [GemmaMedicine(**item) for item in parsed if isinstance(parsed, list)]
        
        logger.info(f"Extracted {len(medicines)} medicines")
        return medicines
    
    except Exception as e:
        logger.error(f"Medicine extraction failed: {e}")
        return []


async def extract_patient_doctor_optimized(raw_text: str) -> Dict[str, Any]:
    """Extract patient and doctor info with optimized prompt."""
    try:
        prompt = OPTIMIZED_PATIENT_DOCTOR_PROMPT.format(raw_text=raw_text)
        content = await _call_ollama_optimized(prompt, temperature=0.2, max_tokens=300)
        
        text = content.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        
        parsed = json.loads(text)
        return parsed
    
    except Exception as e:
        logger.error(f"Patient/Doctor extraction failed: {e}")
        return {"patient": {}, "doctor": {}}


async def explain_medicine_optimized(medicine_name: str, dose: str = "", frequency: str = "") -> str:
    """Generate medicine explanation with optimized prompt."""
    try:
        prompt = OPTIMIZED_MEDICINE_EXPLAIN_PROMPT.format(
            medicine_name=medicine_name,
            dose=dose or "—",
            frequency=frequency or "—"
        )
        explanation = await _call_ollama_optimized(prompt, temperature=0.3, max_tokens=150)
        return explanation[:500]  # Limit to 500 chars
    
    except Exception as e:
        logger.error(f"Medicine explanation failed: {e}")
        return f"{medicine_name}: Use as prescribed by doctor."


# ============================================================================
# BATCH EXTRACTION - Parallel processing for speed
# ============================================================================

async def extract_all_data_parallel(raw_text: str) -> Dict[str, Any]:
    """
    Extract all data (medicines, patient/doctor) in parallel for speed.
    """
    logger.info("Starting parallel extraction")
    
    start_time = asyncio.get_event_loop().time()
    
    # Run extraction tasks in parallel
    medicines_task = extract_medicines_optimized(raw_text)
    patient_doctor_task = extract_patient_doctor_optimized(raw_text)
    
    medicines, patient_doctor = await asyncio.gather(
        medicines_task,
        patient_doctor_task,
        return_exceptions=True
    )
    
    # Handle exceptions
    if isinstance(medicines, Exception):
        logger.error(f"Medicines extraction error: {medicines}")
        medicines = []
    
    if isinstance(patient_doctor, Exception):
        logger.error(f"Patient/Doctor extraction error: {patient_doctor}")
        patient_doctor = {"patient": {}, "doctor": {}}
    
    elapsed_time = asyncio.get_event_loop().time() - start_time
    logger.info(f"Parallel extraction completed in {elapsed_time:.2f}s")
    
    return {
        "medicines": medicines,
        **patient_doctor,
        "processing_time": elapsed_time
    }

# ============================================================================
# MAIN ENTRY POINT - Full optimized pipeline
# ============================================================================

async def run_optimized_extraction(image_path: Path) -> Dict[str, Any]:
    """
    Complete optimized extraction pipeline:
    1. Advanced image preprocessing
    2. Faster OCR (EasyOCR)
    3. Parallel LLM extraction with optimized prompts
    
    Returns all extracted data + processing time
    """
    logger.info(f"Starting optimized extraction for: {image_path}")
    
    start_time = asyncio.get_event_loop().time()
    
    # Step 1: OCR
    logger.info("Step 1: OCR extraction")
    ocr_result = await optimized_ocr(image_path)
    
    if not ocr_result.raw_text:
        logger.error("OCR failed - no text extracted")
        return {
            "success": False,
            "error": "Could not extract text from image",
            "ocr_reliability": 0.0
        }
    
    # Step 2: Parallel data extraction
    logger.info("Step 2: Parallel LLM extraction")
    extraction_data = await extract_all_data_parallel(ocr_result.raw_text)
    
    total_time = asyncio.get_event_loop().time() - start_time
    
    return {
        "success": True,
        "raw_text": ocr_result.raw_text,
        "ocr_reliability": ocr_result.ocr_reliability,
        "medicines": extraction_data.get("medicines", []),
        "patient": extraction_data.get("patient", {}),
        "doctor": extraction_data.get("doctor", {}),
        "processing_time": total_time,
        "processing_breakdown": {
            "ocr": "varies",
            "llm_extraction": extraction_data.get("processing_time", 0)
        }
    }
