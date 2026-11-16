"""Code chunk and bug ticket retrieval engine with hybrid symbol/file boosting."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from app.config import Settings, get_settings
from app.indexing.indexer import (
    CODE_COLLECTION_NAME,
    TICKETS_COLLECTION_NAME,
    get_chroma_client,
)
from app.llm import get_embeddings
from app.logging_setup import get_logger

logger = get_logger("indexing.retriever")


def extract_query_keywords(query: str) -> Set[str]:
    """Extract code identifiers, function names, and file names from query text."""
    # Match potential symbols (alphanumeric + underscores) and filenames (*.py)
    tokens = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]+", query))
    py_files = set(re.findall(r"[\w\-]+\.py", query))
    for f in py_files:
        tokens.add(f)
        tokens.add(Path(f).stem)
    return tokens


def search_code_chunks(
    query: str,
    k: int = 5,
    filters: Optional[Dict[str, Any]] = None,
    settings: Optional[Settings] = None,
    hybrid_boost: bool = True,
    client: Optional[Any] = None,
    embeddings: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Retrieve top-k relevant code chunks with hybrid exact-match boosting.

    Args:
        query: Search string, error log, stack trace, or natural language query.
        k: Maximum number of chunks to return.
        filters: Optional Chroma metadata filter dictionary.
        settings: Application Settings override.
        hybrid_boost: Whether to apply score boosting for exact symbol and file name matches.
        client: Optional custom Chroma client (useful for unit testing).
        embeddings: Optional custom Embeddings instance (useful for unit testing).

    Returns:
        Ranked list of chunk dictionaries with scores and metadata.
    """
    cfg = settings or get_settings()
    chroma_client = client or get_chroma_client(cfg.chroma_dir)
    emb = embeddings or get_embeddings(cfg)

    try:
        collection = chroma_client.get_collection(name=CODE_COLLECTION_NAME)
    except Exception as exc:
        logger.error("Failed to load collection '%s': %s", CODE_COLLECTION_NAME, exc)
        return []

    total_chunks = collection.count()
    if total_chunks == 0:
        logger.warning("Code collection '%s' is empty", CODE_COLLECTION_NAME)
        return []

    query_vec = emb.embed_query(query)
    candidate_limit = min(total_chunks, max(k * 4, 25))

    query_kwargs: Dict[str, Any] = {
        "query_embeddings": [query_vec],
        "n_results": candidate_limit,
    }
    if filters:
        query_kwargs["where"] = filters

    results = collection.query(**query_kwargs)

    ids = results.get("ids", [[]])[0]
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0] if "distances" in results else [0.5] * len(ids)

    query_keywords = extract_query_keywords(query)
    ranked_chunks: List[Dict[str, Any]] = []

    for i in range(len(ids)):
        chunk_id = ids[i]
        meta = metas[i] if i < len(metas) else {}
        doc_text = docs[i] if i < len(docs) else ""
        dist = distances[i] if i < len(distances) else 0.5

        # Base similarity: cosine similarity roughly 1.0 - distance
        base_score = max(0.0, 1.0 - float(dist))
        boost = 0.0

        sym_name = str(meta.get("symbol_name", ""))
        file_path_str = str(meta.get("file_path", ""))
        file_name = Path(file_path_str).name
        file_stem = Path(file_path_str).stem

        if hybrid_boost:
            # 1. Exact symbol match (e.g. function or method name)
            short_sym = sym_name.split(".")[-1]
            if sym_name in query_keywords or short_sym in query_keywords:
                boost += 0.45

            # 2. Exact file name match (e.g. users.py or users)
            if file_name in query_keywords or file_stem in query_keywords:
                boost += 0.25

            # 3. Exact full relative path mention in query
            if file_path_str in query:
                boost += 0.20

        final_score = base_score + boost

        imports_str = str(meta.get("imports_used", ""))
        calls_str = str(meta.get("calls_made", ""))

        ranked_chunks.append({
            "id": chunk_id,
            "score": round(final_score, 4),
            "base_score": round(base_score, 4),
            "file_path": file_path_str,
            "symbol_name": sym_name,
            "kind": meta.get("kind", "unknown"),
            "start_line": int(meta.get("start_line", 1)),
            "end_line": int(meta.get("end_line", 1)),
            "is_test": bool(meta.get("is_test", False)),
            "imports_used": [s for s in imports_str.split(",") if s],
            "calls_made": [s for s in calls_str.split(",") if s],
            "text": doc_text,
        })

    # Sort descending by final score
    ranked_chunks.sort(key=lambda x: x["score"], reverse=True)
    return ranked_chunks[:k]


def search_tickets(
    query: str,
    k: int = 3,
    settings: Optional[Settings] = None,
    client: Optional[Any] = None,
    embeddings: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Retrieve top-k relevant past bug tickets matching query.

    Args:
        query: Search string or bug description.
        k: Maximum number of tickets to return.
        settings: Application Settings override.
        client: Optional custom Chroma client.
        embeddings: Optional custom Embeddings instance.

    Returns:
        List of ticket dictionaries with similarity score and metadata.
    """
    cfg = settings or get_settings()
    chroma_client = client or get_chroma_client(cfg.chroma_dir)
    emb = embeddings or get_embeddings(cfg)

    try:
        collection = chroma_client.get_collection(name=TICKETS_COLLECTION_NAME)
    except Exception as exc:
        logger.error("Failed to load collection '%s': %s", TICKETS_COLLECTION_NAME, exc)
        return []

    total_tickets = collection.count()
    if total_tickets == 0:
        return []

    query_vec = emb.embed_query(query)
    n_res = min(total_tickets, k)

    results = collection.query(
        query_embeddings=[query_vec],
        n_results=n_res,
    )

    ids = results.get("ids", [[]])[0]
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0] if "distances" in results else [0.5] * len(ids)

    tickets: List[Dict[str, Any]] = []
    for i in range(len(ids)):
        tid = ids[i]
        meta = metas[i] if i < len(metas) else {}
        doc_text = docs[i] if i < len(docs) else ""
        dist = distances[i] if i < len(distances) else 0.5
        score = max(0.0, 1.0 - float(dist))

        touched_str = str(meta.get("files_touched", ""))
        tickets.append({
            "ticket_id": tid,
            "score": round(score, 4),
            "title": meta.get("title", ""),
            "files_touched": [s.strip() for s in touched_str.split(",") if s.strip()],
            "text": doc_text,
        })

    tickets.sort(key=lambda x: x["score"], reverse=True)
    return tickets
