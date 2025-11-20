"""
Security tests for SQL injection prevention, input validation, and error information leakage.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

from src.app.api.schemas import AskRequest
from src.app.config import settings
from src.app.core import agent as agent_module
from src.app.main import app


class TestSQLInjectionPrevention:
    """Test SQL injection prevention mechanisms."""

    @pytest.mark.asyncio
    async def test_sql_injection_in_user_question_blocked(self):
        """Test that SQL injection attempts in user questions are blocked at API layer."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
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

    def test_sql_injection_in_generated_query_blocked(self, monkeypatch):
        """Test that if LLM generates malicious SQL, it's blocked before execution."""
        # This test doesn't need TestClient - it directly tests the validation function
        # The query validation should happen in the SQL pipeline
        # This test verifies that _validate_sql_query would reject it
        is_valid, error = agent_module._validate_sql_query("DROP TABLE users;")
        assert is_valid is False
        assert "DROP" in error

    @pytest.mark.asyncio
    async def test_all_dangerous_keywords_blocked_in_questions(self):
        """Test that all dangerous SQL keywords from config are blocked in user questions."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            dangerous_keywords = settings.dangerous_sql_keywords

            for keyword in dangerous_keywords:
                injection_attempt = f"What are sales?; {keyword} TABLE users;"
                response = await client.post("/api/v1/ask", json={"question": injection_attempt})
                assert response.status_code in [422, 400], \
                    f"Keyword '{keyword}' was not blocked in user input"

    def test_sql_validation_blocks_all_dangerous_operations(self):
        """Test that SQL validation blocks all dangerous operations."""
        dangerous_queries = [
            "DROP TABLE users;",
            "DELETE FROM users;",
            "UPDATE users SET password='hacked';",
            "INSERT INTO users VALUES ('hacker');",
            "ALTER TABLE users ADD COLUMN hacked TEXT;",
            "TRUNCATE TABLE users;",
            "EXEC xp_cmdshell('rm -rf /');",
            "EXECUTE sp_delete_database('production');",
            "MERGE INTO users USING hackers;",
            "REPLACE INTO users VALUES ('hacker');",
        ]

        for query in dangerous_queries:
            is_valid, error = agent_module._validate_sql_query(query)
            assert is_valid is False, f"Query '{query}' should be rejected"
            assert error != "", f"Error message should not be empty for '{query}'"

    def test_valid_select_queries_allowed(self):
        """Test that valid SELECT queries are allowed."""
        valid_queries = [
            "SELECT * FROM FACT_SALES",
            "SELECT COUNT(*) FROM FACT_SALES WHERE year = 2024",
            "SELECT fs.contracts, dm.model_name FROM FACT_SALES fs JOIN DIM_MODEL dm ON fs.model_id = dm.model_id",
            "SELECT * FROM FACT_SALES WHERE year = 2024 GROUP BY month",
            "SELECT SUM(contracts) as total FROM FACT_SALES",
        ]

        for query in valid_queries:
            is_valid, error = agent_module._validate_sql_query(query)
            assert is_valid is True, f"Valid query '{query}' should be allowed"
            assert error == "", f"Error message should be empty for valid query '{query}'"


class TestInputValidation:
    """Test input validation rules enforcement."""

    def test_max_length_enforced(self):
        """Test that max_length constraint is enforced."""
        max_length = settings.question_max_length

        # Valid: at max length
        request = AskRequest(question="a" * max_length)
        assert len(request.question) == max_length

        # Invalid: exceeds max length
        with pytest.raises(Exception):  # ValidationError from Pydantic
            AskRequest(question="a" * (max_length + 1))

    def test_min_length_enforced(self):
        """Test that min_length constraint is enforced."""
        # Invalid: empty string
        with pytest.raises(Exception):
            AskRequest(question="")

        # Invalid: whitespace only
        with pytest.raises(Exception):
            AskRequest(question="   ")

    def test_special_characters_validation(self):
        """Test that special characters are properly validated."""
        # SQL injection characters should be rejected
        with pytest.raises(Exception):
            AskRequest(question="What are sales?; DROP TABLE users;")

        # But legitimate special characters should be allowed
        valid_questions = [
            "What are sales in Q1-Q2?",
            "Show me data (all models)",
            "What's the revenue?",
            "Compare Toyota vs Lexus: which is better?",
        ]

        for question in valid_questions:
            request = AskRequest(question=question)
            assert request.question == question.strip()

    @pytest.mark.asyncio
    async def test_required_fields_enforced(self):
        """Test that required fields are enforced."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
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
            async def fake_run_agent(question: str, include_intermediate_steps: bool = True):
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
            async def fake_run_agent(question: str, include_intermediate_steps: bool = True):
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
            async def fake_run_agent(question: str, include_intermediate_steps: bool = True):
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
            # Simulate an error that might include API key
            api_key = settings.openai_api_key
            async def fake_run_agent(question: str, include_intermediate_steps: bool = True):
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
            error_scenarios = [
                (FileNotFoundError("Database file missing"), "file system"),
                (ConnectionError("Cannot connect to OpenAI"), "network"),
                (ValueError("Invalid SQL query"), "validation"),
                (Exception("Unexpected error"), "internal"),
            ]

            for error, error_type in error_scenarios:
                async def fake_run_agent(question: str, include_intermediate_steps: bool = True):
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

