# Sanjeevani AI (MediScript AI)

FastAPI web app that:

- Uploads prescription images
- Runs OCR
- Extracts structured medicines + patient/doctor details using AI
- Generates per-medicine dose schedules
- Provides calendar-based dose tracking with real-time constraints
- Shows adherence analytics
- Exports structured prescription data

## Models Used (Database)

Defined in `app/models/models.py`:

- **User**
- **Prescription**
- **Medicine**
- **Dose**
- **Notification**

Enums stored as strings:

- **PrescriptionStatusEnum** (`needs_review`, `active`, `completed`)
- **NotificationTypeEnum** (`upcoming`, `missed`, `completed`)

## Commands to Run the App

```powershell
cd c:\Users\HP\Downloads\Sanjeevani\mediscript_ai
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Tech Stack

- Backend: FastAPI, SQLAlchemy, Jinja2
- DB: SQLite (default) via SQLAlchemy
- Frontend: Jinja2 templates + TailwindCSS + vanilla JavaScript
- Charts: Chart.js (via CDN in templates)
- AI/Extraction: Google Gemini (`google-generativeai`), optional handwriting/OCR backend

## Project File Structure

```text
mediscript_ai/
  app/
    main.py
    config.py
    utils.py
    core/
      database.py
      security.py
    models/
      models.py
    schemas/
      schemas.py
    routers/
      auth.py
      upload.py
      workspace.py
      calendar.py
      notifications.py
      export.py
      dashboard.py
    services/
      analytics_service.py
      calendar_service.py
      export_service.py
      gemma_service.py
      handwriting_service.py
      notification_service.py
      translation_service.py
      validation_service.py
    templates/
      base.html
      home.html
      workspace.html
    assets/
  static/
  uploads/
  tests/
    test_gemma_service.py
  requirements.txt
  mediscript.db
  migrate_add_columns.py
  .env
```

## Setup

### 1) Create a virtual environment

```bash
python -m venv .venv
```

Activate:

- Windows PowerShell

```powershell
.venv\Scripts\Activate.ps1
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Configure environment variables

Create/edit `.env` in the project root.

Supported keys (see `app/config.py`):

- `DATABASE_URL` (default: `sqlite:///./mediscript.db`)
- `JWT_SECRET_KEY` (default in code is `CHANGE_ME_IN_PRODUCTION`)
- `HANDWRITING_MODEL_ENDPOINT` (optional)
- `HANDWRITING_RAPIDAPI_KEY` (optional)
- `GEMINI_API_KEY` (optional but required to run Gemini extraction)

### 4) Run the server

```bash
uvicorn app.main:app --reload
```

Open:

- Home page: `http://127.0.0.1:8000/`

## How the App Works (High Level)

- Upload a prescription image from the home page.
- The backend stores the file under `uploads/` and creates a `Prescription` record.
- The app then runs a unified extraction pipeline:
  - Medicine extraction (structured list)
  - Patient/Doctor details extraction
- Once medicines are confirmed, dose schedules are generated into the `doses` table.
- Calendar endpoints provide:
  - Monthly summaries
  - Daily dose lists
  - Dose toggle (taken/pending) with time window restrictions
  - Rescheduling of future dose times
- Analytics endpoints compute adherence/streaks and return a daily series for charts.

## Models Used

All database models are defined in `app/models/models.py` (SQLAlchemy ORM). These are the tables used by the application.

### 1) `User`

Represents an account that owns prescriptions.

- **Fields**
  - `id` (PK)
  - `email` (unique)
  - `hashed_password`
  - `created_at`
- **Relationships**
  - `prescriptions`: one-to-many with `Prescription`

### 2) `Prescription`

Represents a single uploaded prescription (image + extracted text + AI output).

- **Fields**
  - `id` (PK)
  - `user_id` (FK → `users.id`)
  - `title`
  - `caption`
  - `raw_text` (OCR result)
  - `image_path` (path under `uploads/`)
  - `confidence_score`
  - `status` (string values from `PrescriptionStatusEnum`)
  - `created_at`
  - `patient_details_json` (JSON stored as string)
  - `doctor_details_json` (JSON stored as string)
  - `transliterated_json` (language → text map as JSON string)
  - `export_overrides_json` (JSON string)
- **Relationships**
  - `user`: many-to-one with `User`
  - `medicines`: one-to-many with `Medicine` (cascade delete)
  - `doses`: one-to-many with `Dose` (cascade delete)
  - `notifications`: one-to-many with `Notification` (cascade delete)

### 3) `Medicine`

A medicine line item extracted from the prescription.

- **Fields**
  - `id` (PK)
  - `prescription_id` (FK → `prescriptions.id`)
  - `original_name`
  - `normalized_name`
  - `dose`
  - `frequency` (e.g., `OD`, `BD`, `TDS`, `PRN`)
  - `duration_days`
  - `instructions`
  - `confidence`
  - `explanation` (AI-generated uses/side-effects, etc.)
  - `age_range`
- **Relationships**
  - `prescription`: many-to-one with `Prescription`
  - `doses`: one-to-many with `Dose` (cascade delete)

### 4) `Dose`

A single scheduled dose instance for a specific medicine on a specific date/time.

- **Fields**
  - `id` (PK)
  - `prescription_id` (FK → `prescriptions.id`)
  - `medicine_id` (FK → `medicines.id`)
  - `date`
  - `time`
  - `taken` (bool)
  - `taken_at` (datetime when marked taken)
- **Relationships**
  - `prescription`: many-to-one with `Prescription`
  - `medicine`: many-to-one with `Medicine`

### 5) `Notification`

Represents scheduled/derived notifications about upcoming/missed/completed doses.

- **Fields**
  - `id` (PK)
  - `prescription_id` (FK → `prescriptions.id`)
  - `dose_id` (nullable FK → `doses.id`)
  - `type` (string values from `NotificationTypeEnum`)
  - `message`
  - `scheduled_for`
  - `sent`
  - `created_at`
- **Relationships**
  - `prescription`: many-to-one with `Prescription`

### Enums (stored as strings)

- `PrescriptionStatusEnum`
  - `needs_review`, `active`, `completed`
- `NotificationTypeEnum`
  - `upcoming`, `missed`, `completed`

## Pydantic Schemas Used (API DTOs)

Defined in `app/schemas/schemas.py`:

- `UserCreate`, `UserOut`
- `Token`
- `MedicineBase`, `MedicineCreate`, `MedicineOut`
- `PrescriptionBase`, `PrescriptionCreate`, `PrescriptionOut`
- `DoseOut`
- `AnalyticsSummary`
- `NotificationOut`
- `OCRResult`
- `GemmaMedicine`, `ExtractionResult`
- `PatientDoctorExtraction`

## Key Routes

- `app/routers/dashboard.py`
  - Basic dashboard/home navigation
- `app/routers/upload.py`
  - Upload prescription image
- `app/routers/workspace.py`
  - Workspace UI, unified extraction (`/workspace/{id}/refresh-all`), confirmation, edits
- `app/routers/calendar.py`
  - Calendar APIs (month/day summary, dose toggle, reschedule, analytics series)
- `app/routers/export.py`
  - Export endpoints
- `app/routers/notifications.py`
  - Notifications endpoints
- `app/routers/auth.py`
  - Authentication endpoints

## Notes

- DB initialization happens on startup in `app/main.py`.
- Default DB is SQLite (`mediscript.db`).
- If you change models, prefer a migration tool; this repo also contains a lightweight SQLite column-add approach in `main.py` and `migrate_add_columns.py`.
