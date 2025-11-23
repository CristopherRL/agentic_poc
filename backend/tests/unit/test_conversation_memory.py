import time
from unittest.mock import patch

import pytest

from src.app.core.conversation_memory import (
    ConversationHistory,
    add_exchange,
    cleanup_expired_sessions,
    get_history,
    get_history_for_prompt,
    get_or_create_session,
)


class TestConversationHistory:
    """Test ConversationHistory class."""

    def test_add_exchange_stores_question_answer(self):
        """Test that add_exchange stores question-answer pairs."""
        history = ConversationHistory("session-1", time.time())
        history.add_exchange("What is X?", "X is Y")
        history.add_exchange("What about Z?", "Z is W")
        
        assert len(history.messages) == 2
        assert history.messages[0] == ("What is X?", "X is Y")
        assert history.messages[1] == ("What about Z?", "Z is W")

    def test_get_history_returns_recent_pairs(self):
        """Test that get_history returns recent conversation pairs."""
        history = ConversationHistory("session-1", time.time())
        for i in range(5):
            history.add_exchange(f"Q{i}", f"A{i}")
        
        result = history.get_history(max_pairs=3)
        assert len(result) == 3
        assert result[-1] == ("Q4", "A4")

    def test_format_for_prompt_includes_history(self):
        """Test that format_for_prompt formats history correctly."""
        history = ConversationHistory("session-1", time.time())
        history.add_exchange("What is X?", "X is Y")
        history.add_exchange("What about Z?", "Z is W")
        
        formatted = history.format_for_prompt()
        assert "Previous conversation:" in formatted
        assert "Q: What is X?" in formatted
        assert "A: X is Y" in formatted
        assert "Q: What about Z?" in formatted
        assert "A: Z is W" in formatted

    def test_format_for_prompt_returns_empty_when_no_history(self):
        """Test that format_for_prompt returns empty string when no history."""
        history = ConversationHistory("session-1", time.time())
        formatted = history.format_for_prompt()
        assert formatted == ""


class TestSessionManagement:
    """Test session management functions."""

    def test_get_or_create_session_creates_new_session(self):
        """Test that get_or_create_session creates a new session when None provided."""
        session_id = get_or_create_session(None)
        assert session_id is not None
        assert isinstance(session_id, str)
        assert len(session_id) > 0

    def test_get_or_create_session_returns_existing_session(self):
        """Test that get_or_create_session returns existing session."""
        session_id1 = get_or_create_session(None)
        session_id2 = get_or_create_session(session_id1)
        assert session_id1 == session_id2

    def test_get_or_create_session_creates_new_with_provided_id(self):
        """Test that get_or_create_session creates new session with provided ID when it doesn't exist."""
        provided_id = "custom-session-123"
        session_id = get_or_create_session(provided_id)
        assert session_id == provided_id
        # Verify session was created
        from src.app.core.conversation_memory import _conversation_store
        assert provided_id in _conversation_store


class TestConversationStorage:
    """Test conversation storage functions."""

    def test_add_exchange_stores_in_session(self):
        """Test that add_exchange stores question-answer in session."""
        session_id = get_or_create_session(None)
        add_exchange(session_id, "Question 1", "Answer 1")
        add_exchange(session_id, "Question 2", "Answer 2")
        
        history = get_history(session_id)
        assert len(history) == 2
        assert history[0] == ("Question 1", "Answer 1")
        assert history[1] == ("Question 2", "Answer 2")

    def test_get_history_returns_empty_for_nonexistent_session(self):
        """Test that get_history returns empty list for non-existent session."""
        history = get_history("non-existent-session")
        assert history == []

    def test_get_history_for_prompt_formats_correctly(self):
        """Test that get_history_for_prompt formats history for prompts."""
        session_id = get_or_create_session(None)
        add_exchange(session_id, "Q1", "A1")
        add_exchange(session_id, "Q2", "A2")
        
        formatted = get_history_for_prompt(session_id)
        assert "Previous conversation:" in formatted
        assert "Q: Q1" in formatted
        assert "A: A1" in formatted

    def test_get_history_for_prompt_returns_empty_for_nonexistent_session(self):
        """Test that get_history_for_prompt returns empty string for non-existent session."""
        formatted = get_history_for_prompt("non-existent-session")
        assert formatted == ""


class TestSessionCleanup:
    """Test session expiration and cleanup."""

    @patch("src.app.core.conversation_memory.settings")
    def test_cleanup_expired_sessions_removes_old_sessions(self, mock_settings):
        """Test that cleanup_expired_sessions removes expired sessions."""
        mock_settings.session_ttl_seconds = 1
        
        # Create a session with old timestamp
        session_id = get_or_create_session(None)
        from src.app.core.conversation_memory import _conversation_store
        _conversation_store[session_id].created_at = time.time() - 2  # 2 seconds ago
        
        # Create a fresh session
        fresh_session_id = get_or_create_session(None)
        _conversation_store[fresh_session_id].created_at = time.time()
        
        # Cleanup should remove expired session
        removed_count = cleanup_expired_sessions()
        assert removed_count == 1
        assert session_id not in _conversation_store
        assert fresh_session_id in _conversation_store

    @patch("src.app.core.conversation_memory.settings")
    def test_cleanup_expired_sessions_keeps_fresh_sessions(self, mock_settings):
        """Test that cleanup_expired_sessions keeps fresh sessions."""
        mock_settings.session_ttl_seconds = 10
        
        session_id = get_or_create_session(None)
        from src.app.core.conversation_memory import _conversation_store
        _conversation_store[session_id].created_at = time.time()  # Just created
        
        removed_count = cleanup_expired_sessions()
        assert removed_count == 0
        assert session_id in _conversation_store

