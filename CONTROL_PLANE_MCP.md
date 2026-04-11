# Control Plane MCP

## Overview

All skill calls go through the FastAPI control plane at `http://localhost:8000`.
The control plane is a single process that includes the KG pipeline, retrieval pipeline,
and baseknowledge retrieve router — no separate ports needed for those.
The MCP server (`python/mcp_control_plane.py`) exposes tools to Claude directly —
no need to call the control plane HTTP endpoints manually.

---

## Starting Services

```bash
python run_all.py          # starts all services
```

Or start individually:

| Service | Script | Port |
|---|---|---|
| Control plane (all-in-one) | `python/control_plane.py` | 8000 |
| Storing pipeline | `baseknowledge/storing.py` | 8002 |
| Chunking pipeline | `baseknowledge/chunking.py` | 8004 |
| Local graph fallback | `baseknowledge/local/local_graph.py` | 8005 |
| MCP server | `python/mcp_control_plane.py` | stdio |

The following are merged into `control_plane.py` (port 8000) and do **not** run as separate services:
- `baseknowledge/retrieve.py` — KG query, search, explore, load-pages
- `python/kg_pipeline.py` — self-improvement review/extract pipeline
- `python/retrieval_pipeline.py` — unified retrieval (cache + LightRAG)

---

## MCP Tools

### `announce`
Open or continue a conversation log. Call once at the start of every new user question, before any skills or cache checks.

**Arguments:** `user_question` (string)
**Returns:** `{ "status": "ok", "conversation_key": "..." }`

---

### `change_conversation_key`
Switch to a fresh conversation key when the topic changes.

**Returns:** `{ "status": "ok", "conversation_key": "<new_key>" }`

---

### `load_last_conversation`
Load prior Q&A from the current conversation key.

**Returns:** `{ "result": "1. user: ...\n1. answer: ...", "conversation_key": "..." }`

---

### `retrieve`
**Primary retrieval tool.** Single call handles entity canonicalization, cache lookup, and LightRAG retrieval concurrently.

**Arguments:**
```json
{
  "queries": {
    "Query #1": {
      "Type": "Question",
      "Question Word": "How",
      "Entities": ["GDP", "Fed Fund"],
      "Relationship": ["affect/right"]
    },
    "Query #2": {
      "Type": "Statement",
      "Entities": ["Inflation", "Interest Rate"],
      "Relationship": ["indicate/right"]
    }
  }
}
```

**Field rules:**
- `Type`: `"Question"` or `"Statement"`
- `Question Word` (Question only): `What` | `How` | `When` | `Where` | `Who`
- `Relationship`: list of `"relationship/direction"` strings

**Returns:** `{ "results": [{ "cache": {...}, "retrieval": {...}, "combined": "..." }] }`

Use the `combined` field as answer context.
- `cache.hit == "answer"` → cached answer ready, respond immediately
- `cache.hit == "miss"` → compose answer from retrieval summary in `combined`
- `error == "format_error"` → fix query per `message` hint and retry

---

### `preprocess_query`
Canonicalize a query into a normalized form and return its hash. Used before manual `cache_lookup` calls.

**Arguments:** `query_type`, `entities` (list), `relationship`, `question_type` (optional)
**Returns:** `{ "canonical": "...", "hash": "..." }`

---

### `cache_lookup`
Two-stage cache lookup (exact hash → cosine similarity).

**Arguments:** `canonical` (string), `query_hash` (string)
**Returns:** `{ "hit": "answer"|"document"|"miss", ... }`

---

### `cache_invalidate`
Remove a stale cache entry. Call when the user says an answer was wrong.

**Arguments:** `canonical` (string), `query_hash` (string)

---

### `finalize`
Log the final answer and trigger auto-cache. Always call this after composing an answer.

**Arguments:** `answer` (string), `canonical` (string), `query_hash` (string)
**Returns:** `{ "status": "ok", "answer": "..." }`

---

### `log_comment`
Save a user comment/correction to a conversation block. Call instead of `announce` when the user is commenting on a previous answer.

**Arguments:** `comment` (string), `block_index` (int, default `-1` = last block)

---

### `invoke_skill`
Call a single skill through the control plane.

**Arguments:** `skill_name` (string), `arguments` (dict)

---

### `invoke_skills`
Call multiple skills in one request.

**Arguments:** `skills` (list of `{ skill_name, arguments }`)

---

### `load_pages`
Load PDF pages for a topic + book through Ollama for key-point extraction.

**Arguments:** `topic` (string), `book_name` (string), `page_indexes` (list of `[from, to]` pairs)
**Returns:** `{ "combined": "...", "sections": [...] }`

---

### `load_pages_by_paths`
Load PDF pages from a list of `topic/bookname/page.pdf` paths. Use when `cache_lookup` returns `"hit": "document"`.

**Arguments:** `page_paths` (list of strings)

---

## `list_skills` — Category Reference

**Arguments:** `category` (string, required)

| Category | When to use | Skills |
|---|---|---|
| `data` | Querying Snowflake mart tables | `get_mart_tables`, `check_valid_column`, `snowflake_json_to_query` |
| `extraction` | Pulling external market / macro data | `finance_data_for_week`, `worldometer_gdp_by_country`, `worldometer_gdp_all_countries`, `country_iso_codes` |
| `model` | Training and running ML models | `gradient_boosting_*`, `lasso_*`, `svm_*`, `random_forest_*`, `pca_*`, `train_gradient_boosting` |
| `storing` | Writing documents into the knowledge graph | `baseknowledge.get_topics`, `select_file`, `split_pdf`, `get_page`, `save_summary`, `analysis_status`, `add_entities`, `add_relationship`, `build_graph`, `build_lookup_index` |
| `retrieve` | Querying the knowledge graph | `retrieve` |

---

## Self-Improvement Tools (KG Pipeline)

Require `python/kg_pipeline.py` running on port 8007. See `instruction/self_improvement/KG_PIPELINE_GUIDE.md`.

| Tool | Description |
|---|---|
| `kg_announce` | Start a review session |
| `kg_next` | Get next block + step (`review` or `extract`) |
| `kg_review` | Submit corrected answer for a block |
| `kg_extract` | Submit extracted entities / policies / relationships / notes |
| `kg_status` | Check pipeline progress |
| `kg_build` | Re-scan `success/` for new conversation files |

---

## Logs

| Outcome | Path |
|---|---|
| Succeeded | `logs/conversation/success/{key}.json` |
| Awaiting answer | `logs/conversation/awaiting/{key}.json` |
| Failed | `logs/conversation/fail/{key}.json` |
