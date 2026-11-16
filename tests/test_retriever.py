"""Unit tests for retriever with fake deterministic embeddings."""

import hashlib
from pathlib import Path
from typing import List
import pytest
import chromadb
from app.indexing.indexer import CODE_COLLECTION_NAME, TICKETS_COLLECTION_NAME
from app.indexing.retriever import search_code_chunks, search_tickets


class FakeDeterministicEmbeddings:
    """Deterministic embedding generator using hashing (no external API calls)."""

    def __init__(self, dim: int = 16):
        self.dim = dim

    def _hash(self, text: str) -> List[float]:
        vec = []
        for i in range(self.dim):
            h = hashlib.sha256(f"{text}:{i}".encode("utf-8")).hexdigest()
            val = (int(h[:4], 16) / 65535.0) * 2.0 - 1.0
            vec.append(val)
        norm = sum(x**2 for x in vec) ** 0.5 or 1.0
        return [round(x / norm, 6) for x in vec]

    def embed_query(self, text: str) -> List[float]:
        return self._hash(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._hash(t) for t in texts]


@pytest.fixture
def fake_chroma_db(tmp_path: Path):
    """Instantiate a test Chroma DB client populated with fake chunks and tickets."""
    client = chromadb.PersistentClient(path=str(tmp_path / "test_chroma"))
    fake_emb = FakeDeterministicEmbeddings()

    # 1. Code collection
    code_coll = client.create_collection(
        name=CODE_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    docs = [
        "# file: auth/login.py | symbol: verify_credentials\ndef verify_credentials(user, pwd): pass",
        "# file: billing/invoice.py | symbol: generate_invoice\ndef generate_invoice(order): pass",
        "# file: catalog/items.py | symbol: list_products\ndef list_products(): pass",
    ]
    ids = ["c1", "c2", "c3"]
    metas = [
        {"file_path": "auth/login.py", "symbol_name": "verify_credentials", "kind": "function", "start_line": 1, "end_line": 2, "is_test": False},
        {"file_path": "billing/invoice.py", "symbol_name": "generate_invoice", "kind": "function", "start_line": 1, "end_line": 2, "is_test": False},
        {"file_path": "catalog/items.py", "symbol_name": "list_products", "kind": "function", "start_line": 1, "end_line": 2, "is_test": False},
    ]
    code_coll.add(
        ids=ids,
        documents=docs,
        embeddings=fake_emb.embed_documents(docs),
        metadatas=metas,
    )

    # 2. Tickets collection
    ticket_coll = client.create_collection(
        name=TICKETS_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    t_docs = [
        "# ticket: TICK-01 | Title: Auth crash on invalid password\nDescription: verify_credentials error",
        "# ticket: TICK-02 | Title: Invoice tax calculation rounding\nDescription: invoice subcent error",
    ]
    t_ids = ["TICK-01", "TICK-02"]
    t_metas = [
        {"ticket_id": "TICK-01", "title": "Auth crash", "files_touched": "auth/login.py"},
        {"ticket_id": "TICK-02", "title": "Invoice tax", "files_touched": "billing/invoice.py"},
    ]
    ticket_coll.add(
        ids=t_ids,
        documents=t_docs,
        embeddings=fake_emb.embed_documents(t_docs),
        metadatas=t_metas,
    )

    return client, fake_emb


def test_search_code_chunks_empty(tmp_path: Path):
    """Verify searching an empty or non-existent collection returns empty list without error."""
    empty_client = chromadb.PersistentClient(path=str(tmp_path / "empty_chroma"))
    fake_emb = FakeDeterministicEmbeddings()
    results = search_code_chunks("test query", client=empty_client, embeddings=fake_emb)
    assert results == []


def test_search_code_chunks_hybrid_boost(fake_chroma_db):
    """Verify exact symbol name in query boosts the matching chunk to top position."""
    client, fake_emb = fake_chroma_db
    query = "User reported failure in verify_credentials during authentication"
    results = search_code_chunks(
        query=query,
        k=2,
        client=client,
        embeddings=fake_emb,
        hybrid_boost=True,
    )

    assert len(results) == 2
    top_result = results[0]
    assert top_result["symbol_name"] == "verify_credentials"
    assert top_result["file_path"] == "auth/login.py"
    assert top_result["score"] > top_result["base_score"]


def test_search_tickets(fake_chroma_db):
    """Verify tickets retrieval returns formatted results with similarity scores."""
    client, fake_emb = fake_chroma_db
    results = search_tickets(
        query="invoice tax rounding discrepancy",
        k=2,
        client=client,
        embeddings=fake_emb,
    )

    assert len(results) == 2
    assert results[0]["ticket_id"] in ("TICK-01", "TICK-02")
    assert "score" in results[0]
