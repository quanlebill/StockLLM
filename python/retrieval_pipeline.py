"""
retrieval_pipeline.py — Unified Retrieval Pipeline

Single module for all retrieval concerns:
  - Neo4j knowledge graph access (explore, search, kg_query, resolve_pages)
  - PDF page loading + Ollama key-point extraction (load_pages, load_pages_by_paths)
  - Query parsing, entity canonicalization, cache lookup, LightRAG orchestration

HTTP endpoints exposed via router (included by control_plane.py):
  POST /retrieve               — main retrieval entry point
  POST /load-pages             — load PDF pages via Ollama
  POST /load-pages-by-paths    — load cached page paths via Ollama
  GET  /health
"""

import asyncio
import hashlib
import json
import os
import re
from pathlib import Path
import uvicorn

import ollama
import PyPDF2
import requests as _requests
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase

from python.basestruct.base import LoadPagesRequest, LoadPagesByPathsRequest, RetrieveRequest
from python.basestruct.agent_prompt import OllamaPrompt
from python.basestruct.base_model import OLLAMA_MODEL

import entity_resolver
from cache_query import cache_lookup, embed
from self_improvement import fetch_context_by_ids, search_policy_qdrant_ids

_ROOT = os.environ["STOCKLLM_ROOT"]
load_dotenv(Path(_ROOT) / ".env")

router = APIRouter()


# Config
DOCS_BASE = os.path.join(_ROOT, "baseknowledge", "docs")
LOCAL_GRAPH_URL = "http://localhost:8005"

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def prewarm_ollama() -> None:
    try:
        ollama.generate(model=OLLAMA_MODEL, prompt="warm up", options={"num_predict": 1})
    except Exception:
        pass  # non-fatal — Ollama may not be running yet

# Neo4j utils
def _local_fallback(endpoint: str, params: dict):
    try:
        resp = _requests.get(f"{LOCAL_GRAPH_URL}/{endpoint}", params=params, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Neo4j unavailable and local graph fallback failed: {e}",
        )


def _name_variants(name: str) -> list[str]:
    variants = [name, name.replace(" ", "_"), name.replace("_", " ")]
    seen, result = set(), []
    for v in variants:
        if v not in seen:
            seen.add(v)
            result.append(v)
    return result


def _fmt(node) -> dict:
    return {
        "name": node["name"],
        "summary": node.get("summary", ""),
        "keywords": node.get("keywords", []),
        "page_index": json.loads(node["page_index"]) if node.get("page_index") else [],
        "included_entities": node.get("included_entities", []),
    }


# Knowledge graph functions (plain — no HTTP endpoints)
def explore(name: str) -> dict:
    try:
        record = None
        with driver.session() as session:
            for variant in _name_variants(name):
                result = session.run(
                    """
                    MATCH (e:Entity {name: $name})
                    OPTIONAL MATCH (e)-[:RELATED_TO]->(child:Entity)
                    RETURN e, collect(child) AS children
                    """,
                    name=variant,
                )
                record = result.single()
                if record and record["e"] is not None:
                    break

        if not record or record["e"] is None:
            raise HTTPException(status_code=404, detail=f"Entity '{name}' not found.")

        entity = _fmt(record["e"])
        children = [{"name": c["name"], "summary": c["summary"]} for c in record["children"] if c]
        return {"entity": entity, "children": children}
    except HTTPException:
        raise
    except Exception:
        return _local_fallback("explore", {"name": name})


def search(keyword: str, limit: int = 10) -> dict:
    kw = keyword.lower()
    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (e:Entity)
                WHERE toLower(e.name) CONTAINS $kw
                   OR toLower(e.summary) CONTAINS $kw
                   OR any(k IN e.keywords WHERE toLower(k) CONTAINS $kw)
                RETURN e
                LIMIT $limit
                """,
                kw=kw,
                limit=limit,
            )
            records = result.data()

        if not records:
            return {"keyword": keyword, "results": [], "count": 0}

        results = [
            {
                "name": r["e"]["name"],
                "summary": r["e"].get("summary", ""),
                "page_index": json.loads(r["e"]["page_index"]) if r["e"].get("page_index") else [],
                "keywords": r["e"].get("keywords", []),
            }
            for r in records
        ]
        return {"keyword": keyword, "count": len(results), "results": results}
    except Exception:
        return _local_fallback("search", {"keyword": keyword, "limit": limit})


def kg_query_graph(entities: str, relationship: str = "", direction: str = "") -> dict:
    """Query entity descriptions, AFFECTS relationships, and entity qdrant_ids."""
    entity_list = [e.strip() for e in entities.split(",") if e.strip()]
    if not entity_list:
        return {"matched": 0, "entities": [], "relationships": []}

    rel_filter = relationship.lower().strip()
    dir_filter = direction.lower().strip()

    try:
        with driver.session() as session:
            resolved_names: list[str] = []
            found_entities: list[dict] = []

            for raw in entity_list:
                for variant in _name_variants(raw):
                    row = session.run(
                        """
                        MATCH (e:Entity {name: $name})
                        WHERE e.description IS NOT NULL
                        RETURN e.name AS name, e.aliases AS aliases,
                        e.category AS category, e.description AS description,
                        e.qdrant_ids AS qdrant_ids
                        LIMIT 1
                        """,
                        name=variant,
                    ).single()
                    if row:
                        resolved_names.append(row["name"])
                        found_entities.append(dict(row))
                        break

            if not resolved_names:
                return {"matched": 0, "entities": [], "relationships": []}

            rel_cypher = """
                MATCH (a:Entity)-[r:AFFECTS]->(b:Entity)
                WHERE a.name IN $names AND b.name IN $names
            """

            rel_params: dict = {"names": resolved_names}

            if dir_filter:
                rel_cypher += "\nAND toLower(r.direction) = $direction"
                rel_params["direction"] = dir_filter
            if rel_filter:
                rel_cypher += "\nAND toLower(r.description) CONTAINS $rel_text"
                rel_params["rel_text"] = rel_filter

            rel_cypher += """
                RETURN a.name AS from_entity,
                b.name AS to_entity,
                r.direction AS direction,
                r.strength AS strength,
                r.description AS description
            """
            rel_records = session.run(rel_cypher, **rel_params).data()

        return {
            "matched": len(found_entities),
            "entities": found_entities,
            "relationships": rel_records,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def kg_query_policy(qdrant_ids: list[str]) -> list[dict]:
    """Look up policies by Qdrant point IDs and return with CAUSED_BY / AFFECTS edges."""
    if not qdrant_ids:
        return []
    try:
        with driver.session() as session:
            records = session.run(
                """
                MATCH (p:Policy)
                WHERE p.qdrant_id IN $ids
                OPTIONAL MATCH (p)-[:CAUSED_BY]->(cause:Entity)
                OPTIONAL MATCH (p)-[:AFFECTS]->(aff:Entity)
                RETURN p.description  AS description,
                       p.entities     AS entities,
                       p.expires_at   AS expires_at,
                       p.qdrant_id    AS qdrant_id,
                       collect(DISTINCT cause.name) AS caused_by,
                       collect(DISTINCT aff.name)   AS affects
                """,
                ids=qdrant_ids,
            ).data()
        return records
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def resolve_pages(entities: str) -> dict:
    entity_list = [e.strip() for e in entities.split(",") if e.strip()]
    if not entity_list:
        raise HTTPException(status_code=400, detail="At least one entity name is required.")

    book_topic_map: dict[str, str] = {}
    if os.path.isdir(DOCS_BASE):
        for topic in os.listdir(DOCS_BASE):
            topic_dir = os.path.join(DOCS_BASE, topic)
            if os.path.isdir(topic_dir):
                for book_name in os.listdir(topic_dir):
                    if os.path.isdir(os.path.join(topic_dir, book_name)):
                        book_topic_map[book_name] = topic
                        book_topic_map[book_name.replace(" ", "_")] = topic

    result: dict = {}

    try:
        with driver.session() as session:
            for raw_name in entity_list:
                resolved = None
                for variant in _name_variants(raw_name):
                    row = session.run(
                        """
                        MATCH (e:Entity {name: $name})
                        WHERE e.page_index IS NOT NULL
                        OPTIONAL MATCH path = (root:Entity)-[:related_to*0..10]->(e)
                        WHERE NOT ()-[:related_to]->(root)
                        WITH e, root, length(path) AS depth
                        ORDER BY depth DESC
                        LIMIT 1
                        RETURN e.name AS name,
                        e.page_index AS page_index,
                        root.name AS root_name
                        """,
                        name=variant,
                    ).single()
                    if row and row["name"] is not None:
                        resolved = row
                        break

                if not resolved:
                    continue

                page_index = json.loads(resolved["page_index"]) if resolved.get("page_index") else []
                root_name = resolved.get("root_name") or ""
                topic = book_topic_map.get(root_name, "") or book_topic_map.get(
                    root_name.replace("_", " "), ""
                )

                page_paths: list[str] = []
                if topic and root_name and page_index:
                    for rng in page_index:
                        if isinstance(rng, (list, tuple)) and len(rng) == 2:
                            for page_num in range(int(rng[0]), int(rng[1]) + 1):
                                page_paths.append(f"{topic}/{root_name}/{page_num}.pdf")

                result[raw_name] = {
                    "root_name": root_name,
                    "topic": topic,
                    "page_index": page_index,
                    "page_paths": page_paths,
                }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"results": result}



# PDF Utils
def _extract_text(pdf_path: str) -> str:
    try:
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            return reader.pages[0].extract_text() or ""
    except Exception:
        return ""


def _keypoints(pages_text: str, topic: str, page_range: str) -> str:
    if not pages_text.strip():
        return "(no text extracted)"
    prompt = OllamaPrompt.get__retrieval_pipeline__keypoint_prompt(page_range, topic, pages_text)

    try:
        resp = ollama.generate(model=OLLAMA_MODEL, prompt=prompt)
        return resp["response"].strip()
    except Exception as e:
        return f"(Ollama failed: {e})"



# HTTP endpoints — PDF page loading
@router.post("/load-pages")
def load_pages(request: LoadPagesRequest) -> dict:
    book_dir = os.path.join(DOCS_BASE, request.topic, request.book_name)
    if not os.path.isdir(book_dir):
        raise HTTPException(status_code=404, detail=f"Book directory not found: {book_dir}")

    sections = []
    for rng in request.page_indexes:
        if len(rng) != 2:
            raise HTTPException(status_code=400, detail=f"Each range must be [from, to], got: {rng}")

        page_from, page_to = rng
        combined_text = ""
        missing = []

        for page_num in range(page_from, page_to + 1):
            pdf_path = os.path.join(book_dir, f"{page_num}.pdf")
            if not os.path.exists(pdf_path):
                missing.append(page_num)
                continue
            combined_text += f"\n--- Page {page_num} ---\n" + _extract_text(pdf_path)

        range_label = f"{page_from}-{page_to}" if page_from != page_to else str(page_from)
        key_points = _keypoints(combined_text, request.book_name, range_label)

        section: dict = {"range": range_label, "key_points": key_points}
        if missing:
            section["missing_pages"] = missing
        sections.append(section)

    combined = "\n\n".join(f"[Pages {s['range']}]\n{s['key_points']}" for s in sections)
    return {"topic": request.topic, "book_name": request.book_name, "sections": sections, "combined": combined}


@router.post("/load-pages-by-paths")
def load_pages_by_paths(request: LoadPagesByPathsRequest) -> dict:
    if not request.page_paths:
        raise HTTPException(status_code=400, detail="page_paths cannot be empty.")

    groups: dict[tuple[str, str], list[int]] = {}
    for path in request.page_paths:
        parts = path.split("/", 2)
        if len(parts) != 3:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid path format (expected topic/bookname/page.pdf): {path}",
            )
        topic, book_name, filename = parts
        try:
            page_num = int(filename.replace(".pdf", ""))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Cannot parse page number from: {filename}")
        groups.setdefault((topic, book_name), []).append(page_num)

    sections = []
    for (topic, book_name), page_nums in groups.items():
        book_dir = os.path.join(DOCS_BASE, topic, book_name)
        if not os.path.isdir(book_dir):
            raise HTTPException(status_code=404, detail=f"Book directory not found: {book_dir}")

        page_nums_sorted = sorted(set(page_nums))
        combined_text = ""
        missing = []

        for page_num in page_nums_sorted:
            pdf_path = os.path.join(book_dir, f"{page_num}.pdf")
            if not os.path.exists(pdf_path):
                missing.append(page_num)
                continue
            combined_text += f"\n--- Page {page_num} ---\n" + _extract_text(pdf_path)

        range_label = (
            f"{page_nums_sorted[0]}-{page_nums_sorted[-1]}"
            if len(page_nums_sorted) > 1
            else str(page_nums_sorted[0])
        )
        key_points = _keypoints(combined_text, book_name, range_label)

        section: dict = {"range": range_label, "book_name": book_name, "key_points": key_points}
        if missing:
            section["missing_pages"] = missing
        sections.append(section)

    combined = "\n\n".join(f"[{s['book_name']} — Pages {s['range']}]\n{s['key_points']}" for s in sections)
    return {"sections": sections, "combined": combined}


# Query string parsing


VALID_QUESTION_TYPES = {"what", "how", "when", "where", "who"}
VALID_DIRECTIONS = {"left", "right", "both", ""}

_FORMAT_HINT = """
    Expected format:
    - Question: Question|<QuestionWord>|<Entity1>, <Entity2>|<relationship>
    - Statement: Statement|<Entity1>, <Entity2>|<relationship>
    Examples:
    - Question|How|GDP, Inflation|affect
    - Statement|GDP, Sector|indicate
"""


class ParseError(ValueError):
    pass


def _parse_query_string(raw: str) -> dict:
    parts = [p.strip() for p in raw.split("|")]

    if not parts or parts[0] not in ("question", "statement"):
        raise ParseError(
            f"First segment must be 'Question' or 'Statement', got: '{parts[0] if parts else ''}'. "
            f"\n{_FORMAT_HINT}"
        )

    query_type = parts[0]

    if query_type == "question":
        if len(parts) < 4:
            raise ParseError(
                f"Question queries require 4 pipe-separated segments, got {len(parts)}. \n{_FORMAT_HINT}"
            )
        question_type = parts[1]
        if question_type not in VALID_QUESTION_TYPES:
            raise ParseError(
                f"Question word must be one of {sorted(VALID_QUESTION_TYPES)}, got: '{question_type}'. \n{_FORMAT_HINT}"
            )
        entities_str = parts[2]
        rel_str = parts[3]
    else:
        if len(parts) < 3:
            raise ParseError(
                f"Statement queries require 3 pipe-separated segments, got {len(parts)}. \n{_FORMAT_HINT}"
            )
        question_type = ""
        entities_str = parts[1]
        rel_str = parts[2]

    entities_raw = [e.strip() for e in entities_str.split(",") if e.strip()]
    if not entities_raw:
        raise ParseError(f"Entities segment is empty or invalid: '{entities_str}'. \n{_FORMAT_HINT}")

    rel_parts = rel_str.split("/")
    relationship = rel_parts[0].strip()
    direction = rel_parts[1].strip() if len(rel_parts) > 1 else ""

    if not relationship:
        raise ParseError(f"Relationship segment is empty: '{rel_str}'. \n{_FORMAT_HINT}")

    return {
        "type": query_type,
        "question_type": question_type,
        "entities_raw": entities_raw,
        "relationship": relationship,
        "direction": direction,
    }

# Entity canonicalization
def _canonicalize_entities(entities_raw: list[str]) -> tuple[list[str], dict[str, str]]:
    mapping: dict[str, str] = {}
    canonical_keys: list[str] = []
    for raw in entities_raw:
        key = entity_resolver.resolve(raw)
        mapping[raw] = key
        if key not in canonical_keys:
            canonical_keys.append(key)
    return canonical_keys, mapping


# Canonical string + hash
def _build_canonical(
        query_type: str,
        question_type: str,
        entities: list[str],
        relationship: str,
) -> tuple[str, str]:
    qt = query_type.strip()
    if qt == "question" and question_type:
        qtype = question_type.strip()
        if qtype in {"what", "who", "when", "where", "how"}:
            qt = f"question:{qtype}"

    sorted_ents = sorted(e.strip() for e in entities)
    rel = re.sub(r"\s+", " ", relationship.strip())
    canonical = f"{qt} | {', '.join(sorted_ents)} | {rel}"
    query_hash = hashlib.sha256(canonical.encode()).hexdigest()[:16]
    return canonical, query_hash



# LightRAG pipeline
async def _lightrag_query(entities: list[str], relationship: str, direction: str) -> dict:
    graph_result: dict = {}
    policy_result: list = []
    doc_results: list = []
    neighbors: list = []
    keypoints: str = ""
    qdrant_hits: list = []

    # Stage 0: Embed query — needed for both policy vector search and Qdrant context ranking
    query_text = f"{' '.join(entities)} {relationship}".strip()
    query_vec = await asyncio.to_thread(embed, query_text)

    # Stage 1: Concurrent — graph query + policy Qdrant search + doc search
    graph_task = asyncio.to_thread(
        kg_query_graph,
        entities=", ".join(entities),
        relationship=relationship,
        direction=direction,
    )
    policy_vec_task = asyncio.to_thread(search_policy_qdrant_ids, query_vec, 5)
    search_tasks = [
        asyncio.to_thread(search, keyword=ent.replace("_", " "), limit=5)
        for ent in entities[:3]
    ]

    stage1 = await asyncio.gather(graph_task, policy_vec_task, *search_tasks, return_exceptions=True)
    graph_result = stage1[0] if not isinstance(stage1[0], Exception) else {}
    policy_vec_ids = stage1[1] if not isinstance(stage1[1], Exception) else []
    search_responses = stage1[2:]

    # Hydrate policy nodes from Neo4j using Qdrant IDs → recovers CAUSED_BY / AFFECTS edges
    if policy_vec_ids:
        try:
            policy_result = await asyncio.to_thread(kg_query_policy, policy_vec_ids)
        except Exception as e:
            print(f"[retrieval_pipeline] policy hydration failed: {e}")

    # Stage 2: Collect qdrant_ids from entities + policies → ID-filtered Qdrant search
    entity_qdrant_ids = []
    for ent in graph_result.get("entities", []):
        entity_qdrant_ids.extend(ent.get("qdrant_ids") or [])

    policy_qdrant_ids = [p["qdrant_id"] for p in policy_result if p.get("qdrant_id")]
    all_qdrant_ids = list(set(entity_qdrant_ids + policy_qdrant_ids))

    if all_qdrant_ids:
        try:
            qdrant_hits = await asyncio.to_thread(fetch_context_by_ids, all_qdrant_ids, query_vec, 5)
        except Exception as e:
            print(f"[retrieval_pipeline] qdrant fetch failed: {e}")

    # Stage 3: Doc graph search results
    seen_names: set[str] = set()
    for r in search_responses:
        if isinstance(r, Exception):
            continue
        for item in r.get("results", []):
            name = item.get("name", "")
            if name and name not in seen_names:
                doc_results.append(item)
                seen_names.add(name)
    doc_results = doc_results[:5]

    # Stage 4: Explore top-2 doc results for neighbors
    explore_tasks = [asyncio.to_thread(explore, name=item["name"]) for item in doc_results[:2]]
    explore_responses = await asyncio.gather(*explore_tasks, return_exceptions=True)

    neighbor_names: set[str] = set()
    for r in explore_responses:
        if isinstance(r, Exception):
            continue
        for child in r.get("children", [])[:5]:
            cname = child.get("name", "")
            if cname and cname not in neighbor_names:
                neighbors.append(child)
                neighbor_names.add(cname)

    # Stage 5: Resolve page paths + load via Ollama
    entities_with_pages = [item for item in doc_results if item.get("page_index")]
    if entities_with_pages:
        try:
            names_str = ", ".join(item["name"] for item in entities_with_pages)
            page_data = await asyncio.to_thread(resolve_pages, entities=names_str)
            page_paths = []
            for _, info in page_data.get("results", {}).items():
                page_paths.extend(info.get("page_paths", []))
            if page_paths:
                load_result = await asyncio.to_thread(
                    load_pages_by_paths, LoadPagesByPathsRequest(page_paths=page_paths[:10])
                )
                keypoints = load_result.get("combined", "")
        except Exception as e:
            print(f"[retrieval_pipeline] load_pages_by_paths failed: {e}")

    # Compose summary
    parts: list[str] = []

    for ent in graph_result.get("entities", []):
        if ent.get("description"):
            parts.append(f"[Entity: {ent['name']}] {ent['description']}")

    for rel in graph_result.get("relationships", []):
        parts.append(
            f"[Relationship] {rel.get('from_entity')} → {rel.get('to_entity')}: "
            f"{rel.get('description', '')} "
            f"(direction={rel.get('direction', '')}, strength={rel.get('strength', '')})"
        )

    for pol in policy_result:
        if pol.get("description"):
            pol_text = f"[Policy] {pol['description']}"
            matched_caused_by = [e for e in (pol.get("caused_by") or []) if e in entities]
            matched_affects   = [e for e in (pol.get("affects")   or []) if e in entities]
            if matched_caused_by:
                pol_text += f" | Caused by: {', '.join(matched_caused_by)}"
            if matched_affects:
                pol_text += f" | Affects: {', '.join(matched_affects)}"
            parts.append(pol_text)

    for hit in qdrant_hits:
        if hit.get("content"):
            parts.append(f"[Context (score={hit['score']})] {hit['content']}")

    for item in doc_results:
        if item.get("summary"):
            parts.append(f"[Document: {item['name']}] {item['summary']}")

    for child in neighbors:
        if child.get("summary"):
            parts.append(f"[Neighbor: {child['name']}] {child['summary']}")

    if keypoints:
        parts.append(f"[Page Keypoints]\n{keypoints}")

    return {
        "graph_result": graph_result,
        "policy_result": policy_result,
        "qdrant_hits": qdrant_hits,
        "doc_results": doc_results,
        "neighbors": neighbors,
        "keypoints": keypoints,
        "summary": "\n".join(parts),
    }


# Per-query processor
async def _process_single_query(raw_query: str, idx: int) -> dict:
    lowercased = raw_query.lower()

    try:
        parsed = _parse_query_string(lowercased)
    except ParseError as e:
        return {
            "query_index": idx,
            "raw_query": raw_query,
            "error": "format_error",
            "message": str(e),
            "combined": "",
        }

    canonical_entities, entity_map = _canonicalize_entities(parsed["entities_raw"])

    canonical, query_hash = _build_canonical(
        parsed["type"],
        parsed["question_type"],
        canonical_entities,
        parsed["relationship"],
    )

    cache_task = asyncio.to_thread(cache_lookup, canonical, query_hash)
    lightrag_task = _lightrag_query(canonical_entities, parsed["relationship"], parsed["direction"])

    cache_result, retrieval_result = await asyncio.gather(
        cache_task, lightrag_task, return_exceptions=True
    )

    if isinstance(cache_result, Exception):
        cache_result = {"hit": "miss", "error": str(cache_result)}
    if isinstance(retrieval_result, Exception):
        retrieval_result = {"kg_results": {}, "doc_results": [], "neighbors": [], "keypoints": "", "summary": ""}

    combined_parts: list[str] = []
    if cache_result.get("hit") == "answer":
        combined_parts.append(f"[CACHE HIT — answer ready]\n{cache_result.get('answer', '')}")
    if retrieval_result.get("summary"):
        combined_parts.append(f"[RETRIEVAL]\n{retrieval_result['summary']}")

    return {
        "query_index": idx,
        "raw_query": raw_query,
        "parsed": {
            "type": parsed["type"],
            "question_type": parsed["question_type"],
            "entities_raw": parsed["entities_raw"],
            "entities": canonical_entities,
            "entity_map": entity_map,
            "relationship": parsed["relationship"],
            "direction": parsed["direction"],
        },
        "canonical": canonical,
        "hash": query_hash,
        "cache": cache_result,
        "retrieval": retrieval_result,
        "combined": "\n\n".join(combined_parts),
    }


# Parsing LLM answer from dict to structure string
_DICT_FORMAT_HINT = """
    Expected dict format:
      {
        "Query #1": { "Type": "Question", "Question Word": "How",
                       "Entities": ["GDP", "Inflation"], "Relationship": ["affect"]
                    },
        "Query #2": { "Type": "Statement",
                       "Entities": ["GDP", "Sector"],   "Relationship": ["indicate"] 
                    }
      }
"""


def _dict_to_pipe_strings(queries_dict: dict) -> list[str]:
    pipe_strings: list[str] = []

    for label, q in queries_dict.items():
        if not isinstance(q, dict):
            raise ParseError(f"Query '{label}' must be a dict. \n{_DICT_FORMAT_HINT}")

        qtype = str(q.get("Type", "")).strip()
        if not qtype:
            raise ParseError(f"Query '{label}' is missing 'Type'. \n{_DICT_FORMAT_HINT}")

        entities: list = q.get("Entities", [])
        if not entities:
            raise ParseError(f"Query '{label}' is missing 'Entities'. \n{_DICT_FORMAT_HINT}")
        entities_str = ", ".join(str(e) for e in entities)

        relationships: list = q.get("Relationship", [])
        if not relationships:
            raise ParseError(f"Query '{label}' is missing 'Relationship'. \n{_DICT_FORMAT_HINT}")

        for rel in relationships:
            if qtype.lower() == "question":
                qword = str(q.get("Question Word", "")).strip()
                if not qword:
                    raise ParseError(
                        f"Query '{label}' is type Question but missing 'Question Word'. \n{_DICT_FORMAT_HINT}"
                    )
                pipe_strings.append(f"{qtype}|{qword}|{entities_str}|{rel}")
            else:
                pipe_strings.append(f"{qtype}|{entities_str}|{rel}")

    return pipe_strings


# HTTP endpoints — retrieval
@router.post("/retrieve")
async def retrieve(request: RetrieveRequest) -> dict:
    try:
        pipe_strings = _dict_to_pipe_strings(request.queries)
    except ParseError as e:
        return {"results": [{"query_index": 0, "error": "format_error", "message": str(e), "combined": ""}]}

    tasks = [_process_single_query(q, i) for i, q in enumerate(pipe_strings)]
    results = await asyncio.gather(*tasks)
    return {"results": list(results)}


@router.get("/health")
def health():
    try:
        with driver.session() as session:
            session.run("RETURN 1")
        return {"status": "ok", "neo4j": "connected"}
    except Exception as e:
        return {"status": "degraded", "neo4j": str(e)}


if __name__ == "__main__":

    prewarm_ollama()
    _app = FastAPI(title="Retrieval Pipeline", version="2.0.0")
    _app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    _app.include_router(router)
    uvicorn.run(_app, host="0.0.0.0", port=8000, reload=False)
