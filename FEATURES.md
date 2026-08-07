# 🏥 Sanjeevani — Feature Documentation

> **Sanjeevani** is an intelligent medical prescription management platform. This document provides a comprehensive reference of every feature available across the platform.

---

## Table of Contents

1. [📸 Prescription Upload & OCR](#-prescription-upload--ocr)
2. [🤖 AI-Powered Medicine Extraction](#-ai-powered-medicine-extraction)
3. [💊 Medicine Management & Information](#-medicine-management--information)
4. [📅 Smart Dose Scheduling & Calendar](#-smart-dose-scheduling--calendar)
5. [🔔 Notifications & Reminders](#-notifications--reminders)
6. [📊 Adherence Analytics & Dashboard](#-adherence-analytics--dashboard)
7. [🌐 Multi-Language Transliteration](#-multi-language-transliteration)
8. [🔊 Neural Audio / Text-to-Speech (TTS)](#-neural-audio--text-to-speech-tts)
9. [🦴 X-Ray Diagnostics (Doctor Portal)](#-x-ray-diagnostics-doctor-portal)
10. [📄 Export & Reports](#-export--reports)
11. [🔐 Authentication & Security](#-authentication--security)
12. [🖥️ Web UI & User Experience](#-web-ui--user-experience)
13. [🔌 REST API](#-rest-api)
14. [🛣️ Future Roadmap](#-future-roadmap)

---

## 📸 Prescription Upload & OCR

### Overview
Patients upload a photo of their handwritten prescription; the platform automatically reads and digitizes it.

### How It Works
```
User uploads image → Image saved to /uploads → OCR engine runs → Raw text extracted → Confidence score returned
```

### Features
| Feature | Details |
|---------|---------|
| **Image Upload** | Accepts common formats (JPEG, PNG, AVIF, etc.) |
| **Handwriting Recognition** | Tesseract OCR with custom preprocessing |
| **Auto-Contrast & Deskew** | Pillow + OpenCV normalize image before OCR |
| **Confidence Scoring** | Each extraction gets a numeric confidence score |
| **Raw Text Storage** | Full OCR output stored for audit and re-processing |
| **Multi-Backend OCR** | Supports Tesseract, PyMuPDF, and custom RapidAPI endpoint |

### API Endpoint
```
POST /upload      — Upload prescription image & trigger OCR pipeline
```

---

## 🤖 AI-Powered Medicine Extraction

### Overview
After OCR, the raw text is sent to a local **Ollama (Llama 3.2:3b)** LLM which intelligently parses and structures the prescription.

### Three Parallel Extractions

#### 1. Medicine Details (`gemma_extract_medicines`)
```json
{
  "medicine": "Aspirin",
  "dose": "500mg",
  "frequency": "twice daily",
  "duration": "7 days",
  "instructions": "Take with food",
  "age_range": "18-65 years"
}
```

#### 2. Patient & Doctor Information (`gemma_extract_patient_doctor`)
```json
{
  "patient": { "name": "John Doe", "age": "34", "gender": "Male", "address": "..." },
  "doctor": { "name": "Dr. Smith", "qualification": "MBBS, MD", "specialization": "Cardiology" }
}
```

#### 3. Medicine Explanations (`gemma_explain_medicine`)
- Patient-friendly description of each medicine
- Uses, side effects, and age-group recommendations
- Up to 500 characters per explanation

### Key Attributes
- ✅ **Fully local** — No internet or API keys needed for Ollama
- ✅ **Natural language frequency** — Converts "OD", "BD", "TDS" to human-readable text
- ✅ **JSON output** — Results stored in the database for instant retrieval
- ✅ **Human Verification** — User can review & correct AI extractions before saving

---

## 💊 Medicine Management & Information

### Per-Medicine Data
| Field | Description |
|-------|-------------|
| `original_name` | Name as written on the prescription |
| `normalized_name` | Cleaned and standardized name |
| `dose` | Dosage amount (e.g., 500 mg) |
| `frequency` | How often to take (once daily, BD, TDS, etc.) |
| `duration_days` | Number of days of treatment |
| `instructions` | Special instructions (take with food, avoid sunlight, etc.) |
| `confidence` | AI confidence score for this extraction |
| `explanation` | AI-generated plain-language description |
| `age_range` | Recommended age group |

### Management Features
- View all medicines from a prescription in a structured list
- Edit or correct any field extracted by AI
- Delete a medicine from the schedule
- Human-in-the-loop verification before confirming data

---

## 📅 Smart Dose Scheduling & Calendar

### Overview
The **Calendar Service** converts medicine frequency data into a detailed day-by-day, time-slotted dose schedule.

### Scheduling Algorithm
```
Frequency parsed → "twice daily" → Morning (8 AM) + Evening (8 PM)
Duration applied → 7 days → 14 individual Dose records created
Calendar view built → Day-by-day grid with color-coded status
```

### Supported Frequencies
| Code | Meaning | Times per Day |
|------|---------|--------------|
| OD / Once Daily | Once a day | 1 |
| BD / Twice Daily | Twice a day | 2 |
| TDS / Three Times | Three times daily | 3 |
| QID | Four times daily | 4 |
| Custom | User-defined | Flexible |

### Calendar Features
- 📆 Visual calendar grid per prescription
- ✅ Mark individual doses as **taken**
- 🕐 Time-aware display (shows AM/PM slots)
- ⏰ Duration-bounded schedule (auto-stops after treatment period)
- 🔄 Timezone-aware scheduling

### API Endpoints
```
GET  /calendar/{prescription_id}          — View full dose calendar
POST /calendar/{dose_id}/mark-taken       — Mark a dose as taken
```

---

## 🔔 Notifications & Reminders

### Overview
The Notification Service creates reminders automatically for every dose in the schedule.

### Notification Types
| Type | Trigger | Timing |
|------|---------|--------|
| **Upcoming** | Dose is approaching | 1 hour before scheduled time |
| **Missed** | Dose was not taken | 2 hours after scheduled time |
| **Completed** | Dose was marked taken | Immediately on confirmation |

### Notification Features
- Stored in database with `sent` flag and `scheduled_for` timestamp
- Retrievable via API for any frontend/mobile integration
- Supports filtering by type (upcoming / missed / completed)

### API Endpoints
```
GET /notifications/           — All notifications for the user
GET /notifications/upcoming   — Only upcoming dose reminders
```

---

## 📊 Adherence Analytics & Dashboard

### Overview
The Analytics Dashboard provides a visual summary of medication compliance over time.

### Metrics Calculated
| Metric | Formula |
|--------|---------|
| **Adherence %** | `(doses_taken / total_doses) × 100` |
| **Missed Count** | Doses not marked as taken past their scheduled time |
| **Upcoming Count** | Future doses not yet due |
| **Trend** | Weekly/monthly compliance patterns |

### Dashboard Features
- 📊 **Chart.js visualizations** — Bar charts, line charts, pie charts
- 📅 **Date range filtering** — View adherence over custom periods
- 🏅 **Adherence rating** — Good / Fair / Poor classification
- 🔍 **Per-prescription breakdown** — Individual prescription compliance
- 📈 **Historical trends** — Long-term medication behavior tracking

### API Endpoints
```
GET /dashboard/           — Overview summary
GET /dashboard/analytics  — Detailed adherence statistics
```

---

## 🌐 Multi-Language Transliteration

### Overview
The Translation Service converts prescription data into regional Indian languages for improved patient accessibility.

### Languages Supported
| Language | Script |
|---------|--------|
| Hindi | Devanagari |
| Tamil | Tamil script |
| Kannada | Kannada script |
| Marathi | Devanagari |
| Bengali | Bengali script |
| Telugu | Telugu script |
| Punjabi | Gurmukhi |
| Gujarati | Gujarati script |
| Malayalam | Malayalam script |
| Odia | Odia script |
| Sanskrit | Devanagari |

### Technology Stack
- **Deep Translator** — Base translation layer
- **Ollama / Llama 3.2:3b** — Native script output for medical accuracy
- **RapidFuzz** — Fuzzy matching to preserve medical terminology

### Preservation Rules
- Medical drug names are preserved in their original form
- Dosage numbers and units are kept as-is
- Transliterated output stored in `transliterated_json` field

---

## 🔊 Neural Audio / Text-to-Speech (TTS)

### Overview
Sanjeevani generates high-fidelity audio clinical reports in the patient's native language for accessibility.

### Technology
| Component | Technology |
|-----------|-----------|
| **TTS Engine** | NVIDIA Magpie Multilingual Model |
| **Protocol** | gRPC (`riva.client` streams) |
| **Browser fallback** | Web Speech API |

### Features
- 🎙️ AI-generated audio in Hindi, Tamil, and other Indian languages
- 📻 Clinical report narration for patients with low literacy
- 🔄 On-the-fly audio generation — no pre-recorded files
- 📂 Downloadable `.wav` audio output
- 🌐 Accessible patient care through native-language audio

---

## 🦴 X-Ray Diagnostics (Doctor Portal)

### Overview
The **Sanjivini AI Multimodal Diagnostics** module provides automated fracture detection and AI-powered clinical correlation — a specialized tool for the **Doctor Portal**.

### Detection Pipeline
```
Upload X-Ray image
        ↓
Letterbox padding + Auto-Contrast normalization (Pillow + OpenCV)
        ↓
ONNX YOLOv7 Bone Fracture Detection (runs in Python runtime)
        ↓
Sanjivini AI Vision Reasoning (Qwen-VL / Kimi K2.5 via NVIDIA NIM)
        ↓
Clinical Correlation Report with severity metrics
```

### Detection Features
| Feature | Details |
|---------|---------|
| **Fracture Detection** | ONNX YOLOv7 model (`yolov7-p6-bonefracture.onnx`) |
| **Letterbox Padding** | Mathematical non-distorting bone scaling |
| **Auto-Contrast** | Contrast equalization for precise analysis |
| **AI Reasoning** | Qwen-VL / Kimi K2.5 multimodal vision model |
| **Clinical Reports** | Doctor-ready reports with cross-verified severity |
| **Detection Classes** | 21+ fracture types (`classes.txt`) |

### Doctor Portal UI
- Aura Medical workspace with right-hand support panels
- Professional report formatting for clinical use
- Side-by-side image + report view
- Regenerate button for re-running AI analysis

---

## 📄 Export & Reports

### Overview
The Export Service allows users to download prescription summaries and dose records in multiple formats.

### Export Formats
| Format | Contents |
|--------|---------|
| **PDF** | Patient info, doctor info, medicines, schedules, adherence summary |
| **JSON** | Full machine-readable prescription data |
| **CSV** | Dose log for spreadsheet import |

### Export Features
- **Override values** before export — correct any AI errors in the final output
- Structured layout with header, medicine table, dose grid
- Customizable report title and metadata
- Download directly from the web UI

### API Endpoints
```
POST /export/pdf    — Generate and download PDF report
POST /export/json   — Export full prescription as JSON
```

---

## 🔐 Authentication & Security

### Authentication
| Mechanism | Description |
|-----------|-------------|
| **JWT Tokens** | HS256-based access tokens (production mode) |
| **Prototype UI Auth** | Simple login/signup pages for development prototyping |
| **Password Hashing** | Bcrypt via Passlib |
| **Token Expiry** | Configurable via `ACCESS_TOKEN_EXPIRE_MINUTES` |

### Security Measures
| Measure | Implementation |
|---------|--------------|
| **SQL Injection Prevention** | SQLAlchemy ORM with parameterized queries |
| **Input Validation** | Pydantic v2 schema validation on all endpoints |
| **CORS Protection** | Configured for secure cross-origin requests |
| **Environment Secrets** | All API keys stored in `.env` (never in git) |
| **HTTPS Ready** | Production-ready with reverse proxy configuration |

### API Endpoints
```
GET  /login     — Login page (UI)
POST /login     — Login submit
GET  /signup    — Registration page (UI)
POST /signup    — Registration submit
```

---

## 🖥️ Web UI & User Experience

### Frontend Stack
| Component | Technology |
|-----------|-----------|
| **Templating** | Jinja2 |
| **Styling** | TailwindCSS (Aura Medical Theme) |
| **Charts** | Chart.js |
| **JavaScript** | Vanilla JS |

### UI Pages
| Page | Description |
|------|-------------|
| `home.html` | Home / landing page |
| `login.html` | Login form |
| `signup.html` | Registration form |
| `workspace.html` | Main prescription management workspace |
| `landing.html` | Public marketing/landing page |
| `base.html` | Shared navbar + footer layout |

### UX Features
- 📱 **Mobile-responsive** — Works across devices
- 🌙 **Aura Medical Theme** — Professional healthcare UI design
- ⚡ **Interactive API Docs** — Swagger UI at `/docs` and ReDoc at `/redoc`
- 🔄 **Auto-reload in dev** — Uvicorn hot reload for fast development

---

## 🔌 REST API

### Complete Endpoint Reference

#### Authentication
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/login` | Login page |
| `POST` | `/login` | Submit login |
| `GET` | `/signup` | Signup page |
| `POST` | `/signup` | Submit signup |

#### Prescriptions (Workspace)
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/workspace/` | List all prescriptions |
| `POST` | `/workspace/` | Create new prescription |
| `GET` | `/workspace/{id}` | Get prescription details |
| `PUT` | `/workspace/{id}` | Update prescription |
| `DELETE` | `/workspace/{id}` | Delete prescription |

#### Upload & OCR
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/upload` | Upload image and run OCR |

#### Calendar & Doses
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/calendar/{prescription_id}` | Get dose calendar |
| `POST` | `/calendar/{dose_id}/mark-taken` | Mark dose as taken |

#### Notifications
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/notifications/` | All notifications |
| `GET` | `/notifications/upcoming` | Upcoming reminders |

#### Analytics
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/dashboard/` | Dashboard overview |
| `GET` | `/dashboard/analytics` | Adherence analytics |

#### Export
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/export/pdf` | Generate PDF report |
| `POST` | `/export/json` | Export as JSON |

---

## 🗄️ Database Models

| Model | Purpose | Key Fields |
|-------|---------|-----------|
| **User** | User accounts | `email`, `hashed_password`, `created_at` |
| **Prescription** | Medical prescriptions | `raw_text`, `image_path`, `confidence_score`, `status`, `patient_details_json`, `doctor_details_json` |
| **Medicine** | Extracted medicines | `orig_name`, `norm_name`, `dose`, `frequency`, `duration_days`, `instructions`, `explanation`, `age_range` |
| **Dose** | Individual dose instances | `date`, `time`, `taken`, `taken_at` |
| **Notification** | Medication reminders | `type` (upcoming/missed/completed), `scheduled_for`, `sent` |

---

## 🛣️ Future Roadmap

| Feature | Status |
|---------|--------|
| Doctor-side digital prescription upload | 🔮 Planned |
| Pharmacy integration | 🔮 Planned |
| Smartwatch / Mobile app notifications | 🔮 Planned |
| Video prescription support | 🔮 Planned |
| AI-powered drug interaction checking | 🔮 Planned |
| Insurance integration | 🔮 Planned |
| Doctor dashboard for patient management | 🔮 Planned |

---

## 🏗️ Tech Stack Summary

| Component | Technology |
|-----------|-----------|
| **Backend Framework** | FastAPI |
| **Web Server** | Uvicorn (ASGI) |
| **Database ORM** | SQLAlchemy |
| **Database** | SQLite (dev) / PostgreSQL (prod) |
| **Frontend** | Jinja2 + TailwindCSS |
| **Authentication** | JWT + Passlib (bcrypt) |
| **LLM** | Ollama with Llama 3.2:3b (Local) |
| **Vision AI** | Sanjivini AI — Qwen-VL / Kimi K2.5 (NVIDIA NIM) |
| **Object Detection** | ONNX YOLOv7 |
| **TTS** | NVIDIA Magpie Multilingual gRPC |
| **OCR** | Tesseract / Custom Handwriting Service |
| **Image Processing** | Pillow + OpenCV + Auto-Contrast |
| **PDF Generation** | ReportLab |
| **Charts** | Chart.js |
| **Translation** | Deep Translator + RapidFuzz |
| **Testing** | Pytest |

---

**Version:** 1.0.0 | **Status:** ✅ Active Development | **Last Updated:** May 2026
