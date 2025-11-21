import re
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from src.app.config import settings


class AskRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=settings.question_max_length,
        description="User question to route through the agent"
    )

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        """
        Validate and sanitize the question input.
        
        - Checks for SQL injection patterns
        - Removes or flags dangerous special characters
        - Ensures the question is not empty after sanitization
        """
        if not v or not v.strip():
            raise ValueError("Question cannot be empty")
        
        question_upper = v.upper()
        
        # Build dangerous patterns using centralized keywords list
        # Pattern 1: Command after semicolon (e.g., "; DROP TABLE")
        keywords_pattern = "|".join(re.escape(kw) for kw in settings.dangerous_sql_keywords)
        dangerous_patterns = [
            rf";\s*({keywords_pattern})",  # SQL command after semicolon
            r"--\s*$",  # SQL comment at end of line
            r"/\*.*?\*/",  # SQL block comments
            r"'\s*OR\s*'",  # SQL OR injection
            r"'\s*UNION\s*",  # SQL UNION injection
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, question_upper, re.IGNORECASE | re.MULTILINE):
                raise ValueError("Question contains potentially dangerous SQL patterns")
        
        # Return sanitized version (strip whitespace)
        return v.strip()


class Citation(BaseModel):
    source_document: str
    page: Optional[int] = None
    content: str


class AskResponse(BaseModel):
    answer: str
    sql_query: Optional[str] = None
    citations: List[Citation] = Field(default_factory=list)
    tool_trace: List[str] = Field(default_factory=list)


# Admin schemas for rate limit management
class RateLimitStats(BaseModel):
    identifier: str
    date: str
    interaction_count: int
    last_interaction_at: Optional[str] = None


class RateLimitStatsResponse(BaseModel):
    stats: List[RateLimitStats]
    total_records: int


class ResetRateLimitRequest(BaseModel):
    identifier: Optional[str] = Field(
        None,
        description="Identifier to reset. If not provided, resets all identifiers for today."
    )


class ResetRateLimitResponse(BaseModel):
    message: str
    records_reset: int