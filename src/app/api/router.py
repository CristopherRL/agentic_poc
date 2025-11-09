from __future__ import annotations
from fastapi import APIRouter, HTTPException
from src.app.api.schemas import AskRequest, AskResponse

router = APIRouter(prefix="/api/v1")


@router.post("/ask", response_model=AskResponse)
def ask_question(_: AskRequest) -> AskResponse:  # pragma: no cover - placeholder until SQL agent is ready
    raise HTTPException(status_code=501, detail="Endpoint will be available once RAG and SQL agents are integrated.")
