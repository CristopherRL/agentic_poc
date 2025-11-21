from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status

from src.app.api.schemas import (
    AskRequest,
    AskResponse,
    Citation,
    RateLimitStats,
    RateLimitStatsResponse,
    ResetRateLimitRequest,
    ResetRateLimitResponse,
)
from src.app.config import settings
from src.app.core.agent import run_agent
from src.app.core.rate_limit import (
    RateLimitExceeded,
    check_rate_limit,
    record_interaction,
)
from src.app.infrastructure.rate_limit_db import (
    get_all_daily_counts,
    reset_daily_count,
)

router = APIRouter(prefix="/api/v1")


def verify_admin_token(x_admin_token: str = Header(..., alias="X-Admin-Token")) -> str:
    """
    Dependency to verify admin token for protected endpoints.
    
    Raises:
        HTTPException: 401 if token is missing or invalid
    """
    if not settings.admin_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin endpoints are not configured. Set ADMIN_TOKEN environment variable."
        )
    
    if x_admin_token != settings.admin_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token"
        )
    
    return x_admin_token


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


def _get_client_identifier(request: Request) -> str:
    """
    Extract client identifier from request (IP address).
    
    Checks X-Forwarded-For header for proxied requests, falls back to direct client IP.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/ask", response_model=AskResponse)
async def ask_question(payload: AskRequest, request: Request) -> AskResponse:
    """
    Handle an ask request by running the agent on the provided question and returning structured results.
    
    Rate limiting: Each IP address is limited to a daily interaction count (default: 20).
    
    Parameters:
        payload (AskRequest): Request payload containing the user's question.
        request (Request): FastAPI request object for extracting client IP.
    
    Returns:
        AskResponse: Result object with:
            - answer: final textual answer (empty string if none),
            - sql_query: optional SQL query produced by the agent,
            - citations: list of Citation objects with `source_document`, `page`, and `content`,
            - tool_trace: list of strings representing intermediate tool outputs.
    
    Raises:
        HTTPException: 
            - 400 Bad Request for validation errors
            - 429 Too Many Requests when daily interaction limit is exceeded
            - 500 Internal Server Error for unexpected internal errors
            - 503 Service Unavailable when external dependencies (OpenAI API) are unavailable
    """
    identifier = _get_client_identifier(request)
    
    # Check rate limit before processing (if enabled)
    if settings.enable_rate_limit:
        try:
            check_rate_limit(identifier, settings.daily_interaction_limit)
        except RateLimitExceeded as exc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Daily interaction limit exceeded: {exc.current_count}/{exc.limit}. Please try again tomorrow."
            ) from exc
        # Record interaction immediately after rate limit check passes
        # This ensures all requests (successful or not) count against the limit
        # Prevents DoS by repeatedly triggering errors to bypass rate limiting
        record_interaction(identifier)
    
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

    response = AskResponse(
        answer=answer,
        sql_query=sql_query,
        citations=citations,
        tool_trace=[str(entry) for entry in tool_trace],
    )
    
    return response


# Admin endpoints for rate limit management
# These endpoints are excluded from OpenAPI docs for security
@router.get(
    "/admin/rate-limit/stats",
    response_model=RateLimitStatsResponse,
    include_in_schema=False,  # Hide from OpenAPI/Swagger docs
    tags=["Admin"],  # Internal tag (won't appear in public docs)
)
async def get_rate_limit_stats(
    date: str | None = None,
    _token: str = Depends(verify_admin_token),
) -> RateLimitStatsResponse:
    """
    Get rate limit statistics (admin only).
    
    Returns all daily interaction counts, optionally filtered by date.
    
    Parameters:
        date: Optional date filter in ISO format (YYYY-MM-DD). If not provided, returns all records.
        _token: Admin token (via X-Admin-Token header)
    
    Returns:
        RateLimitStatsResponse with list of stats and total record count
    """
    stats_data = get_all_daily_counts(date_filter=date)
    stats = [
        RateLimitStats(
            identifier=item["identifier"],
            date=item["date"],
            interaction_count=item["interaction_count"],
            last_interaction_at=item["last_interaction_at"],
        )
        for item in stats_data
    ]
    
    return RateLimitStatsResponse(stats=stats, total_records=len(stats))


@router.post(
    "/admin/rate-limit/reset",
    response_model=ResetRateLimitResponse,
    include_in_schema=False,  # Hide from OpenAPI/Swagger docs
    tags=["Admin"],  # Internal tag (won't appear in public docs)
)
async def reset_rate_limit(
    payload: ResetRateLimitRequest,
    _token: str = Depends(verify_admin_token),
) -> ResetRateLimitResponse:
    """
    Reset daily interaction counts (admin only).
    
    Can reset a specific identifier or all identifiers for today.
    
    Parameters:
        payload: ResetRateLimitRequest with optional identifier
        _token: Admin token (via X-Admin-Token header)
    
    Returns:
        ResetRateLimitResponse with confirmation message and number of records reset
    """
    records_reset = reset_daily_count(identifier=payload.identifier)
    
    if payload.identifier:
        message = f"Reset interaction count for identifier '{payload.identifier}' (today)"
    else:
        message = "Reset interaction counts for all identifiers (today)"
    
    return ResetRateLimitResponse(
        message=message,
        records_reset=records_reset,
    )