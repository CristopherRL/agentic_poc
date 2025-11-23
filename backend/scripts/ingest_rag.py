from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from typing import Iterable
from langchain.schema import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from src.app.config import settings

LOGGER = logging.getLogger(__name__)
SUPPORTED_SUFFIXES = {".pdf", ".txt"}

def iter_source_files(base_dir: Path) -> list[Path]:
    return sorted(
        path for path in base_dir.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )

def split_manual_text(raw_text: str) -> list[str]:
    lines = raw_text.splitlines()
    chunks: list[list[str]] = []
    preamble: list[str] = []
    current: list[str] | None = None

    for line in lines:
        if line.startswith("================"):
            if current is not None:
                chunks.append(current)
            if preamble:
                current = preamble + [line]
                preamble = []
            else:
                current = [line]
        else:
            if current is None:
                preamble.append(line)
            else:
                current.append(line)

    if current is not None:
        chunks.append(current)
    elif preamble:
        chunks.append(preamble)

    return ["\n".join(chunk).strip() for chunk in chunks if any(value.strip() for value in chunk)]

def load_documents(source_paths: Iterable[Path]) -> list[Document]:
    documents: list[Document] = []

    for path in source_paths:
        rel_path = path.relative_to(settings.project_root)
        suffix = path.suffix.lower()
        LOGGER.info("Loading %s", rel_path)

        if suffix == ".pdf":
            loader = PyPDFLoader(str(path))
            pdf_docs = loader.load()
            if not pdf_docs:
                continue
            combined_text = "\n\n".join(doc.page_content for doc in pdf_docs)
            metadata = pdf_docs[0].metadata.copy() if pdf_docs[0].metadata else {}
            metadata.update({"source": str(rel_path), "chunk": 1})
            documents.append(Document(page_content=combined_text, metadata=metadata))
            continue

        raw_text = path.read_text(encoding="utf-8")
        for idx, chunk_text in enumerate(split_manual_text(raw_text), start=1):
            metadata = {"source": str(rel_path), "chunk": idx}
            page_match = re.search(r"PAGE\s+(\d+)", chunk_text)
            if page_match:
                metadata["page"] = int(page_match.group(1))
            documents.append(Document(page_content=chunk_text, metadata=metadata))

    if not documents:
        raise FileNotFoundError("No supported documents (.pdf/.txt) found under docs/public/docs/")

    return documents

def build_vector_store(documents: list[Document]) -> FAISS:
    embeddings = OpenAIEmbeddings(api_key=settings.openai_api_key)
    return FAISS.from_documents(documents, embeddings)

def persist_vector_store(store: FAISS, index_dir: Path | None = None) -> None:
    target_dir = index_dir or settings.faiss_index_dir
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    store.save_local(str(target_dir))
    LOGGER.info("FAISS index saved to %s", target_dir)

def reset_vector_store(index_dir: Path | None = None) -> None:
    target_dir = index_dir or settings.faiss_index_dir
    if target_dir.exists():
        shutil.rmtree(target_dir)
        LOGGER.info("Removed existing FAISS index at %s", target_dir)

def ingest(docs_dir: Path | None = None, index_dir: Path | None = None) -> None:
    source_dir = docs_dir or settings.docs_dir
    target_dir = index_dir or settings.faiss_index_dir
    
    LOGGER.info("Starting RAG ingestion process...")
    LOGGER.info("  Source documents directory: %s", source_dir)
    LOGGER.info("  Target vector store: %s", target_dir)
    
    LOGGER.info("  → Finding source files...")
    source_paths = iter_source_files(source_dir)
    LOGGER.info("  → Loading and processing documents...")
    documents = load_documents(source_paths)
    LOGGER.info("  → Prepared %d document(s) for indexing", len(documents))
    
    LOGGER.info("  → Building vector store (this may take a while)...")
    store = build_vector_store(documents)
    LOGGER.info("  → Persisting vector store to disk...")
    persist_vector_store(store, index_dir=index_dir)
    LOGGER.info("✓ RAG ingestion completed successfully. Vector store saved to %s", target_dir)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ingest()
