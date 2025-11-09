from __future__ import annotations
from functools import lru_cache
from langchain_openai import ChatOpenAI
from src.app.config import settings

@lru_cache(maxsize=1)
def get_chat_llm(model: str | None = None, temperature: float | None = None) -> ChatOpenAI:
    return ChatOpenAI(
        model=model or settings.llm_model,
        temperature=temperature if temperature is not None else settings.llm_temperature,
        api_key=settings.openai_api_key,
    )
