"""
cache_query.py — Two-layer Qdrant-based query cache.

Pure Python module — no FastAPI, no HTTP server.
Imported directly by control_plane.py and mcp_control_plane.py.

Layer 1 — ANSWER_CACHE
    Stores (query_embedding, answer).
    A near-duplicate question (score ≥ ANSWER_THRESHOLD) returns the cached
    answer immediately — zero skill calls needed.

Layer 2 — DOCUMENT_CACHE
    Stores (query_embedding, page_paths) in topic/bookname/page.pdf format.
    A similar-topic question (score ≥ DOCUMENT_THRESHOLD) skips graph traversal
    and jumps straight to load_pages_by_paths.

Caching is automatic — control_plane.py calls cache_store inside log_answer.
cache_lookup and cache_invalidate are called directly from mcp_control_plane.py.

Embedding model: all-MiniLM-L6-v2 (384-dim).
Qdrant connection: QDRANT_URL + QDRANT_API_KEY read from root .env.
"""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from sentence_transformers import SentenceTransformer

from python.basestruct.base_model import EMBEDDING_MODEL

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

load_dotenv(Path(os.environ["STOCKLLM_ROOT"]) / ".env")

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")

ANSWER_COLLECTION = "ANSWER_CACHE"
DOCUMENT_COLLECTION = "DOCUMENT_CACHE"

VECTOR_DIM = 384  # all-MiniLM-L6-v2

# Similarity thresholds (cosine, 0–1).
ANSWER_THRESHOLD = 0.92
DOCUMENT_THRESHOLD = 0.80

# ---------------------------------------------------------------------------
# Singletons (lazy-loaded)
# ---------------------------------------------------------------------------

_model: SentenceTransformer | None = None
_client: QdrantClient | None = None
_collections_ready: bool = False


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)
    return _client


# ---------------------------------------------------------------------------
# Collection bootstrap
# ---------------------------------------------------------------------------

def _ensure_collection(name: str) -> None:
    client = _get_client()
    existing = {c.name for c in client.get_collections().collections}
    if name not in existing:
        client.create_collection(
            collection_name=name,
            vectors_config=qdrant_models.VectorParams(
                size=VECTOR_DIM,
                distance=qdrant_models.Distance.COSINE,
            ),
        )
    # Ensure keyword index on query_hash for O(1) exact-match filter (MatchValue requires it)
    client.create_payload_index(
        collection_name=name,
        field_name="query_hash",
        field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
    )


def _ensure_collections() -> None:
    global _collections_ready
    if _collections_ready:
        return
    _ensure_collection(ANSWER_COLLECTION)
    _ensure_collection(DOCUMENT_COLLECTION)
    _collections_ready = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _embed(text: str) -> list[float]:
    return _get_model().encode([text], normalize_embeddings=True)[0].tolist()


def embed(text: str) -> list[float]:
    """Public embed — used by retrieval_pipeline for Qdrant ID-filtered search."""
    return _embed(text)


def _expand_to_paths(topic: str, book_name: str, page_indexes: list) -> list[str]:
    """
    Expand [[from, to], ...] ranges into individual topic/bookname/page.pdf paths.

    Example:
        ("finance", "Stock Analysis Curriculum", [[3,4],[10,10]])
        → ["finance/Stock Analysis Curriculum/3.pdf",
           "finance/Stock Analysis Curriculum/4.pdf",
           "finance/Stock Analysis Curriculum/10.pdf"]
    """
    paths = []
    for rng in page_indexes:
        for page in range(rng[0], rng[1] + 1):
            paths.append(f"{topic}/{book_name}/{page}.pdf")
    return paths


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _hash_filter(query_hash: str) -> qdrant_models.Filter:
    return qdrant_models.Filter(
        must=[qdrant_models.FieldCondition(
            key="query_hash",
            match=qdrant_models.MatchValue(value=query_hash),
        )]
    )


def _increment_hit_count(client: QdrantClient, collection: str, point_id) -> None:
    """Read current hit_count and increment by 1."""
    points = client.retrieve(collection_name=collection, ids=[point_id], with_payload=True)
    if points:
        current = points[0].payload.get("hit_count", 0)
        client.set_payload(
            collection_name=collection,
            payload={"hit_count": current + 1},
            points=[point_id],
        )


def cache_lookup(canonical: str, query_hash: str) -> dict[str, Any]:
    """
    Two-stage lookup against both cache layers.

    Stage 1 — hash exact match (O(1) payload filter, score = 1.0).
    Stage 2 — canonical similarity search (cosine on embedded canonical string).

    Returns one of:
        { "hit": "answer",   "answer": str, "canonical": str, "score": float }
        { "hit": "document", "page_paths": list, "canonical": str, "score": float }
        { "hit": "miss" }
    """
    _ensure_collections()
    client = _get_client()

    # ── Stage 1: exact hash match ────────────────────────────────────────────
    for collection, hit_type in (
            (ANSWER_COLLECTION, "answer"),
            (DOCUMENT_COLLECTION, "document"),
    ):
        points, _ = client.scroll(
            collection_name=collection,
            scroll_filter=_hash_filter(query_hash),
            limit=1,
            with_payload=True,
            with_vectors=False,
        )
        if points:
            p = points[0]
            _increment_hit_count(client, collection, p.id)
            result = {
                "hit": hit_type,
                "canonical": p.payload.get("canonical", ""),
                "score": 1.0,
            }
            if hit_type == "answer":
                result["answer"] = p.payload.get("answer", "")
            else:
                result["page_paths"] = p.payload.get("page_paths", [])
            return result

    # ── Stage 2: canonical similarity search ─────────────────────────────────
    vec = _embed(canonical)

    hits = client.query_points(
        collection_name=ANSWER_COLLECTION,
        query=vec,
        limit=1,
        with_payload=True,
        score_threshold=ANSWER_THRESHOLD,
    ).points
    if hits:
        best = hits[0]
        _increment_hit_count(client, ANSWER_COLLECTION, best.id)
        return {
            "hit": "answer",
            "answer": best.payload.get("answer", ""),
            "canonical": best.payload.get("canonical", ""),
            "score": round(best.score, 4),
        }

    hits = client.query_points(
        collection_name=DOCUMENT_COLLECTION,
        query=vec,
        limit=1,
        with_payload=True,
        score_threshold=DOCUMENT_THRESHOLD,
    ).points
    if hits:
        best = hits[0]
        _increment_hit_count(client, DOCUMENT_COLLECTION, best.id)
        return {
            "hit": "document",
            "page_paths": best.payload.get("page_paths", []),
            "canonical": best.payload.get("canonical", ""),
            "score": round(best.score, 4),
        }

    return {"hit": "miss"}


def cache_store(
        user_question: str,
        canonical: str,
        query_hash: str,
        answer: str,
        topic: str = "",
        book_name: str = "",
        page_indexes: list = None,
) -> dict[str, Any]:
    """
    Store a Q&A pair into both cache layers.

    Embeds the canonical form (not the raw question) for consistent similarity search.
    Stores query_hash in payload for O(1) exact-match lookup on future calls.

    topic, book_name, page_indexes are optional.
    - Always writes ANSWER_CACHE (layer 1).
    - Only writes DOCUMENT_CACHE (layer 2) when topic + book_name + page_indexes are all present.
    """
    if page_indexes is None:
        page_indexes = []

    _ensure_collections()
    client = _get_client()
    vec = _embed(canonical)
    now = datetime.now(timezone.utc).isoformat()

    base_payload = {
        "query": user_question,
        "canonical": canonical,
        "query_hash": query_hash,
        "cached_at": now,
        "hit_count": 0,
    }

    answer_id = str(uuid.uuid4())
    document_id = None
    page_paths = []

    # Layer 1 — always
    client.upsert(
        collection_name=ANSWER_COLLECTION,
        points=[qdrant_models.PointStruct(
            id=answer_id,
            vector=vec,
            payload={**base_payload, "answer": answer},
        )],
    )

    # Layer 2 — only when document info is available
    if topic and book_name and page_indexes:
        page_paths = _expand_to_paths(topic, book_name, page_indexes)
        document_id = str(uuid.uuid4())
        client.upsert(
            collection_name=DOCUMENT_COLLECTION,
            points=[qdrant_models.PointStruct(
                id=document_id,
                vector=vec,
                payload={**base_payload, "page_paths": page_paths},
            )],
        )

    return {"status": "ok", "answer_id": answer_id, "document_id": document_id, "page_paths": page_paths}


def cache_invalidate(canonical: str, query_hash: str) -> dict[str, Any]:
    """
    Remove entries from both cache layers using the same two-stage strategy as lookup:
    stage 1 tries hash filter, stage 2 falls back to canonical similarity search.
    """
    _ensure_collections()
    client = _get_client()
    deleted = {}

    for collection, threshold in (
            (ANSWER_COLLECTION, ANSWER_THRESHOLD),
            (DOCUMENT_COLLECTION, DOCUMENT_THRESHOLD),
    ):
        # Stage 1: exact hash match
        points, _ = client.scroll(
            collection_name=collection,
            scroll_filter=_hash_filter(query_hash),
            limit=1,
            with_payload=False,
            with_vectors=False,
        )
        if points:
            client.delete(
                collection_name=collection,
                points_selector=qdrant_models.PointIdsList(points=[points[0].id]),
            )
            deleted[collection] = 1
            continue

        # Stage 2: canonical similarity
        vec = _embed(canonical)
        hits = client.query_points(
            collection_name=collection,
            query=vec,
            limit=1,
            with_payload=False,
            score_threshold=threshold,
        ).points
        if hits:
            client.delete(
                collection_name=collection,
                points_selector=qdrant_models.PointIdsList(points=[hits[0].id]),
            )
            deleted[collection] = 1
        else:
            deleted[collection] = 0

    return {"status": "ok", "deleted": deleted}


def evict_bottom_hits(n: int = 100) -> dict[str, Any]:
    """
    Delete the bottom N cache entries (lowest hit_count) from both cache collections.
    Scrolls all points, sorts by hit_count ascending, deletes the lowest n from each.

    Returns:
        { "deleted": { "ANSWER_CACHE": int, "DOCUMENT_CACHE": int } }
    """
    _ensure_collections()
    client = _get_client()
    deleted = {}

    for collection in (ANSWER_COLLECTION, DOCUMENT_COLLECTION):
        # Scroll all points collecting (id, hit_count)
        all_points: list[tuple[Any, int]] = []
        offset = None
        while True:
            batch, next_offset = client.scroll(
                collection_name=collection,
                limit=500,
                offset=offset,
                with_payload=["hit_count"],
                with_vectors=False,
            )
            for p in batch:
                all_points.append((p.id, p.payload.get("hit_count", 0)))
            if next_offset is None:
                break
            offset = next_offset

        if not all_points:
            deleted[collection] = 0
            continue

        # Sort ascending by hit_count and take bottom n
        all_points.sort(key=lambda x: x[1])
        victims = [pid for pid, _ in all_points[:n]]
        client.delete(
            collection_name=collection,
            points_selector=qdrant_models.PointIdsList(points=victims),
        )
        deleted[collection] = len(victims)

    return {"status": "ok", "deleted": deleted}
