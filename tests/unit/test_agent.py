import types

import pytest

from src.app.config import settings
from src.app.core import agent as agent_module


def test_run_agent_sql_route(monkeypatch):
    def fake_decide_route(question: str) -> str:
        assert question == "How many contracts?"
        return agent_module.SQL_ROUTE

    def fake_sql_pipeline(question: str, include_intermediate_steps: bool):
        assert include_intermediate_steps is True
        return {
            "output": "SQL result",
            "route": agent_module.SQL_ROUTE,
            "sql_query": "SELECT 1",
            "citations": [],
            "tool_trace": ["Route selected: SQL"],
        }

    monkeypatch.setattr(agent_module, "_decide_route", fake_decide_route)
    monkeypatch.setattr(agent_module, "_run_sql_pipeline", fake_sql_pipeline)

    result = agent_module.run_agent("How many contracts?")

    assert result["output"] == "SQL result"
    assert result["sql_query"] == "SELECT 1"
    assert result["tool_trace"][0] == "Router decision: SQL"


def test_run_agent_rag_route(monkeypatch):
    def fake_decide_route(question: str) -> str:
        return agent_module.RAG_ROUTE

    def fake_rag_pipeline(question: str, include_intermediate_steps: bool):
        return {
            "output": "RAG answer",
            "route": agent_module.RAG_ROUTE,
            "sql_query": None,
            "citations": [{"source_document": "doc.pdf", "page": 1, "content": "snippet"}],
            "tool_trace": ["Route selected: RAG"],
        }

    monkeypatch.setattr(agent_module, "_decide_route", fake_decide_route)
    monkeypatch.setattr(agent_module, "_run_rag_pipeline", fake_rag_pipeline)

    result = agent_module.run_agent("Where is the warranty info?")

    assert result["route"] == agent_module.RAG_ROUTE
    assert result["citations"]
    assert result["tool_trace"][0] == "Router decision: RAG"


def test_run_agent_hybrid_route(monkeypatch):
    def fake_decide_route(question: str) -> str:
        return agent_module.HYBRID_ROUTE

    def fake_hybrid_pipeline(question: str, include_intermediate_steps: bool):
        return {
            "output": "Hybrid answer",
            "route": agent_module.HYBRID_ROUTE,
            "sql_query": "SELECT * FROM dual",
            "citations": [],
            "tool_trace": ["Router decision: HYBRID", "Hybrid synthesis completed"],
        }

    monkeypatch.setattr(agent_module, "_decide_route", fake_decide_route)
    monkeypatch.setattr(agent_module, "_run_hybrid_pipeline", fake_hybrid_pipeline)

    result = agent_module.run_agent("Hybrid question")

    assert result["route"] == agent_module.HYBRID_ROUTE
    assert result["tool_trace"][0] == "Router decision: HYBRID"


def test_run_agent_insufficient_context(monkeypatch):
    def fake_decide_route(question: str):
        return None

    monkeypatch.setattr(agent_module, "_decide_route", fake_decide_route)

    result = agent_module.run_agent("Hello")

    assert result["route"] == "UNKNOWN"
    assert result["output"] == settings.insufficient_context_message
    assert result["tool_trace"] == ["Router decision: INSUFFICIENT CONTEXT"]
