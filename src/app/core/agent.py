from __future__ import annotations
import json
from functools import lru_cache
from typing import Any, Dict, Iterable, List
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.tools import Tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from src.app.config import settings
from src.app.infrastructure.llm import get_chat_llm
from src.app.infrastructure.vector_store import load_vector_store

def _format_documents(docs: Iterable) -> str:
    payload: List[Dict[str, Any]] = []
    for doc in docs:
        metadata = dict(doc.metadata or {})
        payload.append(
            {
                "source": metadata.get("source"),
                "page": metadata.get("page"),
                "content": doc.page_content,
            }
        )
    return json.dumps(payload, ensure_ascii=False)

def _run_rag_search(query: str) -> str:
    store = load_vector_store()
    docs = store.similarity_search(query, k=settings.rag_top_k)
    if not docs:
        return json.dumps([], ensure_ascii=False)
    return _format_documents(docs)

@lru_cache(maxsize=1)
def get_rag_tool() -> Tool:
    return Tool(
        name="knowledge_base_search",
        description=(
            "Use this for questions answerable from contracts, warranty policies, or owner's manuals. "
            "It returns JSON with the retrieved chunks, including source and page metadata."
        ),
        func=_run_rag_search,
    )


@lru_cache(maxsize=1)
def _get_rag_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a helpful assistant specialized in Lexus/Toyota documentation. "
                "Always ground answers in the retrieved context and cite sources mentioning the source path and page when available.",
            ),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
            ("user", "{input}"),
        ]
    )


@lru_cache(maxsize=1)
def get_rag_agent() -> AgentExecutor:
    llm = get_chat_llm()
    tool = get_rag_tool()
    prompt = _get_rag_prompt()
    agent = create_openai_tools_agent(llm, [tool], prompt)
    return AgentExecutor(agent=agent, tools=[tool])


def run_rag_agent(question: str, *, include_intermediate_steps: bool = True) -> Dict[str, Any]:
    agent = get_rag_agent()
    return agent.invoke(
        {"input": question},
        return_intermediate_steps=include_intermediate_steps,
    )
