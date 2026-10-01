"""The only place that talks to a language model: Google Gemini, or a local model via Ollama.

Which one is used is set in .env:
  LLM_PROVIDER           gemini | ollama            main provider for answers, lessons, checker, Hindi
  LLM_FALLBACK_PROVIDER  ollama (optional)          tried when the main provider fails (quota, outage)
  LLM_BULK_PROVIDER      ollama (optional)          for bulk jobs: link tagging, drafting test questions

Every response is cached on disk under data/llm_cache/, keyed by model + prompt + schema.
That keeps development cheap and lets the demo run offline for questions already asked.
"""
import copy
import hashlib
import json
import logging
import time
from typing import Any

import httpx

from app.core.config import LLM_CACHE_DIR, get_settings

log = logging.getLogger(__name__)
RETRIES = 4  # waits 2, 4, 8, 16 seconds
PROVIDERS = ("gemini", "ollama")


class LLMNotConfigured(RuntimeError):
    """The chosen provider is missing settings in .env (e.g. GEMINI_API_KEY / LLM_MODEL)."""


class LLMUnavailable(RuntimeError):
    """The call failed (network, quota, outage, local model not running) and nothing was cached."""


# --- cache ---------------------------------------------------------------------------------
def _cache_key(model: str, system: str, prompt: str, schema: dict | None) -> str:
    blob = json.dumps({"m": model, "s": system, "p": prompt, "j": schema}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def _model_id(provider: str) -> str:
    """Cache identity of the model. Gemini keeps the bare model name so existing cache stays valid."""
    settings = get_settings()
    if provider == "ollama":
        return f"ollama:{settings.ollama_model}"
    return settings.llm_model or "unconfigured"


# --- Gemini ----------------------------------------------------------------------------------
_gemini_client = None
# Free-tier friendly: once Gemini's daily quota is used up (or it stays overloaded), skip it for a
# while and go straight to the fallback instead of failing on every call first.
_gemini_paused_until = 0.0
PAUSE_AFTER_DAILY_QUOTA = 3600  # seconds
PAUSE_AFTER_OVERLOAD = 300


def _pause_gemini(seconds: float, reason: str) -> None:
    global _gemini_paused_until
    _gemini_paused_until = time.monotonic() + seconds
    log.warning("Gemini paused for %d min: %s", seconds // 60, reason)


def _gemini(system: str, prompt: str, schema: dict) -> Any:
    global _gemini_client
    settings = get_settings()
    if not settings.llm_configured:
        raise LLMNotConfigured("Set GEMINI_API_KEY and LLM_MODEL in .env to use Gemini.")
    if time.monotonic() < _gemini_paused_until:
        raise LLMUnavailable("Gemini paused after quota/overload errors; using the fallback.")
    from google import genai
    from google.genai import errors, types

    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=settings.gemini_api_key)
    model = settings.llm_model
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=0,
        response_mime_type="application/json",
        response_schema=schema,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    for attempt in range(RETRIES + 1):
        try:
            response = _gemini_client.models.generate_content(model=model, contents=prompt, config=config)
            return json.loads(response.text)
        except errors.APIError as exc:
            if exc.code == 429 and "PerDay" in str(exc):
                # A daily quota does not come back in seconds: fail fast with a clear reason.
                _pause_gemini(PAUSE_AFTER_DAILY_QUOTA, f"daily quota for {model} used up")
                raise LLMUnavailable(
                    f"Daily request quota for {model} is used up (Gemini free tier). "
                    "Try again tomorrow, use another model, or enable billing."
                ) from exc
            # 429 (rate limit) and 5xx (overloaded) are usually temporary: wait and retry.
            if exc.code in (429, 500, 502, 503, 504) and attempt < RETRIES:
                wait = 2 ** (attempt + 1)
                log.info("LLM busy (%s); retrying in %ss", exc.code, wait)
                time.sleep(wait)
                continue
            if exc.code in (429, 500, 502, 503, 504):
                _pause_gemini(PAUSE_AFTER_OVERLOAD, f"still {exc.code} after {RETRIES} retries")
            log.warning("LLM call failed: %s %s", exc.code, str(exc)[:160])
            raise LLMUnavailable(str(exc)[:300]) from exc
        except Exception as exc:
            log.warning("LLM call failed: %s", exc)
            raise LLMUnavailable(str(exc)[:300]) from exc
    raise LLMUnavailable("Gemini retries exhausted")


# --- Ollama (local) ------------------------------------------------------------------------------
def to_json_schema(schema: Any) -> Any:
    """Gemini schemas mark optional objects with "nullable": true; standard JSON Schema uses a type list."""
    if isinstance(schema, list):
        return [to_json_schema(s) for s in schema]
    if not isinstance(schema, dict):
        return schema
    out = {k: to_json_schema(v) for k, v in schema.items() if k != "nullable"}
    if schema.get("nullable") and "type" in out:
        out["type"] = [out["type"], "null"]
    return out


def _ollama(system: str, prompt: str, schema: dict) -> Any:
    settings = get_settings()
    body = {
        "model": settings.ollama_model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "format": to_json_schema(copy.deepcopy(schema)),  # constrained decoding to the schema
        "stream": False,
        "think": False,  # reasoning models (qwen3) answer directly
        "options": {"temperature": 0, "num_ctx": 16384},
    }
    try:
        resp = httpx.post(f"{settings.ollama_url}/api/chat", json=body, timeout=settings.ollama_timeout_seconds)
    except httpx.HTTPError as exc:
        raise LLMUnavailable(
            f"Local model not reachable at {settings.ollama_url} ({type(exc).__name__}). Is Ollama running?"
        ) from exc
    if resp.status_code != 200:
        raise LLMUnavailable(f"Ollama error {resp.status_code}: {resp.text[:200]}")
    try:
        return json.loads(resp.json()["message"]["content"])
    except (KeyError, json.JSONDecodeError) as exc:
        raise LLMUnavailable(f"Local model returned invalid JSON: {exc}") from exc


_CALL = {"gemini": _gemini, "ollama": _ollama}


# --- public entry point -----------------------------------------------------------------------------
def providers_for(purpose: str) -> list[str]:
    """Ordered providers to try. `purpose` is "default" or "bulk"."""
    settings = get_settings()
    first = settings.llm_bulk_provider if purpose == "bulk" and settings.llm_bulk_provider else settings.llm_provider
    order = [first]
    if settings.llm_fallback_provider and settings.llm_fallback_provider not in order:
        order.append(settings.llm_fallback_provider)
    for p in order:
        if p not in PROVIDERS:
            raise LLMNotConfigured(f"Unknown LLM provider '{p}'. Use one of: {', '.join(PROVIDERS)}.")
    return order


def generate_json(system: str, prompt: str, schema: dict, *, use_cache: bool = True, purpose: str = "default") -> Any:
    """Ask a model for JSON matching `schema` (a JSON-Schema-style dict). Temperature 0.

    Tries the main provider, then the fallback provider if one is set. A cached response from any
    provider in the list is used before calling anything.
    """
    order = providers_for(purpose)
    if use_cache:
        for provider in order:
            path = LLM_CACHE_DIR / f"{_cache_key(_model_id(provider), system, prompt, schema)}.json"
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))

    errors: list[str] = []
    for provider in order:
        try:
            result = _CALL[provider](system, prompt, schema)
        except LLMNotConfigured as exc:
            errors.append(str(exc))
            continue
        except LLMUnavailable as exc:
            errors.append(f"{provider}: {exc}")
            if provider != order[-1]:
                log.warning("%s failed; falling back to %s", provider, order[order.index(provider) + 1])
            continue
        path = LLM_CACHE_DIR / f"{_cache_key(_model_id(provider), system, prompt, schema)}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        return result

    if all("Set GEMINI_API_KEY" in e or "Unknown LLM provider" in e for e in errors):
        raise LLMNotConfigured("; ".join(errors))
    raise LLMUnavailable(" | ".join(errors))
