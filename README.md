# Agentic Assistant POC

![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)
![Framework](https://img.shields.io/badge/FastAPI-ready-green.svg)
![Agentic Stack](https://img.shields.io/badge/LangChain-hybrid-blueviolet.svg)
![Status](https://img.shields.io/badge/status-POC-orange.svg)

An intelligent agent that answers natural-language questions by intelligently routing between SQL analytics, document retrieval (RAG), or both. This POC demonstrates rapid prototyping discipline with reusable ingestion scripts, configurable multi-model routing, transparent responses, and production-ready documentation.

## 🌐 Live Demo

**Try the application:** [https://agentic-poc-lake.vercel.app/](https://agentic-poc-lake.vercel.app/)

**Note:** The demo has rate limiting enabled (20 interactions per day) to control costs and prevent abuse. If you need more interactions for testing or evaluation purposes, please contact me at **cristopher.rojas.lepe@gmail.com**.

## Project Structure

This is a **monorepo** containing two projects:

- **`backend/`** - FastAPI backend (Python)
  - See [backend/README.md](backend/README.md) for backend-specific documentation
- **`frontend/`** - React frontend (Vite)
  - See [frontend/README.md](frontend/README.md) for frontend-specific documentation

## Quick Start

### Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-your-key-here
python -m scripts.ingest_sql
python -m scripts.ingest_rag
uvicorn src.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend will run on `http://localhost:5173` and connect to the backend on `http://localhost:8000`.

**Note:** All required data files (CSV datasets and PDF documents) are included in `backend/docs/public/`. No additional downloads needed.

For detailed setup instructions, see:
- [Backend README](backend/README.md)
- [Frontend README](frontend/README.md)

---

## Problem & Solution Overview

### The Challenge

Build an intelligent assistant that can answer questions by querying both:
- **Structured data** (CSV files → SQL queries): Sales analytics, model comparisons, regional performance
- **Unstructured documents** (PDFs, manuals → RAG): Contracts, warranty policies, owner's manuals

The system must intelligently route questions to the right tool(s) and combine results for hybrid queries.

### The Solution

**Architecture:** Modular Monolith with Clean Architecture principles
- **API Layer:** FastAPI with async/await patterns, Pydantic validation, rate limiting
- **Core Layer:** Agent orchestrator with LLM-based routing, SQL/RAG tools, conversation memory
- **Infrastructure Layer:** SQLite (structured), FAISS (vector search), OpenAI (multi-model strategy)

**Key Features:**
- **Intelligent Routing:** LLM-based router classifies questions as SQL, RAG, or Hybrid
- **Multi-Model Strategy:** Cost-optimized model selection (gpt-4o-mini for routing/SQL, gpt-4o for synthesis)
- **Hybrid Queries:** Decomposes complex questions into SQL + RAG sub-queries, executes in parallel
- **Transparency:** Returns `sql_query`, `citations`, and `tool_trace` for auditing
- **Conversation Memory:** Session-based context for follow-up questions
- **Rate Limiting:** Daily interaction limits per IP address (configurable)
- **Security:** Input validation, SQL injection prevention, read-only database connections

### High-Level Flow

```
User Question → FastAPI → Agent Router → [SQL Tool | RAG Tool | Both]
                                                      ↓
                                    Synthesis LLM → Structured Response
```

**Example Queries:**
- SQL: "Monthly RAV4 HEV sales in Germany in 2024"
- RAG: "What is the standard Toyota warranty for Europe?"
- Hybrid: "Compare Toyota vs Lexus SUV sales in Western Europe in 2024 and summarize key warranty differences"

---

## Architecture Overview

```
┌─────────────────┐
│   Frontend      │  React + Vite (Chat UI)
│   (Vercel)      │
└────────┬────────┘
         │ HTTP/REST
┌────────▼────────┐
│   Backend       │  FastAPI (Python)
│   (Render)      │
└────────┬────────┘
         │
    ┌────┴───┐
    │ Agent  │  LangChain Orchestrator
    └───┬────┘
        │
    ┌───┴───────────────────┐
    │                       │
┌───▼────┐            ┌─────▼─────┐
│ SQL    │            │ RAG Tool  │
│ Tool   │            │           │
└───┬────┘            └─────┬─────┘
    │                       │
┌───▼────────┐        ┌─────▼─────┐
│SQLite      │        │  FAISS    │
│(Structured)│        │(Vectors)  │
└────────────┘        └───────────┘
```

**Technology Stack:**
- **Backend:** Python 3.10+, FastAPI, LangChain, SQLite, FAISS
- **Frontend:** React 18, Vite, TailwindCSS
- **LLM:** OpenAI (gpt-4o-mini, gpt-4o)
- **Deployment:** Render (backend), Vercel (frontend)

---

## Documentation

For detailed information, see:

- **[Backend README](backend/README.md)** - Backend architecture, API endpoints, testing, deployment
- **[Frontend README](frontend/README.md)** - Frontend setup, features, build instructions

---

## Testing

```bash
# Run all tests
cd backend
pytest

# Run specific test suites
pytest tests/unit/        # Unit tests
pytest tests/integration/ # Integration tests
pytest tests/e2e/        # End-to-End tests
```

**Test Coverage:**
- **Unit Tests:** Agent routing logic, schema validation, SQL query validation, conversation memory
- **Integration Tests:** API endpoints, async behavior, error handling, rate limiting
- **E2E Tests:** Full request/response cycles, SQL injection prevention, input validation, error information leakage

---

## Deployment

**Backend (Render):**
- Root directory: `backend`
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn src.app.main:app --host 0.0.0.0 --port $PORT`
- Environment variables: `OPENAI_API_KEY`, `CORS_ORIGINS`

**Frontend (Vercel):**
- Root directory: `frontend`
- Build command: `npm run build`
- Environment variables: `VITE_API_URL`

See [Backend README](backend/README.md) and [Frontend README](frontend/README.md) for detailed deployment instructions.

---

## Author & Contact

**Cristopher Rojas Lepe** — AI & Data Engineer
- LinkedIn: https://www.linkedin.com/in/cristopherrojaslepe/
- Email: cristopher.rojas.lepe@gmail.com

Feel free to reach out for walkthroughs or to dive into any architectural or prompt-engineering detail.

**Need more demo interactions?** If you're testing the [live demo](https://agentic-poc-lake.vercel.app/) and need additional interactions beyond the daily limit, please email me and I'll be happy to increase your limit.
