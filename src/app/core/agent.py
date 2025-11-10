from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional

from langchain_core.prompts import ChatPromptTemplate

from src.app.config import settings
from src.app.infrastructure.db import get_sql_database
from src.app.infrastructure.llm import get_sql_llm, get_router_llm, get_synthesis_llm, get_split_llm
from src.app.infrastructure.vector_store import load_vector_store

RAG_ROUTE = "RAG"
SQL_ROUTE = "SQL"
HYBRID_ROUTE = "HYBRID"
RAG_TOOL_NAME = "knowledge_base_search"
SQL_TOOL_NAME = "sales_analytics"

SQL_KEYWORDS = tuple(settings.sql_keywords)
DOC_KEYWORDS = tuple(settings.doc_keywords)

#-------- Helper functions --------
# Stringify - For serializing tool output
def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)

# Build citations - For RAG
def _build_citations(docs: Iterable) -> List[Dict[str, Any]]:
    citations: List[Dict[str, Any]] = []
    for doc in docs:
        metadata = doc.metadata or {}
        citations.append(
            {
                "source_document": str(
                    metadata.get("source")
                    or metadata.get("source_document")
                    or metadata.get("file_path")
                    or ""
                ),
                "page": metadata.get("page"),
                "content": doc.page_content,
            }
        )
    return citations

# Format docs for prompt - For RAG
def _format_docs_for_prompt(docs: Iterable) -> str:
    sections: List[str] = []
    for idx, doc in enumerate(docs, start=1):
        metadata = doc.metadata or {}
        source = metadata.get("source") or metadata.get("source_document") or "unknown"
        page = metadata.get("page")
        header = f"[Document {idx}] Source: {source}"
        if page is not None:
            header += f" | Page: {page}"
        sections.append(f"{header}\n{doc.page_content}")
    return "\n\n".join(sections)

####################################### Pipeline functions #######################################

# ------ RAG pipeline ------
# Get RAG synthesis prompt
@lru_cache(maxsize=1)
def _get_rag_synthesis_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", settings.rag_system_prompt),
            ("user", "Question: {question}\n\nContext:\n{context}"),
        ]
    )

# Run RAG pipeline
def _run_rag_pipeline(question: str, include_intermediate_steps: bool) -> Dict[str, Any]:
    store = load_vector_store()
    docs = store.similarity_search(question, k=settings.rag_top_k)
    citations = _build_citations(docs)
    context = _format_docs_for_prompt(docs) if docs else ""

    synthesis_prompt = _get_rag_synthesis_prompt()
    messages = synthesis_prompt.format_prompt(question=question, context=context or "<no relevant context>").to_messages()
    synthesis_llm = get_synthesis_llm()
    answer_message = synthesis_llm.invoke(messages)
    answer = (answer_message.content or "").strip()

    tool_output = json.dumps(citations, ensure_ascii=False)
    tool_trace = [
        f"Route selected: {RAG_ROUTE}",
        f"Tool: {RAG_TOOL_NAME} | input: {question}",
        f"Output: {tool_output[:200]}",
    ]

    result: Dict[str, Any] = {
        "output": answer,
        "route": RAG_ROUTE,
        "sql_query": None,
        "citations": citations,
        "tool_trace": tool_trace,
        "_context": context,
    }

    if include_intermediate_steps:
        result["intermediate_steps"] = [
            {"tool": RAG_TOOL_NAME, "input": question, "output": tool_output}
        ]

    return result

# ------ SQL pipeline ------
# Get SQL synthesis prompt
@lru_cache(maxsize=1)
def _get_sql_synthesis_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", settings.sql_system_prompt),
            (
                "user",
                "Question: {question}\n\nSQL Query:\n{sql_query}\n\nResult Rows:\n{sql_result}\n\nRaw Agent Answer:\n{raw_answer}",
            ),
        ]
    )


@lru_cache(maxsize=1)
def _get_sql_generation_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", settings.sql_generation_system_prompt),
            ("user", settings.sql_generation_user_prompt),
        ]
    )


# Run SQL pipeline
def _run_sql_pipeline(question: str, include_intermediate_steps: bool) -> Dict[str, Any]:
    db = get_sql_database()

    schema_path = settings.sql_schema_path
    if schema_path.exists():
        schema = schema_path.read_text(encoding="utf-8")
    else:
        schema = db.get_table_info()

    gen_prompt = _get_sql_generation_prompt()
    messages = gen_prompt.format_prompt(question=question, schema=schema).to_messages()
    sql_generation_response = get_sql_llm().invoke(messages)
    generated_sql = (sql_generation_response.content or "").strip()

    if generated_sql.startswith("```"):
        generated_sql = generated_sql.strip("`\n")
    if "\n```" in generated_sql:
        generated_sql = generated_sql.split("\n```", 1)[0]

    tool_trace: List[str] = [f"Route selected: {SQL_ROUTE}"]
    intermediate_steps: List[Dict[str, Any]] = []

    tool_trace.append(f"Generated SQL:\n{generated_sql}")
    intermediate_steps.append(
        {"tool": "sql_generation", "input": question, "output": generated_sql}
    )

    rows_repr = ""
    try:
        rows = db.run(generated_sql)
        rows_repr = rows if isinstance(rows, str) else json.dumps(rows, ensure_ascii=False)
        tool_trace.append(f"SQL execution output: {rows_repr[:200]}")
        intermediate_steps.append(
            {"tool": "sql_execution", "input": generated_sql, "output": rows_repr}
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        error_message = f"SQL execution failed: {exc}"
        tool_trace.append(error_message)
        intermediate_steps.append(
            {"tool": "sql_execution", "input": generated_sql, "output": error_message}
        )
        rows_repr = error_message

    synthesis_prompt = _get_sql_synthesis_prompt()
    messages = synthesis_prompt.format_prompt(
        question=question,
        sql_query=generated_sql,
        sql_result=rows_repr,
        raw_answer=rows_repr,
    ).to_messages()
    synthesis_llm = get_synthesis_llm()
    answer_message = synthesis_llm.invoke(messages)
    answer = (answer_message.content or "").strip()

    result: Dict[str, Any] = {
        "output": answer,
        "route": SQL_ROUTE,
        "sql_query": generated_sql,
        "citations": [],
        "tool_trace": tool_trace,
        "_sql_rows": rows_repr,
        "_raw_answer": rows_repr,
    }

    if include_intermediate_steps:
        result["intermediate_steps"] = intermediate_steps

    return result

# ------ Hybrid pipeline ------
# Get hybrid synthesis prompt
@lru_cache(maxsize=1)
def _get_hybrid_synthesis_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", settings.hybrid_system_prompt),
            ("user", 
            "Question: {question}\n\nSQL Summary:\n{sql_summary}\n\nSQL Query:\n{sql_query}\n\nSQL Raw Rows:\n{sql_rows}\n\nDocument Context:\n{document_context}",
            ),
        ]
    )

# Run hybrid pipeline
def _run_hybrid_pipeline(question: str, include_intermediate_steps: bool) -> Dict[str, Any]:
    split_sql_question, split_rag_question = _split_hybrid_question(question)
    sql_question = split_sql_question or question
    rag_question = split_rag_question or question

    sql_result = _run_sql_pipeline(sql_question, include_intermediate_steps=True)
    rag_result = _run_rag_pipeline(rag_question, include_intermediate_steps=True)

    hybrid_prompt = _get_hybrid_synthesis_prompt()
    messages = hybrid_prompt.format_prompt(
        question=question,
        sql_summary=sql_result.get("output") or "",
        sql_query=sql_result.get("sql_query") or "<not generated>",
        sql_rows=sql_result.get("_sql_rows") or sql_result.get("_raw_answer") or "",
        document_context=rag_result.get("_context") or "",
    ).to_messages()
    synthesis_llm = get_synthesis_llm()
    answer_message = synthesis_llm.invoke(messages)
    answer = (answer_message.content or "").strip()

    tool_trace: List[str] = ["Router decision: HYBRID"]
    tool_trace.append(f"Hybrid split -> SQL question: {sql_question}")
    tool_trace.append(f"Hybrid split -> RAG question: {rag_question}")
    tool_trace.extend(sql_result.get("tool_trace", []))
    tool_trace.extend(rag_result.get("tool_trace", []))
    tool_trace.append("Hybrid synthesis completed")

    result: Dict[str, Any] = {
        "output": answer,
        "route": HYBRID_ROUTE,
        "sql_query": sql_result.get("sql_query"),
        "citations": rag_result.get("citations", []),
        "tool_trace": tool_trace,
    }

    if include_intermediate_steps:
        steps: List[Any] = []
        steps.extend(sql_result.get("intermediate_steps", []))
        steps.extend(rag_result.get("intermediate_steps", []))
        result["intermediate_steps"] = steps

    return result

@lru_cache(maxsize=1)
def _get_hybrid_split_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", settings.hybrid_split_system_prompt),
            ("user", settings.hybrid_split_user_prompt),
        ]
    )


def _split_hybrid_question(question: str) -> tuple[str, str]:
    prompt = _get_hybrid_split_prompt()
    messages = prompt.format_prompt(question=question).to_messages()
    response = get_split_llm().invoke(messages)
    try:
        payload = json.loads(response.content or "{}")
        sql_q = str(payload.get("sql_question", ""))
        rag_q = str(payload.get("rag_question", ""))
        return sql_q.strip(), rag_q.strip()
    except (TypeError, ValueError):
        return "", ""

# Run pipeline agents
def run_rag_agent(question: str, *, include_intermediate_steps: bool = True) -> Dict[str, Any]:
    return _run_rag_pipeline(question, include_intermediate_steps)
def run_sql_agent(question: str, *, include_intermediate_steps: bool = True) -> Dict[str, Any]:
    return _run_sql_pipeline(question, include_intermediate_steps)

# Route prompt
@lru_cache(maxsize=1)
def _get_route_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", settings.route_system_prompt),
            (
                "user",
                "Question: {question}\nStructured hint: {structured_hint}\nDocumentary hint: {documentary_hint}"
            ),
        ]
    )


# Heuristic routing
def _looks_structured(question: str) -> bool:
    lowered = question.lower()
    if re.search(r"\bselect\b|\bfrom\b|\bwhere\b|\bgroup by\b", lowered):
        return True
    return any(keyword in lowered for keyword in SQL_KEYWORDS)
def _looks_documentary(question: str) -> bool:
    lowered = question.lower()
    return any(keyword in lowered for keyword in DOC_KEYWORDS)

# Decide route
def _decide_route(question: str) -> Optional[str]:
    structured = _looks_structured(question)
    documentary = _looks_documentary(question)

    llm = get_router_llm()
    prompt = _get_route_prompt()
    response = llm.invoke(
        prompt.format_prompt(
            question=question,
            structured_hint=str(structured),
            documentary_hint=str(documentary),
        ).to_messages()
    )
    choice = (response.content or "").strip().upper()
    # Prioritize explicit routing choices
    if "BOTH" in choice or "HYBRID" in choice:
        return HYBRID_ROUTE
    if "SQL" in choice:
        return SQL_ROUTE
    if "RAG" in choice:
        return RAG_ROUTE        
    if "NONE" in choice:
        return None
    # Fallback to heuristic routing
    if structured and documentary:
        return HYBRID_ROUTE
    if structured:
        return SQL_ROUTE
    if documentary:
        return RAG_ROUTE
    return None


def run_agent(question: str, *, include_intermediate_steps: bool = True) -> Dict[str, Any]:
    route = _decide_route(question)
    # Run decided route
    if route == SQL_ROUTE:
        sql_result = run_sql_agent(question, include_intermediate_steps=include_intermediate_steps)
        sql_result.setdefault("tool_trace", []).insert(0, "Router decision: SQL")
        return sql_result
    if route == HYBRID_ROUTE:
        return _run_hybrid_pipeline(question, include_intermediate_steps)
    if route == RAG_ROUTE:
        rag_result = run_rag_agent(question, include_intermediate_steps=include_intermediate_steps)
        rag_result.setdefault("tool_trace", []).insert(0, "Router decision: RAG")
        return rag_result
    # Fallback to insufficient context
    message = settings.insufficient_context_message
    result: Dict[str, Any] = {
        "output": message,
        "route": "UNKNOWN",
        "sql_query": None,
        "citations": [],
        "tool_trace": ["Router decision: INSUFFICIENT CONTEXT"],
    }
    if include_intermediate_steps:
        result["intermediate_steps"] = []
    return result

