# Agentic Assistant POC

![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)
![Framework](https://img.shields.io/badge/FastAPI-ready-green.svg)
![Agentic Stack](https://img.shields.io/badge/LangChain-hybrid-blueviolet.svg)
![Status](https://img.shields.io/badge/status-POC-orange.svg)

Agent that answers natural-language questions by choosing between SQL analytics, document retrieval, or both. It follows the assignment brief (4 canonical questions) and demonstrates rapid prototyping discipline: reusable ingestion scripts, configurable multi-model routing, transparent responses, and handoff-ready documentation.

---

## 1. Problem Framing

| Requirement from brief | Delivered capability |
| --- | --- |
| SQL over provided CSVs | `scripts/ingest_sql.py` loads the five datasets into SQLite; the agent generates grounded SQL with schema context. |
| RAG over contracts & manuals | `scripts/ingest_rag.py` creates a FAISS index over contracts, warranty appendix, and curated manual excerpts. |
| Hybrid reasoning | `src/app/core/agent.py` routes with a cost-aware SLM, splits hybrid questions with a dedicated LLM, and merges SQL + RAG evidence. |
| Transparent answers | `/api/v1/ask` returns `answer`, `sql_query`, `citations`, `tool_trace` for auditing and debugging. |

---

## 2. System Highlights (ties back to job responsibilities)

- **Agentic orchestration:** LangChain router + tool stack implements SQL/RAG/hybrid routing, with tool traces for explainability.
- **Multi-model strategy:** `src/app/config.py` centralises model choices: `gpt-4o-mini` for routing & SQL generation, `gpt-4o` for synthesis, `gpt-4o` (high quality) for hybrid splitting. Switchable via `.env`.
- **Design-for-advisory:** Architecture diagram, backlog, and technical debt sections document trade-offs, production path, and governance — critical for guiding stakeholders.
- **Rapid prototyping discipline:** Ingestion scripts, local vector DB, and Docker packaging keep the POC runnable offline and ready for iteration.
- **Transparency & observability hooks:** Unified `tool_trace`, schema artefacts (`data/db/sql_schema.md`), and manual testing recipes accelerate debugging and mentoring.

---

## 3. Data Assets

### Structured (SQLite)

| Table | Key columns | Purpose |
| --- | --- | --- |
| `DIM_COUNTRY` | `country`, `country_code`, `region` | Geo metadata for joins and region filters. |
| `DIM_MODEL` | `model_id`, `model_name`, `brand`, `segment`, `powertrain` | Vehicle catalogue bridging to facts. |
| `DIM_ORDERTYPE` | `ordertype_id`, `ordertype_name`, `description` | Sales channel semantics. |
| `FACT_SALES` | `model_id`, `country_code`, `year`, `month`, `contracts` | Monthly sales volumes. |
| `FACT_SALES_ORDERTYPE` | `model_id`, `country_code`, `year`, `month`, `ordertype_id`, `contracts` | Sales by channel. |

`scripts/ingest_sql.py` regenerates `data/db/sql_schema.md` (DDL + samples + table comments) to ground the SQL prompt.

### Unstructured (FAISS index)

| File | Location | Coverage |
| --- | --- | --- |
| `Contract_Toyota_2023.pdf` | `docs/public/docs/` | Toyota fleet contract clauses, warranty obligations. |
| `Contract_Lexus_2023.pdf` | `docs/public/docs/` | Lexus contract counterpart. |
| `Warranty_Policy_Appendix.pdf` | `docs/public/docs/` | Regional warranty rules and escalation paths. |
| `Toyota_RAV4.txt` | `docs/public/docs/manuals/` | Safety section: SRS airbags, child restraints, seat belts. |
| `Toyota_YARIS_GRMN.txt` | `docs/public/docs/manuals/` | Keys, smart entry, alarms, battery recovery. |

#### Information that has been download from Toyota's manuals:
- `Toyota RAV4`: SRS airbag component map, deployment rules, child-seat guidance, and seat-belt pretensioner maintenance checkpoints.
- `Toyota Yaris GRMN`: Smart entry key types, antenna coverage diagrams, alarm troubleshooting, and electronic key battery recovery/customisation notes.

---

## 4. Setup & Environment

| Step | Windows (PowerShell) | macOS / Linux (bash/zsh) |
| --- | --- | --- |
| Clone repo | `git clone <repo-url>`<br>`cd agentic_poc` | same |
| Python venv | `python -m venv .venv` | `python3 -m venv .venv` |
| Activate venv | `.\.venv\Scripts\Activate.ps1` | `source .venv/bin/activate` |
| Install deps | `pip install -r requirements.txt` | `pip install -r requirements.txt` |
| Configure OpenAI key | `Copy-Item .env.example .env` then edit | `cp .env.example .env` then edit |

> `OPEN_API_KEY` must be set (alias `openai_api_key` also accepted). `.env` stays out of Git and Docker context via `.gitignore` / `.dockerignore`.

---

## 5. Data Ingestion (run after setup)

| Task | Windows (PowerShell) | macOS / Linux (bash/zsh) |
| --- | --- | --- |
| Build/refresh SQLite | `python -m scripts.ingest_sql` | same |
| Reset DB file | `python -c "from scripts.ingest_sql import reset_database; reset_database()"` | `python -c 'from scripts.ingest_sql import reset_database; reset_database()'` |
| Build/refresh FAISS | `python -m scripts.ingest_rag` | same |
| Reset FAISS index | `python -c "from scripts.ingest_rag import reset_vector_store; reset_vector_store()"` | `python -c 'from scripts.ingest_rag import reset_vector_store; reset_vector_store()'` |


---

## 6. Running the API

### Option A – Local Uvicorn

| Action | Windows (PowerShell) | macOS / Linux (bash/zsh) |
| --- | --- | --- |
| Start server | `uvicorn src.app.main:app --host 0.0.0.0 --port 8000 --reload` | same |
| Health check | `Invoke-WebRequest -Uri http://127.0.0.1:8000/health` | `curl http://127.0.0.1:8000/health` |
| Ask question | `Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/ask" -Method POST -ContentType "application/json" -Body '{"question": "Compare Toyota vs Lexus SUV sales in Western Europe in 2024 and summarize warranty differences"}'` | `curl -X POST http://127.0.0.1:8000/api/v1/ask -H "Content-Type: application/json" -d '{"question": "Compare Toyota vs Lexus SUV sales in Western Europe in 2024 and summarize warranty differences"}'` |

### Option B – Docker

| Action | Windows (PowerShell) | macOS / Linux (bash/zsh) |
| --- | --- | --- |
| Build image | `docker build -t agentic-poc .` | same |
| Run container | `docker run --rm -p 8001:8000 --env-file .env agentic-poc` | same |
| Health check | `Invoke-WebRequest -Uri http://127.0.0.1:8001/health` | `curl http://127.0.0.1:8001/health` |
| Ask question | `Invoke-WebRequest -Uri "http://127.0.0.1:8001/api/v1/ask" -Method POST -ContentType "application/json" -Body '{"question": "Monthly RAV4 HEV sales in Germany in 2024"}'` | `curl -X POST http://127.0.0.1:8001/api/v1/ask -H "Content-Type: application/json" -d '{"question": "Monthly RAV4 HEV sales in Germany in 2024"}'` |

> Change the host port (`-p 8002:8000`) if 8001 is already taken. Docker requires the `.env` file for the API key via `--env-file`.

---

## 7. Sample Questions (from the brief)

| Question | Expected route | Notes |
| --- | --- | --- |
| “Monthly RAV4 HEV sales in Germany in 2024.” | SQL | Aggregates monthly contracts using schema hints; `sql_query` returned. |
| “What is the standard Toyota warranty for Europe?” | RAG | Pulls contract + appendix snippets; citations reference source PDF. |
| “Where is the tire repair kit located for the UX?” | RAG | Manual excerpt (extendable set; current manual covers analogous safety topics). |
| “Compare Toyota vs Lexus SUV sales in Western Europe in 2024 and summarize key warranty differences.” | Hybrid | Split LLM issues SQL and RAG sub-questions; final LLM synthesises both contexts. |

`tool_trace` shows the router decision, executed tools, and hybrid synthesis steps for transparency.

---

## 8. Testing

| Scope | Command |
| --- | --- |
| Pytest (unit + integration) | `python -m pytest tests/unit/test_agent.py tests/integration/test_api.py -vv` |

- Unit tests monkeypatch the router to assert SQL/RAG/hybrid branches and insufficient-context fallback.
- Integration tests call `/api/v1/ask` through FastAPI’s `TestClient`, validating response schema and mapping logic.
- Extended manual checks (hybrid splits, FAISS probes, settings inspection) are documented in the local testing guide bundled with the project.

---

## 9. Technical Debt & Follow-up Items

1. **Conversation memory:** implement short-term memory management within the same conversation session (e.g., LangChain `ConversationBufferMemory` or custom session store) to enable contextual follow-up questions and maintain conversation state across multiple API calls.
2. **Managed persistence:** migrate SQLite → Postgres/Snowflake; FAISS → managed vector store (Azure AI Search, Pinecone) for scale & concurrency.
3. **Automated manual ingestion:** replace manual TXT extraction with Playwright/puppeteer crawler or official API; address licensing.
4. **Secrets & security:** move `.env` into a vault (Azure Key Vault), enforce least-privilege DB roles, add request auth.
5. **Observability & LLMOps:** add structured logging, tracing, and LangSmith instrumentation for prompt cost/drift monitoring.
6. **CI/CD:** GitHub Actions or Azure DevOps pipeline running lint/tests/docker build on push.
7. **LangGraph migration:** upgrade planner to LangGraph for explicit state management, retries, and better guardrails.
8. **Stakeholder interface:** wrap the API with a lightweight UI (Streamlit/Gradio) for demos and workshops.

These items are documented to guide next-phase investment and client advisory discussions.

---

## 10. Author

Cristopher Rojas Lepe — Lead AI Engineer
- LinkedIn: https://www.linkedin.com/in/cristopherrojas
- Email: crojaslepe@gmail.com

Feel free to reach out for walkthroughs or to dive into any architectural or prompt-engineering detail. Every decision traces back to the PRD/TDD/backlog for quick context.
