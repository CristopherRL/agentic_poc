from __future__ import annotations
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status

from src.app.api.schemas import (
    AskRequest,
    AskResponse,
    Citation,
    RateLimitInfo,
    RateLimitStats,
    RateLimitStatsResponse,
    ResetRateLimitRequest,
    ResetRateLimitResponse,
)
from src.app.config import settings
from src.app.core.agent import run_agent
from src.app.core.conversation_memory import (
    add_exchange,
    cleanup_expired_sessions,
    get_history_for_prompt,
    get_or_create_session,
)
from src.app.core.rate_limit import (
    RateLimitExceeded,
    check_rate_limit,
    get_remaining_interactions,
    record_interaction,
)
from src.app.infrastructure.rate_limit_db import (
    get_all_daily_counts,
    reset_daily_count,
)

router = APIRouter(prefix="/api/v1")
logger = logging.getLogger(__name__)


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
    
    Checks multiple headers in order for proxied requests (Render.com, Cloudflare, etc.):
    - X-Forwarded-For (standard proxy header)
    - X-Real-IP (nginx and other proxies)
    - CF-Connecting-IP (Cloudflare)
    Falls back to direct client IP.
    """
    # Check headers in order of preference
    forwarded_for = request.headers.get("X-Forwarded-For")
    real_ip = request.headers.get("X-Real-IP")
    cf_connecting_ip = request.headers.get("CF-Connecting-IP")
    client_host = request.client.host if request.client else None
    
    # Log all available headers for debugging
    logger.debug(
        f"[IP Detection] Headers: X-Forwarded-For={forwarded_for}, "
        f"X-Real-IP={real_ip}, CF-Connecting-IP={cf_connecting_ip}, "
        f"Client={client_host}"
    )
    
    # Use first available IP from headers
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        identifier = forwarded_for.split(",")[0].strip()
        logger.debug(f"[IP Detection] Selected from X-Forwarded-For: {identifier}")
        return identifier
    
    if real_ip:
        identifier = real_ip.strip()
        logger.debug(f"[IP Detection] Selected from X-Real-IP: {identifier}")
        return identifier
    
    if cf_connecting_ip:
        identifier = cf_connecting_ip.strip()
        logger.debug(f"[IP Detection] Selected from CF-Connecting-IP: {identifier}")
        return identifier
    
    # Fallback to direct client IP
    identifier = client_host if client_host else "unknown"
    logger.debug(f"[IP Detection] Selected from Client: {identifier}")
    return identifier


@router.post("/ask", response_model=AskResponse)
async def ask_question(payload: AskRequest, request: Request) -> AskResponse:
    """
    Handle an ask request by running the agent on the provided question and returning structured results.
    
    Rate limiting: Each IP address is limited to a daily interaction count (default: 20).
    Conversation memory: Optional session_id enables conversation continuity within a session.
    
    Parameters:
        payload (AskRequest): Request payload containing the user's question and optional session_id.
        request (Request): FastAPI request object for extracting client IP.
    
    Returns:
        AskResponse: Result object with:
            - answer: final textual answer (empty string if none),
            - sql_query: optional SQL query produced by the agent,
            - citations: list of Citation objects with `source_document`, `page`, and `content`,
            - tool_trace: list of strings representing intermediate tool outputs,
            - session_id: session identifier for conversation continuity.
    
    Raises:
        HTTPException: 
            - 400 Bad Request for validation errors
            - 429 Too Many Requests when daily interaction limit is exceeded
            - 500 Internal Server Error for unexpected internal errors
            - 503 Service Unavailable when external dependencies (OpenAI API) are unavailable
    """
    identifier = _get_client_identifier(request)
    
    # Cleanup expired sessions periodically
    cleanup_expired_sessions()
    
    # Get or create session
    session_id = get_or_create_session(payload.session_id)
    
    # Get conversation history for this session
    conversation_history = get_history_for_prompt(session_id)
    
    # Log incoming request
    logger.info(f"[Request] Question: {payload.question[:100]}{'...' if len(payload.question) > 100 else ''} | Session: {session_id}")
    if conversation_history:
        logger.info(f"[Request] Conversation history: {len(conversation_history)} chars")
    
    # Check rate limit before processing (if enabled)
    rate_limit_info = None
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
        current_count = record_interaction(identifier)
        remaining = get_remaining_interactions(identifier, settings.daily_interaction_limit)
        rate_limit_info = RateLimitInfo(
            remaining_interactions=remaining,
            daily_limit=settings.daily_interaction_limit,
            current_count=current_count
        )
        logger.info(
            f"[Rate Limit] Identifier: {identifier} | "
            f"Remaining: {remaining}/{settings.daily_interaction_limit} | "
            f"Current: {current_count}"
        )
    
    try:
        start_time = time.time()
        logger.info(f"[Request] Processing question with agent...")
        agent_result = await run_agent(
            payload.question,
            include_intermediate_steps=True,
            conversation_history=conversation_history
        )
        elapsed_time = time.time() - start_time
        logger.info(f"[Request] Agent completed | Route: {agent_result.get('route', 'UNKNOWN')} | Time: {elapsed_time:.2f}s")
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

    # Store question-answer exchange in conversation memory
    add_exchange(session_id, payload.question, answer)
    
    response = AskResponse(
        answer=answer,
        sql_query=sql_query,
        citations=citations,
        tool_trace=[str(entry) for entry in tool_trace],
        session_id=session_id,
        rate_limit_info=rate_limit_info,
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