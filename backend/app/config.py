import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str = "sqlite:///./fitness.db"
    # LLM: "google" (Gemini via LangChain) | "openai"
    llm_provider: str = "google"
    llm_model: str = "gemini-2.5-flash"


settings = Settings()

# Keys the app reads from the shared project-root .env. LangChain / LangSmith read
# these straight from os.environ. The legacy DATABASE_URL / OPENAI Postgres values
# are intentionally NOT imported — the rebuilt app is SQLite + Gemini.
_SHARED_ENV_KEYS = (
    "GOOGLE_API_KEY",
    "OPENAI_API_KEY",
    "LANGCHAIN_TRACING_V2",
    "LANGSMITH_API_KEY",
    "LANGSMITH_PROJECT",
    "LANGSMITH_ENDPOINT",
    "USDA_API_KEY",
)


def load_project_env() -> None:
    """Load shared secrets from the project-root `.env` into os.environ (idempotent).

    Called at server startup / before a live agent run — NOT at import time, so the
    test suite stays hermetic (no API keys, no tracing).
    """
    from dotenv import dotenv_values

    root_env = Path(__file__).resolve().parents[2] / ".env"
    if not root_env.exists():
        return
    values = dotenv_values(root_env)
    for key in _SHARED_ENV_KEYS:
        if values.get(key):
            os.environ.setdefault(key, values[key])
