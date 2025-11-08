from typing import List, Optional

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="User question to route through the agent")


class Citation(BaseModel):
    source_document: str
    page: Optional[int] = None
    content: str


class AskResponse(BaseModel):
    answer: str
    sql_query: Optional[str] = None
    citations: List[Citation] = Field(default_factory=list)
    tool_trace: List[str] = Field(default_factory=list)
