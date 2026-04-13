"""
self_improvement.py — Knowledge Graph Extraction Pipeline (Neo4j + Qdrant for notes)

FastAPI service on port 8007.

Workflow
--------
1. Server starts → all success/ conversation files are merged into a flat block list
2. POST /kg/announce    → LLM signals start of review session; returns session stats
3. GET  /kg/next        → returns next block (auto-preprocesses via Ollama3 if pending)
                          always returns step = "extract" with preprocess_result
4. POST /kg/extract     → LLM submits entities/policies/relationships/notes
                          → entity names canonicalized via entity_resolver
                          → graph written to Neo4j; notes embedded into Qdrant
                          → block → done

Block states:  pending → preprocessed → done

Ollama3 preprocessing (automatic in /kg/next):
  - Fixes the answer using the comment (if any)
  - Extracts key information including numerical thresholds
  - Returns fixed_answer + key_info for Claude to use in kg/extract

Neo4j schema
------------
Nodes:
  (:Entity  {name, aliases, category, description, created_at, qdrant_ids})
  (:Policy  {id, description, entities, created_at, expires_at, qdrant_id})

  Entity.qdrant_ids: list of Qdrant point IDs — rich context stored in KG_NOTES
  Policy.description format:
    "entities: [gdp, fed_fund], policy: [if gdp < -1.2% → fed raises 0.5%, ...]"
  Policy.entities: list of canonical entity keys (for Neo4j filtering)
  Policy.qdrant_id: pointer to full context in KG_NOTES Qdrant collection

Edges:
  (Entity)-[:AFFECTS {direction, strength, description}]->(Entity)
"""

import json
import os
import shutil
import uuid
import ollama
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from sentence_transformers import SentenceTransformer

import entity_resolver
from python.basestruct.neo4j_relationship import PolicyRel, EntityRel
from python.basestruct.base import EntityInput, PolicyInput, RelationshipInput, NoteInput, ExtractRequest
from python.basestruct.agent_prompt import OllamaPrompt
from python.basestruct.base_model import OLLAMA_MODEL

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ROOT = os.environ["STOCKLLM_ROOT"]
SUCCESS_DIR = os.path.join(ROOT, "logs", "conversation", "success")  # control_plane writes here
CHUNKED_DIR = os.path.join(ROOT, "logs", "conversation", "chunked")  # KG pipeline moves files here on load
REVIEWED_DIR = os.path.join(CHUNKED_DIR, "reviewed")  # fully extracted files land here
STATE_PATH = os.path.join(ROOT, "logs", "kg_state.json")

os.makedirs(SUCCESS_DIR, exist_ok=True)
os.makedirs(CHUNKED_DIR, exist_ok=True)
os.makedirs(REVIEWED_DIR, exist_ok=True)
os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)

load_dotenv(os.path.join(ROOT, ".env"))

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")

NOTE_COLLECTION = "KG_NOTES"
VECTOR_DIM = 384


_neo4j_driver = None
_qdrant: Optional[QdrantClient] = None
_embed_model: Optional[SentenceTransformer] = None


def _neo4j():
    global _neo4j_driver
    if _neo4j_driver is None:
        _neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    return _neo4j_driver


def _qdrant_client() -> QdrantClient:
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)
        # Ensure KG_NOTES collection exists
        existing = {c.name for c in _qdrant.get_collections().collections}
        if NOTE_COLLECTION not in existing:
            _qdrant.create_collection(
                collection_name=NOTE_COLLECTION,
                vectors_config=qm.VectorParams(size=VECTOR_DIM, distance=qm.Distance.COSINE),
            )
        # Ensure payload index on attached_to exists (required for filtered vector search)
        try:
            _qdrant.create_payload_index(
                collection_name=NOTE_COLLECTION,
                field_name="attached_to",
                field_schema=qm.PayloadSchemaType.KEYWORD,
            )
        except Exception:
            pass  # index already exists — safe to ignore
    return _qdrant


def _embed_model_get() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embed_model


def _embed(text: str) -> list[float]:
    return _embed_model_get().encode([text], normalize_embeddings=True)[0].tolist()


# ---------------------------------------------------------------------------
# In-memory pipeline state
# ---------------------------------------------------------------------------

BUFFER_SIZE = 4  # number of conversation files to keep loaded at once

_blocks: list[dict] = []  # blocks from currently-loaded conversation files
_states: dict[str, str] = {}  # block_id → "pending" | "preprocessed" | "done"
_file_queue: list[str] = []  # conversation_keys waiting to be loaded (ordered)


def _pending() -> list[dict]:
    return [b for b in _blocks if _states.get(b["id"]) == "pending"]

def _preprocessed() -> list[dict]:
    return [b for b in _blocks if _states.get(b["id"]) == "preprocessed"]

def _done() -> list[dict]:
    return [b for b in _blocks if _states.get(b["id"]) == "done"]

def _next_block() -> Optional[dict]:
    """Return the next block to process, prioritising preprocessed over pending."""
    preprocessed = _preprocessed()
    if preprocessed:
        return preprocessed[0]
    pending = _pending()
    if pending:
        return pending[0]
    return None


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def _save_state() -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {"blocks": _blocks, "states": _states, "file_queue": _file_queue},
            f, ensure_ascii=False, indent=2,
        )


def _load_state() -> None:
    global _blocks, _states, _file_queue
    if not os.path.exists(STATE_PATH):
        return
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    _blocks = data.get("blocks", [])
    _states = data.get("states", {})
    _file_queue = data.get("file_queue", [])


# ---------------------------------------------------------------------------
# Queue-based file loading
# ---------------------------------------------------------------------------

def _reviewed_keys() -> set[str]:
    """Keys already fully extracted — sitting in chunked/reviewed/."""
    return {f[:-5] for f in os.listdir(REVIEWED_DIR) if f.endswith(".json")}


def _chunked_keys() -> set[str]:
    """Keys already moved to chunked/ (in-progress or awaiting buffer load)."""
    return {f[:-5] for f in os.listdir(CHUNKED_DIR) if f.endswith(".json")}


def _loaded_keys() -> set[str]:
    """Conversation keys currently loaded into _blocks."""
    return {b["conversation_key"] for b in _blocks}


def _load_conversation(key: str) -> int:
    """
    Load all blocks from a conversation file into _blocks.
    Looks first in success/ (new file), then in chunked/ (already moved or recovery).
    Moves the file from success/ → chunked/ on first load.
    Skips block IDs already present (idempotent).
    Returns the number of new blocks added.
    """
    src = os.path.join(SUCCESS_DIR, f"{key}.json")
    dst = os.path.join(CHUNKED_DIR, f"{key}.json")

    if os.path.exists(src):
        shutil.move(src, dst)  # claim the file into chunked/
        path = dst
    elif os.path.exists(dst):
        path = dst  # already in chunked/ (e.g. recovery after restart)
    else:
        return 0

    try:
        with open(path, "r", encoding="utf-8") as f:
            conv = json.load(f)
    except Exception:
        return 0

    existing_ids = {b["id"] for b in _blocks}
    date = conv.get("conversation_date", "")
    added = 0

    for idx, block in enumerate(conv.get("conversation_block", [])):
        block_id = f"{key}_{idx}"
        if block_id in existing_ids:
            continue
        _blocks.append({
            "id": block_id,
            "conversation_key": key,
            "conversation_date": date,
            "block_index": idx,
            "user": block.get("user", ""),
            "canonical": block.get("canonical", ""),
            "hash": block.get("hash", ""),
            "answer": block.get("answer", ""),
            "comment": block.get("comment", ""),
        })
        _states[block_id] = "pending"
        added += 1

    return added


def _sync_queue() -> int:
    """
    Scan success/ and chunked/ for files not yet queued or loaded.
    - success/ : new conversations from control_plane (not yet picked up)
    - chunked/ : files moved on a previous run but lost from state (recovery)
    Appends new keys to _file_queue in chronological order, no duplicates.
    Returns number of new keys added to the queue.
    """
    reviewed = _reviewed_keys()
    loaded = _loaded_keys()
    queued = set(_file_queue)

    # Recovery: files in chunked/ not in _blocks (e.g. state was wiped)
    for key in sorted(_chunked_keys()):
        if key not in reviewed and key not in loaded and key not in queued:
            _file_queue.append(key)

    # New files waiting in success/
    added = 0
    for key in sorted(f[:-5] for f in os.listdir(SUCCESS_DIR) if f.endswith(".json")):
        if key not in reviewed and key not in loaded and key not in queued and key not in _chunked_keys():
            _file_queue.append(key)
            added += 1

    return added


def _topup_buffer() -> int:
    """
    Pull files from _file_queue until BUFFER_SIZE conversation files are
    actively loaded (have at least one non-done block), or the queue empties.
    Returns number of new blocks loaded.
    """
    total_added = 0
    while _file_queue:
        active_keys = {
            b["conversation_key"] for b in _blocks
            if _states.get(b["id"]) != "done"
        }
        if len(active_keys) >= BUFFER_SIZE:
            break
        key = _file_queue.pop(0)
        total_added += _load_conversation(key)

    if total_added:
        _save_state()

    return total_added


# ---------------------------------------------------------------------------
# Neo4j helpers
# ---------------------------------------------------------------------------

def _neo4j_run(query: str, **params) -> list[dict]:
    with _neo4j().session() as session:
        result = session.run(query, **params)
        return [dict(r) for r in result]


def _upsert_entity(name: str, aliases: list[str], category: str,
                   description: str, now: str) -> None:
    _neo4j_run("""
        MERGE (e:Entity {name: $name})
        ON CREATE SET
            e.aliases     = $aliases,
            e.category    = $category,
            e.description = $description,
            e.created_at  = $now,
            e.qdrant_ids  = []
        ON MATCH SET
            e.aliases     = apoc.coll.toSet(e.aliases + $aliases),
            e.description = CASE WHEN size($description) > size(e.description)
                                  THEN $description ELSE e.description END
    """, name=name, aliases=aliases, category=category,
               description=description, now=now)


def _append_qdrant_id_to_entity(name: str, qdrant_id: str) -> None:
    _neo4j_run("""
        MATCH (e:Entity {name: $name})
        SET e.qdrant_ids = apoc.coll.toSet(coalesce(e.qdrant_ids, []) + [$qdrant_id])
    """, name=name, qdrant_id=qdrant_id)


def _upsert_relationship(from_e: str, to_e: str, direction: str,
                         strength: str, description: str) -> None:
    neo4j_cypher = f"""
        MATCH (a:Entity {{name: $from_e}})
        MATCH (b:Entity {{name: $to_e}})
        MERGE (a)-[r:{EntityRel.RELATED_TO}]->(b)
        ON CREATE SET
            r.direction   = $direction,
            r.strength    = $strength,
            r.description = $description
        ON MATCH SET
            r.strength    = CASE WHEN $strength <> '' THEN $strength ELSE r.strength END,
            r.description = CASE WHEN size($description) > size(r.description)
                                  THEN $description ELSE r.description END
    """
    _neo4j_run(neo4j_cypher, from_e=from_e, to_e=to_e, direction=direction,
               strength=strength, description=description)


def _create_policy(pol_id: str, description: str, entities: list[str],
                   expires_at: Optional[str], qdrant_id: str, now: str) -> None:
    _neo4j_run("""
        CREATE (p:Policy {
            id:          $pol_id,
            description: $description,
            entities:    $entities,
            created_at:  $now,
            expires_at:  $expires_at,
            qdrant_id:   $qdrant_id
        })
    """, pol_id=pol_id, description=description, entities=entities,
               expires_at=expires_at, qdrant_id=qdrant_id, now=now)


def _link_policy_to_entities(pol_id: str, cause_entities: list[str], affect_entities: list[str]) -> None:
    """
    Create two edge types from a Policy node:
      (Policy)-[:CAUSED_BY]->(Entity)  — entity whose state/value triggers the policy condition
      (Policy)-[:AFFECTS]->(Entity)    — entity changed/impacted as a result of the policy
    """
    for entity_name in cause_entities:
        _neo4j_run(f"""
            MATCH (p:Policy {{id: $pol_id}})
            MATCH (e:Entity {{name: $entity_name}})
            MERGE (p)-[:{PolicyRel.CAUSED_BY}]->(e)
        """, pol_id=pol_id, entity_name=entity_name)
    for entity_name in affect_entities:
        _neo4j_run(f"""
            MATCH (p:Policy {{id: $pol_id}})
            MATCH (e:Entity {{name: $entity_name}})
            MERGE (p)-[:{PolicyRel.AFFECTS}]->(e)
        """, pol_id=pol_id, entity_name=entity_name)


def _store_in_qdrant(point_id: str, content: str, attached_to: str, now: str) -> str:
    """Embed content and store in KG_NOTES Qdrant collection. Returns the Qdrant point ID."""
    qdrant_id = str(uuid.uuid4())
    vec = _embed(content)
    _qdrant_client().upsert(
        collection_name=NOTE_COLLECTION,
        points=[qm.PointStruct(
            id=qdrant_id,
            vector=vec,
            payload={
                "point_id": point_id,
                "content": content,
                "attached_to": attached_to,
                "created_at": now,
            },
        )],
    )
    return qdrant_id


def search_policy_qdrant_ids(query_vector: list[float], top_k: int = 5) -> list[str]:
    """
    Vector search in Qdrant filtered to policy points only.
    Returns a list of qdrant_ids for the top-k matching policies.
    Used to supplement entity-name-based policy lookup with semantic matching.
    """
    hits = _qdrant_client().query_points(
        collection_name=NOTE_COLLECTION,
        query=query_vector,
        query_filter=qm.Filter(
            must=[qm.FieldCondition(
                key="attached_to",
                match=qm.MatchValue(value="policy"),
            )]
        ),
        limit=top_k,
        with_payload=False,
    ).points
    return [str(h.id) for h in hits]


def fetch_context_by_ids(qdrant_ids: list[str], query_vector: list[float], top_k: int = 5) -> list[dict]:
    """
    Similarity search within a pre-filtered set of Qdrant point IDs.
    Stage 1 (Neo4j) narrows the candidate pool → Stage 2 (this) ranks by relevance.

    Args:
        qdrant_ids   : IDs collected from entity.qdrant_ids + policy.qdrant_id
        query_vector : embedded user query for semantic ranking
        top_k        : max results to return

    Returns:
        [{"content": str, "score": float}, ...]
    """
    if not qdrant_ids:
        return []
    hits = _qdrant_client().query_points(
        collection_name=NOTE_COLLECTION,
        query=query_vector,
        query_filter=qm.Filter(
            must=[qm.HasIdCondition(has_id=qdrant_ids)]
        ),
        limit=top_k,
        with_payload=True,
    ).points
    return [{"content": h.payload.get("content", ""), "score": round(h.score, 4)} for h in hits]


# ---------------------------------------------------------------------------
# Reviewed-file management
# ---------------------------------------------------------------------------

def _move_to_reviewed(conversation_key: str) -> None:
    """
    Move chunked/{key}.json → chunked/reviewed/{key}.json once all blocks
    from that conversation are done.
    Silently skips if the file is already moved or doesn't exist.
    """
    src = os.path.join(CHUNKED_DIR, f"{conversation_key}.json")
    dst = os.path.join(REVIEWED_DIR, f"{conversation_key}.json")
    if os.path.exists(src):
        shutil.move(src, dst)


def _all_blocks_done_for_key(conversation_key: str) -> bool:
    """Return True if every block from this conversation is in 'done' state."""
    return all(
        _states.get(b["id"]) == "done"
        for b in _blocks
        if b.get("conversation_key") == conversation_key
    )


# ---------------------------------------------------------------------------
# Ollama3 preprocessing
# ---------------------------------------------------------------------------

def _ollama_preprocess(user: str, answer: str, comment: str) -> dict:
    """
    Call Ollama3 to:
    1. Fix the answer using the comment (if any).
    2. Extract key information including numerical thresholds and relationships.

    Returns:
        {
          "fixed_answer": str,   # corrected answer (or original if no comment)
          "key_info":     str,   # bullet-point extraction of key facts/numbers
        }
    On Ollama failure, returns the original answer with an error note in key_info.
    """

    prompt = OllamaPrompt.get__self_improvement__ollama_preprocess_prompt(user, answer, comment)

    try:
        resp = ollama.generate(model=OLLAMA_MODEL, prompt=prompt, format="json")
        parsed = json.loads(resp["response"])
        return {
            "fixed_answer": parsed.get("fixed_answer", answer),
            "key_info": parsed.get("key_info", ""),
        }
    except Exception as e:
        return {
            "fixed_answer": answer,
            "key_info": f"(Ollama preprocessing failed: {e})",
        }


# ---------------------------------------------------------------------------
# Router (included by control_plane) + standalone startup hook
# ---------------------------------------------------------------------------

def startup() -> None:
    """Load persisted state, sync queue with any new files, and fill the buffer."""
    _load_state()
    _sync_queue()
    _topup_buffer()


router = APIRouter()

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/kg/announce")
def announce() -> dict:
    """
    LLM calls this to announce the start of a self-improvement session.
    Returns the current pipeline state so the LLM knows what to expect.
    """
    total = len(_blocks)
    done = len(_done())
    preprocessed = len(_preprocessed())
    pending = len(_pending())
    return {
        "status": "ready",
        "message": (
            f"{pending} blocks pending, {preprocessed} preprocessed (ready to extract), "
            f"{done} done. {len(_file_queue)} conversation files still in queue."
        ),
        "total": total,
        "pending": pending,
        "preprocessed": preprocessed,
        "done": done,
        "queue_remaining": len(_file_queue),
    }


@router.post("/kg/build")
def build() -> dict:
    """
    Scan success/ for any new conversation files and add them to the queue.
    Tops up the in-memory buffer to BUFFER_SIZE active files.
    Additive — already-processed blocks keep their status.
    """
    new_queued = _sync_queue()
    new_loaded = _topup_buffer()
    return {
        "status": "ok",
        "new_queued": new_queued,
        "new_loaded": new_loaded,
        "queue_size": len(_file_queue),
        "total": len(_blocks),
        "pending": len(_pending()),
        "done": len(_done()),
    }


@router.get("/kg/next")
def next_block() -> dict:
    """
    Return the next block to process.

    If the block is "pending", Ollama3 automatically preprocesses it:
      - Fixes the answer using the comment (if any)
      - Extracts key information including numerical thresholds
    The block transitions pending → preprocessed.

    Always returns step = "extract" with a preprocess_result field.
    block = null means all blocks are done.
    """
    block = _next_block()
    if block is None:
        return {
            "block": None,
            "step": None,
            "preprocess_result": None,
            "total": len(_blocks),
            "done": len(_done()),
        }

    block_id = block["id"]

    # Auto-preprocess pending blocks via Ollama3
    if _states.get(block_id) == "pending":
        result = _ollama_preprocess(
            user=block.get("user", ""),
            answer=block.get("answer", ""),
            comment=block.get("comment", ""),
        )
        for b in _blocks:
            if b["id"] == block_id:
                b["preprocess_result"] = result
                break
        _states[block_id] = "preprocessed"
        _save_state()
    else:
        # Already preprocessed — retrieve stored result
        result = block.get("preprocess_result", {})

    return {
        "block": block,
        "step": "extract",
        "preprocess_result": result,
        "total": len(_blocks),
        "done": len(_done()),
    }


@router.post("/kg/extract")
def extract(request: ExtractRequest) -> dict:
    """
    Submit extracted knowledge for a reviewed block.
    Entity names are canonicalized automatically via entity_resolver.
    Writes entities, policies, relationships to Neo4j.
    Embeds and stores notes in Qdrant, links them in Neo4j.
    Moves block from reviewed → done.
    """
    if request.block_id not in _states:
        raise HTTPException(404, f"Block '{request.block_id}' not found.")
    if _states[request.block_id] != "preprocessed":
        state = _states[request.block_id]
        raise HTTPException(400, f"Block must be in 'preprocessed' state (currently '{state}').")

    now = datetime.now(timezone.utc).isoformat()

    if not request.skipped:

        # ── 1. Canonicalize and upsert entities ──────────────────────────────
        canonical_map: dict[str, str] = {}  # raw name → canonical key

        for ent in request.entities:
            canonical_key = entity_resolver.resolve(ent.name)
            canonical_map[ent.name] = canonical_key

            for alias in ent.aliases:
                entity_resolver.resolve(alias)

            all_aliases = [entity_resolver.normalize(a) for a in ent.aliases]
            _upsert_entity(
                name=canonical_key,
                aliases=all_aliases,
                category=ent.category,
                description=ent.description,
                now=now,
            )

        # ── 2. Create policies ────────────────────────────────────────────────
        for pol in request.policies:
            canonical_cause = [
                canonical_map.get(e) or entity_resolver.resolve(e)
                for e in pol.cause_entities
            ]
            canonical_affect = [
                canonical_map.get(e) or entity_resolver.resolve(e)
                for e in pol.affect_entities
            ]
            # Store union of all entities on the node for fast property-based filtering
            all_entities = list(set(canonical_cause + canonical_affect))
            pol_id = str(uuid.uuid4())
            qdrant_id = _store_in_qdrant(pol_id, pol.description, "policy", now)

            _create_policy(
                pol_id=pol_id,
                description=pol.description,
                entities=all_entities,
                expires_at=pol.expires_at,
                qdrant_id=qdrant_id,
                now=now,
            )
            _link_policy_to_entities(pol_id, canonical_cause, canonical_affect)

        # ── 3. Upsert relationships ───────────────────────────────────────────
        for rel in request.relationships:
            from_e = canonical_map.get(rel.from_entity) or entity_resolver.resolve(rel.from_entity)
            to_e = canonical_map.get(rel.to_entity) or entity_resolver.resolve(rel.to_entity)

            for ename in (from_e, to_e):
                if ename not in {entity_resolver.to_key(e.name) for e in request.entities}:
                    _upsert_entity(ename, [], "", "", now)

            _upsert_relationship(from_e, to_e, rel.direction, rel.strength, rel.description)

        # ── 4. Store notes in Qdrant, append qdrant_id to entity ─────────────
        for note in request.notes:
            entity_name = canonical_map.get(note.entity) or entity_resolver.resolve(note.entity)
            qdrant_id = _store_in_qdrant(str(uuid.uuid4()), note.content, entity_name, now)
            _append_qdrant_id_to_entity(entity_name, qdrant_id)

    # ── Mark done ─────────────────────────────────────────────────────────────
    _states[request.block_id] = "done"
    _save_state()

    # Move source file to reviewed/ when all its blocks are done, then refill buffer
    conv_key = next(
        (b.get("conversation_key", "") for b in _blocks if b["id"] == request.block_id), ""
    )
    moved_to_reviewed = False
    if conv_key and _all_blocks_done_for_key(conv_key):
        _move_to_reviewed(conv_key)
        moved_to_reviewed = True
        _topup_buffer()  # pull next file from queue now that a slot freed up

    return {
        "status": "ok",
        "block_id": request.block_id,
        "skipped": request.skipped,
        "moved_to_reviewed": moved_to_reviewed,
        "queue_remaining": len(_file_queue),
        "pending": len(_pending()),
        "preprocessed": len(_preprocessed()),
        "done": len(_done()),
    }


@router.get("/kg/status")
def status() -> dict:
    """Return pipeline progress."""
    return {
        "blocks": {
            "total": len(_blocks),
            "pending": len(_pending()),
            "preprocessed": len(_preprocessed()),
            "done": len(_done()),
        },
        "queue_remaining": len(_file_queue),
    }


@router.post("/kg/reset")
def reset() -> dict:
    """
    Reset all in-memory block states back to pending and clear preprocess_result.
    Does NOT clear the Neo4j graph or move files back from reviewed/.
    """
    global _states
    _states = {b["id"]: "pending" for b in _blocks}
    for b in _blocks:
        b.pop("preprocess_result", None)
    _save_state()
    return {"status": "ok", "reset": len(_states), "queue_remaining": len(_file_queue)}


if __name__ == "__main__":
    import uvicorn

    _app = FastAPI(title="KG Pipeline", version="2.0.0")
    _app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    startup()
    _app.include_router(router)
    uvicorn.run(_app, host="0.0.0.0", port=8007, reload=False)
