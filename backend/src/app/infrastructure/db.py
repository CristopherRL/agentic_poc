from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Union
from langchain_community.utilities import SQLDatabase
from src.app.config import settings


def _coerce_path(db_path: Union[str, Path, None] = None) -> Path:
    resolved = Path(db_path) if db_path is not None else settings.sqlite_path
    if not resolved.exists():
        raise FileNotFoundError(f"SQLite database not found at {resolved}")
    return resolved


@lru_cache(maxsize=1)
def get_sql_database(db_path: Union[str, Path, None] = None) -> SQLDatabase:
    """
    Get a read-only SQLDatabase connection to SQLite.
    
    Uses SQLite's read-only mode (`?mode=ro`) to prevent any write operations.
    This provides an additional layer of security beyond query validation.
    """
    resolved = _coerce_path(db_path)
    # Use read-only mode for additional security
    uri = f"sqlite:///{resolved}?mode=ro"
    return SQLDatabase.from_uri(uri)
