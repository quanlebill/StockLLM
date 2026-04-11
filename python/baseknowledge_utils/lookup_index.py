"""
lookup_index.py

Builds and queries a vector lookup index for stored books/documents.

- Key   = book/root entity name
- Value = { "summary": str, "vector": List[float] }

The vector is embedded from the book's summary (not its name).
Model: all-MiniLM-L6-v2  (384-dim, fast, strong cosine similarity quality)

Functions:
  build_index()              → query Neo4j for root entities, embed summaries, save JSON
  search_books(query, top_k) → embed query, cosine similarity, return top_k results
"""

import os
import json
import numpy as np
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent.parent
load_dotenv(ROOT / ".env")

from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer

from python.basestruct.base_model import EMBEDDING_MODEL
from python.basestruct.neo4j_relationship import EntityRel

INDEX_PATH = ROOT / "baseknowledge" / "lookup_index.json"

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

_model = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def _get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def build_index() -> dict:
    """
    Query Neo4j for root entities (books) — entities with no incoming RELATED_TO edges.
    Embed each book's summary, save to lookup_index.json.
    Returns a summary of what was indexed.
    """
    driver = _get_driver()
    model = _get_model()

    with driver.session() as session:
        # Root entities = no other entity points to them via RELATED_TO
        neo4j_cypher =  f"""
            MATCH (e:Entity)
            WHERE NOT ()-[:{EntityRel.RELATED_TO}]->(e)
            RETURN e.name AS name, e.summary AS summary
            """
        result = session.run(neo4j_cypher)
        roots = [{"name": r["name"], "summary": r["summary"]} for r in result]

    driver.close()

    if not roots:
        return {"status": "no root entities found", "indexed": 0}

    # Filter out entries with no summary
    valid = [r for r in roots if r["summary"]]

    summaries = [r["summary"] for r in valid]
    vectors = model.encode(summaries, normalize_embeddings=True)

    index = {}
    for i, r in enumerate(valid):
        index[r["name"]] = {
            "summary": r["summary"],
            "vector": vectors[i].tolist(),
        }

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    return {
        "status": "ok",
        "indexed": len(index),
        "books": list(index.keys()),
        "path": str(INDEX_PATH),
    }


def search_books(query: str, top_k: int = 5) -> dict:
    """
    Embed the query, compute cosine similarity against all book vectors,
    return top_k book names with scores and summaries.
    """
    if not INDEX_PATH.exists():
        return {"error": "lookup_index.json not found. Run build_index() first."}

    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        index = json.load(f)

    if not index:
        return {"error": "Index is empty."}

    model = _get_model()
    query_vector = model.encode([query], normalize_embeddings=True)[0]

    scores = []
    for book_name, data in index.items():
        vec = np.array(data["vector"], dtype=np.float32)
        score = _cosine_similarity(query_vector, vec)
        scores.append({
            "book": book_name,
            "score": round(score, 4),
            "summary": data["summary"],
        })

    scores.sort(key=lambda x: x["score"], reverse=True)
    top = scores[:top_k]

    return {
        "query": query,
        "top_k": top_k,
        "results": top,
    }


if __name__ == "__main__":
    print("Building index...")
    result = build_index()
    print(result)

    print("\nTest search: 'how to analyze stock sectors'")
    print(search_books("how to analyze stock sectors", top_k=3))
