from __future__ import annotations

from functools import partial

from anyio import to_thread
from fastapi import APIRouter, HTTPException

from src.app.api.schemas import AskRequest, AskResponse, Citation
from src.app.core.agent import run_agent

router = APIRouter(prefix="/api/v1")


@router.post("/ask", response_model=AskResponse)
async def ask_question(payload: AskRequest) -> AskResponse:
    try:
        agent_result = await to_thread.run_sync(
            partial(run_agent, payload.question, include_intermediate_steps=True)
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=500, detail="Agent execution failed") from exc

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
