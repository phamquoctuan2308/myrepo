from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

from src.config import get_settings


def get_llm(*, temperature: float | None = None) -> BaseChatModel:
    settings = get_settings()
    effective_temperature = settings.llm_temperature if temperature is None else temperature
    if settings.llm_provider == "groq":
        return ChatGroq(
            model=settings.model_name,
            api_key=settings.groq_api_key,
            temperature=effective_temperature,
        )
    if settings.llm_provider == "openai":
        return ChatOpenAI(
            model=settings.model_name,
            api_key=settings.openai_api_key,
            temperature=effective_temperature,
        )
    return ChatGoogleGenerativeAI(
        model=settings.model_name,
        google_api_key=settings.google_api_key,
        temperature=effective_temperature,
    )
