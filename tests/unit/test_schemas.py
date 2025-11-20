"""
Unit tests for Pydantic schema validation with edge cases.
"""
import pytest
from pydantic import ValidationError

from src.app.api.schemas import AskRequest
from src.app.config import settings


class TestAskRequestValidation:
    """Test AskRequest schema validation with edge cases."""

    def test_valid_question(self):
        """Test that a valid question passes validation."""
        request = AskRequest(question="What are the sales figures?")
        assert request.question == "What are the sales figures?"

    def test_empty_string_raises_error(self):
        """Test that empty string raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AskRequest(question="")
        # Pydantic validates min_length before custom validator runs
        # So we check for either the Pydantic message or our custom message
        error_str = str(exc_info.value)
        assert "at least 1 character" in error_str or "Question cannot be empty" in error_str

    def test_whitespace_only_raises_error(self):
        """Test that whitespace-only string raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AskRequest(question="   ")
        assert "Question cannot be empty" in str(exc_info.value)

    def test_max_length_valid(self):
        """Test that question at max length is valid."""
        max_length = settings.question_max_length
        long_question = "a" * max_length
        request = AskRequest(question=long_question)
        assert len(request.question) == max_length

    def test_exceeds_max_length_raises_error(self):
        """Test that question exceeding max length raises ValidationError."""
        max_length = settings.question_max_length
        too_long = "a" * (max_length + 1)
        with pytest.raises(ValidationError) as exc_info:
            AskRequest(question=too_long)
        # Pydantic will raise a validation error for max_length constraint
        assert "at most" in str(exc_info.value).lower() or "ensure this value has at most" in str(exc_info.value)

    def test_sql_injection_semicolon_drop_raises_error(self):
        """Test that SQL injection with DROP is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AskRequest(question="What are sales?; DROP TABLE users;")
        assert "dangerous SQL patterns" in str(exc_info.value)

    def test_sql_injection_semicolon_delete_raises_error(self):
        """Test that SQL injection with DELETE is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AskRequest(question="Show me data; DELETE FROM users;")
        assert "dangerous SQL patterns" in str(exc_info.value)

    def test_sql_injection_comment_raises_error(self):
        """Test that SQL comment injection is rejected."""
        # The pattern r"--\s*$" only matches if comment is at end of line
        # So we test with comment at the end
        with pytest.raises(ValidationError) as exc_info:
            AskRequest(question="What are sales? --")
        assert "dangerous SQL patterns" in str(exc_info.value)

    def test_sql_injection_block_comment_raises_error(self):
        """Test that SQL block comment injection is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AskRequest(question="What are sales? /* malicious */")
        assert "dangerous SQL patterns" in str(exc_info.value)

    def test_sql_injection_union_raises_error(self):
        """Test that SQL UNION injection is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AskRequest(question="What are sales? ' UNION SELECT * FROM users --")
        assert "dangerous SQL patterns" in str(exc_info.value)

    def test_sql_injection_or_raises_error(self):
        """Test that SQL OR injection is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AskRequest(question="What are sales? ' OR '1'='1")
        assert "dangerous SQL patterns" in str(exc_info.value)

    def test_legitimate_question_with_semicolon_passes(self):
        """Test that legitimate questions with semicolons (not SQL) pass."""
        # This should pass because it doesn't match the dangerous patterns
        request = AskRequest(question="What are the sales; and revenue figures?")
        assert request.question == "What are the sales; and revenue figures?"

    def test_special_characters_allowed(self):
        """Test that special characters (not SQL injection) are allowed."""
        request = AskRequest(question="What are sales in Q1-Q2 2024? (Include all models)")
        assert "?" in request.question
        assert "(" in request.question
        assert ")" in request.question
        assert "-" in request.question

    def test_question_stripped_of_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        request = AskRequest(question="  What are sales?  ")
        assert request.question == "What are sales?"

    def test_all_dangerous_keywords_rejected(self):
        """Test that all dangerous SQL keywords from config are rejected."""
        dangerous_keywords = settings.dangerous_sql_keywords
        for keyword in dangerous_keywords:
            with pytest.raises(ValidationError) as exc_info:
                AskRequest(question=f"What are sales?; {keyword} TABLE users;")
            assert "dangerous SQL patterns" in str(exc_info.value)

