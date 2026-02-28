from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect
from sqlalchemy import text

from app.config import get_settings
from app.core.database import Base, engine
from app.routers import auth, upload, workspace, calendar, notifications, export, dashboard


settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def init_db() -> None:
    inspector = inspect(engine)
    if not inspector.get_table_names():
        Base.metadata.create_all(bind=engine)
        return

    # Lightweight schema migration for SQLite (keeps project runnable without a migration tool).
    try:
        cols = [c.get("name") for c in inspector.get_columns("prescriptions")]
        if "caption" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE prescriptions ADD COLUMN caption TEXT"))
        if "export_overrides_json" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE prescriptions ADD COLUMN export_overrides_json TEXT"))
    except Exception:
        # If introspection or ALTER fails, skip migration (app can still run; caption will remain unavailable).
        pass


static_dir = settings.static_dir
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

uploads_dir = settings.uploads_dir
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


app.include_router(dashboard.router)
app.include_router(auth.router)
app.include_router(upload.router)
app.include_router(workspace.router)
app.include_router(calendar.router)
app.include_router(notifications.router)
app.include_router(export.router)


@app.on_event("startup")
async def on_startup():
    init_db()

