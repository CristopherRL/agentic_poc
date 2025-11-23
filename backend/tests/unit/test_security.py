"""
Unit tests for security: SQL validation and input validation.

These tests verify security mechanisms directly without HTTP layer.
"""
import pytest

from src.app.api.schemas import AskRequest
from src.app.config import settings
from src.app.core import agent as agent_module


class TestSQLValidation:
    """Test SQL query validation security mechanisms."""

    def test_sql_injection_in_generated_query_blocked(self):
        """Test that if LLM generates malicious SQL, it's blocked before execution."""
        is_valid, error = agent_module._validate_sql_query("DROP TABLE users;")
        assert is_valid is False
        assert "DROP" in error

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

