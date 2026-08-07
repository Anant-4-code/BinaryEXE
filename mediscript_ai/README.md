# 🏥 Sanjeevani AI - Medical Prescription Management System

![Python](https://img.shields.io/badge/Python-3.9+-blue?style=flat-square&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green?style=flat-square&logo=fastapi)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-red?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

> **Sanjeevani AI** is an intelligent prescription management system that digitizes paper prescriptions, extracts medicine details using AI, and provides real-time medication tracking with adherence analytics.

---

## 🎯 Features

✨ **Core Capabilities:**
- 📸 **Prescription Upload & OCR** - Upload prescription images and extract text using advanced handwriting recognition
- 🦴 **Clinical X-Ray Diagnostics** - ONNX YOLOv7 object detection combined with Sanjivini AI (Qwen-VL/Kimi K2.5) multimodal vision reasoning.
- 🤖 **AI-Powered Extraction** - Automatically extract medicines, dosages, and patient/doctor details using Ollama (Llama 3.2:3b)
- 💊 **Medicine Information** - Get AI-generated explanations of medicines, uses, side effects, and age recommendations
- 🔊 **Magpie Medical Audio (TTS)** - High-fidelity NVIDIA Magpie Multilingual gRPC audio streams for native-language patient reports.
- 📅 **Smart Dose Scheduling** - Create calendar-based dose schedules with time-aware constraints
- 🔔 **Notifications** - Real-time reminders for upcoming, missed, and completed doses
- 📊 **Adherence Analytics** - Track medication compliance and visualize adherence patterns
- 🌐 **Multi-Language Support** - Transliterate prescriptions to Hindi, Tamil, Kannada, Marathi, Bengali, and more
- 📄 **Export & Reports** - Generate structured prescription reports in multiple formats
- 🔐 **User Authentication (Prototype)** - Simple login/signup pages for prototyping (not production-ready)

---

## 📋 Tech Stack

### Backend
- **Framework:** [FastAPI](https://fastapi.tiangolo.com/) - Modern, fast Python web framework
- **Server:** Uvicorn - ASGI application server
- **ORM:** SQLAlchemy - SQL toolkit and Object Relational Mapper
- **Database:** SQLite (default, configurable to PostgreSQL)
- **Authentication:** Prototype login/signup pages (UI prototype only)
- **API Validation:** Pydantic v2 with BaseSettings

### Frontend
- **Templating:** Jinja2
- **Styling:** TailwindCSS (via CDN)
- **Charts:** Chart.js
- **JavaScript:** Vanilla JS

### Accessibility & UX
- **Text-to-Speech (TTS):** Web Speech API (browser-based)

### AI & NLP Services
- **LLM:** Ollama with Llama 3.2:3b (Local, runs offline)
- **Vision:** Sanjivini AI Multimodal (Qwen-VL / Kimi K2.5 via NVIDIA NIM)
- **Object Detection:** YOLOv7 (Letterbox scaled)
- **TTS:** NVIDIA Magpie Multilingual gRPC (`riva.client`)
- **Handwriting Recognition:** Tesseract OCR / Custom service
- **Text Extraction:** Tesseract-compatible backends
- **Translation:** Deep Translator
- **Fuzzy Matching:** RapidFuzz

### Utilities
- **Image Processing:** Pillow, AVIF plugin
- **Document Generation:** ReportLab (PDF exports)
- **Testing:** Pytest
- **Environment:** Python-dotenv

---

## 🏗️ Architecture & Data Flow

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     USER INTERFACE                          │
│              (Jinja2 Templates + TailwindCSS)               │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                      FASTAPI SERVER                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ Auth Router  │  │ Upload Router│  │ Workspace Router │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │Calendar Route│  │NotifyRouter  │  │Export/Dashboard  │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
    ┌────▼────┐    ┌─────▼─────┐   ┌───▼──────┐
    │ Services│    │Core Layer │   │ Schemas  │
    │ (AI/Biz)│    │ (DB/Auth) │   │(Validation)
    └────┬────┘    └─────┬─────┘   └──────────┘
         │               │
    ┌────▼─────────────────▼────────────┐
    │      SQLAlchemy ORM Models        │
    │  (User, Prescription, Medicine,   │
    │    Dose, Notification, etc.)      │
    └────┬─────────────────────────────┘
         │
    ┌────▼──────────────────┐
    │   SQLite Database     │
    │  (mediscript.db)      │
    └──────────────────────┘

External APIs:
- Google Generative AI (Gemini LLM)
- Optional Custom Handwriting OCR
- Optional Rapid API Services
```

### Data Flow: Prescription Processing

```
1. UPLOAD PHASE
   ├─ User uploads prescription image
   ├─ File saved to /uploads directory
   └─ Triggers handwriting_service.run_handwriting_model()

2. OCR & TEXT EXTRACTION
   ├─ OCR engine processes image
   ├─ Returns raw_text to Prescription model
   └─ confidence_score calculated

3. AI EXTRACTION (Ollama/Llama 3.2:3b)
   ├─ Raw text sent to gemma_service
   ├─ Three parallel extractions:
   │  ├─ Medicine Details (gemma_extract_medicines)
   │  ├─ Patient/Doctor Info (gemma_extract_patient_doctor)
   │  └─ Medicine Explanations (gemma_explain_medicine)
   └─ Results stored as JSON in database

4. DOSE SCHEDULING
   ├─ calendar_service.generate_doses_for_prescription()
   ├─ Creates Dose records for each medicine
   ├─ Frequency-aware scheduling (daily, BD, TDS, etc.)
   └─ Duration-based termination dates

5. NOTIFICATION SETUP
   ├─ notification_service creates Notification records
   ├─ scheduled_for timestamps calculated
   └─ Sent status tracked for real-time reminders

6. USER DASHBOARD
   ├─ analytics_service aggregates data
   ├─ Counts: taken, missed, upcoming doses
   ├─ Adherence % = (taken / total) * 100
   └─ Charts generated via Chart.js

7. EXPORT & REPORTS
   ├─ export_service.generate_pdf_report()
   ├─ export_service.export_to_json()
   └─ Option to override values before export
```

---

## 📊 Database Models

### Entity Relationship Diagram

```
┌──────────────┐
│    User      │
├──────────────┤
│ id (PK)      │
│ email        │
│ hashed_pwd   │
│ created_at   │
└────────┬─────┘
         │ 1:N
         │
    ┌────▼─────────────────┐
    │  Prescription         │
    ├───────────────────────┤
    │ id (PK)               │
    │ user_id (FK)          │
    │ title                 │
    │ caption               │
    │ raw_text              │
    │ image_path            │
    │ confidence_score      │
    │ status (enum)         │
    │ patient_details_json  │
    │ doctor_details_json   │
    │ transliterated_json   │
    │ export_overrides_json │
    │ created_at            │
    └────┬──────────────┬───┘
         │ 1:N          │ 1:N
         │              │
    ┌────▼──────────┐  ┌─▼───────────────┐
    │  Medicine     │  │  Dose           │
    ├───────────────┤  ├─────────────────┤
    │ id (PK)       │  │ id (PK)         │
    │ presc_id (FK) │  │ presc_id (FK)   │
    │ orig_name     │  │ med_id (FK)     │
    │ norm_name     │  │ date            │
    │ dose          │  │ time            │
    │ frequency     │  │ taken (bool)    │
    │ duration_days │  │ taken_at        │
    │ instructions  │  └─────────────────┘
    │ confidence    │
    │ explanation   │
    │ age_range     │
    └───────────────┘

    ┌──────────────────────┐
    │  Notification        │
    ├──────────────────────┤
    │ id (PK)              │
    │ presc_id (FK)        │
    │ dose_id (FK, null ok)│
    │ type (enum)          │
    │ message              │
    │ scheduled_for        │
    │ sent (bool)          │
    │ created_at           │
    └──────────────────────┘
```

### Model Details

| Model | Purpose | Key Fields |
|-------|---------|-----------|
| **User** | User accounts | email, hashed_password, created_at |
| **Prescription** | Medical prescriptions | patient/doctor JSON, status, OCR text |
| **Medicine** | Extracted medicine details | dosage, frequency, AI-generated explanation |
| **Dose** | Individual medication instances | date/time, taken status |
| **Notification** | Medication reminders | type (upcoming/missed/completed), scheduled time |

---

## 🚀 Installation & Setup

### Prerequisites
- **Python:** 3.9 or higher
- **Git:** For version control
- **Virtual Environment:** venv (recommended)
- **Ollama:** Download from https://ollama.ai/download (runs local LLM)

### Step 1️⃣ Clone the Repository

```bash
# Clone from GitHub (if applicable)
git clone https://github.com/yourusername/sanjeevani-ai.git
cd sanjeevani-ai/mediscript_ai

# Or navigate to existing folder
cd c:\Users\HP\Downloads\Sanjeevani\mediscript_ai
```

### Step 2️⃣ Create Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**Linux/macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3️⃣ Install Dependencies

```bash
# Upgrade pip (recommended)
pip install --upgrade pip

# Install from requirements
pip install -r requirements.txt
```

**Core Dependencies Installed:**
```
fastapi                  # Web framework
uvicorn[standard]       # ASGI server
sqlalchemy              # ORM
alembic                 # Database migrations
psycopg2-binary        # PostgreSQL adapter (optional)
pydantic                # Data validation
passlib[bcrypt]         # Password hashing (optional / future)
python-dotenv          # Environment variables
pillow                  # Image processing
deep-translator         # Multi-language support
reportlab               # PDF generation
pytest                  # Testing framework
```

**Note:** Ollama runs locally on your machine - no API keys required!

### Step 4️⃣ Configure Environment

Create `.env` file in `mediscript_ai/` directory:

```bash
# Core Settings
APP_NAME="Sanjeevani AI"
DEBUG=True

# Database
DATABASE_URL="sqlite:///./mediscript.db"
# For PostgreSQL: DATABASE_URL="postgresql://user:password@localhost:5432/mediscript"

# Security
# Note: UI auth is currently a prototype flow (no JWT required)

# AI Services - Ollama (Local LLM)
OLLAMA_BASE_URL="http://localhost:11434"  # Ollama server (default)
OLLAMA_MODEL="llama3.2:3b"  # Local model

# Optional: Handwriting OCR Service
HANDWRITING_MODEL_ENDPOINT="http://your-ocr-api:port"
HANDWRITING_RAPIDAPI_KEY="your-rapidapi-key"

# OCR Configuration
OCR_ENGINE="auto"  # Options: auto, tesseract, pymupdf
TESSERACT_CMD="C:\\Program Files\\Tesseract-OCR\\tesseract.exe"  # Windows path
```

### Step 5️⃣ Initialize Database

```bash
# Database will auto-initialize on first run
# Or manually:
python -c "from app.core.database import Base, engine; Base.metadata.create_all(bind=engine)"
```

---

## 🎮 Running the Application

### Development Mode (with Auto-Reload)

```bash
# Make sure virtual environment is activated
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

**Output:**
```
Uvicorn running on http://127.0.0.1:8001
- Docs: http://127.0.0.1:8001/docs
- ReDoc: http://127.0.0.1:8001/redoc
```

### Production Mode

```bash
# Without auto-reload (faster, safer)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 4
```

### Access the Application

| URL | Purpose |
|-----|---------|
| `http://localhost:8001` | Main application |
| `http://localhost:8001/docs` | Interactive API documentation (Swagger UI) |
| `http://localhost:8001/redoc` | ReDoc API documentation |

### Prototype Login (UI)

This project currently uses a simple prototype login/signup flow for the UI.

- **Signup:** `http://localhost:8001/signup`
- **Login:** `http://localhost:8001/login`

**Sample credentials (prototype):**

- **Email:** `anantrai0809@gmail.com`
- **Password:** `Anantrai`

### For Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_gemma_service.py

# Run with coverage report
pytest --cov=app tests/
```

---

## 📁 Project Structure

```
mediscript_ai/
│
├── app/                                    # Main application package
│   ├── __init__.py                        # Package initializer
│   ├── main.py                            # FastAPI app setup, routes, startup
│   ├── config.py                          # Settings management (pydantic BaseSettings)
│   ├── utils.py                           # Utility functions
│   │
│   ├── core/                              # Core functionality
│   │   ├── database.py                    # SQLAlchemy setup, session dependency
│   │   └── security.py                    # (Optional) security helpers
│   │
│   ├── models/                            # SQLAlchemy ORM models
│   │   └── models.py                      # User, Prescription, Medicine, Dose, Notification
│   │
│   ├── schemas/                           # Pydantic request/response schemas
│   │   └── schemas.py                     # API input/output contracts
│   │
│   ├── routers/                           # API route handlers
│   │   ├── auth.py                        # (Optional/legacy) auth endpoints
│   │   ├── upload.py                      # Prescription image upload & OCR
│   │   ├── workspace.py                   # Prescription CRUD operations
│   │   ├── calendar.py                    # Dose scheduling & calendar view
│   │   ├── notifications.py               # Notification retrieval & management
│   │   ├── export.py                      # PDF/JSON export endpoints
│   │   └── dashboard.py                   # Analytics & adherence dashboard
│   │
│   ├── services/                          # Business logic & external integrations
│   │   ├── gemma_service.py               # Ollama/Llama LLM extraction
│   │   ├── handwriting_service.py         # OCR and image-to-text
│   │   ├── calendar_service.py            # Dose schedule generation
│   │   ├── notification_service.py        # Notification creation & sending
│   │   ├── analytics_service.py           # Adherence calculations & stats
│   │   ├── export_service.py              # PDF & structured exports
│   │   ├── translation_service.py         # Multi-language transliteration
│   │   └── validation_service.py          # Input validation business rules
│   │
│   ├── templates/                         # Jinja2 HTML templates
│   │   ├── base.html                      # Base template with navbar, footer
│   │   ├── home.html                      # Home/landing page
│   │   ├── login.html                     # Login form
│   │   ├── signup.html                    # Registration form
│   │   ├── landing.html                   # Public landing page
│   │   └── workspace.html                 # Main prescription management UI
│   │
│   ├── assets/                            # Static assets
│   │   └── fonts/                         # Custom fonts (if any)
│   │
│   └── __pycache__/                       # Compiled Python cache
│
├── static/                                # Static files (CSS, JS, images)
│   ├── css/
│   ├── js/
│   └── images/
│
├── templates/                             # Additional template files
│
├── tests/                                 # Unit & integration tests
│   ├── __init__.py
│   ├── test_gemma_service.py              # LLM extraction tests
│   └── __pycache__/
│
├── uploads/                               # User-uploaded prescription images
│
├── migrate_add_columns.py                 # Database migration script
├── mediscript.db                          # SQLite database file
├── requirements.txt                       # Python dependencies
├── .env                                   # Environment variables (create locally)
├── .env.example                           # Example environment file
├── .gitignore                             # Git ignore patterns
├── README.md                              # This file
└── .venv/                                 # Virtual environment (local only)
```

---

## 🔌 API Endpoints Overview

### Authentication
```
GET    /login                    - Prototype login page (UI)
POST   /login                    - Prototype login submit (UI)
GET    /signup                   - Prototype signup page (UI)
POST   /signup                   - Prototype signup submit (UI)
```

### Prescription Management
```
GET    /workspace/               - List all prescriptions
POST   /workspace/               - Create new prescription
GET    /workspace/{id}           - Get prescription details
PUT    /workspace/{id}           - Update prescription
DELETE /workspace/{id}           - Delete prescription
```

### Upload & OCR
```
POST   /upload                   - Upload prescription image & run OCR
```

### Dose Calendar
```
GET    /calendar/{prescription_id}    - Get dose calendar
POST   /calendar/{dose_id}/mark-taken - Mark dose as taken
```

### Notifications
```
GET    /notifications/           - Get all notifications
GET    /notifications/upcoming   - Get upcoming reminders
```

### Analytics & Dashboard
```
GET    /dashboard/               - Dashboard overview
GET    /dashboard/analytics      - Adherence analytics
```

### Export
```
POST   /export/pdf               - Generate PDF report
POST   /export/json              - Export as JSON
```

---

## 🤖 AI Services & Models

### 1. **Ollama LLM Service** (`gemma_service.py`)
**Models Used:** Ollama with Llama 3.2:3b (Local, runs offline - no API key needed)

**Capabilities (Local Processing):**
- **Extract Medicines:** Parse dosage, frequency, duration from OCR text
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
- **Extract Patient/Doctor:** Parse demographic and clinic details
  ```json
  {
    "patient": {
      "name": "John Doe",
      "age": "34",
      "gender": "Male",
      "address": "..."
    },
    "doctor": {
      "name": "Dr. Smith",
      "qualification": "MBBS, MD",
      "specialization": "Cardiology"
    }
  }
  ```
- **Medicine Explanations:** Generate patient-friendly descriptions
  - Uses, side effects, age recommendations
  - Limited to 500 characters for simplicity

### 2. **Handwriting Recognition Service** (`handwriting_service.py`)
**Models Supported:**
- Tesseract OCR (local, open-source)
- Custom handwriting recognition API
- Rapid API integration

**Process:**
- Image preprocessing (contrast, deskew)
- Text extraction with confidence scoring
- Returns structured OCR result

### 3. **Calendar Service** (`calendar_service.py`)
**Algorithm:** Frequency-aware dose scheduling
- Parses human-readable frequency ("once daily", "twice daily", "TDS")
- Generates Dose records for each occurrence
- Respects duration (stop dates)
- Timezone-aware scheduling

### 4. **Translation Service** (`translation_service.py`)
**Languages Supported:** Hindi, Tamil, Kannada, Marathi, Bengali, Telugu, Punjabi, Gujarati, Malayalam, Odia, Sanskrit

**Technology:**
- Deep Translator for base translation
- Ollama/Llama (or Gemini if configured) for native script output in Devanagari, Tamil, Kannada, etc.
- Preserves medical terminology accuracy

### 5. **Analytics Service** (`analytics_service.py`)
**Metrics Calculated:**
- **Adherence %:** (doses_taken / total_doses) × 100
- **Missed Count:** Doses not marked as taken
- **Upcoming Count:** Future doses
- **Trend Analysis:** Weekly/monthly adherence patterns

### 6. **Export Service** (`export_service.py`)
**Formats:**
- PDF with structured layout (patient info, medicines, schedules)
- JSON with all extracted details
- CSV for spreadsheet import
- Option to override values before export

### 7. **Notification Service** (`notification_service.py`)
**Types:**
- **Upcoming:** 1 hour before scheduled dose
- **Missed:** 2 hours after missed dose
- **Completed:** Confirmation for taken doses

---

## 🔐 Security Features

- **Prototype Authentication:** UI-only login/signup for prototyping (not production-grade)
- **CORS:** Configured for cross-origin requests
- **SQL Injection Protection:** SQLAlchemy parameterized queries
- **Input Validation:** Pydantic schema validation on all endpoints
- **Environment Secrets:** Sensitive keys in `.env` (never in git)

---

## 🌐 Version Control & Git Commands

### Initialize Git Repository (First Time Only)

```bash
git init
git add .
git commit -m "Initial commit: Sanjeevani AI prescription management system"
```

### Common Git Commands

#### Cloning
```bash
git clone https://github.com/yourusername/sanjeevani-ai.git
cd sanjeevani-ai
```

#### Branching
```bash
# Create new feature branch
git checkout -b feature/medicine-search

# List all branches
git branch -a

# Switch to branch
git checkout feature/medicine-search

# Delete branch
git branch -d feature/medicine-search
```

#### Staging & Committing
```bash
# Check status
git status

# Stage all changes
git add .

# Stage specific file
git add app/routers/upload.py

# Commit with message
git commit -m "feat: Add medicine search functionality"

# Amend last commit
git commit --amend -m "Updated message"
```

#### Pushing to Remote
```bash
# Push current branch
git push origin feature/medicine-search

# Push all branches
git push origin --all

# Force push (use carefully!)
git push origin feature/name --force

# Push with tracking (first time)
git push -u origin feature/medicine-search
```

#### Pulling Updates
```bash
# Pull latest changes
git pull origin main

# Pull with rebase
git pull --rebase origin main

# Fetch without merging
git fetch origin
```

#### Viewing History
```bash
# View commit log
git log

# Condensed log
git log --oneline

# With graph
git log --graph --oneline --all

# Commits by author
git log --author="John Doe"

# Changes in last 5 commits
git log --stat -5
```

#### Merging
```bash
# Merge feature branch into main
git checkout main
git pull origin main
git merge feature/medicine-search

# Squash commits before merge
git merge --squash feature/medicine-search
git commit -m "feat: Add medicine search"

# Abort merge if conflicts arise
git merge --abort
```

#### Handling Conflicts
```bash
# View conflicts
git status

# Edit conflicted files manually, then:
git add .
git commit -m "Resolve merge conflicts"
git push origin main
```

#### Tagging Releases
```bash
# Create lightweight tag
git tag v1.0.0

# Create annotated tag
git tag -a v1.0.0 -m "Release version 1.0.0"

# Push tags
git push origin v1.0.0
git push origin --tags

# List tags
git tag -l
```

#### Cleanup
```bash
# Remove untracked files (dry run)
git clean -fd --dry-run

# Remove untracked files (execute)
git clean -fd

# Reset to last commit
git reset --hard HEAD

# Reset to specific commit
git reset --hard commit-hash

# Revert a commit (creates new commit)
git revert commit-hash
```

### GitHub Workflow Example

```bash
# 1. Create feature branch
git checkout -b feature/dose-reminders

# 2. Make changes and commit
git add app/services/notification_service.py
git commit -m "feat: Add SMS reminder capabilities"

# 3. Push to remote
git push origin feature/dose-reminders

# 4. Create Pull Request on GitHub (UI)
# 5. After review and approval, merge to main
git checkout main
git pull origin main
git merge feature/dose-reminders
git push origin main

# 6. Delete feature branch
git branch -d feature/dose-reminders
git push origin --delete feature/dose-reminders
```

---

## 📝 Environment Variables Reference

```env
# Application
APP_NAME=Sanjeevani AI
DEBUG=True/False

# Database
DATABASE_URL=sqlite:///./mediscript.db
# PostgreSQL example:
# DATABASE_URL=postgresql://user:password@localhost:5432/mediscript

# Note: UI auth is currently a prototype flow (no JWT required)

# AI Services - Ollama (Local LLM)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b

# Optional: Google Gemini (if using instead of Ollama)
# GEMINI_API_KEY=sk-your-google-api-key

# Optional OCR
HANDWRITING_MODEL_ENDPOINT=http://localhost:5000
HANDWRITING_RAPIDAPI_KEY=your-rapidapi-key

# OCR Configuration
OCR_ENGINE=auto
TESSERACT_CMD=/usr/bin/tesseract  # Linux
# or
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe  # Windows
```

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_gemma_service.py

# Run with verbose output
pytest -v tests/

# Run with coverage
pytest --cov=app --cov-report=html

# Run tests matching pattern
pytest -k "test_extract" -v
```

---

## 📊 Database Migrations

For PostgreSQL or production databases, use Alembic:

```bash
# Initialize Alembic (one-time)
alembic init alembic

# Create migration after model changes
alembic revision --autogenerate -m "Add new columns"

# Apply migrations
alembic upgrade head

# Rollback to previous version
alembic downgrade -1
```

---

## 🚨 Troubleshooting

### Virtual Environment Not Activating
```bash
# Windows PowerShell error?
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Then try again
.venv\Scripts\Activate.ps1
```

### Dependencies Installation Fails
```bash
# Upgrade pip first
python -m pip install --upgrade pip

# Install with compatible versions
pip install --upgrade setuptools wheel
pip install -r requirements.txt
```

### Gemini API Key Error
- Ensure Ollama is running: `ollama serve` (or open the Ollama app)
- Pull the Llama model: `ollama pull llama3.2:3b` (one-time)
- Verify `.env` has correct `OLLAMA_BASE_URL=http://localhost:11434`
- Download Ollama from: https://ollama.ai/download

### Database Locked Error
```bash
# Remove corrupted database and reinit
rm mediscript.db
# App will auto-create on next run
```

### Port 8001 Already in Use
```bash
# Use different port
python -m uvicorn app.main:app --reload --port 8002

# Or find process using port (Linux/macOS)
lsof -i :8001
kill -9 process_id
```

---

## 📚 Documentation & Resources

- **FastAPI Docs:** https://fastapi.tiangolo.com/
- **SQLAlchemy ORM:** https://docs.sqlalchemy.org/
- **Pydantic Documentation:** https://docs.pydantic.dev/
- **Ollama:** https://ollama.ai/ | https://llama.meta.com
- **TailwindCSS:** https://tailwindcss.com/
- **Chart.js:** https://www.chartjs.org/

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/your-feature`
3. Commit changes: `git commit -m "Add your feature"`
4. Push to branch: `git push origin feature/your-feature`
5. Open Pull Request

---

## 📄 License

MIT License - Feel free to use this project for personal or commercial purposes.

---

## 👨‍💻 Author

**Sanjeevani AI Development Team**

For issues, suggestions, or questions, please open an issue on GitHub or contact the development team.

---

## 🎉 Acknowledgments

- **Ollama & Llama 3.2:3b** - Local LLM processing
- **FastAPI community** - Excellent web framework
- **SQLAlchemy team** - Powerful ORM
- **All open-source contributors**

---

**Last Updated:** March 2026  
**Version:** 1.0.0

---

### Quick Start Cheat Sheet

```bash
# Clone & Setup
git clone <repo-url>
cd mediscript_ai
python -m venv .venv
.venv\Scripts\Activate.ps1  # Windows

# Install & Configure
pip install -r requirements.txt
# Create .env (optional). Ollama is local - no API keys required by default.

# Run App
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
# Visit http://localhost:8001

# Push Changes
git add .
git commit -m "Your message"
git push origin feature/branch-name
```

---

💡 **Tip:** Bookmark the API docs at `http://localhost:8001/docs` for interactive API exploration!
