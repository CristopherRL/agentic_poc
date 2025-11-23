from __future__ import annotations

import time
from collections import deque
from typing import Dict, List, Optional, Tuple

from src.app.config import settings


class ConversationHistory:
    """Stores question-answer pairs for a session."""
    
    def __init__(self, session_id: str, created_at: float):
        self.session_id = session_id
        self.created_at = created_at
        self.messages: deque[Tuple[str, str]] = deque()  # (question, answer) pairs
    
    def add_exchange(self, question: str, answer: str) -> None:
        """Add a question-answer pair to the history."""
        self.messages.append((question, answer))
    
    def get_history(self, max_pairs: int = 10) -> List[Tuple[str, str]]:
        """Get recent conversation history, limited to max_pairs."""
        return list(self.messages)[-max_pairs:]
    
    def format_for_prompt(self, max_pairs: int = 10) -> str:
        """Format conversation history for inclusion in LLM prompts."""
        history = self.get_history(max_pairs)
        if not history:
            return ""
        
        lines = ["Previous conversation:"]
        for question, answer in history:
            lines.append(f"Q: {question}")
            lines.append(f"A: {answer}")
        return "\n".join(lines)


# In-memory storage: session_id -> ConversationHistory
_conversation_store: Dict[str, ConversationHistory] = {}


def get_or_create_session(session_id: Optional[str] = None) -> str:
    """
    Get existing session or create a new one.
    
    If session_id is provided but doesn't exist, creates a new session with that ID.
    If session_id is None, generates a new UUID.
    
    Returns:
        str: Session ID (existing, provided, or newly generated)
    """
    if session_id and session_id in _conversation_store:
        return session_id
    
    # Create new session (with provided ID or generate new UUID)
    import uuid
    new_session_id = session_id if session_id else str(uuid.uuid4())
    _conversation_store[new_session_id] = ConversationHistory(
        session_id=new_session_id,
        created_at=time.time()
    )
    return new_session_id


def add_exchange(session_id: str, question: str, answer: str) -> None:
    """Add a question-answer exchange to the session history."""
    if session_id in _conversation_store:
        _conversation_store[session_id].add_exchange(question, answer)


def get_history(session_id: str, max_pairs: int = 10) -> List[Tuple[str, str]]:
    """
    Get conversation history for a session.
    
    Returns:
        List of (question, answer) tuples, empty list if session doesn't exist
    """
    if session_id not in _conversation_store:
        return []
    return _conversation_store[session_id].get_history(max_pairs)


def get_history_for_prompt(session_id: str, max_pairs: int = 10) -> str:
    """
    Get formatted conversation history for inclusion in LLM prompts.
    
    Returns:
        Formatted string with conversation history, empty string if no history
    """
    if session_id not in _conversation_store:
        return ""
    return _conversation_store[session_id].format_for_prompt(max_pairs)


def cleanup_expired_sessions() -> int:
    """
    Remove expired sessions based on TTL.
    
    Returns:
        Number of sessions removed
    """
    current_time = time.time()
    expired_sessions = [
        session_id
        for session_id, history in _conversation_store.items()
        if current_time - history.created_at > settings.session_ttl_seconds
    ]
    
    for session_id in expired_sessions:
        del _conversation_store[session_id]
    
    return len(expired_sessions)

