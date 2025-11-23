# Backend - Agentic Assistant POC

FastAPI backend for the Agentic Assistant POC.

## Quick Start

```bash
# Setup virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-your-key-here

# Ingest data
python -m scripts.ingest_sql
python -m scripts.ingest_rag

# Start server
uvicorn src.app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Project Structure

```
backend/
├── src/app/          # Application code
│   ├── api/         # FastAPI routes and schemas
│   ├── core/        # Business logic (Agent, Tools)
│   └── infrastructure/  # External services (LLM, DB, Vector Store)
├── scripts/         # Data ingestion scripts
├── tests/           # Test suite
├── data/            # Data stores (SQLite, FAISS)
└── docs/            # Documentation and public data
```

## Environment Variables

See `.env.example` for all available configuration options.

**Required:**
- `OPENAI_API_KEY`: OpenAI API key for LLM and embeddings

**Optional:**
- `ADMIN_TOKEN`: Admin token for rate limit management endpoints
- `CORS_ORIGINS`: Comma-separated list of allowed CORS origins
- `ENABLE_RATE_LIMIT`: Enable/disable rate limiting (default: true)
- `DAILY_INTERACTION_LIMIT`: Daily interaction limit per IP (default: 20)

## API Endpoints

- `GET /health` - Health check
- `POST /api/v1/ask` - Ask a question to the agent

See main [README.md](../README.md) for detailed API documentation.

## Testing

```bash
# Run all tests
pytest

# Run specific test suite
pytest tests/unit/
pytest tests/integration/
pytest tests/security/
```

## Deployment

See main [README.md](../README.md) for Vercel deployment instructions.


