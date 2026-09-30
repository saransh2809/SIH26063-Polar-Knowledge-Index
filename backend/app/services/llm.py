"""The only place that talks to the language model (Google Gemini).

Every response is cached on disk under data/llm_cache/, keyed by model + prompt + schema.
That keeps development cheap and lets the demo run offline for questions already asked.
"""
import hashlib
import json
import logging
from typing import Any

from app.core.config import LLM_CACHE_DIR, get_settings

log = logging.getLogger(__name__)


class LLMNotConfigured(RuntimeError):
    """GEMINI_API_KEY or LLM_MODEL is missing from .env."""


class LLMUnavailable(RuntimeError):
    """The API call failed (network, quota, outage) and nothing was cached."""


_client = None


def _get_client():
    global _client
    settings = get_settings()
    if not settings.llm_configured:
        raise LLMNotConfigured("Set GEMINI_API_KEY and LLM_MODEL in .env to enable AI features.")
    if _client is None:
        from google import genai

        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def _cache_key(model: str, system: str, prompt: str, schema: dict | None) -> str:
    blob = json.dumps({"m": model, "s": system, "p": prompt, "j": schema}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def generate_json(system: str, prompt: str, schema: dict, *, use_cache: bool = True) -> Any:
    """Ask the model for JSON matching `schema` (a JSON-Schema-style dict). Temperature 0."""
    settings = get_settings()
    model = settings.llm_model or "unconfigured"
    key = _cache_key(model, system, prompt, schema)
    path = LLM_CACHE_DIR / f"{key}.json"
    if use_cache and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    client = _get_client()
    from google.genai import types

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=0,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        result = json.loads(response.text)
    except Exception as exc:
        log.warning("LLM call failed: %s", exc)
        raise LLMUnavailable(str(exc)) from exc

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result
