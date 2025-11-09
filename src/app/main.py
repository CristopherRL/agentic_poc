from fastapi import FastAPI
from src.app.api.router import router

app = FastAPI(title="Agentic Assistant POC", version="0.1.0")
app.include_router(router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}

