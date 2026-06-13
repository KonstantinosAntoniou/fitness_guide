from app.config import Settings


def test_defaults_are_local_friendly():
    s = Settings(_env_file=None)
    assert s.database_url == "sqlite:///./fitness.db"
    assert s.llm_provider == "google"


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x/y")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    s = Settings(_env_file=None)
    assert s.database_url == "postgresql://x/y"
    assert s.llm_provider == "openai"
