# Self-Improvement: Knowledge Graph Pipeline Guide

## Overview

This pipeline extracts structured financial knowledge from reviewed conversations
and builds a Neo4j knowledge graph. It runs on **port 8000** (via `control_plane.py`).

**Folder layout:**
```
logs/conversation/
  success/           ← control_plane writes new conversations here (never touch this)
  chunked/           ← KG pipeline moves files here when loading into the buffer
  chunked/reviewed/  ← fully extracted conversations land here
```

**Queue-based processing:** Up to 4 conversation files (BUFFER_SIZE) are active in memory
at once. When the pipeline picks up a file it moves it from `success/` → `chunked/`. When
all blocks in a file are done, it moves to `chunked/reviewed/` and the next queued file
is loaded automatically. This cleanly separates new incoming conversations from in-progress
and completed ones — no duplicates, no re-processing.

Ollama3 automatically preprocesses each block (fixing the answer using any comment, and
extracting key facts) before you see it. Your job is only to call `kg.extract`.

---

## Workflow — Follow This Order Every Session

```
1. kg.announce          → start the session, get stats
2. loop until block = null:
     a. kg.next         → Ollama3 auto-preprocesses the block and returns:
                            block         : original Q&A + comment
                            preprocess_result:
                              fixed_answer : answer corrected using comment (if any)
                              key_info     : bullet-point extraction of key facts/numbers
     b. step = "extract":
           read fixed_answer + key_info from preprocess_result
           extract entities, policies, relationships, notes
           kg.extract    → submit extraction (canonicalization is automatic)
3. done when kg.next returns block = null
```

---

## Step-by-Step

### Step 1 — Announce
Call `kg.announce` to start the session.  
Returns: total blocks, pending, preprocessed, done count.

---

### Step 2a — Get Next Block
Call `kg.next` → returns `{ block, step, preprocess_result }`.

**Block fields:**
| Field | Description |
|---|---|
| `id` | Block ID — pass to kg.extract |
| `user` | Original user question |
| `answer` | Original stored answer |
| `comment` | Any correction left by the user |
| `canonical` | Normalized query form (if preprocess_query was called) |

**preprocess_result fields:**
| Field | Description |
|---|---|
| `fixed_answer` | Answer corrected by Ollama3 using the comment (use this, not `answer`) |
| `key_info` | Bullet-point list of key facts, numbers, and relationships extracted by Ollama3. Each entity/condition is labeled `[CAUSE]` (triggers the policy) or `[AFFECTS]` (changed as a result) |

**key_info label meanings:**
| Label | Meaning | Maps to |
|---|---|---|
| `[CAUSE]` | Entity whose state triggers the policy condition (e.g. "GDP < -1.2%") | `cause_entities` in `kg.extract` |
| `[AFFECTS]` | Entity changed or impacted as a result (e.g. "Fed Fund Rate cut 0.5%") | `affect_entities` in `kg.extract` |

If `block = null` → all done, stop.

---

### Step 2b — Extract Step (`step = "extract"`)

Read `user`, `preprocess_result.fixed_answer`, and `preprocess_result.key_info`.  
Use these as the source of truth. Call `kg.extract` with:

#### Entities
Financial concepts, indicators, instruments, institutions.
```
name        : raw name as it appears (canonicalization is automatic)
aliases     : other names for the same entity
category    : "macro" | "rate" | "market" | "sector" | "institution" | "instrument"
description : brief description (optional)
```

#### Policies (quantified/conditional rules)
Use when `key_info` contains **specific magnitudes or conditions**.

Two separate entity lists are required — do not mix them:
```
description     : "cause: [gdp < -1.2%], policy: [fed cuts rate by 0.5%]"
cause_entities  : raw names of entities whose state TRIGGERS the policy (labeled [CAUSE] in key_info)
affect_entities : raw names of entities CHANGED/IMPACTED as a result (labeled [AFFECTS] in key_info)
expires_at      : ISO date string or null if permanent
```

Neo4j edges created:
- `(Policy)-[:CAUSED_BY]->(Entity)` for each entity in `cause_entities`
- `(Policy)-[:AFFECTS]->(Entity)` for each entity in `affect_entities`

#### Relationships (directional, no specific magnitude)
Use when knowledge is general: **"X affects Y"**.
```
from_entity : raw entity name
to_entity   : raw entity name
direction   : "positive" | "negative" | "neutral"
strength    : "weak" | "moderate" | "strong"
description : brief explanation
```

#### Notes (long explanations)
Use the `fixed_answer` text as note content when it is detailed and worth preserving.
```
content : the full explanation text (use fixed_answer)
entity  : raw entity name to attach this context to
```
Notes are embedded in Qdrant for semantic search and linked to entities in Neo4j via `qdrant_ids`.

#### Skipping
If the block has **no financial knowledge to extract** (e.g. a coding question,
a meta question, a failed answer), set `skipped = true` and pass empty lists.
The block will be marked done without writing to the graph.

---

## Canonicalization — Automatic

You do **not** need to normalize entity names before submitting.  
Pass raw names as they appear in the text:
- `"Fed Fund"`, `"federal funds rate"`, `"FFR"` → all resolve to `"federal_funds_rate"`
- `"GDP"`, `"gross domestic product"` → resolve to `"gross_domestic_product"`

The pipeline runs three-stage resolution:
1. Exact alias lookup (instant)
2. Cosine similarity + word overlap bonus (in-memory)
3. Creates new entity if no match found

---

## Decision Guide — Policy vs Relationship

| Signal | Use |
|---|---|
| Numbers/magnitudes present | Policy |
| Specific condition stated | Policy |
| Time-bound or temporary rule | Policy (expires_at set) |
| Just "X affects Y" | Relationship |
| Directional but no magnitude | Relationship |
| Long detailed explanation | Note |

---

## MCP Tools Reference

| Tool | When to call |
|---|---|
| `kg.announce` | Once at session start — shows pending/preprocessed/done + queue_remaining |
| `kg.next` | After each extract to get next block (Ollama3 runs automatically) |
| `kg.extract` | Submit extracted knowledge; triggers file move + buffer refill automatically |
| `kg.status` | Check progress at any time |
| `kg.build` | Sync queue with new success files added mid-session |

---

## Example — Full Block Processing

**kg.next returns:**
```
block:
  user:    "how does gdp affect fed fund"
  answer:  "When GDP falls, the Fed typically cuts the federal funds rate to
            stimulate growth. Conversely when GDP grows strongly, the Fed may
            raise rates to prevent inflation."
  comment: "add that historically a 1% GDP drop leads to roughly a 0.5% rate cut"

preprocess_result:
  fixed_answer: "When GDP falls, the Fed typically cuts the federal funds rate to
                 stimulate growth. Historically, a 1% GDP drop leads to roughly a
                 0.5% rate cut. Conversely, strong GDP growth prompts rate increases
                 to prevent inflation."
  key_info: "• [CAUSE]   GDP < -1% (GDP decline triggers the policy)
             • [AFFECTS] Federal funds rate → cut ~0.5% per 1% GDP drop
             • [CAUSE]   Strong GDP growth
             • [AFFECTS] Federal funds rate → raised to curb inflation"
```

**Extract:**
```
entities:
  - name: "GDP",                category: "macro"
  - name: "federal funds rate", category: "rate", aliases: ["fed fund", "FFR"]

policies:
  - description: "cause: [gdp < -1%], policy: [fed cuts rate ~0.5% per 1% GDP drop]"
    cause_entities:  ["GDP"]
    affect_entities: ["federal funds rate"]
    expires_at: null

relationships:
  - from_entity: "GDP", to_entity: "federal funds rate"
    direction: "negative", strength: "strong"
    description: "GDP decline leads to rate cuts; GDP growth leads to rate increases"

notes:
  - content: <fixed_answer text>, entity: "federal funds rate"
```

**Resulting Neo4j edges:**
```
(Policy)-[:CAUSED_BY]->(gdp)
(Policy)-[:AFFECTS]->(federal_funds_rate)
```
