"""
MCP Server — Control Plane Client

Exposes tools to Claude:
  - announce                : open or continue a conversation log (call once per user question)
  - change_conversation_key : switch to a new conversation key when the topic changes
  - invoke_skill            : call ONE skill via the StockLLM control plane
  - invoke_skills           : call MULTIPLE skills in one request
  - finalize                : log the final answer and trigger cache (replaces set_answer + log_answer)
  - log_comment             : save a comment/correction to a conversation block
  - load_last_conversation  : return prior Q&A from the current conversation key
  - list_skills             : return registered skills for a given category
  - cache_lookup            : check the two-layer query cache before retrieval
  - cache_invalidate        : remove a stale cache entry
  - load_pages              : load PDF pages for a topic + book via Ollama
  - load_pages_by_paths     : load PDF pages from cached page paths
  - retrieve                : unified retrieval pipeline (cache + LightRAG in one call)

Self-improvement tools (kg.*):
  - kg.announce             : start a KG self-improvement session
  - kg.next                 : get next block (auto-preprocessed by Ollama3); always returns step="extract"
  - kg.extract              : submit extracted entities/policies/relationships/notes
  - kg.status               : check pipeline progress
  - kg.build                : re-scan success/ for new files

The active conversation key is stored in .env (CONVERSATION_KEY).
All invoke/log calls read the key from .env automatically — no need to pass it manually.
Every tool call (except announce, finalize, and navigation tools) is automatically
appended to the conversation workflow log.

The control plane (all-in-one) must be running at http://localhost:8000.
Start it with:  python run_all.py   (or: python python/control_plane.py)
"""

import hashlib
import os
import re
import uuid
import requests
from pathlib import Path
from datetime import datetime
from dotenv import dotenv_values, set_key
from mcp.server.fastmcp import FastMCP

CONTROL_PLANE_URL = "http://localhost:8000"
ROOT     = os.environ.get("STOCKLLM_ROOT") or str(Path(__file__).resolve().parent.parent)
ENV_PATH = os.path.join(ROOT, ".env")

mcp = FastMCP("control-plane")
RETRIEVE_CACHE = {}


# Pre-warm the SentenceTransformer model at startup so cache_lookup Stage 2
# doesn't incur a 30–90s cold load on the first question.
try:
    from cache_query import _get_model as _warm_cache_model
    _warm_cache_model()
except Exception:
    pass  # non-fatal — cache_lookup will still work, just slower on first call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _invoke(conversation_key: str, skills: list[dict]) -> dict:
    payload = {"conversation_key": conversation_key, "skills": skills}
    resp = requests.post(f"{CONTROL_PLANE_URL}/invoke", json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()


def _new_key() -> str:
    """Generate a unique conversation key: YYYYMMDD_HHMMSS_<uuid4>."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{ts}_{str(uuid.uuid4()).replace('-', '_')}"


def _get_key() -> str:
    """Read current CONVERSATION_KEY from .env. Returns empty string if not set."""
    return dotenv_values(ENV_PATH).get("CONVERSATION_KEY", "") or ""


def _require_key() -> str:
    """Return current key or raise if not set."""
    key = _get_key()
    if not key:
        raise ValueError("No active conversation key. Call announce first.")
    return key


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _log_step(tool_name: str, args: dict, result: any) -> None:
    """Append a tool call entry to the current conversation's workflow log."""
    key = _get_key()
    if not key:
        return
    result_preview = str(result)[:400] if result is not None else "None"
    text = f"---TOOL: {tool_name}---\nArgs: {args}\nResult: {result_preview}\n---END---"
    try:
        requests.post(
            f"{CONTROL_PLANE_URL}/conversation/append-workflow",
            json={"conversation_key": key, "workflow": text},
            timeout=5,
        )
    except Exception:
        pass  # logging is best-effort


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def announce(user_question: str) -> dict:
    """
    Open or continue a conversation log for the current key in .env.
    Each call adds a new block (user → workflow → answer) to the same conversation file.
    If no key exists yet, a UUID is generated and saved to .env automatically.

    Call this ONCE at the start of every new user question, before any skills or cache checks.

    Args:
        user_question: The user's question or task description.

    Returns:
        { "status": "ok", "conversation_key": "..." }
    """
    key = _get_key() or _new_key()
    payload = {"conversation_key": key, "user_question": user_question}
    resp = requests.post(f"{CONTROL_PLANE_URL}/conversation/start", json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def preprocess_query(query_type: str, entities: list[str], relationship: str, question_type: str = "") -> dict:
    """
    Canonicalize a user query into a normalized form and return its hash.
    Call this right after announce(), before cache_lookup().

    Canonicalization rules:
      - query_type    : lowercased ("question" or "statement")
      - question_type : only for questions — one of: what, who, when, where, how (lowercased)
                        appended to query_type as "question:what", "question:how", etc.
                        ignored when query_type is "statement"
      - entities      : each lowercased, sorted alphabetically, joined by ", "
      - relationship  : lowercased, whitespace normalized

    The canonical string format:
      "<query_type> | <entity1>, <entity2>, ... | <relationship>"

    The hash is SHA-256 of the canonical string, truncated to 16 hex chars.
    Pass both canonical and hash to cache_lookup() and finalize().

    Args:
        query_type    : "question" or "statement"
        entities      : list of entity names (e.g. ["GDP", "Fed Fund"])
        relationship  : relationship between entities (e.g. "GDP affect Fed Fund")
        question_type : (questions only) one of: what, who, when, where, how

    Returns:
        { "canonical": str, "hash": str }

    Example:
        preprocess_query("question", ["GDP", "Fed Fund"], "GDP affect Fed Fund", "how")
        → { "canonical": "question:how | fed fund, gdp | gdp affect fed fund",
            "hash": "a3f2c891d4b07e55" }
    """
    qt   = _normalize(query_type)
    ents = sorted(_normalize(e) for e in entities)
    rel  = _normalize(relationship)

    valid_question_types = {"what", "who", "when", "where", "how"}
    qt_normalized = qt
    if qt == "question" and question_type:
        qtype = _normalize(question_type)
        if qtype in valid_question_types:
            qt_normalized = f"question:{qtype}"

    canonical  = f"{qt_normalized} | {', '.join(ents)} | {rel}"
    query_hash = hashlib.sha256(canonical.encode()).hexdigest()[:16]
    return {"canonical": canonical, "hash": query_hash}


@mcp.tool()
def change_conversation_key() -> dict:
    """
    Switch to a new conversation key when the topic changes.
    Writes the new UUID to .env so that the next announce() creates a fresh file.
    Call announce() afterward to open the new conversation log.

    Returns:
        { "status": "ok", "conversation_key": "<new_key>" }
    """
    new_key = _new_key()
    set_key(ENV_PATH, "CONVERSATION_KEY", new_key)
    return {"status": "ok", "conversation_key": new_key}


@mcp.tool()
def invoke_skill(skill_name: str, arguments: dict = {}) -> dict:
    """
    Call a single skill via the StockLLM control plane.
    The conversation key is read automatically from .env — call announce first.

    Args:
        skill_name : Name of the skill to invoke (e.g. "finance_data_for_week").
        arguments  : Dict of keyword arguments for the skill.

    Returns:
        {
          "conversation_key": "...",
          "skills": [{ "skill_name": "...", "output": ..., "error": null }]
        }
    """
    return _invoke(_require_key(), [{"skill_name": skill_name, "arguments": arguments}])


@mcp.tool()
def invoke_skills(skills: list[dict]) -> dict:
    """
    Call MULTIPLE skills in a single request to the StockLLM control plane.
    The conversation key is read automatically from .env — call announce first.

    Args:
        skills: List of skill descriptors, each with:
                  { "skill_name": str, "arguments": dict }

    Returns:
        {
          "conversation_key": "...",
          "skills": [
            { "skill_name": "...", "output": ..., "error": null },
            ...
          ]
        }

    Example:
        invoke_skills([
            {"skill_name": "get_mart_tables", "arguments": {}},
            {"skill_name": "finance_data_for_week", "arguments": {"ticker": "AAPL"}}
        ])
    """
    return _invoke(_require_key(), skills)


@mcp.tool()
def finalize(answer: str, canonical: str = "", query_hash: str = "") -> dict:
    """
    Log the final answer to the current conversation block and trigger auto-cache.
    Call this once after composing your answer — it both saves the answer and returns
    it for display to the user.

    Pass the canonical and hash from preprocess_query() so the cache is stored
    under the normalized key. If omitted, the answer is logged but not cached.

    Args:
        answer     : The assistant's final answer text.
        canonical  : Canonical query string from preprocess_query().
        query_hash : Hash from preprocess_query().

    Returns:
        { "status": "ok", "answer": str }
    """
    key = _require_key()
    payload = {
        "conversation_key": key,
        "answer":           answer,
        "canonical":        canonical,
        "query_hash":       query_hash,
    }
    resp = requests.post(f"{CONTROL_PLANE_URL}/conversation/log-answer", json=payload, timeout=10)
    resp.raise_for_status()
    return {"status": "ok", "answer": answer}


@mcp.tool()
def log_comment(comment: str, block_index: int = -1) -> dict:
    """
    Save a comment to a specific block in the current conversation.
    Call this when the user comments on, corrects, or gives feedback about a previous answer
    — do NOT open a new conversation block for this, just log the comment directly.

    Args:
        comment     : The comment text to save.
        block_index : Index of the block to comment on (0-based). -1 = last block (default).

    Returns:
        { "status": "ok" }
    """
    payload = {
        "conversation_key": _require_key(),
        "comment": comment,
        "block_index": block_index,
    }
    resp = requests.post(f"{CONTROL_PLANE_URL}/conversation/log-comment", json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def load_last_conversation() -> dict:
    """
    Load the prior Q&A from the current conversation key stored in .env.
    Returns a numbered list of user questions and answers for context.
    Returns null if no key is set or no conversation file exists.

    Returns:
        {
          "result": "1. user: ...\\n1. answer: ...\\n2. user: ...\\n2. answer: ...",
          "conversation_key": "..."
        }
        or { "result": null, "conversation_key": null }
    """
    resp = requests.get(f"{CONTROL_PLANE_URL}/conversation/load-last", timeout=10)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def list_skills(category: str = "") -> dict:
    """
    Return the names of skills registered in the control plane for a given category.
    If category is omitted or empty, an empty skill list is returned.

    Args:
        category: Required to get any skills. Valid values:
                    "data"             — Snowflake mart query skills
                    "extraction"       — external market / macro data skills
                    "model"            — ML training, prediction, and performance skills
                    "storing"          — baseknowledge write pipeline (chunk → analyse → graph)
                    "retrieve"         — baseknowledge read pipeline (explore / search / traverse)
                    "self_improvement" — KG pipeline tools for reviewing and extracting knowledge

    Returns:
        { "skills": [...], "category": "<category>" }
        If category is omitted: { "skills": [], "category": null }

    IMPORTANT — always pass the correct category flag:
      - storing documents / building the knowledge graph → category="storing"
      - answering questions from the knowledge graph     → category="retrieve"
      - running a self-improvement session               → category="self_improvement"
    """
    _KG_SKILLS = [
        "kg.announce",
        "kg.next",
        "kg.extract",
        "kg.status",
        "kg.build",
    ]

    if category == "self_improvement":
        return {"skills": _KG_SKILLS, "category": "self_improvement"}

    params = {"category": category} if category else {}
    resp = requests.get(f"{CONTROL_PLANE_URL}/skills", params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Retrieve tools
# ---------------------------------------------------------------------------

@mcp.tool()
def load_pages(topic: str, book_name: str, page_indexes: list) -> dict:
    """
    Load PDF pages for a topic + book, process each page range through Ollama3
    to extract key points, and return the concatenated result.

    Use this when you have page_indexes from a baseknowledge.details call and want
    the full content rather than just the stored summary.
    For a cache "hit": "document", use load_pages_by_paths instead.

    Args:
        topic        : Subfolder under baseknowledge/docs/ (e.g. "finance")
        book_name    : Document folder name (e.g. "Stock Analysis Curriculum")
        page_indexes : List of [from, to] page ranges, e.g. [[3, 4], [10, 10]]

    Returns:
        {
          "topic": str,
          "book_name": str,
          "sections": [{ "range": "3-4", "key_points": str }, ...],
          "combined": str   # all sections concatenated — use this as answer context
        }
    """
    payload = {
        "topic":        topic,
        "book_name":    book_name,
        "page_indexes": page_indexes,
    }
    resp = requests.post(f"{CONTROL_PLANE_URL}/load-pages", json=payload, timeout=300)
    resp.raise_for_status()
    result = resp.json()
    _log_step("load_pages", {"topic": topic, "book_name": book_name, "page_indexes": page_indexes}, result)
    return result


@mcp.tool()
def load_pages_by_paths(page_paths: list) -> dict:
    """
    Load and process PDF pages given a list of paths in topic/bookname/page.pdf format.

    Use this when cache_lookup returns "hit": "document" — pass the cached
    page_paths directly here. No graph traversal needed.

    Args:
        page_paths : List of paths returned by cache_lookup,
                     e.g. ["finance/Stock Analysis Curriculum/3.pdf",
                           "finance/Stock Analysis Curriculum/4.pdf"]

    Returns:
        {
          "sections": [{ "range": str, "book_name": str, "key_points": str }, ...],
          "combined": str   # use this as answer context
        }
    """
    resp = requests.post(f"{CONTROL_PLANE_URL}/load-pages-by-paths", json={"page_paths": page_paths}, timeout=300)
    resp.raise_for_status()
    result = resp.json()
    _log_step("load_pages_by_paths", {"page_paths": page_paths}, result)
    return result


# ---------------------------------------------------------------------------
# Cache tools  (direct function calls — no HTTP, no separate service)
# ---------------------------------------------------------------------------

@mcp.tool()
def cache_lookup(canonical: str, query_hash: str) -> dict:
    """
    Two-stage cache lookup using the output of preprocess_query().
    Call this after preprocess_query() and before invoking any skills.

    Stage 1 — exact hash match (O(1), score = 1.0).
    Stage 2 — canonical similarity search (cosine, score < 1.0).

    Returns one of:
        { "hit": "answer",   "answer": str,      "canonical": str, "score": float }
            → Call finalize(answer, canonical, query_hash) and return it to the user.

        { "hit": "document", "page_paths": list, "canonical": str, "score": float }
            → Call load_pages_by_paths(page_paths), compose answer, then finalize().

        { "hit": "miss" }
            → Run full retrieval workflow, then finalize(answer, canonical, query_hash).

    Args:
        canonical  : Canonical query string from preprocess_query().
        query_hash : Hash from preprocess_query().
    """
    try:
        from cache_query import cache_lookup as _lookup
        result = _lookup(canonical, query_hash)
        _log_step("cache_lookup", {"canonical": canonical, "query_hash": query_hash}, result)
        return result
    except Exception as e:
        return {"hit": "miss", "error": str(e)}


@mcp.tool()
def cache_invalidate(canonical: str, query_hash: str) -> dict:
    """
    Remove the cached entry from both cache layers using the same two-stage strategy
    as cache_lookup (hash exact match first, then canonical similarity fallback).
    Call this when the user says an answer was wrong.

    Use preprocess_query() on the original question to get canonical + hash, then
    pass both here.

    Args:
        canonical  : Canonical query string from preprocess_query().
        query_hash : Hash from preprocess_query().

    Returns:
        { "status": "ok", "deleted": { "ANSWER_CACHE": int, "DOCUMENT_CACHE": int } }
    """
    try:
        from cache_query import cache_invalidate as _invalidate
        return _invalidate(canonical, query_hash)
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# ---------------------------------------------------------------------------
# Self-improvement — KG pipeline tools
# Read instruction/self_improvement/KG_PIPELINE_GUIDE.md before using these.
# KG pipeline is merged into control_plane.py (port 8000).
# ---------------------------------------------------------------------------

def _kg(method: str, path: str, body: dict = None) -> dict:
    """Best-effort call to the KG pipeline endpoints (now part of control plane)."""
    url = f"{CONTROL_PLANE_URL}{path}"
    try:
        if method == "GET":
            resp = requests.get(url, timeout=30)
        else:
            resp = requests.post(url, json=body or {}, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def kg_announce() -> dict:
    """
    Start a self-improvement review session.
    Call this ONCE before beginning to process blocks.
    Returns the number of blocks pending review, pending extraction, and done.

    Read instruction/self_improvement/KG_PIPELINE_GUIDE.md for the full workflow.
    """
    return _kg("POST", "/kg/announce")


@mcp.tool()
def kg_next() -> dict:
    """
    Get the next conversation block to process.

    If the block is "pending", Ollama3 automatically preprocesses it before returning:
      - Fixes the answer using the comment (if any)
      - Extracts key information including numerical thresholds

    Returns:
        {
          "block":             { id, user, answer, comment, canonical, hash, ... },
          "step":              "extract" | null,
          "preprocess_result": { "fixed_answer": str, "key_info": str } | null,
          "total":             int,
          "done":              int
        }

    step = "extract" → use preprocess_result.fixed_answer + preprocess_result.key_info
                       to compose entities/policies/relationships/notes for kg_extract()
    step = null      → all blocks are done, session complete

    Always call kg_next() again after each kg_extract() to get the next block.
    """
    return _kg("GET", "/kg/next")


@mcp.tool()
def kg_extract(
    block_id:      str,
    entities:      list[dict] = [],
    policies:      list[dict] = [],
    relationships: list[dict] = [],
    notes:         list[dict] = [],
    skipped:       bool = False,
) -> dict:
    """
    Submit extracted knowledge for a block. Call this when kg_next() returns step = "extract".
    Use preprocess_result.fixed_answer and preprocess_result.key_info from kg_next() as the
    source of truth for extraction. Entity names are canonicalized automatically.

    Args:
        block_id      : id field from the block
        entities      : list of { name, aliases?, category?, description? }
        policies      : list of { description, cause_entities, affect_entities, expires_at? }
                          description format: "cause: [gdp < -1.2%], policy: [fed cuts rate 0.5%]"
                          cause_entities: raw names of entities whose state TRIGGERS the policy (conditions)
                          affect_entities: raw names of entities CHANGED/IMPACTED as a result
                          expires_at: ISO datetime string, or null if permanent
        relationships : list of { from_entity, to_entity, direction?, strength?, description? }
        notes         : list of { content, entity }
                          content: rich explanation to embed and store in Qdrant
                          entity: raw entity name to attach the context to
        skipped       : set True if this block has nothing to extract (coding Q, meta, failed)

    Category values for entities:
        "macro" | "rate" | "market" | "sector" | "institution" | "instrument"

    Direction values:  "positive" | "negative" | "neutral"
    Strength values:   "weak" | "moderate" | "strong"

    Use Policy when magnitudes or conditions are present ("if GDP < -1.2% → fed raises 0.5%").
    Use Relationship for general directional knowledge ("GDP affects fed fund").
    Use Note for the full answer text when it contains rich detail worth preserving.

    See instruction/self_improvement/KG_PIPELINE_GUIDE.md for full decision guide.
    """
    return _kg("POST", "/kg/extract", {
        "block_id":      block_id,
        "entities":      entities,
        "policies":      policies,
        "relationships": relationships,
        "notes":         notes,
        "skipped":       skipped,
    })


@mcp.tool()
def kg_status() -> dict:
    """
    Return current KG pipeline progress.

    Returns:
        {
          "blocks": { "total": int, "pending": int, "preprocessed": int, "done": int }
        }
    """
    return _kg("GET", "/kg/status")


@mcp.tool()
def kg_build() -> dict:
    """
    Scan success/ for any new conversation files not yet queued or loaded.
    Tops up the in-memory buffer to BUFFER_SIZE active files from the queue.
    Additive — already-processed blocks keep their status.
    Call this if new success files were added after the session started.

    Returns: { new_queued, new_loaded, queue_size, total, pending, done }
    """
    return _kg("POST", "/kg/build")


@mcp.tool()
def cache_retrieve(queries) -> dict:
    cache_result = requests.post(f"{CONTROL_PLANE_URL}/get_cache_query", json=queries, timeout=180)
    cache_result.raise_for_status()
    cache_result = cache_result.json()
    _log_step("cache_retrieve", {"queries": queries}, cache_result)
    return cache_result
# ---------------------------------------------------------------------------
# Retrieval pipeline tool  (replaces multiple individual skill calls)
# Merged into control_plane.py (port 8000) — no separate service needed.
# ---------------------------------------------------------------------------

@mcp.tool()
def retrieve(queries: dict) -> dict:
    """
    Call the unified retrieval pipeline with a dict of structured queries.

    This replaces multiple individual skill calls — one call handles:
      - Dict → pipe-string conversion
      - Lowercasing + format parsing (returns reformat hint on error)
      - Entity canonicalization  (e.g. "Fed Fund" → "federal_funds_rate")
      - Concurrent cache lookup + LightRAG pipeline

    Args:
        queries: Dict of structured queries in this format:
          {
            "Query #1": {
              "Type": "Question",
              "Question Word": "How",
              "Entities": ["GDP", "Inflation"],
              "Relationship": ["affect/right"]
            },
            "Query #2": {
              "Type": "Statement",
              "Entities": ["GDP", "Sector"],
              "Relationship": ["indicate/right"]
            }
          }

        Type          : "Question" or "Statement"
        Question Word : (Question only) one of: What | How | When | Where | Who
        Entities      : list of entity name strings
        Relationship  : list of "relationship/direction" strings
                        (multiple entries fan out into separate queries)

    Returns:
        {
          "results": [
            {
              "query_index": int,
              "raw_query":   str,           # internal pipe string
              "error":       "format_error" (only on bad input),
              "message":     str,           # reformat hint (only on error)
              "parsed": {
                "type": str, "question_type": str,
                "entities_raw": [...],
                "entities": [...],          # canonicalized entity keys
                "entity_map": { raw: canonical },
                "relationship": str, "direction": str
              },
              "canonical": str,
              "hash":      str,
              "cache":     { "hit": "answer" | "document" | "miss", ... },
              "retrieval": { kg_results, doc_results, neighbors, keypoints, summary },
              "combined":  str              ← use this as answer context
            }
          ]
        }

    Usage:
      - error == "format_error" → reformat the offending query per message and retry
      - cache.hit == "answer"   → answer immediately from combined
      - cache.hit == "miss"     → compose answer from combined (retrieval summary)
    """
    resp = requests.post(
        f"{CONTROL_PLANE_URL}/retrieve",
        json={"queries": queries},
        timeout=180,
    )
    resp.raise_for_status()
    result = resp.json()
    _log_step("retrieve", {"queries": queries}, result)
    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
