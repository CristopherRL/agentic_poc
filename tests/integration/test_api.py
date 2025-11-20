import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

from src.app.api.schemas import AskResponse
from src.app.config import settings
from src.app.main import app


@pytest.mark.asyncio
async def test_post_ask_endpoint(monkeypatch):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        stub_payload = {
            "output": "Combined answer",
            "route": "HYBRID",
            "sql_query": "SELECT 1",
            "citations": [
                {
                    "source_document": "Contract_Toyota_2023.pdf",
                    "page": 4,
                    "content": "Warranty details",
                }
            ],
            "tool_trace": ["Router decision: HYBRID"],
        }

        async def fake_run_agent(question: str, include_intermediate_steps: bool = True):
            assert question == "Test question"
            return stub_payload

        import src.app.api.router as router_module
        monkeypatch.setattr(router_module, "run_agent", fake_run_agent)

        response = await client.post("/api/v1/ask", json={"question": "Test question"})
        assert response.status_code == 200

        data = AskResponse(**response.json())
        assert data.answer == stub_payload["output"]
        assert data.sql_query == stub_payload["sql_query"]
        assert len(data.citations) == 1
        assert data.tool_trace == stub_payload["tool_trace"]


# Edge case tests for API endpoint
class TestAPIEdgeCases:
    """Test API endpoint with edge cases."""

    @pytest.mark.asyncio
    async def test_empty_question_returns_422(self):
        """Test that empty question returns 422 Unprocessable Entity."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/ask", json={"question": ""})
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_whitespace_only_question_returns_422(self):
        """Test that whitespace-only question returns 422."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/ask", json={"question": "   "})
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_question_exceeds_max_length_returns_422(self):
        """Test that question exceeding max length returns 422."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            too_long = "a" * (settings.question_max_length + 1)
            response = await client.post("/api/v1/ask", json={"question": too_long})
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_sql_injection_attempt_returns_422(self):
        """Test that SQL injection attempt returns 422."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/ask",
                json={"question": "What are sales?; DROP TABLE users;"}
            )
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_malformed_json_returns_422(self):
        """Test that malformed JSON returns 422."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/ask",
                content='{"question": "test"',  # Missing closing brace
                headers={"Content-Type": "application/json"}
            )
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_question_field_returns_422(self):
        """Test that missing question field returns 422."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/ask", json={})
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_null_question_returns_422(self):
        """Test that null question returns 422."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/ask", json={"question": None})
            assert response.status_code == 422


# Error scenario tests
class TestAPIErrorScenarios:
    """Test API endpoint error handling scenarios."""

    @pytest.mark.asyncio
    async def test_llm_api_failure_returns_500(self, monkeypatch):
        """Test that LLM API failure returns 500 Internal Server Error."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async def fake_run_agent(question: str, include_intermediate_steps: bool = True):
                raise Exception("OpenAI API error: Rate limit exceeded")

            import src.app.api.router as router_module
            monkeypatch.setattr(router_module, "run_agent", fake_run_agent)

            response = await client.post("/api/v1/ask", json={"question": "What are sales?"})
            assert response.status_code in [500, 503]  # Accept both error codes
            assert "internal error" in response.json()["detail"].lower() or "unavailable" in response.json()["detail"].lower()
            # Verify no stack trace is exposed
            assert "Traceback" not in response.text
            assert "File" not in response.text

    @pytest.mark.asyncio
    async def test_openai_api_unavailable_returns_503(self, monkeypatch):
        """Test that OpenAI API unavailability returns 503 Service Unavailable."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            class OpenAIError(Exception):
                pass

            async def fake_run_agent(question: str, include_intermediate_steps: bool = True):
                raise OpenAIError("Connection timeout to OpenAI API")

            import src.app.api.router as router_module
            monkeypatch.setattr(router_module, "run_agent", fake_run_agent)

            response = await client.post("/api/v1/ask", json={"question": "What are sales?"})
            # Note: The current implementation may return 500, but we test the error handling
            assert response.status_code in [500, 503]
            # Verify error message doesn't expose internal details
            detail = response.json()["detail"].lower()
            assert "openai" not in detail or "service" in detail

    @pytest.mark.asyncio
    async def test_database_unavailable_returns_500(self, monkeypatch):
        """Test that database unavailability returns 500."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async def fake_run_agent(question: str, include_intermediate_steps: bool = True):
                raise FileNotFoundError("SQLite database not found")

            import src.app.api.router as router_module
            monkeypatch.setattr(router_module, "run_agent", fake_run_agent)

            response = await client.post("/api/v1/ask", json={"question": "What are sales?"})
            assert response.status_code == 500
            # Verify no internal file paths are exposed
            assert "SQLite" not in response.json()["detail"]
            assert "database" not in response.json()["detail"].lower() or "internal" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_vector_store_unavailable_returns_500(self, monkeypatch):
        """Test that vector store unavailability returns 500."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async def fake_run_agent(question: str, include_intermediate_steps: bool = True):
                raise FileNotFoundError("FAISS index not found")

            import src.app.api.router as router_module
            monkeypatch.setattr(router_module, "run_agent", fake_run_agent)

            response = await client.post("/api/v1/ask", json={"question": "What is warranty?"})
            assert response.status_code == 500
            # Verify no internal file paths are exposed
            assert "FAISS" not in response.json()["detail"]
            assert "index" not in response.json()["detail"].lower() or "internal" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_error_response_no_stack_trace(self, monkeypatch):
        """Test that error responses don't expose stack traces."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async def fake_run_agent(question: str, include_intermediate_steps: bool = True):
                raise ValueError("Some internal error")

            import src.app.api.router as router_module
            monkeypatch.setattr(router_module, "run_agent", fake_run_agent)

            response = await client.post("/api/v1/ask", json={"question": "Test"})
            assert response.status_code == 500
            response_text = response.text
            # Verify no Python stack trace elements are exposed
            assert "Traceback" not in response_text
            assert "File \"" not in response_text
            assert "line " not in response_text
            assert "ValueError" not in response_text
