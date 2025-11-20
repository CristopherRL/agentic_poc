from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from src.app.api.schemas import AskRequest, AskResponse, Citation
from src.app.core.agent import run_agent

router = APIRouter(prefix="/api/v1")


def _is_openai_api_error(exc: Exception) -> bool:
    """Check if the exception is related to OpenAI API (network, rate limit, service unavailable)."""
    exc_type_name = type(exc).__name__
    exc_str = str(exc).lower()
    
    # Check for OpenAI-specific exceptions
    if "openai" in exc_type_name.lower() or "openai" in exc_str:
        return True
    
    # Check for network/connection errors that might indicate API unavailability
    if any(keyword in exc_str for keyword in ["connection", "timeout", "rate limit", "api key", "authentication"]):
        return True
    
    return False


@router.post("/ask", response_model=AskResponse)
async def ask_question(payload: AskRequest) -> AskResponse:
    """
    Handle an ask request by running the agent on the provided question and returning structured results.
    
    Parameters:
        payload (AskRequest): Request payload containing the user's question.
    
    Returns:
        AskResponse: Result object with:
            - answer: final textual answer (empty string if none),
            - sql_query: optional SQL query produced by the agent,
            - citations: list of Citation objects with `source_document`, `page`, and `content`,
            - tool_trace: list of strings representing intermediate tool outputs.
    
    Raises:
        HTTPException: 
            - 400 Bad Request for validation errors
            - 500 Internal Server Error for unexpected internal errors
            - 503 Service Unavailable when external dependencies (OpenAI API) are unavailable
    """
    try:
        agent_result = await run_agent(payload.question, include_intermediate_steps=True)
    except Exception as exc:  # pragma: no cover - defensive guard
        # Check if it's an OpenAI API error (service unavailable)
        if _is_openai_api_error(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="External service temporarily unavailable. Please try again later."
            ) from exc
        
        # For all other errors, return 500 with generic message
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while processing your request."
        ) from exc

    answer = agent_result.get("output", "")
    sql_query = agent_result.get("sql_query")
    citations_data = agent_result.get("citations") or []
    tool_trace = agent_result.get("tool_trace") or []

    citations = [
        Citation(
            source_document=str(item.get("source_document") or ""),
            page=item.get("page"),
            content=str(item.get("content") or ""),
        )
        for item in citations_data
    ]

    return AskResponse(
        answer=answer,
        sql_query=sql_query,
        citations=citations,
        tool_trace=[str(entry) for entry in tool_trace],
    )