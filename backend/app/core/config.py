"""Application settings, read from the repo-root .env file."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
OCR_DIR = DATA_DIR / "ocr"
LLM_CACHE_DIR = DATA_DIR / "llm_cache"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    database_url: str = "postgresql+psycopg://ncpor:change-me@localhost:5433/ncpor"

    # Language model providers (see app/services/llm.py).
    llm_provider: str = "gemini"
    llm_fallback_provider: str | None = None
    llm_bulk_provider: str | None = None
    gemini_api_key: str | None = None
    llm_model: str | None = None
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    ollama_timeout_seconds: float = 300.0

    embedding_model: str = "intfloat/multilingual-e5-base"
    # Refusal thresholds on cosine similarity (0-1). Calibrated in docs/decisions.md.
    qa_min_similarity: float = 0.82
    qa_strong_similarity: float = 0.86
    tesseract_cmd: str | None = None

    jwt_secret: str = "dev-only-insecure-secret"
    jwt_expiry_minutes: int = 12 * 60

    harvest_user_agent: str = "NCPOR-Polar-Index-SIH-Prototype/0.1 (student project)"
    harvest_min_interval_seconds: float = 1.0

    @property
    def llm_configured(self) -> bool:
        placeholder = ("your-", "change-me")
        key, model = self.gemini_api_key or "", self.llm_model or ""
        return bool(key and model) and not key.startswith(placeholder) and not model.startswith(placeholder)


@lru_cache
def get_settings() -> Settings:
    return Settings()
