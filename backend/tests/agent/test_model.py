import pytest
from app.agent.model import make_chat_model


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setattr("app.agent.model.settings.llm_provider", "nope")
    with pytest.raises(ValueError):
        make_chat_model()


def test_google_model_built(monkeypatch):
    monkeypatch.setattr("app.agent.model.settings.llm_provider", "google")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    model = make_chat_model()
    assert "gemini" in model.model.lower()
