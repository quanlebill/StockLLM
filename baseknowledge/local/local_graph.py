"""
local_graph.py — Local fallback graph API loaded from knowledge_graph.json.
Mirrors the retrieve.py API (explore, traverse, details, search).
Runs on port 8005.

The graph is loaded once at server startup into memory.
"""

import os
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query

LOCAL_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_graph.json")

# In-memory graph state populated at startup
_entities: dict = {}
_children_map: dict = {}


def _build_children_map(relationships: list) -> dict:
    children: dict[str, list[str]] = {}
    for from_e, _rel, to_e in relationships:
        children.setdefault(from_e, []).append(to_e)
    return children


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _entities, _children_map
    if os.path.exists(LOCAL_JSON):
        with open(LOCAL_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        _entities = data.get("entities", {})
        _children_map = _build_children_map(data.get("relationships", []))
        print(f"[local_graph] Loaded {len(_entities)} entities, {sum(len(v) for v in _children_map.values())} relationships.")
    else:
        print("[local_graph] knowledge_graph.json not found — starting with empty graph.")
    yield


app = FastAPI(lifespan=lifespan)


def _fmt(name: str, props: dict) -> dict:
    return {
        "name": name,
        "summary": props.get("summary", ""),
        "keywords": props.get("keywords", []),
        "page_index": props.get("page_index", []),
        "included_entities": props.get("included_entities", []),
    }


@app.get("/explore")
def explore(name: str = Query(..., description="Entity name to explore")):
    if name not in _entities:
        raise HTTPException(status_code=404, detail=f"Entity '{name}' not found.")
    children = [
        {"name": c, "summary": _entities.get(c, {}).get("summary", "")}
        for c in _children_map.get(name, [])
    ]
    return {
        "entity": _fmt(name, _entities[name]),
        "children": children,
        "hint": "Pass one of the children names back to /explore or build a /traverse path.",
    }


@app.get("/traverse")
def traverse(path: str = Query(..., description="Slash-separated entity path")):
    steps = [s.strip() for s in path.split("/") if s.strip()]
    if not steps:
        raise HTTPException(status_code=400, detail="Path cannot be empty.")

    for i in range(len(steps) - 1):
        if steps[i + 1] not in _children_map.get(steps[i], []):
            raise HTTPException(
                status_code=400,
                detail=f"No connection between '{steps[i]}' and '{steps[i + 1]}'.",
            )

    target = steps[-1]
    if target not in _entities:
        raise HTTPException(status_code=404, detail=f"Entity '{target}' not found.")

    children = [
        {"name": c, "summary": _entities.get(c, {}).get("summary", "")}
        for c in _children_map.get(target, [])
    ]
    return {
        "path": steps,
        "current": _fmt(target, _entities[target]),
        "children": children,
    }


@app.get("/details")
def details(path: str = Query(..., description="Slash-separated path to the target entity")):
    steps = [s.strip() for s in path.split("/") if s.strip()]
    if not steps:
        raise HTTPException(status_code=400, detail="Path cannot be empty.")
    target = steps[-1]
    if target not in _entities:
        raise HTTPException(status_code=404, detail=f"Entity '{target}' not found.")
    props = _entities[target]
    return {
        "path": steps,
        "name": target,
        "summary": props.get("summary", ""),
        "page_index": props.get("page_index", []),
        "keywords": props.get("keywords", []),
        "included_entities": props.get("included_entities", []),
    }


@app.get("/search")
def search(
    keyword: str = Query(..., description="Keyword to search across entity names, summaries, and keywords"),
    limit: int = Query(10, description="Max number of results"),
):
    kw = keyword.lower()
    results = []
    for name, props in _entities.items():
        if (
            kw in name.lower()
            or kw in props.get("summary", "").lower()
            or any(kw in k.lower() for k in props.get("keywords", []))
        ):
            results.append({
                "name": name,
                "summary": props.get("summary", ""),
                "page_index": props.get("page_index", []),
                "keywords": props.get("keywords", []),
            })
        if len(results) >= limit:
            break
    return {"keyword": keyword, "count": len(results), "results": results}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "entities_loaded": len(_entities),
        "json_path": LOCAL_JSON,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
