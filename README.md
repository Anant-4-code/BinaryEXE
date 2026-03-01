# Sanjeevani

Sanjeevani is a simple project that helps patients understand handwritten doctor prescriptions.

Many times prescriptions are hard to read. This creates confusion about medicine name, dosage, and timing. Sanjeevani converts handwritten prescriptions into clear and structured information.

## Problem

Doctors write prescriptions quickly.
Patients struggle to read them.
This can cause dosage errors and misuse.

There is a gap between doctor intent and patient understanding.

## Solution

Sanjeevani converts handwriting into clear instructions in the 4 steps:

1. User uploads prescription image  
2. OCR extracts text  
3. Llama 3.2:3b structures the data  
4. System generates a clear medicine schedule  

The patient receives a simple and understandable action plan.

## Features

- Handwritten prescription recognition  
- Structured extraction of medicine name, dosage, frequency, duration  
- Confidence score for each field  
- Human verification before final confirmation  
- Automatic schedule generation  
- Medicine reminders  
- Multilingual support  
- Adherence tracking  
- Offline processing for privacy  

## Tech Stack

- OCR: Tesseract or EasyOCR  
- LLM: Llama 3.2:3b (runs locally)  
- Backend: Python + FastAPI  
- Frontend: React or Vue  
- Database: SQLite or PostgreSQL  
- Scheduler: APScheduler or Celery  
- PDF Generator: ReportLab or WeasyPrint  

## How It Works

1. User uploads image  
2. Image is preprocessed  
3. OCR extracts text  
4. LLM converts text into structured JSON  
5. Parser extracts medicine details  
6. Confidence score is generated  
7. Human verifies data  
8. Schedule and reminders are created  
9. System tracks adherence  

## Privacy

- All processing runs locally  
- No external API calls  
- Secure data storage  

## Impact

- Reduces medication errors  
- Improves patient understanding  
- Saves pharmacist time  
- Increases medication adherence  

## Future Scope

- Doctor-side digital upload  
- Pharmacy integration  
- More language support  
- Smartwatch reminder integration  

## Goal

To make prescriptions clear, understandable, and safe for every patient.
