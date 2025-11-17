# Agentic Assistant POC

![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)
![Framework](https://img.shields.io/badge/FastAPI-ready-green.svg)
![Agentic Stack](https://img.shields.io/badge/LangChain-hybrid-blueviolet.svg)
![Status](https://img.shields.io/badge/status-POC-orange.svg)

An intelligent agent that answers natural-language questions by intelligently routing between SQL analytics, document retrieval (RAG), or both. This POC demonstrates rapid prototyping discipline with reusable ingestion scripts, configurable multi-model routing, transparent responses, and production-ready documentation.

---

## 1. Problem Framing & Solution Overview

### Assignment Requirements

| Requirement from brief | Delivered capability | Technical approach |
| --- | --- | --- |
| SQL over provided CSVs | `scripts/ingest_sql.py` loads five datasets into SQLite; the agent generates grounded SQL with schema context. | **Offline ingestion:** CSV → SQLite with schema generation. **Online query:** LLM generates SQL using `data/db/sql_schema.md` as context. |
| RAG over contracts & manuals | `scripts/ingest_rag.py` creates a FAISS index over contracts, warranty appendix, and curated manual excerpts. | **Distinct chunking:** PDFs as single chunks; TXT manuals split by `====== PAGE` markers. **Embeddings:** OpenAI `text-embedding-3-small` via LangChain. |
| Hybrid reasoning | `src/app/core/agent.py` routes with a cost-aware SLM, splits hybrid questions with a dedicated LLM, and merges SQL + RAG evidence. | **Three-stage pipeline:** (1) Router classifies intent, (2) Split LLM decomposes hybrid questions, (3) Synthesis LLM combines results. |
| Transparent answers | `/api/v1/ask` returns `answer`, `sql_query`, `citations`, `tool_trace` for auditing and debugging. | **Structured response:** Pydantic schemas enforce transparency. `tool_trace` logs router decisions, tool invocations, and intermediate steps. |

### Architectural Approach: Modular Monolith

**Pragmatic Justification (The "Why"):**

This POC follows a **Modular Monolith** architecture with **Clean Architecture principles**, organized into three distinct layers:

1. **`src/app/api` (🔵 Layer 1 - API):** Knows about FastAPI, Pydantic schemas, and HTTP. Handles request/response validation and routing. Calls `core` layer.
2. **`src/app/core` (🟢 Layer 2 - Business Logic):** The "brain" of the application. Knows about the Agent, Tools, and routing logic. Does NOT know about FastAPI or HTTP.
3. **`src/app/infrastructure` (🔴 Layer 3 - External Services):** Knows how to talk to the "outside world" (LLM APIs, SQLite, FAISS). Implements the "how" for the `core` layer.

**Why this approach?**
- **Development velocity:** For a POC, this avoids microservices overhead while enforcing strong internal boundaries.
- **Maintainability:** Clean Architecture ensures core logic is decoupled from infrastructure, making it easy to swap LLM providers, databases, or vector stores.
- **Testability:** Each layer can be tested independently with mocks/stubs.
- **Future-proofing:** To migrate from SQLite → Postgres or FAISS → Azure AI Search, we only change the `infrastructure` layer. The `core` agent logic remains unchanged.

---

## 2. System Architecture & Data Flows

### 2.1. Offline Data Ingestion Flow

**Design Constraint:** The system must operate on pre-ingested data. Users query local data stores, not external APIs, ensuring sub-second response times.

This flow runs **asynchronously** (via manual script execution) to populate our dual data stores:

1. **SQL Ingestion (`scripts/ingest_sql.py`):**
   - **Input:** Five CSV files from `docs/public/data/` (dimension and fact tables).
   - **Process:** 
     - Uses `pandas` to read CSVs and `SQLAlchemy` to create tables.
     - Generates `data/db/sql_schema.md` with DDL, sample rows, and table comments (from `settings.table_comments`).
   - **Output:** SQLite database at `data/db/app.db` + schema artifact for LLM context.
   - **Reset capability:** `reset_database()` safely removes the DB file (handles locked files by dropping tables individually).

2. **RAG Ingestion (`scripts/ingest_rag.py`):**
   - **Input:** PDF contracts and TXT manuals from `docs/public/docs/`.
   - **Process:**
     - **PDFs:** Loaded as single chunks (contracts are self-contained documents).
     - **TXT manuals:** Split by `====== PAGE` markers (preserves page-level context for citations).
     - Uses `OpenAIEmbeddings` to generate vector embeddings.
     - Stores in FAISS index with metadata (source path, page numbers).
   - **Output:** FAISS index at `data/vdb/faiss_index/`.
   - **Reset capability:** `reset_vector_store()` removes the index directory.

**Why dual stores?**
- **SQLite:** Optimized for structured, aggregate queries (COUNT, GROUP BY, JOINs). Indexed for millisecond responses.
- **FAISS:** Optimized for semantic similarity search. Can't efficiently handle both structured and unstructured queries in a single store.

### 2.2. Online Query Flow (Real-time)

This flow describes what happens from the moment a user sends a question to `/api/v1/ask`:

1. **Input:** FastAPI receives `POST /api/v1/ask` with `{"question": "..."}`.
2. **Validation:** Pydantic `AskRequest` validates the input (non-empty string).
3. **Route to Core:** `src/app/api/router.py` calls `run_agent(question)` from `src/app/core/agent.py`.
4. **Router Decision (`_decide_route`):**
   - **Heuristic hints:** Checks for `settings.sql_keywords` (e.g., "sales", "revenue", "month") and `settings.doc_keywords` (e.g., "manual", "warranty").
   - **LLM classification:** Uses `router_llm` (default: `gpt-4o-mini`, temperature=0.0) with `settings.route_system_prompt` to classify intent:
     - `SQL`: Structured analytics query
     - `RAG`: Document/policy lookup
     - `BOTH`: Hybrid question requiring both
     - `NONE`: Insufficient context → returns `settings.insufficient_context_message`
   - **Fallback:** If LLM returns invalid response, falls back to heuristics. If still ambiguous, returns `None` (triggers clarification message).
5. **Tool Execution:**
   - **If `SQL`:** 
     - `_run_sql_pipeline()`:
       - Reads `data/db/sql_schema.md` for schema context.
       - Uses `sql_llm` (default: `gpt-4o-mini`) with `settings.sql_generation_system_prompt` and `settings.sql_generation_user_prompt` to generate SQL.
       - Executes query via LangChain `SQLDatabase.run()` (read-only).
       - Synthesizes answer using `synthesis_llm` (default: `gpt-4o`, temperature=0.2) with `settings.sql_system_prompt`.
   - **If `RAG`:**
     - `_run_rag_pipeline()`:
       - Loads FAISS index via `load_vector_store()`.
       - Performs `similarity_search(question, k=settings.rag_top_k)` (default: 4 documents).
       - Formats retrieved docs with source/page metadata.
       - Synthesizes answer using `synthesis_llm` with `settings.rag_system_prompt`.
   - **If `BOTH` (Hybrid):**
     - `_run_hybrid_pipeline()`:
       - Uses `split_llm` (default: `gpt-4o`, temperature=0.0) with `settings.hybrid_split_system_prompt` to decompose question into:
         - `sql_question`: Structured analytics portion
         - `rag_question`: Document lookup portion
       - Executes `_run_sql_pipeline(sql_question)` and `_run_rag_pipeline(rag_question)` in parallel (future: async).
       - Combines SQL results + RAG citations.
       - Synthesizes unified answer using `synthesis_llm` with `settings.hybrid_system_prompt`.
6. **Response Assembly:**
   - Maps agent output to `AskResponse` schema:
     - `answer`: Natural language response
     - `sql_query`: Generated SQL (if SQL route)
     - `citations`: List of `Citation` objects with `source_document`, `page`, `content` (if RAG route)
     - `tool_trace`: List of strings logging router decision, tool invocations, intermediate steps
7. **Return:** FastAPI serializes `AskResponse` to JSON and returns to client.

**Key Technical Challenges & Solutions:**

- **Challenge 1: SQL Query Accuracy.** LLMs can hallucinate table names, join keys, or filter values.
  - **Solution:** (1) Provide detailed schema context from `sql_schema.md` in the prompt. (2) Use strict prompt rules (`SQL_GENERATION_USER_PROMPT`) with examples. (3) Use `gpt-4o-mini` with temperature=0.0 for deterministic SQL generation.
- **Challenge 2: Hybrid Question Decomposition.** Splitting "Compare Toyota vs Lexus sales and warranty differences" into SQL and RAG portions is non-trivial.
  - **Solution:** Dedicated `split_llm` (`gpt-4o`) with explicit JSON schema (`{"sql_question": "...", "rag_question": "..."}`) and structured prompt.
- **Challenge 3: Cost Control.** Using `gpt-4o` for every task would be prohibitively expensive.
  - **Solution:** Multi-model strategy (see Section 3.2).

---

## 3. Technology Choices & Justifications

### 3.1. Backend Stack

**Language: Python 3.10+**
- **Justification:** Industry-standard for AI/ML with unparalleled library support (LangChain, FastAPI, SQLAlchemy, FAISS). Async support for concurrent operations.

**Web Framework: FastAPI**
- **Justification:** 
  - High-performance async framework (comparable to Node.js/Go).
  - Native Pydantic integration for request/response validation.
  - Automatic OpenAPI (Swagger) documentation.
  - Built-in support for streaming responses (future: SSE for chat UX).

**Orchestration: LangChain**
- **Justification:**
  - Provides abstraction layer for LLM providers (OpenAI, Anthropic, etc.). Enables easy provider switching.
  - Built-in components: `ChatOpenAI`, `SQLDatabase`, `FAISS` wrappers.
  - Tool/Agent patterns for routing logic.
  - **Future-proofing:** If we migrate to LangGraph or a different framework, the core agent logic (`src/app/core/agent.py`) remains isolated.

**Validation: Pydantic v2**
- **Justification:**
  - Type-safe schemas for API contracts (`AskRequest`, `AskResponse`, `Citation`).
  - Settings management via `pydantic-settings` (reads from `.env` with validation).
  - Automatic serialization/deserialization.

### 3.2. Multi-Model Strategy (Cost & Performance Optimization)

**Challenge:** Different tasks require different model capabilities. Using a single expensive model for everything would be cost-prohibitive and slow.

**Solution: Task-Specific Model Selection**

| Model | Use Case | Justification |
| --- | --- | --- |
| `gpt-4o-mini` (Router) | Intent classification | Fast, cheap ($0.15/1M input tokens). Deterministic (temperature=0.0) for consistent routing. |
| `gpt-4o-mini` (SQL Generation) | Text-to-SQL translation | Structured output (SQL) doesn't require creative reasoning. Temperature=0.0 ensures deterministic queries. |
| `gpt-4o` (Hybrid Split) | Question decomposition | Requires nuanced understanding to split hybrid questions. Higher quality model ensures accurate decomposition. |
| `gpt-4o` (Synthesis) | Answer generation | Natural language synthesis requires high-quality reasoning. Temperature=0.2 allows slight variation for natural responses. |

**Cost Impact:**
- **Example query:** "Monthly RAV4 HEV sales in Germany in 2024"
  - Router: `gpt-4o-mini` (~100 tokens) = $0.000015
  - SQL generation: `gpt-4o-mini` (~500 tokens) = $0.000075
  - Synthesis: `gpt-4o` (~200 tokens) = $0.0006
  - **Total: ~$0.0007 per query**
- **If using `gpt-4o` for all steps:** ~$0.002 per query (3x more expensive).

**Configuration:** All models and temperatures are configurable via `.env` (see `src/app/config.py`), enabling A/B testing and cost optimization.

### 3.3. Data Infrastructure

**Structured Store: SQLite**
- **Justification (POC):**
  - Zero-configuration, file-based database. Perfect for local development and demos.
  - SQLAlchemy provides abstraction layer. Migration to Postgres/Snowflake requires only changing the connection string.
  - **Production path:** Migrate to managed Postgres (Azure Database for PostgreSQL) for concurrency and scale.

**Vector Store: FAISS (CPU)**
- **Justification (POC):**
  - Local, file-based vector index. No external dependencies.
  - LangChain wrappers provide consistent API. Migration to Azure AI Search/Pinecone requires only changing the `load_vector_store()` implementation.
  - **Production path:** Migrate to managed vector store (Azure AI Search) for scale, security, and hybrid search capabilities.

**Why not a single database?**
- **SQLite/Postgres:** Optimized for structured queries (JOINs, aggregations, indexes). Cannot efficiently perform semantic similarity search.
- **FAISS/Azure AI Search:** Optimized for vector similarity search. Cannot efficiently handle complex SQL queries.
- **Dual-store architecture:** Each store is optimized for its use case. The agent orchestrates both as needed.

### 3.4. Configuration Management

**Centralized Settings: `src/app/config.py`**

All configurable parameters are centralized using `pydantic-settings`:

- **Paths:** Database locations, document directories, vector store paths.
- **LLM Models & Temperatures:** Router, SQL, Split, Synthesis models.
- **RAG Tuning:** `rag_top_k` (number of documents to retrieve).
- **Routing Heuristics:** `sql_keywords`, `doc_keywords` for hint generation.
- **Prompts:** All system and user prompts (router, SQL generation, RAG synthesis, hybrid split/synthesis).
- **Table Comments:** Metadata for SQL schema generation.

**Why `.env` + `config.py`?**
- **`.env`:** Stores secrets (API keys) and environment-specific overrides. Git-ignored for security.
- **`config.py`:** Provides defaults and validation. Ensures type safety and prevents runtime errors.
- **Override precedence:** `.env` values override `config.py` defaults. Enables per-environment configuration (dev/staging/prod) without code changes.

---

## 4. Data Assets

### 4.1. Structured Data (SQLite)

| Table | Key columns | Purpose | Design rationale |
| --- | --- | --- | --- |
| `DIM_COUNTRY` | `country`, `country_code`, `region` | Geo metadata for joins and region filters. | Dimension table for star schema. Enables efficient region-based aggregations. |
| `DIM_MODEL` | `model_id`, `model_name`, `brand`, `segment`, `powertrain` | Vehicle catalogue bridging to facts. | Dimension table. Supports filtering by brand/model/powertrain without denormalizing fact table. |
| `DIM_ORDERTYPE` | `ordertype_id`, `ordertype_name`, `description` | Sales channel semantics. | Dimension table for order type analysis (B2C vs B2B). |
| `FACT_SALES` | `model_id`, `country_code`, `year`, `month`, `contracts` | Monthly sales volumes. | Core fact table. Grain: model × country × year × month. |
| `FACT_SALES_ORDERTYPE` | `model_id`, `country_code`, `year`, `month`, `ordertype_id`, `contracts` | Sales by channel. | Extended fact table for order type analysis. |

**Schema Artifact:** `scripts/ingest_sql.py` generates `data/db/sql_schema.md` containing:
- `CREATE TABLE` statements (DDL)
- Sample rows (first 3 rows per table)
- Table comments (from `settings.table_comments`) explaining purpose and relationships

This artifact is injected into the SQL generation prompt, providing the LLM with accurate schema context and reducing hallucination.

### 4.2. Unstructured Data (FAISS Index)

| File | Location | Coverage | Chunking strategy |
| --- | --- | --- | --- |
| `Contract_Toyota_2023.pdf` | `docs/public/docs/` | Toyota fleet contract clauses, warranty obligations. | Single chunk (entire PDF). Contracts are self-contained documents. |
| `Contract_Lexus_2023.pdf` | `docs/public/docs/` | Lexus contract counterpart. | Single chunk. |
| `Warranty_Policy_Appendix.pdf` | `docs/public/docs/` | Regional warranty rules and escalation paths. | Single chunk. |
| `Toyota_RAV4.txt` | `docs/public/docs/manuals/` | Safety section: SRS airbags, child restraints, seat belts. | Split by `====== PAGE` markers. Preserves page-level context for citations. |
| `Toyota_YARIS_GRMN.txt` | `docs/public/docs/manuals/` | Keys, smart entry, alarms, battery recovery. | Split by `====== PAGE` markers. |

**Information Coverage:**
- **Toyota RAV4:** SRS airbag component map, deployment rules, child-seat guidance, seat-belt pretensioner maintenance checkpoints.
- **Toyota Yaris GRMN:** Smart entry key types, antenna coverage diagrams, alarm troubleshooting, electronic key battery recovery/customisation notes.

**Why distinct chunking strategies?**
- **PDFs (contracts):** Legal documents are best understood as complete units. Splitting could lose context (e.g., warranty terms spanning multiple pages).
- **TXT manuals:** Technical manuals have page-level structure. Splitting by `====== PAGE` preserves citation accuracy (users can reference "page 4") while maintaining semantic coherence.

---

## 5. Setup & Environment

### 5.1. Prerequisites

- Python 3.10+ (tested on 3.11)
- OpenAI API key (for LLM and embeddings)

### 5.2. Installation Steps

| Step | Windows (PowerShell) | macOS / Linux (bash/zsh) |
| --- | --- | --- |
| Clone repo | `git clone <repo-url>`<br>`cd agentic_poc` | same |
| Python venv | `python -m venv .venv` | `python3 -m venv .venv` |
| Activate venv | `.\.venv\Scripts\Activate.ps1` | `source .venv/bin/activate` |
| Install deps | `pip install -r requirements.txt` | `pip install -r requirements.txt` |
| Configure OpenAI key | `Copy-Item .env.example .env` then edit | `cp .env.example .env` then edit |

> **Important:** `OPEN_API_KEY` (or `openai_api_key`) must be set in `.env`. The `.env` file is Git-ignored for security. Docker requires `--env-file .env` at runtime.

### 5.3. Data Ingestion (Run After Setup)

| Task | Windows (PowerShell) | macOS / Linux (bash/zsh) |
| --- | --- | --- |
| Build/refresh SQLite | `python -m scripts.ingest_sql` | same |
| Reset DB file | `python -c "from scripts.ingest_sql import reset_database; reset_database()"` | `python -c 'from scripts.ingest_sql import reset_database; reset_database()'` |
| Build/refresh FAISS | `python -m scripts.ingest_rag` | same |
| Reset FAISS index | `python -c "from scripts.ingest_rag import reset_vector_store; reset_vector_store()"` | `python -c 'from scripts.ingest_rag import reset_vector_store; reset_vector_store()'` |

**Why reset functions?**
- Enables iterative development: update CSVs/manuals → reset → re-ingest.
- Handles locked files gracefully (SQLite on Windows can be locked by active connections).

---

## 6. Running the API

### Option A – Local Uvicorn

| Action | Windows (PowerShell) | macOS / Linux (bash/zsh) |
| --- | --- | --- |
| Start server | `uvicorn src.app.main:app --host 0.0.0.0 --port 8000 --reload` | same |
| Health check | `Invoke-WebRequest -Uri http://127.0.0.1:8000/health` | `curl http://127.0.0.1:8000/health` |
| Ask question | `Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/ask" -Method POST -ContentType "application/json" -Body '{"question": "Compare Toyota vs Lexus SUV sales in Western Europe in 2024 and summarize warranty differences"}'` | `curl -X POST http://127.0.0.1:8000/api/v1/ask -H "Content-Type: application/json" -d '{"question": "Compare Toyota vs Lexus SUV sales in Western Europe in 2024 and summarize warranty differences"}'` |

**Why `--reload`?**
- Enables hot-reload during development. Code changes trigger automatic server restart.

### Option B – Docker

| Action | Windows (PowerShell) | macOS / Linux (bash/zsh) |
| --- | --- | --- |
| Build image | `docker build -t agentic-poc .` | same |
| Run container | `docker run --rm -p 8001:8000 --env-file .env agentic-poc` | same |
| Health check | `Invoke-WebRequest -Uri http://127.0.0.1:8001/health` | `curl http://127.0.0.1:8001/health` |
| Ask question | `Invoke-WebRequest -Uri "http://127.0.0.1:8001/api/v1/ask" -Method POST -ContentType "application/json" -Body '{"question": "Monthly RAV4 HEV sales in Germany in 2024"}'` | `curl -X POST http://127.0.0.1:8001/api/v1/ask -H "Content-Type: application/json" -d '{"question": "Monthly RAV4 HEV sales in Germany in 2024"}'` |

> **Note:** Change the host port (`-p 8002:8000`) if 8001 is already taken. Docker requires the `.env` file for the API key via `--env-file`.

**Dockerfile Strategy:**
- Multi-stage builds (future optimization).
- Copies only `src/`, `data/`, `docs/public/` (excludes private docs and `.env`).
- Exposes port 8000 for FastAPI.

---

## 7. Sample Questions & Expected Behavior

| Question | Expected route | Technical details |
| --- | --- | --- |
| "Monthly RAV4 HEV sales in Germany in 2024." | SQL | Router detects `sql_keywords` ("sales", "month"). LLM generates SQL with `JOIN DIM_MODEL`, filters `brand='Toyota'`, `model_name='RAV4'`, `powertrain='HEV'`, `country_code='DE'`, `year=2024`, `GROUP BY month`. `sql_query` returned in response. |
| "What is the standard Toyota warranty for Europe?" | RAG | Router detects `doc_keywords` ("warranty"). FAISS retrieves relevant chunks from `Contract_Toyota_2023.pdf` and `Warranty_Policy_Appendix.pdf`. Citations include source PDF and page numbers. |
| "Where is the tire repair kit located for the UX?" | RAG | Router routes to RAG. FAISS searches manuals. Current manual set covers analogous safety topics (extendable). Citations reference manual source. |
| "Compare Toyota vs Lexus SUV sales in Western Europe in 2024 and summarize key warranty differences." | Hybrid | Router detects both SQL and RAG intent. Split LLM decomposes: `sql_question="Compare Toyota vs Lexus SUV sales in Western Europe in 2024"`, `rag_question="summarize key warranty differences between Toyota and Lexus"`. Both pipelines execute. Synthesis LLM combines results with citations. |

**Transparency Features:**
- `tool_trace` shows router decision, executed tools, and hybrid synthesis steps.
- `sql_query` enables SQL validation and debugging.
- `citations` enable source verification for RAG answers.

---

## 8. Testing Strategy

### 8.1. Automated Tests

| Scope | Command | What it tests |
| --- | --- | --- |
| Pytest (unit + integration) | `python -m pytest tests/unit/test_agent.py tests/integration/test_api.py -vv` | Unit tests: Router logic, SQL/RAG/hybrid branches, insufficient-context fallback. Integration tests: FastAPI endpoint, response schema validation, error handling. |

**Testing Philosophy:**
- **Unit tests:** Mock LLM calls and database/vector store access. Test routing logic, prompt formatting, citation building.
- **Integration tests:** Use FastAPI `TestClient` to test full request/response cycle. Validate Pydantic schemas.

### 8.2. Manual Testing

Extended manual checks (hybrid splits, FAISS probes, settings inspection) are documented in `docs/private/local_testing.md`. This includes:
- Direct FAISS similarity searches
- SQL schema inspection
- Agent function invocation from Python REPL
- Configuration validation

**Why manual testing?**
- LLM behavior is non-deterministic (even with temperature=0.0, prompts can vary).
- Vector search quality requires human evaluation.
- Prompt engineering requires iterative testing.

---

## 9. Technical Debt & Production Path

This POC is designed for **rapid demonstration** and **iterative development**. The following items are documented to guide next-phase investment and stakeholder discussions:

1. **Conversation memory:** Implement short-term memory management within the same conversation session (e.g., LangChain `ConversationBufferMemory` or custom session store) to enable contextual follow-up questions and maintain conversation state across multiple API calls.
2. **Managed persistence:** Migrate SQLite → Postgres/Snowflake; FAISS → managed vector store (Azure AI Search, Pinecone) for scale & concurrency.
3. **Automated manual ingestion:** Replace manual TXT extraction with Playwright/puppeteer crawler or official API; address licensing.
4. **Secrets & security:** Move `.env` into a vault (Azure Key Vault), enforce least-privilege DB roles, add request auth (API keys, OAuth).
5. **Observability & LLMOps:** Add structured logging, tracing, and LangSmith instrumentation for prompt cost/drift monitoring.
6. **CI/CD:** GitHub Actions or Azure DevOps pipeline running lint/tests/docker build on push.
7. **LangGraph migration:** Upgrade planner to LangGraph for explicit state management, retries, and better guardrails.
8. **Stakeholder interface:** Wrap the API with a lightweight UI (Streamlit/Gradio) for demos and workshops.
9. **Streaming responses:** Implement Server-Sent Events (SSE) for real-time answer streaming (improves perceived latency).
10. **Caching:** Add Redis cache for identical queries to reduce LLM costs and latency.

**Production Readiness Checklist:**
- [ ] Authentication/authorization
- [ ] Rate limiting
- [ ] Error handling & retries
- [ ] Monitoring & alerting
- [ ] Load testing
- [ ] Security audit

---

## 10. Author & Contact

**Cristopher Rojas Lepe** — Lead AI Engineer
- LinkedIn: https://www.linkedin.com/in/cristopherrojas
- Email: crojaslepe@gmail.com

Feel free to reach out for walkthroughs or to dive into any architectural or prompt-engineering detail. Every decision traces back to the PRD/TDD/backlog for quick context.

---

## Appendix: Key Design Decisions

### A.1. Why LangChain Instead of Direct OpenAI SDK?

**Decision:** Use LangChain as an abstraction layer for LLM orchestration.

**Rationale:**
- **Provider agnosticism:** LangChain supports OpenAI, Anthropic, Azure OpenAI, etc. Switching providers requires only changing the model wrapper, not the agent logic.
- **Tool patterns:** Built-in support for agents, tools, and chains simplifies routing logic.
- **Future-proofing:** If we migrate to LangGraph or a different framework, the core agent logic remains isolated in `src/app/core/agent.py`.

**Trade-off:** Slight performance overhead vs. direct SDK calls. Acceptable for POC; can optimize in production.

### A.2. Why Heuristic + LLM Routing Instead of Pure LLM?

**Decision:** Combine keyword heuristics with LLM classification for routing.

**Rationale:**
- **Cost:** Heuristics are free. LLM call costs ~$0.000015 per query. Using heuristics as hints reduces LLM token count.
- **Reliability:** Heuristics provide fallback if LLM returns invalid response.
- **Speed:** Heuristic checks are instant. LLM calls add ~100-200ms latency.

**Trade-off:** Heuristics can be brittle (e.g., "sales manual" might trigger SQL keywords). LLM classification handles edge cases.

### A.3. Why Separate Split LLM for Hybrid Questions?

**Decision:** Use dedicated `gpt-4o` model for hybrid question decomposition.

**Rationale:**
- **Complexity:** Splitting "Compare Toyota vs Lexus sales and warranty differences" requires nuanced understanding of which parts are SQL vs. RAG.
- **Quality:** `gpt-4o-mini` can misclassify hybrid questions. `gpt-4o` ensures accurate decomposition.
- **Cost:** Split LLM is called once per hybrid query. Synthesis LLM is called regardless. Net cost increase is minimal (~$0.0002 per hybrid query).

**Trade-off:** Slightly higher cost vs. improved accuracy. Worth it for hybrid queries (typically <10% of total queries).

---


