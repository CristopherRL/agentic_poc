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
    resolved = _coerce_path(db_path)
    uri = f"sqlite:///{resolved}"
    return SQLDatabase.from_uri(uri)
