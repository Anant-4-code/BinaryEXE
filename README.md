# 🏥 Sanjeevani - Medical Prescription Management Platform

![Python](https://img.shields.io/badge/Python-3.9+-blue?style=flat-square&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green?style=flat-square&logo=fastapi)
![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=flat-square)

> **Sanjeevani** is an intelligent medical prescription management platform that helps patients understand handwritten doctor prescriptions through AI-powered extraction, OCR, and real-time medication tracking.

---

## 🎯 Problem & Solution

### The Problem
- 😕 Doctors write prescriptions quickly and messily
- 🤔 Patients struggle to read handwritten prescriptions
- ⚠️ Creates confusion about medicine names, dosages, and timing
- ❌ Can cause medication errors and misuse
- 📊 Gap between doctor intent and patient understanding

### Our Solution
Sanjeevani digitizes and clarifies prescriptions in **4 smart steps:**

```
1️⃣ Upload           → 2️⃣ OCR Extract          → 3️⃣ AI Structure      → 4️⃣ Schedule
Upload prescription   Extract text from         Structure data using   Generate clear
image                 handwriting              Ollama/Llama (local)  medicine schedule
```

**Result:** Patients get a simple, clear, understandable action plan with real-time medication tracking! 📱✅

---

## ✨ Key Features

### 📸 **Prescription Processing**
- Handwritten prescription image recognition
- OCR text extraction with confidence scoring
- AI-powered medicine extraction using Ollama (Llama 3.2:3b)
- Patient and doctor information parsing

### 💊 **Medicine Management**
- Structured extraction of medicine name, dosage, frequency, duration
- AI-generated medicine explanations (uses, side effects, age recommendations)
- Confidence scoring for each field
- Human verification before final confirmation

### 📅 **Smart Scheduling & Tracking**
- Automatic dose schedule generation
- Calendar-based medication view
- Time-aware dose management
- Medicine reminders (upcoming, missed, completed)

### 📊 **Analytics & Adherence**
- Medication adherence tracking
- Adherence percentage & trends
- Visual charts and reports
- Dose compliance patterns

### 🌐 **Neural Transliteration & Audio**
- High-fidelity **NVIDIA Magpie Multilingual gRPC** Text-to-Speech (TTS) integration.
- AI-generated native language audio clinical reports (Hindi, Tamil, etc.).
- Regional language transliteration for clinical prescriptions.

### 🦴 **Multimodal X-Ray Diagnostics (Doctor Portal)**
- Auto-detect fractures via mathematical **Letterbox-padded YOLOv7** engine.
- Deep multimodal reasoning powered by **Sanjivini AI Vision Models** (Qwen-VL/Kimi K2.5).
- Doctor-ready clinical correlation reports with cross-verified severity metrics.
- Professional Aura Medical workspace UI with right-hand support panels.

### 📄 **Export & Reports**
- PDF report generation
- JSON data export
- Structured prescription records
- Customizable export options

### 🔐 **Security & Privacy**
- JWT-based user authentication
- Secure password hashing (bcrypt)
- Optional: Local processing for privacy
- Encrypted data storage

---

## 📦 Project Structure

This repository contains multiple applications:

### 🚀 **Main Application: MediScript AI** (`mediscript_ai/`)
A complete **FastAPI** web application with:
- RESTful APIs
- Interactive web UI (Jinja2 + TailwindCSS)
- SQLAlchemy ORM with SQLite/PostgreSQL
- AI services (Ollama/Llama, OCR, Analytics)
- Real-time notifications
- Database migrations

```
Sanjeevani/
├── mediscript_ai/              ⭐ Main FastAPI application
│   ├── app/
│   │   ├── routers/           # API endpoints (auth, upload, calendar, etc.)
│   │   ├── services/          # Business logic (AI, OCR, analytics, etc.)
│   │   ├── models/            # Database models (SQLAlchemy)
│   │   ├── schemas/           # API schemas (Pydantic)
│   │   ├── templates/         # HTML templates (Jinja2)
│   │   ├── core/              # Core utilities (database, security)
│   │   └── main.py            # Application entry point
│   ├── static/                # CSS, JS, images
│   ├── uploads/               # User prescription images
│   ├── tests/                 # Unit and integration tests
│   ├── requirements.txt       # Python dependencies
│   └── README.md              # Full documentation
│
├── app3.py                     # Streamlit alternative UI
├── test_web_app.py            # Web application tests
├── users.json                 # User data (JSON)
├── requirements.txt           # Root dependencies
└── README.md                  # This file
```

---

## 🏗️ Tech Stack

| Component | Technology |
|-----------|-----------|
| **Backend Framework** | FastAPI |
| **Web Server** | Uvicorn (ASGI) |
| **Database ORM** | SQLAlchemy |
| **Database** | SQLite (dev) / PostgreSQL (prod) |
| **Frontend** | Jinja2 Templates + TailwindCSS (Aura Medical Theme) |
| **Authentication** | JWT + Passlib (bcrypt) |
| **Prescription extraction** | Ollama with Llama 3.2:3b (Local) |
| **X-Ray AI Reasoning** | Sanjivini AI (Qwen-VL/Kimi K2.5 Multimodal) |
| **Fracture Detection** | Object Detection (ONNX YOLOv7) |
| **Clinical Audio TTS** | NVIDIA Magpie Multilingual gRPC |
| **OCR** | Tesseract / Custom Handwriting Service |
| **Image Processing** | Pillow + OpenCV + Auto-Contrast |
| **PDF Generation** | ReportLab |

---

## 🚀 Quick Start

### 1️⃣ **Clone & Navigate**

```bash
git clone https://github.com/yourusername/sanjeevani-ai.git
cd sanjeevani-ai/mediscript_ai
```

### 2️⃣ **Setup Python Environment**

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Activate (Linux/macOS)
source .venv/bin/activate
```

### 3️⃣ **Install Dependencies**

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4️⃣ **Configure Environment**

Create `.env` file:

```bash
APP_NAME="Sanjeevani AI"
DEBUG=True

# Database
DATABASE_URL="sqlite:///./mediscript.db"

# Security
JWT_SECRET_KEY="your-secret-key-here"
JWT_ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# AI Services - Ollama (Local LLM)
OLLAMA_BASE_URL="http://localhost:11434"
OLLAMA_MODEL="llama3.2:3b"

# Optional
OCR_ENGINE="auto"
TESSERACT_CMD="C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
```

**Install Ollama:**
- 📥 Download: https://ollama.ai/download
- Run: `ollama pull llama3.2:3b` (one-time setup)
- Start: `ollama serve` (runs on localhost:11434)

### 5️⃣ **Run the Application**

```bash
# Development mode (auto-reload)
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001

# Production mode (4 workers)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 4
```

### 6️⃣ **Access the App**

| URL | Purpose |
|-----|---------|
| 🏠 `http://localhost:8001` | Web UI |
| 📖 `http://localhost:8001/docs` | Interactive API Docs (Swagger) |
| 📚 `http://localhost:8001/redoc` | ReDoc Documentation |

---

## 🎮 Common Commands

### Development
```bash
# Run with auto-reload
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001

# Run tests
pytest -v

# Run with coverage
pytest --cov=app

# Format code
black .
```

### Database
```bash
# Auto-initialize on startup
# Or manually:
python -c "from app.core.database import Base, engine; Base.metadata.create_all(bind=engine)"

# Migrations with Alembic
alembic init alembic
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

### Git Operations
```bash
# Clone
git clone <repo-url>
cd sanjeevani-ai

# Create branch
git checkout -b feature/your-feature

# Commit
git add .
git commit -m "feat: Your feature description"

# Push
git push origin feature/your-feature
```

---

## 📊 System Architecture

### Data Flow

```
┌──────────────────┐
│ User Upload      │ 📸 Prescription image
└────────┬─────────┘
         │
    ┌────▼─────────────────┐
    │ OCR Processing       │ Extract text
    │ (Handwriting → Text) │
    └────┬─────────────────┘
         │
    ┌────▼──────────────────────────┐
    │ AI Extraction (Ollama/Llama)   │
    │ - Medicines                    │
    │ - Patient/Doctor Info          │
    │ - Medicine Explanations        │
    └────┬───────────────────────────┘
         │
    ┌────▼─────────────────┐
    │ Schedule Generation  │ Create dose calendar
    │ (Calendar Service)   │
    └────┬─────────────────┘
         │
    ┌────▼──────────────────┐
    │ Notification Setup    │ Schedule reminders
    └────┬───────────────────┘
         │
    ┌────▼──────────────┐
    │ Database Storage  │ Save to SQLite/PostgreSQL
    └────┬──────────────┘
         │
    ┌────▼──────────────────────┐
    │ User Dashboard            │ View & track
    │ - Calendar view           │ medications
    │ - Adherence analytics     │
    │ - Reminders               │
    └───────────────────────────┘
```

---

## 🗄️ Database Models

### Core Models
| Model | Purpose |
|-------|---------|
| **User** | User accounts with authentication |
| **Prescription** | Medical prescriptions with OCR text & AI extractions |
| **Medicine** | Individual medicines with dosage & frequency |
| **Dose** | Medication instances (date/time) |
| **Notification** | Medication reminders (upcoming/missed/completed) |

**Full Details:** See [mediscript_ai/README.md](mediscript_ai/README.md#-database-models)

---

## 🔌 API Endpoints

### Core Endpoints
```
Authentication
├─ POST   /auth/signup          # Register new user
├─ POST   /auth/login           # Login (returns JWT)
└─ POST   /auth/refresh         # Refresh token

Prescriptions
├─ GET    /workspace/           # List prescriptions
├─ POST   /upload               # Upload & OCR
├─ GET    /workspace/{id}       # Get details
├─ PUT    /workspace/{id}       # Update
└─ DELETE /workspace/{id}       # Delete

Calendar & Doses
├─ GET    /calendar/{id}        # View calendar
└─ POST   /calendar/{dose_id}/mark-taken  # Mark as taken

Analytics
├─ GET    /dashboard/           # Overview
└─ GET    /dashboard/analytics  # Adherence stats

Export
├─ POST   /export/pdf           # PDF report
└─ POST   /export/json          # JSON export
```

**Full API Documentation:** [mediscript_ai/README.md](mediscript_ai/README.md#-api-endpoints-overview)

---

## 🤖 AI & Services

### Ollama/Llama LLM Integration (Local Processing)
- Automatic medicine extraction from OCR text (no internet required)
- Patient/doctor information parsing
- AI-generated medicine explanations
- Natural language frequency conversion (OD → "once daily")

### OCR Services
- Handwriting recognition
- Text extraction with confidence scoring
- Image preprocessing

### Analytics Engine
- Adherence percentage calculation
- Trend analysis
- Visual chart generation

### Sanjivini AI Multimodal Diagnostics
- Object detection processing using ONNX YOLOv7 directly in the Python runtime.
- Automated Letterbox-padding and contrast equalization for precise non-distorted bone scaling.
- Cross-verified clinical correlation generation via NVIDIA NIM Vision endpoints.

### Neural Audio Clinical System
- High-fidelity `riva.client` gRPC streams into NVIDIA Magpie Multilingual model.
- Generates regional language audio on-the-fly for accessible patient care.

**Full Details:** [mediscript_ai/README.md](mediscript_ai/README.md#-ai-services--models)

---

## 🔐 Security Features

✅ **JWT Authentication** - HS256 token-based auth
✅ **Password Security** - Bcrypt hashing via Passlib
✅ **SQL Injection Prevention** - SQLAlchemy ORM parameterized queries
✅ **Input Validation** - Pydantic schema validation
✅ **CORS Protection** - Configured for secure cross-origin requests
✅ **Environment Secrets** - API keys in `.env` (never in git)
✅ **HTTPS Ready** - Production-ready with reversed proxy setup

---

## 🚨 Troubleshooting

### Common Issues

**Port 8001 already in use:**
```bash
python -m uvicorn app.main:app --reload --port 8002
```

**Virtual environment activation fails (Windows PowerShell):**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\.venv\Scripts\Activate.ps1
```

**Dependencies installation fails:**
```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

**Ollama connection errors:**
- Download & install Ollama: https://ollama.ai/download
- Start in another terminal: `ollama serve`
- Pull model: `ollama pull llama3.2:3b` (one-time)
- Check `.env` has: `OLLAMA_BASE_URL=http://localhost:11434`

**Database locked:**
```bash
rm mediscript.db
# App will auto-create on restart
```

**More Help:** [mediscript_ai/README.md#-troubleshooting](mediscript_ai/README.md#-troubleshooting)

---

## 📚 Documentation

| Topic | Link |
|-------|------|
| **Full Setup & Installation** | [mediscript_ai/README.md#-installation--setup](mediscript_ai/README.md#-installation--setup) |
| **Architecture & Data Flow** | [mediscript_ai/README.md#-architecture--data-flow](mediscript_ai/README.md#-architecture--data-flow) |
| **Database Schema** | [mediscript_ai/README.md#-database-models](mediscript_ai/README.md#-database-models) |
| **API Reference** | [mediscript_ai/README.md#-api-endpoints-overview](mediscript_ai/README.md#-api-endpoints-overview) |
| **Git Commands** | [mediscript_ai/README.md#-version-control--git-commands](mediscript_ai/README.md#-version-control--git-commands) |
| **Testing Guide** | [mediscript_ai/README.md#-testing](mediscript_ai/README.md#-testing) |
| **Troubleshooting** | [mediscript_ai/README.md#-troubleshooting](mediscript_ai/README.md#-troubleshooting) |

---

## 🌟 Key Highlights

| Feature | Benefit |
|---------|---------|
| **AI-Powered Extraction** | Accurate medicine data from handwritten text |
| **Real-Time Reminders** | Never miss a medication |
| **Adherence Tracking** | Monitor and visualize medication compliance |
| **Multi-Language** | Support for major Indian languages |
| **Export & Reports** | Generate PDF reports |
| **Secure & Private** | JWT auth + encrypted storage |
| **Easy to Use** | Intuitive web UI + mobile-friendly |
| **Scalable** | PostgreSQL ready for production |

---

## 🎯 Impact

✅ **Reduces medication errors** - Clear, structured information
✅ **Improves patient understanding** - Simple action plans
✅ **Increases adherence** - Real-time reminders & tracking
✅ **Saves time** - Automatic extraction & scheduling
✅ **Better healthcare outcomes** - Complete medication history

---

## 🛣️ Future Roadmap

- [ ] Doctor-side digital prescription upload
- [ ] Pharmacy integration
- [ ] Smartwatch/mobile app notifications
- [ ] Video prescription support
- [ ] AI-powered drug interactions checking
- [ ] Insurance integration
- [ ] Doctor dashboard for patient management

---

## 🤝 Contributing

We welcome contributions! Here's how:

```bash
# 1. Fork the repo
# 2. Create feature branch
git checkout -b feature/amazing-feature

# 3. Make your changes
# 4. Commit
git commit -m "feat: Add amazing feature"

# 5. Push
git push origin feature/amazing-feature

# 6. Open Pull Request on GitHub
```

**Contributing Guidelines:**
- Follow PEP 8 code style
- Add tests for new features
- Update documentation
- Use meaningful commit messages

---

## 📄 License

MIT License - Free to use for personal and commercial purposes.

---

## 👥 Team

**Sanjeevani Development Team** 🏥

Contact: support@sanjeevani-ai.com

---

## 🙏 Acknowledgments

- **Ollama & Llama 3.2:3b** - Local LLM processing
- **FastAPI Community** - Excellent web framework
- **SQLAlchemy Team** - Powerful ORM
- **Open Source Community** - All contributors

---

## 📞 Support

- 📖 **Documentation:** [Read the Full Guide](mediscript_ai/README.md)
- 🐛 **Report Bugs:** Open an issue on GitHub
- 💡 **Suggest Features:** GitHub Discussions
- 💬 **Chat:** GitHub Issues

---

## 🚀 Get Started Now!

```bash
cd mediscript_ai
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # Windows
source .venv/bin/activate     # Linux/macOS
pip install -r requirements.txt
# Setup Ollama first: ollama pull llama3.2:3b && ollama serve
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

Visit **http://localhost:8001** 🎉

👉 **[Full Documentation →](mediscript_ai/README.md)**

---

**Version:** 1.0.0  
**Last Updated:** March 2026  
**Status:** ✅ Active Development
