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
# LLM model
def _default_llm_model() -> str:
    return "gpt-4o-mini"
# LLM temperature
def _default_llm_temperature() -> float:
    return 0.0
# RAG top k
def _default_rag_top_k() -> int:
    return 4


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Secrets / credentials
    openai_api_key: str = Field(validation_alias=AliasChoices("openai_api_key", "open_api_key"))

    # Filesystem layout
    project_root: Path = Field(default_factory=_default_project_root)
    csv_dir: Path = Field(default_factory=_default_csv_dir)
    sqlite_path: Path = Field(default_factory=_default_sqlite_path)
    docs_dir: Path = Field(default_factory=_default_docs_dir)
    manuals_dir: Path = Field(default_factory=_default_manuals_dir)
    vdb_dir: Path = Field(default_factory=_default_vdb_dir)
    faiss_index_name: str = Field(default_factory=_default_faiss_index_name)

    # LLM defaults
    llm_model: str = Field(default_factory=_default_llm_model)
    llm_temperature: float = Field(default_factory=_default_llm_temperature)

    # Retrieval tuning
    rag_top_k: int = Field(default_factory=_default_rag_top_k)

    @property
    def faiss_index_dir(self) -> Path:
        return self.vdb_dir / self.faiss_index_name


settings = Settings()

