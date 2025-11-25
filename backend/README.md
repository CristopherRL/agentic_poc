# Backend - Agentic Assistant POC

FastAPI backend for the Agentic Assistant POC. Implements an intelligent agent that routes questions between SQL analytics and RAG document retrieval.

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
├── src/app/              # Application code
│   ├── api/             # FastAPI routes and schemas
│   │   ├── router.py    # API endpoints (/api/v1/ask, admin endpoints)
│   │   └── schemas.py   # Pydantic request/response models
│   ├── core/            # Business logic (Agent, Tools)
│   │   ├── agent.py     # Main agent orchestrator with routing logic
│   │   ├── conversation_memory.py  # Session-based conversation history
│   │   └── rate_limit.py           # Rate limiting business logic
│   ├── infrastructure/  # External services (LLM, DB, Vector Store)
│   │   ├── db.py        # SQLite database operations
│   │   ├── llm.py        # OpenAI LLM client initialization
│   │   ├── vector_store.py  # FAISS vector store operations
│   │   └── rate_limit_db.py  # Rate limiting database operations
│   ├── config.py        # Centralized configuration (pydantic-settings)
│   └── main.py          # FastAPI application entrypoint
├── scripts/             # Data ingestion scripts
│   ├── ingest_sql.py    # CSV → SQLite ingestion
│   └── ingest_rag.py    # PDF/TXT → FAISS ingestion
├── tests/               # Test suite
│   ├── unit/            # Unit tests (agent logic, schemas)
│   ├── integration/     # Integration tests (API endpoints)
│   └── e2e/             # End-to-End tests (full request/response cycles)
├── data/                # Data stores (SQLite, FAISS)
│   ├── db/              # SQLite database and schema artifacts
│   └── vdb/             # FAISS vector index
└── docs/                # Documentation and public data
    └── public/          # CSV datasets and PDF documents
```

## Architecture

The backend follows **Clean Architecture** principles with three distinct layers:

1. **API Layer (`src/app/api`)**: FastAPI routes, Pydantic validation, HTTP handling
2. **Core Layer (`src/app/core`)**: Business logic, agent orchestration, routing decisions
3. **Infrastructure Layer (`src/app/infrastructure`)**: External services (LLM, SQLite, FAISS)

**Key Design Principles:**
- **Async/Await:** All I/O-bound operations use async/await patterns for optimal performance
- **Dependency Injection:** Configuration and external services are injected, not hardcoded
- **Separation of Concerns:** Each layer has clear responsibilities and dependencies

## Features

### 1. Intelligent Routing
- **LLM-based Router:** Uses `gpt-4o-mini` to classify questions as SQL, RAG, or Hybrid
- **Heuristic Fallback:** Keyword-based hints improve routing accuracy
- **Hybrid Decomposition:** Dedicated `gpt-4o` model splits complex questions into SQL + RAG sub-queries

### 2. Multi-Model Strategy
- **Router/SQL Generation:** `gpt-4o-mini` (fast, cheap, deterministic)
- **Hybrid Split:** `gpt-4o` (high-quality decomposition)
- **Synthesis:** `gpt-4o` (high-quality natural language responses)

**Cost Optimization:** ~$0.0007 per query (vs ~$0.002 if using gpt-4o for all steps)

### 3. Conversation Memory
- **Session-based:** Optional `session_id` enables conversation continuity
- **In-memory Storage:** Conversation history stored per session (no persistent DB)
- **Context Integration:** History included in all LLM prompts for contextual follow-ups
- **TTL:** Sessions expire after configurable TTL (default: 1 hour)

### 4. Rate Limiting
- **Daily Limits:** Configurable daily interaction limit per IP address (default: 20)
- **SQLite-backed:** Persistent rate limit tracking across restarts
- **Admin Endpoints:** Hidden endpoints for rate limit management (protected by admin token)
- **Enable/Disable:** Can be disabled via `ENABLE_RATE_LIMIT=false` for development

### 5. Security
- **Input Validation:** Pydantic schemas with strict constraints (max length, SQL injection detection)
- **SQL Injection Prevention:** Query validation blocks DML/DDL operations, read-only connections
- **Error Handling:** Generic error messages (no stack traces, file paths, or API keys exposed)

## API Endpoints

### `POST /api/v1/ask`

Ask a question to the agent.

**Request:**
```json
{
  "question": "Monthly RAV4 HEV sales in Germany in 2024",
  "session_id": "optional-session-id"
}
```

**Response:**
```json
{
  "answer": "The monthly RAV4 HEV sales in Germany in 2024...",
  "sql_query": "SELECT month, SUM(contracts) FROM FACT_SALES...",
  "citations": [
    {
      "source_document": "Contract_Toyota_2023.pdf",
      "page": 4,
      "content": "Relevant snippet..."
    }
  ],
  "tool_trace": [
    "Router selected: SQL_Tool",
    "SQL_Tool executed with query: '...'",
    "LLM synthesized final answer."
  ],
  "session_id": "generated-or-provided-session-id",
  "rate_limit_info": {
    "remaining_interactions": 19,
    "daily_limit": 20,
    "current_count": 1
  }
}
```

**Status Codes:**
- `200 OK`: Success
- `422 Unprocessable Entity`: Validation error (empty question, exceeds max length, SQL injection detected)
- `429 Too Many Requests`: Daily interaction limit exceeded
- `500 Internal Server Error`: Unexpected internal error
- `503 Service Unavailable`: External service (OpenAI API) unavailable

### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "ok"
}
```

### Admin Endpoints (Hidden from OpenAPI)

These endpoints are excluded from `/docs` and `/openapi.json` for security:

- `GET /api/v1/admin/rate-limit/stats` - Get rate limit statistics
- `POST /api/v1/admin/rate-limit/reset` - Reset daily interaction counts

**Authentication:** Requires `X-Admin-Token` header matching `ADMIN_TOKEN` environment variable.

## Environment Variables

See `.env.example` for all available configuration options.

**Required:**
- `OPENAI_API_KEY`: OpenAI API key for LLM and embeddings

**Optional:**
- `ADMIN_TOKEN`: Admin token for rate limit management endpoints
- `CORS_ORIGINS`: Comma-separated list of allowed CORS origins (default: includes localhost)
- `ENABLE_RATE_LIMIT`: Enable/disable rate limiting (default: `true`)
- `DAILY_INTERACTION_LIMIT`: Daily interaction limit per IP (default: `20`)
- `SESSION_TTL_SECONDS`: Session expiration time in seconds (default: `3600`)

**LLM Configuration:**
- `ROUTER_LLM_MODEL`: Router model (default: `gpt-4o-mini`)
- `SQL_LLM_MODEL`: SQL generation model (default: `gpt-4o-mini`)
- `SPLIT_LLM_MODEL`: Hybrid split model (default: `gpt-4o`)
- `SYNTHESIS_LLM_MODEL`: Synthesis model (default: `gpt-4o`)

**RAG Configuration:**
- `RAG_TOP_K`: Number of documents to retrieve (default: `4`)

See `src/app/config.py` for complete configuration options.

## Data Ingestion

### SQL Ingestion

```bash
python -m scripts.ingest_sql
```

**Process:**
1. Reads CSV files from `docs/public/data/`
2. Creates SQLite database at `data/db/app.db`
3. Generates schema artifact at `data/db/sql_schema.sql` (used for SQL generation prompts)

**Reset Database:**
```bash
python -c "from scripts.ingest_sql import reset_database; reset_database()"
```

### RAG Ingestion

```bash
python -m scripts.ingest_rag
```

**Process:**
1. Loads PDFs and TXT files from `docs/public/docs/`
2. Chunks documents (PDFs as single chunks, TXT split by `====== PAGE` markers)
3. Generates embeddings using OpenAI `text-embedding-3-small`
4. Creates FAISS index at `data/vdb/faiss_index/`

**Reset Vector Store:**
```bash
python -c "from scripts.ingest_rag import reset_vector_store; reset_vector_store()"
```

## Testing

```bash
# Run all tests
pytest

# Run specific test suites
pytest tests/unit/        # Unit tests (agent logic, schemas)
pytest tests/integration/ # Integration tests (API endpoints)
pytest tests/e2e/        # End-to-End tests (full request/response cycles)

# Run with coverage
pytest --cov=src --cov-report=html
```

**Test Coverage:**
- **Unit Tests:** Agent routing logic, schema validation, SQL query validation, conversation memory
- **Integration Tests:** API endpoints, async behavior, error handling, rate limiting
- **E2E Tests:** Full request/response cycles, SQL injection prevention, input validation, error information leakage

**Test Philosophy:**
- Mock external dependencies (LLM, database, vector store)
- Test edge cases (empty strings, max length, special characters)
- Test error scenarios (API failures, validation errors)
- Use `httpx.AsyncClient` with `ASGITransport` for proper async testing

## Deployment

### Render Deployment (Recommended)

The backend is optimized for deployment on [Render](https://render.com) due to:
- Large dependencies (`faiss-cpu` ~150-200 MB)
- Data files (SQLite DB and FAISS index)
- No size limitations compared to serverless platforms

#### Quick Setup

1. **Connect Repository:**
   - Go to [render.com](https://render.com)
   - Click "New +" → "Web Service"
   - Connect your Git repository

2. **Configure Service:**
   - **Root Directory:** `backend`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn src.app.main:app --host 0.0.0.0 --port $PORT`
   - Render auto-detects `render.yaml` if present

3. **Environment Variables:**
   ```
   OPENAI_API_KEY=sk-your-key-here  # Required
   CORS_ORIGINS=https://your-frontend.vercel.app  # Required for production
   ADMIN_TOKEN=your-admin-token  # Optional
   ENABLE_RATE_LIMIT=true  # Optional
   DAILY_INTERACTION_LIMIT=20  # Optional
   ```

4. **Deploy:**
   - Click "Create Web Service"
   - First deployment takes 5-10 minutes
   - Backend available at `https://your-backend.onrender.com`

**Note:** Data files (`data/db/app.db`, `data/vdb/faiss_index/`) must be committed to the repository or uploaded separately. For production, consider using external storage (S3, Azure Blob).

### Docker Deployment

```bash
# Build image
docker build -t agentic-poc .

# Run container
docker run --rm -p 8000:8000 --env-file .env agentic-poc
```

See `Dockerfile` for details.

## Troubleshooting

**Common Issues:**

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError` | Ensure virtual environment is activated |
| `OPENAI_API_KEY` not found | Check `.env` file exists and contains valid key |
| SQLite database locked | Close DB browser tools or use reset function |
| Port 8000 already in use | Change port: `--port 8001` |
| RAG ingestion fails | Check OpenAI API key is valid and has credits |

**Verification Steps:**

```bash
# Check Python version
python --version  # Should be 3.10+

# Check dependencies
pip list | grep -E "(fastapi|langchain|faiss)"

# Check data files
ls docs/public/data/*.csv  # Should show 5 CSV files
ls docs/public/docs/*.pdf  # Should show 3 PDF files

# Check ingestion completed
ls data/db/app.db  # Should exist
ls data/vdb/faiss_index/  # Should contain index files

# Test API health
curl http://127.0.0.1:8000/health  # Should return {"status":"ok"}
```

## Technical Debt & Future Work

See main [README.md](../README.md) for production readiness checklist and future enhancements.

**Key Areas:**
- Conversation memory: Migrate to persistent storage (Redis, PostgreSQL)
- Managed persistence: SQLite → Postgres, FAISS → Azure AI Search
- Authentication: User-based rate limiting (currently IP-based)
- Monitoring: Structured logging, APM, metrics collection
- CI/CD: Automated testing and deployment pipelines

## Documentation

- **[Main README](../README.md)** - Project overview and quick start
- **[Frontend README](../frontend/README.md)** - Frontend documentation