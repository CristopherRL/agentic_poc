from __future__ import annotations

import asyncio
import json
import logging
import re
import time
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

logger = logging.getLogger(__name__)


def _extract_token_usage(response: Any) -> Dict[str, int]:
    """
    Extract token usage from LLM response in a provider-agnostic way.
    
    Works with OpenAI, Azure OpenAI, and other LangChain-compatible providers.
    Returns default values (0) if token information is not available.
    
    Args:
        response: LLM response object (AIMessage or similar)
    
    Returns:
        Dict with keys: prompt_tokens, completion_tokens, total_tokens
    """
    default_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    
    try:
        # Try to get token usage from response_metadata (standard LangChain format)
        if hasattr(response, "response_metadata"):
            token_usage = response.response_metadata.get("token_usage", {})
            if token_usage:
                return {
                    "prompt_tokens": token_usage.get("prompt_tokens", 0),
                    "completion_tokens": token_usage.get("completion_tokens", 0),
                    "total_tokens": token_usage.get("total_tokens", 0),
                }
        
        # Try alternative locations (some providers may store it differently)
        if hasattr(response, "token_usage"):
            token_usage = response.token_usage
            if isinstance(token_usage, dict):
                return {
                    "prompt_tokens": token_usage.get("prompt_tokens", 0),
                    "completion_tokens": token_usage.get("completion_tokens", 0),
                    "total_tokens": token_usage.get("total_tokens", 0),
                }
        
        # Try llm_output (another common location)
        if hasattr(response, "llm_output") and isinstance(response.llm_output, dict):
            token_usage = response.llm_output.get("token_usage", {})
            if token_usage:
                return {
                    "prompt_tokens": token_usage.get("prompt_tokens", 0),
                    "completion_tokens": token_usage.get("completion_tokens", 0),
                    "total_tokens": token_usage.get("total_tokens", 0),
                }
    except Exception:
        # If anything fails, return defaults (don't break the flow)
        pass
    
    return default_usage

#-------- Security functions --------
# SQL Query Validation
def _validate_sql_query(sql_query: str) -> tuple[bool, str]:
    """
    Validate SQL query to ensure it only contains SELECT operations.
    
    Uses centralized dangerous_sql_keywords from settings (shared with input validation in schemas.py).
    
    Returns:
        tuple[bool, str]: (is_valid, error_message)
        - is_valid: True if query is safe to execute, False otherwise
        - error_message: Error description if query is invalid, empty string if valid
    """
    if not sql_query or not sql_query.strip():
        return False, "SQL query cannot be empty"
    
    # Normalize query for analysis (uppercase, remove extra whitespace)
    normalized = re.sub(r'\s+', ' ', sql_query.upper().strip())
    
    # Block DML/DDL operations using centralized keywords list from settings
    # This list is shared with schemas.py for input validation (defense in depth)
    for keyword in settings.dangerous_sql_keywords:
        # Check for keyword as a complete word (not part of another word)
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, normalized):
            return False, f"SQL query contains forbidden operation: {keyword}"
    
    # Ensure query starts with SELECT (after removing leading comments/whitespace)
    # Remove SQL comments first
    normalized_no_comments = re.sub(r'--.*?$', '', normalized, flags=re.MULTILINE)
    normalized_no_comments = re.sub(r'/\*.*?\*/', '', normalized_no_comments, flags=re.DOTALL)
    normalized_no_comments = normalized_no_comments.strip()
    
    if not normalized_no_comments.startswith('SELECT'):
        return False, "SQL query must be a SELECT statement only"
    
    return True, ""

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
def _sanitize_document_source(source: str) -> str:
    """
    Sanitize document source path to generic document type.
    
    Replaces file paths and names with generic document types.
    Examples:
    - "Contract_Toyota_2023.pdf" -> "Contract Document"
    - "Toyota_RAV4.txt" -> "Manual Document"
    - "Warranty_Policy_Appendix.pdf" -> "Policy Document"
    """
    source_lower = source.lower()
    
    # Map file patterns to generic document types
    if "contract" in source_lower:
        return "Contract Document"
    elif "manual" in source_lower or "rav4" in source_lower or "yaris" in source_lower:
        return "Manual Document"
    elif "warranty" in source_lower or "policy" in source_lower:
        return "Policy Document"
    elif "appendix" in source_lower:
        return "Policy Appendix"
    else:
        # Generic fallback
        return "Document"


def _build_citations(docs: Iterable) -> List[Dict[str, Any]]:
    citations: List[Dict[str, Any]] = []
    for doc in docs:
        metadata = doc.metadata or {}
        raw_source = str(
            metadata.get("source")
            or metadata.get("source_document")
            or metadata.get("file_path")
            or ""
        )
        # Sanitize source to generic document type
        sanitized_source = _sanitize_document_source(raw_source) if raw_source else "Document"
        citations.append(
            {
                "source_document": sanitized_source,
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
        raw_source = metadata.get("source") or metadata.get("source_document") or "unknown"
        # Sanitize source to generic document type
        source = _sanitize_document_source(str(raw_source)) if raw_source else "Document"
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
            ("user", "{conversation_history}Question: {question}\n\nContext:\n{context}"),
        ]
    )

# Run RAG pipeline
async def _run_rag_pipeline(question: str, include_intermediate_steps: bool, conversation_history: str = "") -> Dict[str, Any]:
    pipeline_start = time.time()
    logger.info(f"[RAG Pipeline] Starting RAG pipeline for question")
    store = load_vector_store()
    # FAISS similarity_search is synchronous, run in thread pool
    search_start = time.time()
    logger.info(f"[RAG Pipeline] Searching vector store (top_k={settings.rag_top_k})...")
    docs = await asyncio.to_thread(store.similarity_search, question, k=settings.rag_top_k)
    search_time = time.time() - search_start
    logger.info(f"[RAG Pipeline] Found {len(docs)} document(s) | Search time: {search_time:.2f}s")
    citations = _build_citations(docs)
    if citations:
        logger.info(f"[RAG Pipeline] Citations: {len(citations)} | Sources: {', '.join(set(c.get('source_document', 'unknown') for c in citations[:3]))}{'...' if len(citations) > 3 else ''}")
    context = _format_docs_for_prompt(docs) if docs else ""

    synthesis_prompt = _get_rag_synthesis_prompt()
    history_text = f"{conversation_history}\n\n" if conversation_history else ""
    messages = synthesis_prompt.format_prompt(
        conversation_history=history_text,
        question=question,
        context=context or "<no relevant context>"
    ).to_messages()
    synthesis_llm = get_synthesis_llm()
    synthesis_start = time.time()
    logger.info(f"[RAG Pipeline] Synthesizing answer from {len(docs)} document(s)...")
    answer_message = await synthesis_llm.ainvoke(messages)
    answer = (answer_message.content or "").strip()
    synthesis_time = time.time() - synthesis_start
    synthesis_tokens = _extract_token_usage(answer_message)
    total_time = time.time() - pipeline_start
    synthesis_token_info = f" | Tokens: P={synthesis_tokens['prompt_tokens']}, C={synthesis_tokens['completion_tokens']}, T={synthesis_tokens['total_tokens']}" if synthesis_tokens['total_tokens'] > 0 else ""
    total_token_info = f" | Total tokens: {synthesis_tokens['total_tokens']}" if synthesis_tokens['total_tokens'] > 0 else ""
    logger.info(f"[RAG Pipeline] Answer synthesized | Length: {len(answer)} chars | Synthesis time: {synthesis_time:.2f}s{synthesis_token_info} | Total pipeline time: {total_time:.2f}s{total_token_info}")

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
                "{conversation_history}Question: {question}\n\nSQL Query:\n{sql_query}\n\nResult Rows:\n{sql_result}\n\nRaw Agent Answer:\n{raw_answer}",
            ),
        ]
    )


@lru_cache(maxsize=1)
def _get_sql_generation_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", settings.sql_generation_system_prompt),
            ("user", "{conversation_history}" + settings.sql_generation_user_prompt),
        ]
    )


# Run SQL pipeline
async def _run_sql_pipeline(question: str, include_intermediate_steps: bool, conversation_history: str = "") -> Dict[str, Any]:
    pipeline_start = time.time()
    logger.info(f"[SQL Pipeline] Starting SQL pipeline for question")
    db = get_sql_database()

    schema_path = settings.sql_schema_path
    if schema_path.exists():
        # File I/O is synchronous, run in thread pool
        schema = await asyncio.to_thread(schema_path.read_text, encoding="utf-8")
    else:
        # Database get_table_info is synchronous, run in thread pool
        schema = await asyncio.to_thread(db.get_table_info)

    gen_prompt = _get_sql_generation_prompt()
    history_text = f"{conversation_history}\n\n" if conversation_history else ""
    messages = gen_prompt.format_prompt(conversation_history=history_text, question=question, schema=schema).to_messages()
    sql_gen_start = time.time()
    logger.info(f"[SQL Pipeline] Generating SQL query...")
    sql_generation_response = await get_sql_llm().ainvoke(messages)
    generated_sql = (sql_generation_response.content or "").strip()
    sql_gen_time = time.time() - sql_gen_start
    sql_gen_tokens = _extract_token_usage(sql_generation_response)
    sql_gen_token_info = f" | Tokens: P={sql_gen_tokens['prompt_tokens']}, C={sql_gen_tokens['completion_tokens']}, T={sql_gen_tokens['total_tokens']}" if sql_gen_tokens['total_tokens'] > 0 else ""
    logger.info(f"[SQL Pipeline] SQL generation completed | Time: {sql_gen_time:.2f}s{sql_gen_token_info}")

    if generated_sql.startswith("```"):
        generated_sql = generated_sql.strip("`\n")
    if "\n```" in generated_sql:
        generated_sql = generated_sql.split("\n```", 1)[0]

    logger.info(f"[SQL Pipeline] Generated SQL: {generated_sql[:150]}{'...' if len(generated_sql) > 150 else ''}")

    tool_trace: List[str] = [f"Route selected: {SQL_ROUTE}"]
    intermediate_steps: List[Dict[str, Any]] = []

    tool_trace.append(f"Generated SQL:\n{generated_sql}")
    intermediate_steps.append(
        {"tool": "sql_generation", "input": question, "output": generated_sql}
    )

    # Validate SQL query before execution
    is_valid, validation_error = _validate_sql_query(generated_sql)
    if not is_valid:
        logger.warning(f"[SQL Pipeline] SQL validation failed: {validation_error}")
        error_message = f"SQL query validation failed: {validation_error}"
        tool_trace.append(error_message)
        intermediate_steps.append(
            {"tool": "sql_validation", "input": generated_sql, "output": error_message}
        )
        rows_repr = error_message
    else:
        rows_repr = ""
        try:
            sql_exec_start = time.time()
            logger.info(f"[SQL Pipeline] Executing SQL query...")
            # Database run is synchronous, run in thread pool
            rows = await asyncio.to_thread(db.run, generated_sql)
            rows_repr = rows if isinstance(rows, str) else json.dumps(rows, ensure_ascii=False)
            sql_exec_time = time.time() - sql_exec_start
            logger.info(f"[SQL Pipeline] SQL executed successfully | Rows returned: {len(rows_repr)} chars | Time: {sql_exec_time:.2f}s")
            tool_trace.append(f"SQL execution output: {rows_repr[:200]}")
            intermediate_steps.append(
                {"tool": "sql_execution", "input": generated_sql, "output": rows_repr}
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.error(f"[SQL Pipeline] SQL execution failed: {exc}")
            error_message = f"SQL execution failed: {exc}"
            tool_trace.append(error_message)
            intermediate_steps.append(
                {"tool": "sql_execution", "input": generated_sql, "output": error_message}
            )
            rows_repr = error_message

    synthesis_prompt = _get_sql_synthesis_prompt()
    history_text = f"{conversation_history}\n\n" if conversation_history else ""
    messages = synthesis_prompt.format_prompt(
        conversation_history=history_text,
        question=question,
        sql_query=generated_sql,
        sql_result=rows_repr,
        raw_answer=rows_repr,
    ).to_messages()
    synthesis_llm = get_synthesis_llm()
    synthesis_start = time.time()
    logger.info(f"[SQL Pipeline] Synthesizing answer from SQL results...")
    answer_message = await synthesis_llm.ainvoke(messages)
    answer = (answer_message.content or "").strip()
    synthesis_time = time.time() - synthesis_start
    synthesis_tokens = _extract_token_usage(answer_message)
    total_tokens = sql_gen_tokens['total_tokens'] + synthesis_tokens['total_tokens']
    total_time = time.time() - pipeline_start
    synthesis_token_info = f" | Tokens: P={synthesis_tokens['prompt_tokens']}, C={synthesis_tokens['completion_tokens']}, T={synthesis_tokens['total_tokens']}" if synthesis_tokens['total_tokens'] > 0 else ""
    total_token_info = f" | Total tokens: {total_tokens}" if total_tokens > 0 else ""
    logger.info(f"[SQL Pipeline] Answer synthesized | Length: {len(answer)} chars | Synthesis time: {synthesis_time:.2f}s{synthesis_token_info} | Total pipeline time: {total_time:.2f}s{total_token_info}")

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
            "{conversation_history}Question: {question}\n\nSQL Summary:\n{sql_summary}\n\nSQL Query:\n{sql_query}\n\nSQL Raw Rows:\n{sql_rows}\n\nDocument Context:\n{document_context}",
            ),
        ]
    )

# Run hybrid pipeline
async def _run_hybrid_pipeline(question: str, include_intermediate_steps: bool, conversation_history: str = "") -> Dict[str, Any]:
    pipeline_start = time.time()
    logger.info(f"[Hybrid Pipeline] Starting hybrid pipeline for question")
    split_sql_question, split_rag_question = await _split_hybrid_question(question, conversation_history=conversation_history)
    sql_question = split_sql_question or question
    rag_question = split_rag_question or question

    # Execute SQL and RAG pipelines in parallel
    sql_result, rag_result = await asyncio.gather(
        _run_sql_pipeline(sql_question, include_intermediate_steps=True, conversation_history=conversation_history),
        _run_rag_pipeline(rag_question, include_intermediate_steps=True, conversation_history=conversation_history),
    )

    hybrid_prompt = _get_hybrid_synthesis_prompt()
    history_text = f"{conversation_history}\n\n" if conversation_history else ""
    messages = hybrid_prompt.format_prompt(
        conversation_history=history_text,
        question=question,
        sql_summary=sql_result.get("output") or "",
        sql_query=sql_result.get("sql_query") or "<not generated>",
        sql_rows=sql_result.get("_sql_rows") or sql_result.get("_raw_answer") or "",
        document_context=rag_result.get("_context") or "",
    ).to_messages()
    synthesis_llm = get_synthesis_llm()
    synthesis_start = time.time()
    logger.info(f"[Hybrid Pipeline] Synthesizing final answer from SQL and RAG results...")
    answer_message = await synthesis_llm.ainvoke(messages)
    answer = (answer_message.content or "").strip()
    synthesis_time = time.time() - synthesis_start
    synthesis_tokens = _extract_token_usage(answer_message)
    total_time = time.time() - pipeline_start
    synthesis_token_info = f" | Tokens: P={synthesis_tokens['prompt_tokens']}, C={synthesis_tokens['completion_tokens']}, T={synthesis_tokens['total_tokens']}" if synthesis_tokens['total_tokens'] > 0 else ""
    logger.info(f"[Hybrid Pipeline] Answer synthesized | Length: {len(answer)} chars | Synthesis time: {synthesis_time:.2f}s{synthesis_token_info} | Total pipeline time: {total_time:.2f}s")

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
            ("user", "{conversation_history}" + settings.hybrid_split_user_prompt),
        ]
    )


async def _split_hybrid_question(question: str, conversation_history: str = "") -> tuple[str, str]:
    prompt = _get_hybrid_split_prompt()
    history_text = f"{conversation_history}\n\n" if conversation_history else ""
    messages = prompt.format_prompt(conversation_history=history_text, question=question).to_messages()
    response = await get_split_llm().ainvoke(messages)
    split_tokens = _extract_token_usage(response)
    if split_tokens['total_tokens'] > 0:
        logger.info(f"[Hybrid Pipeline] Question split completed | Tokens: P={split_tokens['prompt_tokens']}, C={split_tokens['completion_tokens']}, T={split_tokens['total_tokens']}")
    try:
        payload = json.loads(response.content or "{}")
        sql_q = str(payload.get("sql_question", ""))
        rag_q = str(payload.get("rag_question", ""))
        return sql_q.strip(), rag_q.strip()
    except (TypeError, ValueError):
        return "", ""

# Run pipeline agents
async def run_rag_agent(question: str, *, include_intermediate_steps: bool = True) -> Dict[str, Any]:
    return await _run_rag_pipeline(question, include_intermediate_steps)
async def run_sql_agent(question: str, *, include_intermediate_steps: bool = True) -> Dict[str, Any]:
    return await _run_sql_pipeline(question, include_intermediate_steps)

# Route prompt
@lru_cache(maxsize=1)
def _get_route_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", settings.route_system_prompt),
            (
                "user",
                "{conversation_history}Question: {question}\nStructured hint: {structured_hint}\nDocumentary hint: {documentary_hint}"
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
async def _decide_route(question: str, conversation_history: str = "") -> Optional[str]:
    start_time = time.time()
    structured = _looks_structured(question)
    documentary = _looks_documentary(question)
    
    logger.info(f"[Router] Analyzing question | Structured hint: {structured} | Documentary hint: {documentary}")

    llm = get_router_llm()
    prompt = _get_route_prompt()
    history_text = f"{conversation_history}\n\n" if conversation_history else ""
    response = await llm.ainvoke(
        prompt.format_prompt(
            conversation_history=history_text,
            question=question,
            structured_hint=str(structured),
            documentary_hint=str(documentary),
        ).to_messages()
    )
    choice = (response.content or "").strip().upper()
    elapsed_time = time.time() - start_time
    token_usage = _extract_token_usage(response)
    token_info = f" | Tokens: P={token_usage['prompt_tokens']}, C={token_usage['completion_tokens']}, T={token_usage['total_tokens']}" if token_usage['total_tokens'] > 0 else ""
    # Prioritize explicit routing choices
    if "BOTH" in choice or "HYBRID" in choice:
        logger.info(f"[Router] Decision: HYBRID (LLM choice: {choice}) | Time: {elapsed_time:.2f}s{token_info}")
        return HYBRID_ROUTE
    if "SQL" in choice:
        logger.info(f"[Router] Decision: SQL (LLM choice: {choice}) | Time: {elapsed_time:.2f}s{token_info}")
        return SQL_ROUTE
    if "RAG" in choice:
        logger.info(f"[Router] Decision: RAG (LLM choice: {choice}) | Time: {elapsed_time:.2f}s{token_info}")
        return RAG_ROUTE        
    if "NONE" in choice:
        logger.info(f"[Router] Decision: NONE (LLM choice: {choice}) | Time: {elapsed_time:.2f}s{token_info}")
        return None
    # Fallback to heuristic routing
    if structured and documentary:
        logger.info(f"[Router] Decision: HYBRID (heuristic fallback) | Time: {elapsed_time:.2f}s{token_info}")
        return HYBRID_ROUTE
    if structured:
        logger.info(f"[Router] Decision: SQL (heuristic fallback) | Time: {elapsed_time:.2f}s{token_info}")
        return SQL_ROUTE
    if documentary:
        logger.info(f"[Router] Decision: RAG (heuristic fallback) | Time: {elapsed_time:.2f}s{token_info}")
        return RAG_ROUTE
    logger.info(f"[Router] Decision: NONE (no matching hints) | Time: {elapsed_time:.2f}s{token_info}")
    return None


async def run_agent(question: str, *, include_intermediate_steps: bool = True, conversation_history: str = "") -> Dict[str, Any]:
    route = await _decide_route(question, conversation_history=conversation_history)
    # Run decided route
    if route == SQL_ROUTE:
        sql_result = await _run_sql_pipeline(question, include_intermediate_steps=include_intermediate_steps, conversation_history=conversation_history)
        sql_result.setdefault("tool_trace", []).insert(0, "Router decision: SQL")
        return sql_result
    if route == HYBRID_ROUTE:
        return await _run_hybrid_pipeline(question, include_intermediate_steps, conversation_history=conversation_history)
    if route == RAG_ROUTE:
        rag_result = await _run_rag_pipeline(question, include_intermediate_steps=include_intermediate_steps, conversation_history=conversation_history)
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

