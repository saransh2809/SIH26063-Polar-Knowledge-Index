from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    """Reports whether the database and the pgvector extension are reachable."""
    result: dict = {"status": "ok", "database": "unreachable", "pgvector": None}
    try:
        db.execute(text("SELECT 1"))
        result["database"] = "ok"
        version = db.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar()
        result["pgvector"] = version or "not installed"
    except Exception as exc:  # report, don't crash, so the check itself stays usable
        result["error"] = type(exc).__name__
    if result["database"] != "ok" or not result["pgvector"] or result["pgvector"] == "not installed":
        result["status"] = "degraded"
    settings = get_settings()
    result["llm_configured"] = settings.llm_configured or settings.llm_provider == "ollama"
    result["llm"] = {
        "provider": settings.llm_provider,
        "fallback": settings.llm_fallback_provider or None,
        "bulk": settings.llm_bulk_provider or None,
        "gemini_model": settings.llm_model if settings.llm_configured else None,
        "ollama_model": settings.ollama_model,
    }
    return result
