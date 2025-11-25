from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from typing import Iterable
from langchain.schema import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.prompts import ChatPromptTemplate
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


def write_rag_summary(documents: list[Document], summary_path: Path) -> None:
    """Generate a brief summary of RAG documents using LLM for user reference."""
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not documents:
        LOGGER.warning("No documents to summarize")
        summary_path.write_text("RAG summary not available. No documents were indexed.", encoding="utf-8")
        return
    
    # Collect document metadata and representative content samples for summary
    doc_info = []
    seen_sources = set()
    
    for doc in documents:
        source = doc.metadata.get("source", "unknown")
        source_name = Path(source).name
        
        # Only process each unique source once (documents may be chunked)
        if source in seen_sources:
            continue
        seen_sources.add(source)
        
        # Take first 1000 chars as sample, or full content if shorter
        content_sample = doc.page_content[:1000] if len(doc.page_content) > 1000 else doc.page_content
        page_info = f" (Page {doc.metadata.get('page', 'N/A')})" if doc.metadata.get('page') else ""
        doc_info.append(f"Document: {source_name}{page_info}\nContent preview: {content_sample}")
    
    documents_text = "\n\n---\n\n".join(doc_info)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a document analyst assistant. Generate a brief, user-friendly summary of the documents being indexed. Focus on what information is available and what users can ask about."),
        ("user", "Based on these documents being indexed, generate a concise summary (2-3 paragraphs) explaining:\n1. What types of documents are available (e.g., contracts, manuals, policies)\n2. What information users can find in them\n3. What questions users can ask about this content\n\nDocuments:\n{documents}")
    ])
    
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.0,
        api_key=settings.openai_api_key,
    )
    
    LOGGER.info("Generating RAG summary using LLM from %d document(s)...", len(documents))
    messages = prompt.format_prompt(documents=documents_text).to_messages()
    response = llm.invoke(messages)
    summary = (response.content or "").strip()
    
    summary_path.write_text(summary, encoding="utf-8")
    LOGGER.info("RAG summary written to %s", summary_path)

def reset_vector_store(index_dir: Path | None = None) -> None:
    target_dir = index_dir or settings.faiss_index_dir
    if target_dir.exists():
        shutil.rmtree(target_dir)
        LOGGER.info("Removed existing FAISS index at %s", target_dir)

def ingest(docs_dir: Path | None = None, index_dir: Path | None = None) -> None:
    source_dir = docs_dir or settings.docs_dir
    target_dir = index_dir or settings.faiss_index_dir
    summary_path = target_dir.parent / "rag_summary.md"
    
    LOGGER.info("Starting RAG ingestion process...")
    LOGGER.info("  Source documents directory: %s", source_dir)
    LOGGER.info("  Target vector store: %s", target_dir)
    
    reset_vector_store(index_dir)
    LOGGER.info("  → Vector store reset completed")
    
    LOGGER.info("  → Finding source files...")
    source_paths = iter_source_files(source_dir)
    LOGGER.info("  → Loading and processing documents...")
    documents = load_documents(source_paths)
    LOGGER.info("  → Prepared %d document(s) for indexing", len(documents))
    
    LOGGER.info("  → Building vector store (this may take a while)...")
    store = build_vector_store(documents)
    LOGGER.info("  → Persisting vector store to disk...")
    persist_vector_store(store, index_dir=index_dir)
    LOGGER.info("  → Writing RAG summary...")
    write_rag_summary(documents, summary_path)
    LOGGER.info("✓ RAG ingestion completed successfully. Vector store saved to %s", target_dir)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ingest()
