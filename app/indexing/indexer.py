"""Chroma indexing pipeline for code chunks and historical bug tickets."""

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import chromadb

from app.config import Settings, get_settings
from app.indexing.chunker import chunk_file, chunk_repository
from app.llm import get_embeddings
from app.logging_setup import get_logger
from app.models import CodeChunk

logger = get_logger("indexing.indexer")

CODE_COLLECTION_NAME = "code_chunks"
TICKETS_COLLECTION_NAME = "bug_tickets"
HASH_STORE_FILENAME = "file_hashes.json"


def compute_file_hash(filepath: Path) -> str:
    """Compute SHA-256 hash of file content."""
    with open(filepath, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def get_chroma_client(chroma_dir: Path | str) -> chromadb.PersistentClient:
    """Create or retrieve a persistent Chroma client."""
    path_obj = Path(chroma_dir).resolve()
    path_obj.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(path_obj))


def chunk_to_chroma_metadata(chunk: CodeChunk) -> Dict[str, Any]:
    """Format CodeChunk attributes into Chroma-compatible primitive metadata."""
    return {
        "file_path": chunk.file_path,
        "symbol_name": chunk.symbol_name,
        "kind": chunk.kind,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "is_test": chunk.is_test,
        "imports_used": ",".join(chunk.imports_used),
        "calls_made": ",".join(chunk.calls_made),
    }


def build_code_index(
    repo_path: Optional[Path | str] = None,
    chroma_dir: Optional[Path | str] = None,
    incremental: bool = False,
    batch_size: int = 15,
    settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    """Index repository code chunks into persistent Chroma collection.

    Args:
        repo_path: Path to codebase root (defaults to settings.target_repo_path).
        chroma_dir: Path to Chroma persistence directory (defaults to settings.chroma_dir).
        incremental: Whether to only re-index files with changed content hashes.
        batch_size: Batch size for embedding calls.
        settings: Application Settings override.

    Returns:
        Summary dictionary with indexing statistics.
    """
    start_time = time.time()
    cfg = settings or get_settings()
    target_repo = Path(repo_path or cfg.target_repo_path).resolve()
    storage_dir = Path(chroma_dir or cfg.chroma_dir).resolve()
    storage_dir.mkdir(parents=True, exist_ok=True)

    client = get_chroma_client(storage_dir)
    embeddings = get_embeddings(cfg)
    hash_file = storage_dir / HASH_STORE_FILENAME

    previous_hashes: Dict[str, str] = {}
    if incremental and hash_file.is_file():
        try:
            with open(hash_file, "r", encoding="utf-8") as f:
                previous_hashes = json.load(f)
        except Exception as exc:
            logger.warning("Could not load previous file hashes (%s). Performing full reindex.", exc)
            incremental = False

    # Discover and hash all current Python files
    current_files: Dict[str, Path] = {}
    current_hashes: Dict[str, str] = {}
    for p in target_repo.rglob("*.py"):
        rel = p.relative_to(target_repo).as_posix()
        if any(part in {".git", ".venv", "venv", "__pycache__"} for part in Path(rel).parts):
            continue
        current_files[rel] = p
        current_hashes[rel] = compute_file_hash(p)

    if not incremental:
        # Wipe and recreate collection
        try:
            client.delete_collection(name=CODE_COLLECTION_NAME)
            logger.info("Deleted existing collection '%s'", CODE_COLLECTION_NAME)
        except Exception:
            pass
        collection = client.create_collection(
            name=CODE_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        files_to_index = list(current_files.keys())
    else:
        collection = client.get_or_create_collection(
            name=CODE_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        # Identify deleted files
        deleted_files = set(previous_hashes.keys()) - set(current_hashes.keys())
        for d_rel in deleted_files:
            logger.info("Removing chunks for deleted file: %s", d_rel)
            try:
                collection.delete(where={"file_path": d_rel})
            except Exception as exc:
                logger.warning("Error deleting chunks for %s: %s", d_rel, exc)

        # Identify changed or new files
        files_to_index = []
        for rel, curr_hash in current_hashes.items():
            if rel not in previous_hashes or previous_hashes[rel] != curr_hash:
                files_to_index.append(rel)
                # Remove stale chunks for changed file
                try:
                    collection.delete(where={"file_path": rel})
                except Exception:
                    pass

    # Extract chunks for files to index
    chunks_to_embed: List[CodeChunk] = []
    for rel in files_to_index:
        file_chunks = chunk_file(current_files[rel], repo_root=target_repo)
        chunks_to_embed.extend(file_chunks)

    logger.info(
        "Files to index: %d, Chunks to embed: %d (Incremental: %s)",
        len(files_to_index),
        len(chunks_to_embed),
        incremental,
    )

    # Embed and insert in batches
    embedded_count = 0
    total_chunks = len(chunks_to_embed)

    for i in range(0, total_chunks, batch_size):
        batch = chunks_to_embed[i : i + batch_size]
        texts = [c.text for c in batch]
        ids = [c.id for c in batch]
        metadatas = [chunk_to_chroma_metadata(c) for c in batch]

        logger.debug(
            "Embedding batch %d-%d of %d chunks...",
            i + 1,
            min(i + batch_size, total_chunks),
            total_chunks,
        )

        vectors = embeddings.embed_documents(texts)
        collection.add(
            ids=ids,
            embeddings=vectors,
            documents=texts,
            metadatas=metadatas,
        )
        embedded_count += len(batch)

        # Small pause for Gemini free-tier rate limits
        if cfg.embedding_provider == "gemini" and i + batch_size < total_chunks:
            time.sleep(0.5)

    # Save updated file hashes
    with open(hash_file, "w", encoding="utf-8") as f:
        json.dump(current_hashes, f, indent=2)

    elapsed_time = round(time.time() - start_time, 2)
    final_count = collection.count()

    summary = {
        "repository": str(target_repo),
        "incremental": incremental,
        "files_scanned": len(current_files),
        "files_indexed": len(files_to_index),
        "chunks_embedded": embedded_count,
        "total_chunks_in_collection": final_count,
        "time_taken_seconds": elapsed_time,
        "embedding_provider": cfg.embedding_provider,
    }
    logger.info("Code indexing complete: %s", summary)
    return summary


def build_ticket_index(
    tickets_path: Optional[Path | str] = None,
    chroma_dir: Optional[Path | str] = None,
    settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    """Index past bug tickets into persistent Chroma collection.

    Args:
        tickets_path: Path to tickets JSON file (defaults to data/tickets/tickets.json).
        chroma_dir: Path to Chroma persistence directory.
        settings: Application Settings override.

    Returns:
        Summary dictionary with ticket indexing statistics.
    """
    start_time = time.time()
    cfg = settings or get_settings()
    storage_dir = Path(chroma_dir or cfg.chroma_dir).resolve()
    storage_dir.mkdir(parents=True, exist_ok=True)

    if tickets_path is None:
        tickets_file = Path("data") / "tickets" / "tickets.json"
    else:
        tickets_file = Path(tickets_path)

    if not tickets_file.is_file():
        raise FileNotFoundError(f"Tickets file not found at: {tickets_file}")

    with open(tickets_file, "r", encoding="utf-8") as f:
        tickets_data = json.load(f)

    client = get_chroma_client(storage_dir)
    embeddings = get_embeddings(cfg)

    # Wipe and recreate bug_tickets collection
    try:
        client.delete_collection(name=TICKETS_COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(
        name=TICKETS_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    ids: List[str] = []
    documents: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    for item in tickets_data:
        tid = item["ticket_id"]
        title = item.get("title", "")
        desc = item.get("description", "")
        resol = item.get("resolution", "")
        touched = item.get("files_touched", [])
        touched_str = ", ".join(touched)

        text = (
            f"# ticket: {tid} | Title: {title}\n"
            f"Description: {desc}\n"
            f"Resolution: {resol}\n"
            f"Files touched: {touched_str}"
        )

        ids.append(tid)
        documents.append(text)
        metadatas.append({
            "ticket_id": tid,
            "title": title,
            "files_touched": touched_str,
        })

    logger.info("Embedding %d historical bug tickets...", len(ids))
    vectors = embeddings.embed_documents(documents)
    collection.add(
        ids=ids,
        embeddings=vectors,
        documents=documents,
        metadatas=metadatas,
    )

    elapsed_time = round(time.time() - start_time, 2)
    summary = {
        "tickets_file": str(tickets_file),
        "tickets_indexed": len(ids),
        "total_tickets_in_collection": collection.count(),
        "time_taken_seconds": elapsed_time,
    }
    logger.info("Ticket indexing complete: %s", summary)
    return summary
