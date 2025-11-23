"""
Integration tests for security: SQL injection prevention and error information leakage.

These tests verify security mechanisms through HTTP endpoints.
"""
import pytest
from httpx import AsyncClient, ASGITransport

from src.app.config import settings
from src.app.main import app


class TestSQLInjectionPrevention:
    """Test SQL injection prevention mechanisms at API layer."""

    @pytest.mark.asyncio
    async def test_sql_injection_in_user_question_blocked(self, monkeypatch):
        """Test that SQL injection attempts in user questions are blocked at API layer."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Disable rate limiting for this test
            monkeypatch.setattr(settings, "enable_rate_limit", False)
            
            # Various SQL injection patterns
            injection_attempts = [
                "What are sales?; DROP TABLE users;",
                "Show data; DELETE FROM users WHERE 1=1;",
                "Sales info'; DROP TABLE users; --",
                "Query: ' OR '1'='1",
                "Data' UNION SELECT * FROM users --",
                "Sales'; UPDATE users SET password='hacked'; --",
                "Info'; INSERT INTO users VALUES ('hacker'); --",
                "Data'; ALTER TABLE users ADD COLUMN hacked TEXT; --",
                "Query'; TRUNCATE TABLE users; --",
                "Sales'; EXEC xp_cmdshell('rm -rf /'); --",
            ]

            for injection_attempt in injection_attempts:
                response = await client.post("/api/v1/ask", json={"question": injection_attempt})
                # Should be blocked at validation layer (422) or rejected
                assert response.status_code in [422, 400], \
                    f"Injection attempt '{injection_attempt}' was not blocked"

    @pytest.mark.asyncio
    async def test_all_dangerous_keywords_blocked_in_questions(self, monkeypatch):
        """Test that all dangerous SQL keywords from config are blocked in user questions."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Disable rate limiting for this test
            monkeypatch.setattr(settings, "enable_rate_limit", False)
            
            dangerous_keywords = settings.dangerous_sql_keywords

            for keyword in dangerous_keywords:
                injection_attempt = f"What are sales?; {keyword} TABLE users;"
                response = await client.post("/api/v1/ask", json={"question": injection_attempt})
                assert response.status_code in [422, 400], \
                    f"Keyword '{keyword}' was not blocked in user input"


class TestInputValidation:
    """Test input validation rules enforcement at API layer."""

    @pytest.mark.asyncio
    async def test_required_fields_enforced(self, monkeypatch):
        """Test that required fields are enforced."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Disable rate limiting for this test
            monkeypatch.setattr(settings, "enable_rate_limit", False)
            
            # Missing question field
            response = await client.post("/api/v1/ask", json={})
            assert response.status_code == 422

            # Null question
            response = await client.post("/api/v1/ask", json={"question": None})
            assert response.status_code == 422


class TestErrorInformationLeakage:
    """Test that error responses don't leak internal system information."""

    @pytest.mark.asyncio
    async def test_no_stack_traces_in_error_responses(self, monkeypatch):
        """Test that stack traces are not exposed in error responses."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Disable rate limiting for this test
            monkeypatch.setattr(settings, "enable_rate_limit", False)
            
            async def fake_run_agent(question: str, include_intermediate_steps: bool = True, conversation_history: str = ""):
                raise ValueError("Internal database error")

            import src.app.api.router as router_module
            monkeypatch.setattr(router_module, "run_agent", fake_run_agent)

            response = await client.post("/api/v1/ask", json={"question": "Test"})
            assert response.status_code == 500

            response_text = response.text
            # Verify no Python stack trace elements
            assert "Traceback" not in response_text
            assert "File \"" not in response_text
            assert "line " not in response_text
            assert "ValueError" not in response_text

    @pytest.mark.asyncio
    async def test_no_file_paths_in_error_responses(self, monkeypatch):
        """Test that file paths are not exposed in error responses."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Disable rate limiting for this test
            monkeypatch.setattr(settings, "enable_rate_limit", False)
            
            async def fake_run_agent(question: str, include_intermediate_steps: bool = True, conversation_history: str = ""):
                raise FileNotFoundError("/path/to/internal/database.db not found")

            import src.app.api.router as router_module
            monkeypatch.setattr(router_module, "run_agent", fake_run_agent)

            response = await client.post("/api/v1/ask", json={"question": "Test"})
            assert response.status_code == 500

            response_text = response.text
            # Verify no file paths are exposed
            assert "/path/to" not in response_text
            assert ".db" not in response_text or "internal" in response_text.lower()

    @pytest.mark.asyncio
    async def test_no_database_schemas_in_error_responses(self, monkeypatch):
        """Test that database schemas are not exposed in error responses."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Disable rate limiting for this test
            monkeypatch.setattr(settings, "enable_rate_limit", False)
            
            async def fake_run_agent(question: str, include_intermediate_steps: bool = True, conversation_history: str = ""):
                raise Exception("Table FACT_SALES does not exist")

            import src.app.api.router as router_module
            monkeypatch.setattr(router_module, "run_agent", fake_run_agent)

            response = await client.post("/api/v1/ask", json={"question": "Test"})
            assert response.status_code == 500

            response_text = response.text
            # Verify no table names are exposed
            assert "FACT_SALES" not in response_text
            assert "DIM_" not in response_text

    @pytest.mark.asyncio
    async def test_no_api_keys_in_error_responses(self, monkeypatch):
        """Test that API keys are not exposed in error responses."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Disable rate limiting for this test
            monkeypatch.setattr(settings, "enable_rate_limit", False)
            
            # Simulate an error that might include API key
            api_key = settings.openai_api_key
            async def fake_run_agent(question: str, include_intermediate_steps: bool = True, conversation_history: str = ""):
                raise Exception(f"OpenAI API error with key: {api_key}")

            import src.app.api.router as router_module
            monkeypatch.setattr(router_module, "run_agent", fake_run_agent)

            response = await client.post("/api/v1/ask", json={"question": "Test"})
            assert response.status_code in [500, 503]  # Accept both error codes

            response_text = response.text
            # Verify API key is not exposed
            assert api_key not in response_text
            assert "sk-" not in response_text

    @pytest.mark.asyncio
    async def test_generic_error_messages(self, monkeypatch):
        """Test that error messages are generic and don't expose internal details."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Disable rate limiting for this test
            monkeypatch.setattr(settings, "enable_rate_limit", False)
            
            error_scenarios = [
                (FileNotFoundError("Database file missing"), "file system"),
                (ConnectionError("Cannot connect to OpenAI"), "network"),
                (ValueError("Invalid SQL query"), "validation"),
                (Exception("Unexpected error"), "internal"),
            ]

            for error, error_type in error_scenarios:
                async def fake_run_agent(question: str, include_intermediate_steps: bool = True, conversation_history: str = ""):
                    raise error

                import src.app.api.router as router_module
                monkeypatch.setattr(router_module, "run_agent", fake_run_agent)

                response = await client.post("/api/v1/ask", json={"question": "Test"})
                assert response.status_code in [500, 503]

                detail = response.json()["detail"].lower()
                # Verify error message is generic
                assert "internal" in detail or "error" in detail or "unavailable" in detail
                # Verify specific error details are not exposed
                assert error_type not in detail or "internal" in detail

