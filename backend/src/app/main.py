import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.app.api.router import router
from src.app.core.auto_ingest import auto_ingest_if_needed
from src.app.infrastructure.rate_limit_db import init_rate_limit_table

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    # Startup
    logger.info("=" * 60)
    logger.info("Starting up application...")
    logger.info("=" * 60)
    
    logger.info("Step 1/3: Initializing rate limit table...")
    try:
        init_rate_limit_table()
        logger.info("✓ Rate limit table initialized")
    except Exception as e:
        logger.error(f"✗ Failed to initialize rate limit table: {e}", exc_info=True)
        raise
    
    logger.info("Step 2/3: Checking and auto-ingesting databases if needed...")
    try:
        # Ejecutar en thread pool para no bloquear el event loop
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            await loop.run_in_executor(executor, auto_ingest_if_needed)
        logger.info("✓ Database verification completed")
    except Exception as e:
        logger.error(f"✗ Database verification failed: {e}", exc_info=True)
        raise
    
    logger.info("Step 3/3: Application startup complete")
    logger.info("=" * 60)
    logger.info("Server is ready to accept requests")
    logger.info("=" * 60)
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    try:
        # Cleanup can be added here if needed
        pass
    except asyncio.CancelledError:
        # Suppress cancellation errors during shutdown (normal when server is interrupted)
        pass


app = FastAPI(title="Agentic Assistant POC", version="0.1.0", lifespan=lifespan)

# Configure CORS
# Default origins for local development
default_origins = [
    "http://localhost:5173",  # Vite dev server
    "http://localhost:3000",  # Alternative dev port
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

# Add production origins from environment variable (comma-separated)
cors_origins_env = os.getenv("CORS_ORIGINS", "")
if cors_origins_env:
    production_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
    default_origins.extend(production_origins)

# CORS middleware must be added BEFORE including routers
app.add_middleware(
    CORSMiddleware,
    allow_origins=default_origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods including OPTIONS
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

app.include_router(router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}

