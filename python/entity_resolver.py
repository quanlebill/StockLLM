"""
entity_resolver.py — Three-stage entity resolution for knowledge graph building.

Stage 1: Exact alias lookup  (lookup table JSON — O(1), deterministic)
Stage 2: Cosine + word overlap bonus  (in-memory brute-force, no Qdrant needed)
Stage 3: Create new entity  (if no match above threshold)

On a Stage 2 hit, the alias is written back to the lookup table so the next
call for the same alias hits Stage 1 instead.

Thread-safe for single-process use.
"""

import json
import os
import re
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from python.basestruct.base_model import EMBEDDING_MODEL

ROOT = os.environ["STOCKLLM_ROOT"]
LOOKUP_PATH = os.path.join(ROOT, "logs", "entity_lookup.json")
EMBED_PATH = os.path.join(ROOT, "logs", "entity_embeddings.json")

os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)

# Tuning knobs
COSINE_THRESHOLD = 0.82
WORD_OVERLAP_BONUS = 0.12  # added when canonical contains every input word


# Singletons
_model: Optional[SentenceTransformer] = None
_lookup: dict[str, str] = {}
_embeddings: dict[str, list[float]] = {}

#Utils
def _get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def load() -> None:
    """Load lookup table and embeddings from disk. Called once at startup."""
    global _lookup, _embeddings
    if os.path.exists(LOOKUP_PATH):
        with open(LOOKUP_PATH, "r", encoding="utf-8") as f:
            _lookup = json.load(f)
    if os.path.exists(EMBED_PATH):
        with open(EMBED_PATH, "r", encoding="utf-8") as f:
            _embeddings = json.load(f)


def _save() -> None:
    with open(LOOKUP_PATH, "w", encoding="utf-8") as f:
        json.dump(_lookup, f, ensure_ascii=False, indent=2)
    with open(EMBED_PATH, "w", encoding="utf-8") as f:
        json.dump(_embeddings, f, ensure_ascii=False)

def normalize(text: str) -> str:
    """Lowercase + collapse whitespace. Public for use by self_improvement."""
    return re.sub(r"\s+", " ", text.lower().strip())


def to_key(text: str) -> str:
    """Canonical key format: underscore_separated, lowercase. Public for use by self_improvement."""
    return normalize(text).replace(" ", "_")


# Internal aliases kept for backward compat within this module
_normalize = normalize
_to_key = to_key


def _embed(text: str) -> np.ndarray:
    return _get_embedding_model().encode([text], normalize_embeddings=True)[0]


def _word_overlap_bonus(input_text: str, canonical_key: str) -> float:
    """
    Return WORD_OVERLAP_BONUS if every word in input_text appears as a
    substring inside canonical_key (spaces replaced for readability).

    Example:
        input:    "fed fund"      → words: ["fed", "fund"]
        canonical: "federal_funds_rate" → "federal funds rate"
        "fed" in "federal funds rate" ✓, "fund" in "federal funds rate" ✓
        → bonus
    """
    words = input_text.split()
    target = canonical_key.replace("_", " ")
    if words and all(w in target for w in words):
        return WORD_OVERLAP_BONUS
    return 0.0


def resolve(raw: str) -> str:
    """
    Resolve a raw entity string to its canonical key.
    Automatically creates a new entity if no match is found.

    Returns the canonical key (lowercase, underscore-separated).

    Examples:
        resolve("Fed Fund")          → "federal_funds_rate"
        resolve("gross domestic product") → "gross_domestic_product"
        resolve("some new concept")  → "some_new_concept"  (new entity)
    """
    normalized = _normalize(raw)

    # Stage 1 — exact alias lookup (O(1))
    if normalized in _lookup:
        return _lookup[normalized]

    # Stage 2 — cosine similarity + word overlap bonus
    if _embeddings:
        vec = _embed(normalized)
        best_score = -1.0
        best_key = None

        for canonical_key, stored_vec in _embeddings.items():
            cosine = float(np.dot(vec, np.array(stored_vec)))
            bonus = _word_overlap_bonus(normalized, canonical_key)
            total = cosine + bonus
            if total > best_score:
                best_score, best_key = total, canonical_key

        if best_key and best_score >= COSINE_THRESHOLD:
            _lookup[normalized] = best_key  # write-back so Stage 1 hits next time
            _save()
            return best_key

    # Stage 3 — new entity
    canonical_key = _to_key(normalized)
    _lookup[normalized] = canonical_key
    _embeddings[canonical_key] = _embed(normalized).tolist()
    _save()
    return canonical_key


def register(canonical: str, aliases: list[str] = [], category: str = "") -> str:
    canonical_key = _to_key(canonical)

    if canonical_key not in _embeddings:
        _embeddings[canonical_key] = _embed(canonical_key.replace("_", " ")).tolist()

    for alias in [canonical] + aliases:
        _lookup[_normalize(alias)] = canonical_key

    _save()
    return canonical_key


def all_canonicals() -> list[str]:
    """Return all registered canonical entity keys."""
    return list(_embeddings.keys())


# Load on import
load()
