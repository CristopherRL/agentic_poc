from __future__ import annotations
from pathlib import Path
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# ----- default path helpers -----

# Project root
def _default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]

# ----- SQLITE DATABASE -----
# CSV directory
def _default_csv_dir() -> Path:
    return _default_project_root() / "docs" / "public" / "data"
# SQLite database
def _default_sqlite_path() -> Path:
    return _default_project_root() / "data" / "db" / "app.db"
# SQL schema report path
def _default_sql_schema_path() -> Path:
    return _default_project_root() / "data" / "db" / "sql_schema.md"

# ----- RAG DATABASE -----
# Documents directory
def _default_docs_dir() -> Path:
    return _default_project_root() / "docs" / "public" / "docs"
# Manuals directory
def _default_manuals_dir() -> Path:
    return _default_project_root() / "docs" / "public" / "docs" / "manuals"
# Vector database directory
def _default_vdb_dir() -> Path:
    return _default_project_root() / "data" / "vdb"
# FAISS index name
def _default_faiss_index_name() -> str:
    return "faiss_index"

# ----- default model hyperparameters -----

# Define Router LLM model
def _default_router_llm_model() -> str:
    return "gpt-4o-mini"
# Define Router LLM temperature
def _default_router_llm_temperature() -> float:
    return 0.0

# Define SQL LLM model
def _default_sql_llm_model() -> str:
    return "gpt-4o-mini"
# Define SQL LLM temperature
def _default_sql_llm_temperature() -> float:
    return 0.0

# Define Hybrid split LLM
def _default_split_llm_model() -> str:
    return "gpt-4o"
# Define Hybrid split LLM temperature
def _default_split_llm_temperature() -> float:
    return 0.0

# Define Synthesis LLM model
def _default_synthesis_llm_model() -> str:
    return "gpt-4o"
# Define Synthesis LLM temperature
def _default_synthesis_llm_temperature() -> float:
    return 0.2

# Define RAG top k
def _default_rag_top_k() -> int:
    return 4


# Define SQL keywords
def _default_sql_keywords() -> list[str]:
    return [
        "sales",
        "revenue",
        "quantity",
        "count",
        "sum",
        "average",
        "table",
        "query",
        "sql",
        "fact",
        "dim",
        "month",
        "year",
        "country",
        "model",
        "analytics",
        "report",
    ]
# Define Document keywords
def _default_doc_keywords() -> list[str]:
    return [
        "manual",
        "warranty",
        "contract",
        "policy",
        "appendix",
        "instructions",
        "procedure",
    ]

# Define question max length (for input validation)
def _default_question_max_length() -> int:
    """
    Maximum allowed length for user questions.
    Used to prevent DoS attacks via extremely long input strings.
    """
    return 2000

# Define rate limiting enable/disable flag
def _default_enable_rate_limit() -> bool:
    """
    Enable or disable daily rate limiting.
    Set to False for local development, True for demo/production environments.
    """
    return True

# Define daily interaction limit (for rate limiting)
def _default_daily_interaction_limit() -> int:
    """
    Maximum allowed interactions per day per identifier (IP address or user ID).
    Used to limit API usage in demo/production environments.
    Only applies when enable_rate_limit is True.
    """
    return 20

# Define dangerous SQL keywords (for security validation)
def _default_dangerous_sql_keywords() -> list[str]:
    """
    List of SQL keywords that are forbidden in generated queries.
    Used for security validation in both input validation (schemas) and SQL query validation (agent).
    """
    return [
        "DROP",
        "DELETE",
        "UPDATE",
        "INSERT",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "EXEC",
        "EXECUTE",
        "MERGE",
        "REPLACE",
    ]

# Define Route system prompt to determine the type of data required
def _default_route_system_prompt() -> str:
    return (
        "Decide whether the user's question requires structured SQL data, unstructured documents, both, or neither. "
        "Reply with exactly one word: 'SQL', 'RAG', 'BOTH', or 'NONE'. Use the provided heuristic hints as guidance."
    )

# Define RAG system prompt to answer the user's question
def _default_rag_system_prompt() -> str:
    return (
        "You are a Lexus/Toyota documentation expert. Answer using only the provided context. "
        "If the context is insufficient, say so. Cite sources in the format (Source: <path>, Page: <n>) whenever possible."
    )


# Define SQL generation system prompt to generate the SQL query
def _default_sql_generation_system_prompt() -> str:
    return (
        "You are a data analyst writing SQL for a Toyota/Lexus sales warehouse. "
        "Always return a single valid SQL SELECT statement. "
        "Respect filters implied by the user's question (models, powertrains, countries, years, months, order types). "
        "Use only the provided schema and join keys. Do not add commentary or markdown fences."
    )

# Define SQL system prompt to summarize the SQL results
def _default_sql_system_prompt() -> str:
    return (
        "You are a sales analytics assistant. Summarize the SQL results clearly and reference key figures. "
        "If the result is empty, explain why or state that more data is required."
    )

# Define Hybrid system prompt to combine the SQL and RAG results
def _default_hybrid_system_prompt() -> str:
    return (
        "You are an AI assistant that combines structured analytics with policy/manual insights. "
        "Blend both inputs, reconcile discrepancies, and cite document sources when applicable."
    )


# Define Insufficient context message
def _default_insufficient_context_message() -> str:
    return (
        "I'm here to help with Toyota/Lexus analytics and documentation. "
        "Could you provide more detail so I can choose the right data sources?"
    )

# Define Table comments
def _default_table_comments() -> dict[str, str]:
    return {
        "DIM_COUNTRY": (
            "Stores geography metadata: 'country' (full name), 'country_code' (ISO-2), and 'region' (e.g., Western Europe)."
        ),
        "DIM_MODEL": (
            "Catalog of vehicles: 'model_id' (unique), 'model_name', 'brand' (Toyota/Lexus), 'segment' (SUV), 'powertrain' (Petrol/HEV/PHEV)."
        ),
        "DIM_ORDERTYPE": (
            "Order classifications: 'ordertype_id' (unique), 'ordertype_name' (Private/Fleet/Demo), 'description' (B2C/B2B/Dealer demo)."
        ),
        "FACT_SALES": (
            "Core fact table of sales: 'model_id' -> DIM_MODEL, 'country_code' -> DIM_COUNTRY, plus 'year', 'month', 'contracts' (units sold)."
        ),
        "FACT_SALES_ORDERTYPE": (
            "Sales by order type: same keys as FACT_SALES plus 'ordertype_id' -> DIM_ORDERTYPE."
        ),
    }

# Define Hybrid split system prompt
def _default_hybrid_split_system_prompt() -> str:
    return (
        "You are a planning assistant. Split the incoming user question into two focused queries:"
        " one for SQL analytics against the sales warehouse and one for document-based RAG lookup."
        " Return a JSON object with keys 'sql_question' and 'rag_question'."
        " If a portion is unnecessary, return an empty string for that key."
        " Keep the phrasing concise and suitable for direct execution by downstream tools."
    )


def _default_sql_generation_user_prompt() -> str:
    return (
        "Database context:\n{schema}\n\n"
        "You are an expert SQL generation assistant. Your ONLY job is to write a single, valid SQL query.\n\n"
        "--- RULES ---\n"
        "1. **Analyze the User Question:** Identify all explicit filters (brand, model, segment, powertrain, country, region, year, month).\n"
        "2. **Use Exact Values:** You MUST use the exact filter values from the question (e.g., `fs.year = 2024` for '2024').\n"
        "3. **NO INVENTED FILTERS:** NEVER add filters that are not in the question. **NEVER** use 'Sample rows' for filter values.\n"
        "4. **Handle Comparisons:** For questions like 'Compare Toyota vs Lexus', use an `IN` clause (e.g., `dm.brand IN ('Toyota', 'Lexus')`) and `GROUP BY` the comparison column (e.g., `GROUP BY dm.brand`).\n"
        "5. **Handle Regions:** For regional questions (e.g., 'Western Europe'), you MUST `JOIN DIM_COUNTRY dc ON fs.country_code = dc.country_code` and filter on `dc.region`.\n"
        "6. **Handle Monthly:** If the question asks for 'monthly' results, add `fs.month` to the `SELECT` and `GROUP BY` clauses, but do **not** add a month filter unless a specific month is mentioned.\n"
        "7. **Output SQL ONLY:** Your output MUST be ONLY the SQL query. No commentary, no markdown.\n\n"
        "--- EXAMPLES (FOR REFERENCE ONLY; DO NOT ANSWER THESE) ---\n"
        "Question: Monthly RAV4 HEV sales in Germany in 2024\n"
        "SQL: SELECT fs.year, fs.month, SUM(fs.contracts) AS total_contracts FROM FACT_SALES fs JOIN DIM_MODEL dm ON fs.model_id = dm.model_id JOIN DIM_COUNTRY dc ON fs.country_code = dc.country_code WHERE dm.brand = 'Toyota' AND dm.model_name = 'RAV4' AND dm.powertrain = 'HEV' AND dc.country = 'Germany' AND fs.year = 2024 GROUP BY fs.year, fs.month;\n"
        "\n"
        "Question: Compare Toyota vs Lexus SUV sales in Western Europe in 2024\n"
        "SQL: SELECT dm.brand, SUM(fs.contracts) AS total_contracts FROM FACT_SALES fs JOIN DIM_MODEL dm ON fs.model_id = dm.model_id JOIN DIM_COUNTRY dc ON fs.country_code = dc.country_code WHERE dm.segment = 'SUV' AND dc.region = 'Western Europe' AND fs.year = 2024 AND dm.brand IN ('Toyota', 'Lexus') GROUP BY dm.brand;\n"
        "\n"
        "Question: Total sales for B2B fleet orders in France in 2023\n"
        "SQL: SELECT SUM(fs.contracts) AS total_contracts FROM FACT_SALES_ORDERTYPE fs JOIN DIM_ORDERTYPE do ON fs.ordertype_id = do.ordertype_id JOIN DIM_COUNTRY dc ON fs.country_code = dc.country_code WHERE do.ordertype_name = 'Fleet' AND dc.country_code = 'FR' AND fs.year = 2023;\n"
        "--- END OF EXAMPLES ---\n\n"
        "Now apply the rules to the actual user request below.\n"
        "USER QUESTION: {question}\n"
        "Return only the SQL query that answers this question."
    )


def _default_hybrid_split_user_prompt() -> str:
    return "User question: {question}\nReturn JSON with keys 'sql_question' and 'rag_question'."


class Settings(BaseSettings):
    """
    Application settings with environment-agnostic configuration.
    
    Configuration precedence (highest to lowest):
    1. Environment variables (system/env) - Used in cloud/production
    2. .env file (if exists) - Used in local development
    3. Default values (default_factory) - Fallback defaults
    
    This design allows the same code to work in:
    - Local development: Uses .env file
    - Cloud deployments: Uses environment variables/secrets (Azure Key Vault, AWS Secrets Manager, etc.)
    
    Example cloud deployment:
    - Set OPENAI_API_KEY as environment variable or secret
    - Set QUESTION_MAX_LENGTH as environment variable
    - .env file is ignored in cloud (or can be omitted)
    """
    model_config = SettingsConfigDict(
        env_file=".env",  # Optional: only used if file exists (local dev)
        env_file_encoding="utf-8",
        extra="ignore",
        # Note: env_file is optional - if .env doesn't exist, it's silently ignored
        # Environment variables always take precedence over .env file
    )

    # Secrets / credentials
    openai_api_key: str = Field(validation_alias=AliasChoices("openai_api_key", "open_api_key"))
    admin_token: str = Field(
        default="",
        description="Admin token for rate limit management endpoints. Set via ADMIN_TOKEN env var."
    )

    # Filesystem layout
    project_root: Path = Field(default_factory=_default_project_root)
    csv_dir: Path = Field(default_factory=_default_csv_dir)
    sqlite_path: Path = Field(default_factory=_default_sqlite_path)
    docs_dir: Path = Field(default_factory=_default_docs_dir)
    manuals_dir: Path = Field(default_factory=_default_manuals_dir)
    vdb_dir: Path = Field(default_factory=_default_vdb_dir)
    faiss_index_name: str = Field(default_factory=_default_faiss_index_name)
    sql_schema_path: Path = Field(default_factory=_default_sql_schema_path)

    # LLM defaults
    sql_llm_model: str = Field(default_factory=_default_sql_llm_model)
    sql_llm_temperature: float = Field(default_factory=_default_sql_llm_temperature)
    router_llm_model: str = Field(default_factory=_default_router_llm_model)
    router_llm_temperature: float = Field(default_factory=_default_router_llm_temperature)
    synthesis_llm_model: str = Field(default_factory=_default_synthesis_llm_model)
    synthesis_llm_temperature: float = Field(default_factory=_default_synthesis_llm_temperature)
    split_llm_model: str = Field(default_factory=_default_split_llm_model)
    split_llm_temperature: float = Field(default_factory=_default_split_llm_temperature)

    # Retrieval tuning
    rag_top_k: int = Field(default_factory=_default_rag_top_k)

    # Routing heuristics
    sql_keywords: list[str] = Field(default_factory=_default_sql_keywords)
    doc_keywords: list[str] = Field(default_factory=_default_doc_keywords)
    table_comments: dict[str, str] = Field(default_factory=_default_table_comments)
    
    # Security settings
    question_max_length: int = Field(default_factory=_default_question_max_length)
    dangerous_sql_keywords: list[str] = Field(default_factory=_default_dangerous_sql_keywords)
    
    # Rate limiting settings
    enable_rate_limit: bool = Field(default_factory=_default_enable_rate_limit)
    daily_interaction_limit: int = Field(default_factory=_default_daily_interaction_limit)

    # Prompt templates
    rag_system_prompt: str = Field(default_factory=_default_rag_system_prompt)
    sql_generation_system_prompt: str = Field(default_factory=_default_sql_generation_system_prompt)
    sql_generation_user_prompt: str = Field(default_factory=_default_sql_generation_user_prompt)
    sql_system_prompt: str = Field(default_factory=_default_sql_system_prompt)
    hybrid_system_prompt: str = Field(default_factory=_default_hybrid_system_prompt)
    hybrid_split_system_prompt: str = Field(default_factory=_default_hybrid_split_system_prompt)
    hybrid_split_user_prompt: str = Field(default_factory=_default_hybrid_split_user_prompt)
    route_system_prompt: str = Field(default_factory=_default_route_system_prompt)
    insufficient_context_message: str = Field(default_factory=_default_insufficient_context_message)

    @property
    def faiss_index_dir(self) -> Path:
        return self.vdb_dir / self.faiss_index_name


settings = Settings()

