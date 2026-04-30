"""
ollama_model.py — Centralized Ollama Inference Service

FastAPI service on port 8008.

Correct flow — each caller is responsible for all 3 steps:
  1. store_prompt(prompt, fmt, options) → key   [direct Qdrant write, no HTTP]
  2. run_by_key(key)                            [HTTP POST /run — only key travels]
  3. fetch_response(key)            → response  [direct Qdrant read, no HTTP]

The prompt never travels over HTTP at any point.
"""

import os
import uuid
import requests as _requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import ollama
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from sentence_transformers import SentenceTransformer

from python.basestruct.base_model import OLLAMA_MODEL, EMBEDDING_MODEL

load_dotenv(Path(os.environ["STOCKLLM_ROOT"]) / ".env")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

QDRANT_URL         = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY     = os.getenv("QDRANT_API_KEY", "")
OLLAMA_SERVICE_URL = os.getenv("OLLAMA_SERVICE_URL", "http://localhost:8008")

COLLECTION = "OLLAMA_REQUESTS"
VECTOR_DIM = 384  # all-MiniLM-L6-v2

# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------

_qdrant: Optional[QdrantClient] = None
_embed_model: Optional[SentenceTransformer] = None


def _get_qdrant() -> QdrantClient:
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)
        existing = {c.name for c in _qdrant.get_collections().collections}
        if COLLECTION not in existing:
            _qdrant.create_collection(
                collection_name=COLLECTION,
                vectors_config=qm.VectorParams(size=VECTOR_DIM, distance=qm.Distance.COSINE),
            )
    return _qdrant


def _get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embed_model


def _embed(text: str) -> list[float]:
    return _get_embed_model().encode([text], normalize_embeddings=True)[0].tolist()


# ---------------------------------------------------------------------------
# Public client API — called directly by callers (no HTTP)
# ---------------------------------------------------------------------------

def store_prompt(prompt: str, fmt: Optional[str] = None, options: Optional[dict] = None) -> str:
    """
    Step 1 — caller writes the prompt directly to Qdrant.
    Returns the key (UUID). The prompt never leaves the caller's process via HTTP.
    """
    key = str(uuid.uuid4())
    vec = _embed(prompt)
    now = datetime.now(timezone.utc).isoformat()
    _get_qdrant().upsert(
        collection_name=COLLECTION,
        points=[qm.PointStruct(
            id=key,
            vector=vec,
            payload={
                "prompt":       prompt,
                "format":       fmt,
                "options":      options or {},
                "status":       "pending",
                "response":     None,
                "created_at":   now,
                "completed_at": None,
            },
        )],
    )
    return key


def run_by_key(key: str) -> None:
    """
    Step 2 — send only the key over HTTP to the ollama_model service.
    The service reads the prompt from Qdrant, runs Ollama, saves the response.
    """
    resp = _requests.post(
        f"{OLLAMA_SERVICE_URL}/run",
        json={"key": key},
        timeout=300,
    )
    resp.raise_for_status()


def fetch_response(key: str) -> str:
    """
    Step 3 — caller reads the response directly from Qdrant.
    Returns the response string. No HTTP involved.
    """
    points = _get_qdrant().retrieve(
        collection_name=COLLECTION,
        ids=[key],
        with_payload=True,
        with_vectors=False,
    )
    if not points:
        raise KeyError(f"Key not found: {key}")
    return points[0].payload["response"]


# ---------------------------------------------------------------------------
# Internal Qdrant helpers (used by the /run endpoint only)
# ---------------------------------------------------------------------------

def _fetch_task(key: str) -> tuple[dict, list[float]]:
    """Read full task payload + vector. Used by /run to get the prompt."""
    points = _get_qdrant().retrieve(
        collection_name=COLLECTION,
        ids=[key],
        with_payload=True,
        with_vectors=True,
    )
    if not points:
        raise KeyError(f"Key not found: {key}")
    return points[0].payload, points[0].vector


def _save_response(key: str, existing_payload: dict, vec: list[float], response: str) -> None:
    """Write the Ollama response back into the existing Qdrant record."""
    now = datetime.now(timezone.utc).isoformat()
    _get_qdrant().upsert(
        collection_name=COLLECTION,
        points=[qm.PointStruct(
            id=key,
            vector=vec,
            payload={
                **existing_payload,
                "status":       "complete",
                "response":     response,
                "completed_at": now,
            },
        )],
    )


# ---------------------------------------------------------------------------
# Core inference (server-side only)
# ---------------------------------------------------------------------------

def _run_ollama(prompt: str, fmt: Optional[str], options: dict) -> str:
    kwargs: dict = {"model": OLLAMA_MODEL, "prompt": prompt}
    if fmt:
        kwargs["format"] = fmt
    if options:
        kwargs["options"] = options
    return ollama.generate(**kwargs)["response"]


# ---------------------------------------------------------------------------
# FastAPI
# ---------------------------------------------------------------------------

app = FastAPI(title="Ollama Model Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    key: str


@app.post("/run")
def run(request: RunRequest) -> dict:
    """
    Receive a key, read the prompt from Qdrant, run Ollama,
    save the response back to Qdrant. Returns {key, status} only.
    """
    try:
        payload, vec = _fetch_task(request.key)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    prompt  = payload["prompt"]
    fmt     = payload.get("format")
    options = payload.get("options") or {}

    try:
        response = _run_ollama(prompt, fmt, options)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama request failed: {e}")

    _save_response(request.key, payload, vec, response)
    return {"key": request.key, "status": "complete"}


@app.get("/result/{key}")
def get_result(key: str) -> dict:
    """Fetch a stored result by key — status and response."""
    try:
        payload, _ = _fetch_task(key)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"key": key, "status": payload["status"], "response": payload["response"]}


@app.get("/health")
def health() -> dict:
    try:
        _get_qdrant().get_collections()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008)
