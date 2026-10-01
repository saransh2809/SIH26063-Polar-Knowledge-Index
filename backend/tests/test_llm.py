"""Provider selection and fallback for the language-model layer (no network calls)."""
import pytest

from app.core.config import get_settings
from app.services import llm


@pytest.fixture
def settings(monkeypatch, tmp_path):
    s = get_settings()
    monkeypatch.setattr(llm, "LLM_CACHE_DIR", tmp_path)  # never read or write the real cache
    for field, value in {"llm_provider": "gemini", "llm_fallback_provider": None, "llm_bulk_provider": None}.items():
        monkeypatch.setattr(s, field, value)
    return s


def test_nullable_becomes_type_list():
    schema = {"type": "object", "properties": {"e": {"type": "object", "nullable": True, "properties": {}}}}
    out = llm.to_json_schema(schema)
    assert out["properties"]["e"]["type"] == ["object", "null"]
    assert "nullable" not in out["properties"]["e"]


def test_provider_order(settings, monkeypatch):
    assert llm.providers_for("default") == ["gemini"]
    monkeypatch.setattr(settings, "llm_fallback_provider", "ollama")
    monkeypatch.setattr(settings, "llm_bulk_provider", "ollama")
    assert llm.providers_for("default") == ["gemini", "ollama"]
    assert llm.providers_for("bulk") == ["ollama"]
    monkeypatch.setattr(settings, "llm_provider", "claude")
    with pytest.raises(llm.LLMNotConfigured):
        llm.providers_for("default")


def test_falls_back_when_main_provider_fails(settings, monkeypatch):
    monkeypatch.setattr(settings, "llm_fallback_provider", "ollama")
    calls = []

    def gemini_down(system, prompt, schema):
        calls.append("gemini")
        raise llm.LLMUnavailable("quota")

    def ollama_ok(system, prompt, schema):
        calls.append("ollama")
        return {"ok": True}

    monkeypatch.setitem(llm._CALL, "gemini", gemini_down)
    monkeypatch.setitem(llm._CALL, "ollama", ollama_ok)
    assert llm.generate_json("s", "p", {"type": "object"}) == {"ok": True}
    assert calls == ["gemini", "ollama"]
    # Second call is served from the cache written by the fallback provider.
    assert llm.generate_json("s", "p", {"type": "object"}) == {"ok": True}
    assert calls == ["gemini", "ollama"]


def test_all_providers_down_is_unavailable(settings, monkeypatch):
    monkeypatch.setattr(settings, "llm_fallback_provider", "ollama")

    def down(system, prompt, schema):
        raise llm.LLMUnavailable("down")

    monkeypatch.setitem(llm._CALL, "gemini", down)
    monkeypatch.setitem(llm._CALL, "ollama", down)
    with pytest.raises(llm.LLMUnavailable):
        llm.generate_json("s", "p", {"type": "object"})
