"""Provider-agnostic chat-model factory. Defaults to Gemini (AI Studio key)."""
from app.config import settings


def make_chat_model(model_name: str | None = None, temperature: float = 0.2):
    provider = settings.llm_provider
    name = model_name or settings.llm_model
    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=name, temperature=temperature)
    if provider == "openai":
        from langchain_openai import ChatOpenAI  # requires `uv add langchain-openai`
        return ChatOpenAI(model=name, temperature=temperature)
    raise ValueError(f"unsupported llm_provider: {provider!r}")
