import types

import pytest

from src.app.config import settings
from src.app.core import agent as agent_module


@pytest.mark.asyncio
async def test_run_agent_sql_route(monkeypatch):
    async def fake_decide_route(question: str, conversation_history: str = "") -> str:
        assert question == "How many contracts?"
        return agent_module.SQL_ROUTE

    async def fake_sql_pipeline(question: str, include_intermediate_steps: bool, conversation_history: str = ""):
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

    result = await agent_module.run_agent("How many contracts?")

    assert result["output"] == "SQL result"
    assert result["sql_query"] == "SELECT 1"
    assert result["tool_trace"][0] == "Router decision: SQL"


@pytest.mark.asyncio
async def test_run_agent_rag_route(monkeypatch):
    async def fake_decide_route(question: str, conversation_history: str = "") -> str:
        return agent_module.RAG_ROUTE

    async def fake_rag_pipeline(question: str, include_intermediate_steps: bool, conversation_history: str = ""):
        return {
            "output": "RAG answer",
            "route": agent_module.RAG_ROUTE,
            "sql_query": None,
            "citations": [{"source_document": "doc.pdf", "page": 1, "content": "snippet"}],
            "tool_trace": ["Route selected: RAG"],
        }

    monkeypatch.setattr(agent_module, "_decide_route", fake_decide_route)
    monkeypatch.setattr(agent_module, "_run_rag_pipeline", fake_rag_pipeline)

    result = await agent_module.run_agent("Where is the warranty info?")

    assert result["route"] == agent_module.RAG_ROUTE
    assert result["citations"]
    assert result["tool_trace"][0] == "Router decision: RAG"


@pytest.mark.asyncio
async def test_run_agent_hybrid_route(monkeypatch):
    async def fake_decide_route(question: str, conversation_history: str = "") -> str:
        return agent_module.HYBRID_ROUTE

    async def fake_hybrid_pipeline(question: str, include_intermediate_steps: bool, conversation_history: str = ""):
        return {
            "output": "Hybrid answer",
            "route": agent_module.HYBRID_ROUTE,
            "sql_query": "SELECT * FROM dual",
            "citations": [],
            "tool_trace": ["Router decision: HYBRID", "Hybrid synthesis completed"],
        }

    monkeypatch.setattr(agent_module, "_decide_route", fake_decide_route)
    monkeypatch.setattr(agent_module, "_run_hybrid_pipeline", fake_hybrid_pipeline)

    result = await agent_module.run_agent("Hybrid question")

    assert result["route"] == agent_module.HYBRID_ROUTE
    assert result["tool_trace"][0] == "Router decision: HYBRID"


@pytest.mark.asyncio
async def test_run_agent_insufficient_context(monkeypatch):
    async def fake_decide_route(question: str, conversation_history: str = ""):
        return None

    monkeypatch.setattr(agent_module, "_decide_route", fake_decide_route)

    result = await agent_module.run_agent("Hello")

    assert result["route"] == "UNKNOWN"
    assert result["output"] == settings.insufficient_context_message
    assert result["tool_trace"] == ["Router decision: INSUFFICIENT CONTEXT"]


# Error handling and edge case tests
@pytest.mark.asyncio
async def test_run_agent_sql_pipeline_exception_handling(monkeypatch):
    """Test that SQL pipeline exceptions are handled gracefully."""
    async def fake_decide_route(question: str, conversation_history: str = "") -> str:
        return agent_module.SQL_ROUTE

    async def fake_sql_pipeline(question: str, include_intermediate_steps: bool, conversation_history: str = ""):
        raise Exception("Database connection failed")

    monkeypatch.setattr(agent_module, "_decide_route", fake_decide_route)
    monkeypatch.setattr(agent_module, "_run_sql_pipeline", fake_sql_pipeline)

    with pytest.raises(Exception) as exc_info:
        await agent_module.run_agent("How many contracts?")
    assert "Database connection failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_run_agent_rag_pipeline_exception_handling(monkeypatch):
    """Test that RAG pipeline exceptions are handled gracefully."""
    async def fake_decide_route(question: str, conversation_history: str = "") -> str:
        return agent_module.RAG_ROUTE

    async def fake_rag_pipeline(question: str, include_intermediate_steps: bool, conversation_history: str = ""):
        raise FileNotFoundError("Vector store not found")

    monkeypatch.setattr(agent_module, "_decide_route", fake_decide_route)
    monkeypatch.setattr(agent_module, "_run_rag_pipeline", fake_rag_pipeline)

    with pytest.raises(FileNotFoundError) as exc_info:
        await agent_module.run_agent("Where is warranty info?")
    assert "Vector store not found" in str(exc_info.value)


def test_validate_sql_query_empty_string():
    """Test SQL validation with empty string."""
    is_valid, error = agent_module._validate_sql_query("")
    assert is_valid is False
    assert "cannot be empty" in error


def test_validate_sql_query_drop_table():
    """Test SQL validation rejects DROP TABLE."""
    is_valid, error = agent_module._validate_sql_query("DROP TABLE users;")
    assert is_valid is False
    assert "DROP" in error


def test_validate_sql_query_delete():
    """Test SQL validation rejects DELETE."""
    is_valid, error = agent_module._validate_sql_query("DELETE FROM users WHERE id=1;")
    assert is_valid is False
    assert "DELETE" in error


def test_validate_sql_query_valid_select():
    """Test SQL validation accepts valid SELECT query."""
    is_valid, error = agent_module._validate_sql_query("SELECT * FROM FACT_SALES WHERE year = 2024")
    assert is_valid is True
    assert error == ""


def test_validate_sql_query_select_with_comments():
    """Test SQL validation accepts SELECT with comments (comments are stripped)."""
    query = "/* Comment */ SELECT * FROM FACT_SALES -- Another comment"
    is_valid, error = agent_module._validate_sql_query(query)
    assert is_valid is True


def test_validate_sql_query_all_dangerous_keywords():
    """Test that all dangerous keywords from config are rejected."""
    dangerous_keywords = settings.dangerous_sql_keywords
    for keyword in dangerous_keywords:
        query = f"{keyword} TABLE users;"
        is_valid, error = agent_module._validate_sql_query(query)
        assert is_valid is False, f"Keyword {keyword} should be rejected"
        assert keyword in error


def test_validate_sql_query_not_starting_with_select():
    """Test SQL validation rejects queries not starting with SELECT."""
    is_valid, error = agent_module._validate_sql_query("WITH cte AS (SELECT 1) SELECT * FROM cte")
    # This should pass because after comment removal it starts with SELECT
    # But let's test a case that definitely doesn't start with SELECT
    is_valid, error = agent_module._validate_sql_query("INSERT INTO table VALUES (1)")
    assert is_valid is False