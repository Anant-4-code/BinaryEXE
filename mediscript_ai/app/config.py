from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "MediScript AI"
    debug: bool = True

    # Database
    database_url: str = "sqlite:///./mediscript.db"

    # Security
    jwt_secret_key: str = "CHANGE_ME_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    # Uploads & static
    base_dir: Path = Path(__file__).resolve().parent.parent
    static_dir: Path = base_dir / "static"
    uploads_dir: Path = base_dir / "uploads"

    # AI backends
    handwriting_model_endpoint: Optional[AnyHttpUrl] = None
    handwriting_rapidapi_key: Optional[str] = None
    gemini_api_key: Optional[str] = None

    # Ollama configuration
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"

    # OCR configuration
    ocr_engine: str = "rapidapi"
    tesseract_cmd: Optional[str] = None

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()

