from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Union
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from src.app.config import settings

@lru_cache(maxsize=1)
def _get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(api_key=settings.openai_api_key)

def load_vector_store(index_dir: Union[str, Path, None] = None) -> FAISS:
    resolved_dir = Path(index_dir) if index_dir is not None else settings.faiss_index_dir
    if not resolved_dir.exists():
        raise FileNotFoundError(f"FAISS index directory not found: {resolved_dir}")

    embeddings = _get_embeddings()
    return FAISS.load_local(
        str(resolved_dir),
        embeddings,
        allow_dangerous_deserialization=True,
    )
