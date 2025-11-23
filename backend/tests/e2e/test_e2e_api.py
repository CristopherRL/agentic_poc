"""
End-to-end tests for the API endpoint.

These tests make real requests to the API without mocks.
They require:
- Database to be ingested (SQLite)
- Vector store to be built (FAISS)
- OpenAI API key configured (tests will skip if not available)
"""

import os
import pytest
from httpx import AsyncClient, ASGITransport

from src.app.main import app


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_health_check():
    """Test that the health check endpoint works."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_ask_endpoint_sql_question():
    """Test SQL-only question end-to-end."""
    # Skip if OpenAI API key is not configured
    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "test-key-for-tests-only":
        pytest.skip("OpenAI API key not configured for E2E tests")
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/ask",
            json={"question": "What were RAV4 sales in Germany in 2024?"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "answer" in data
        assert "sql_query" in data
        assert "session_id" in data
        assert data["sql_query"] is not None


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_ask_endpoint_rag_question():
    """Test RAG-only question end-to-end."""
    # Skip if OpenAI API key is not configured
    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "test-key-for-tests-only":
        pytest.skip("OpenAI API key not configured for E2E tests")
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/ask",
            json={"question": "What is the standard Toyota warranty for Europe?"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "answer" in data
        assert "citations" in data
        assert "session_id" in data
        assert len(data["citations"]) > 0


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_conversation_memory():
    """Test conversation memory across multiple requests."""
    # Skip if OpenAI API key is not configured
    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "test-key-for-tests-only":
        pytest.skip("OpenAI API key not configured for E2E tests")
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # First request
        response1 = await client.post(
            "/api/v1/ask",
            json={"question": "What were RAV4 sales in Germany in 2024?"}
        )
        assert response1.status_code == 200
        data1 = response1.json()
        session_id = data1["session_id"]
        
        # Second request with same session_id
        response2 = await client.post(
            "/api/v1/ask",
            json={"question": "And what about France?", "session_id": session_id}
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["session_id"] == session_id

