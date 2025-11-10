from __future__ import annotations
from functools import lru_cache
from langchain_openai import ChatOpenAI
from src.app.config import settings


def _build_chat_llm(model: str, temperature: float) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=settings.openai_api_key,
    )

@lru_cache(maxsize=1)
def get_sql_llm() -> ChatOpenAI:
    return _build_chat_llm(settings.sql_llm_model, settings.sql_llm_temperature)

@lru_cache(maxsize=1)
def get_router_llm() -> ChatOpenAI:
    return _build_chat_llm(settings.router_llm_model, settings.router_llm_temperature)

@lru_cache(maxsize=1)
def get_synthesis_llm() -> ChatOpenAI:
    return _build_chat_llm(settings.synthesis_llm_model, settings.synthesis_llm_temperature)


@lru_cache(maxsize=1)
def get_split_llm() -> ChatOpenAI:
    return _build_chat_llm(settings.split_llm_model, settings.split_llm_temperature)
