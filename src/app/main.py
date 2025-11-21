from contextlib import asynccontextmanager

from fastapi import FastAPI
from src.app.api.router import router
from src.app.infrastructure.rate_limit_db import init_rate_limit_table


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    # Startup
    init_rate_limit_table()
    yield
    # Shutdown (no cleanup needed)


app = FastAPI(title="Agentic Assistant POC", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}

