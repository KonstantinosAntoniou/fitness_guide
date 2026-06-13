from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./fitness.db"
    # LLM: "google" (Gemini via LangChain) | "openai"
    llm_provider: str = "google"
    llm_model: str = "gemini-2.5-flash"


settings = Settings()
