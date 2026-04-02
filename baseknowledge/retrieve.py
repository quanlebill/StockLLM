import os
import re
import json
import glob
import numpy as np
from typing import TypedDict, Any
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer, CrossEncoder
from langchain_ollama import ChatOllama
from neo4j import GraphDatabase
from langgraph.graph import StateGraph, END
import logging, logging.config

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = False
file_handler = logging.FileHandler("logs/retrieval.log" , encoding="utf-8")
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
load_dotenv()

QDRANT_COLLECTION = "pdf_rag_chunks"

INITIAL_K = 5
MAX_DEPTH = 2
TOP_K_NEIGHBORS = 5
RERANK_TOP_N = 30
CROSS_ENCODER_TOP_N = 5
LOOKUP_TOP_K = 10

#Reranking weights
W_SEMANTIC = 0.4
W_GRAPH = 0.3
W_ENTITY_IOU = 0.3

encoder = SentenceTransformer("all-mpnet-base-v2")
cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

class RAGState(TypedDict):
    query: str
    enriched_query: str          # LLM-expanded version of the query
    lookup_chunk_ids: list[int]  # chunk_ids from LookUpIndex search
    initial_chunks: list[dict]
    query_entities: list[str]
    starting_nodes: list[str]
    paths: list[dict]
    ranked_paths: list[dict]
    top_paths: list[dict]
    context: str
    graph_context: str
    answer: str


def cosine_sim(a: list[float], b: list[float]) -> float:
    a = np.array(a)
    b = np.array(b)
    denominator = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / (denominator + 0.0005))


def extract_entities_from_text(text: str, llm: ChatOllama) -> list[str]:
    prompt = f"""Extract the key named entities from the text below.
        Text: {text}
        Respond ONLY with a comma-separated list of entity names, nothing else."""
    response = llm.invoke(prompt)
    entity_list = [e.strip().strip("\"'").lower() for e in response.content.split(",") if e.strip()]

    return entity_list


def _render_path(path: list[str], edges: list[dict]) -> str:
    """Render a graph path as a human-readable relationship chain.
    e.g. Apple Inc --[reports (0.90)]--> Earnings Per Share --[signals (0.80)]--> Bull Market
    """
    parts = [path[0]]
    for i, edge in enumerate(edges):
        rel = edge.get("type") or "related_to"
        weight = edge.get("weight", 0.0)
        parts.append(f"--[{rel} ({weight:.2f})]-->")
        parts.append(path[i + 1])
    return " ".join(parts)


def entity_iou(path_entities: set[str], query_entities: set[str]) -> float:
    #Entity matching
    if not query_entities:
        return 0.0
    intersection = len(path_entities & query_entities)
    union = len(path_entities | query_entities)
    return intersection / union if union > 0 else 0.0


def enrich_query_node(state: RAGState, llm: ChatOllama) -> RAGState:
    """LLM enriches the raw user query with more detail and financial context."""
    prompt = f"""You are a financial research assistant. Expand the user query below into a
more detailed and specific version that will improve document retrieval.
Include related financial concepts, possible entity types, and relevant context.
Keep the enriched query under 150 words.

Original query: {state["query"]}

Enriched query:"""
    state["enriched_query"] = llm.invoke(prompt).content.strip()
    logger.info(f"\n0. Query enrichment:\nOriginal: {state['query']}\nEnriched: {state['enriched_query']}")
    return state


def lookup_search_node(state: RAGState, lookup_index: dict[str, list[float]]) -> RAGState:
    """Cosine similarity search over the LookUpIndex (chunk_id → summary embedding)."""
    if not lookup_index:
        state["lookup_chunk_ids"] = []
        return state

    query_vec = np.array(encoder.encode(state["enriched_query"]))
    scored: list[tuple[float, int]] = []
    for chunk_id_str, summary_vec in lookup_index.items():
        sim = cosine_sim(query_vec.tolist(), summary_vec)
        scored.append((sim, int(chunk_id_str)))

    scored.sort(key=lambda x: x[0], reverse=True)
    state["lookup_chunk_ids"] = [cid for _, cid in scored[:LOOKUP_TOP_K]]

    logger.info(f"\n0b. LookUpIndex search — top {LOOKUP_TOP_K} chunk_ids: {state['lookup_chunk_ids']}")
    return state


def vector_search_node(state: RAGState, qdrant: QdrantClient) -> RAGState:
    #Qdrant vector search using enriched query
    query_vec = encoder.encode(state["enriched_query"]).tolist()
    results = qdrant.query_points(
        collection_name=QDRANT_COLLECTION,
        query=query_vec,
        limit=INITIAL_K,
    )
    state["initial_chunks"] = [
        {
            "id": p.id,
            "score": p.score,
            "text": p.payload.get("text", ""),
            "entities": p.payload.get("entities", []),
            "source": p.payload.get("sources", ""),
            "summary": p.payload.get("summary", ""),
        }
        for p in results.points
    ]
    return state


def fuse_chunks_node(state: RAGState, qdrant: QdrantClient) -> RAGState:
    """Merge chunk_ids from all 3 sources (vector, lookup, graph) and fetch missing chunks."""
    existing_ids = {c["id"] for c in state["initial_chunks"]}

    # Gather chunk_ids from graph paths
    graph_chunk_ids: list[int] = []
    for p in state["paths"]:
        for cid in p.get("chunk_ids", []):
            if cid not in existing_ids and cid not in graph_chunk_ids:
                graph_chunk_ids.append(cid)

    # Gather chunk_ids from lookup that aren't already fetched
    lookup_only_ids: list[int] = [
        cid for cid in state["lookup_chunk_ids"]
        if cid not in existing_ids and cid not in graph_chunk_ids
    ]

    ids_to_fetch = graph_chunk_ids + lookup_only_ids
    if ids_to_fetch:
        results = qdrant.retrieve(
            collection_name=QDRANT_COLLECTION,
            ids=ids_to_fetch,
            with_payload=True,
            with_vectors=False,
        )
        for r in results:
            if r.payload:
                state["initial_chunks"].append({
                    "id": r.id,
                    "score": 0.0,
                    "text": r.payload.get("text", ""),
                    "entities": r.payload.get("entities", []),
                    "source": r.payload.get("sources", ""),
                    "summary": r.payload.get("summary", ""),
                })

    logger.info(
        f"\n3b. Fused chunks — total: {len(state['initial_chunks'])} "
        f"(vector={len(existing_ids)}, graph={len(graph_chunk_ids)}, lookup={len(lookup_only_ids)})"
    )
    return state


def extract_query_entities_node(state: RAGState, llm: ChatOllama) -> RAGState:
    #LLM extract entities
    entities = extract_entities_from_text(state["query"], llm)

    #include entities from chunk
    for chunk in state["initial_chunks"]:
        entities.extend(chunk["entities"])
    state["query_entities"] = list(set(entities))

    logger.info(f"""\n
        1. Extracting entities from user query:
            List of entities: {state["query_entities"]}
    """)

    return state


def find_starting_nodes_node(state: RAGState, neo4j_driver) -> RAGState:
    #Cosine check for selecting top k starting nodes
    if not state["query_entities"]:
        state["starting_nodes"] = []
        return state

    query_embs = [encoder.encode(e).tolist() for e in state["query_entities"]]

    with neo4j_driver.session() as session:
        result = session.run("MATCH (e:Entity) RETURN e.name AS name, e.embedding AS embedding")
        records = result.data()

    best: dict[str, float] = {}
    for rec in records:
        if not rec["embedding"]:
            continue
        score = max(cosine_sim(qe, rec["embedding"]) for qe in query_embs)
        best[rec["name"]] = score

    # pick top INITIAL_K starting nodes
    sorted_nodes = sorted(best.items(), key=lambda x: x[1], reverse=True)
    state["starting_nodes"] = [name for name, _ in sorted_nodes[:INITIAL_K]]

    logger.info(f"""\n
        2. Picking Stating Node
        All Entity in graph: {sorted_nodes}
        Top {INITIAL_K} Nodes with highest similarity to query entity embeddings: {state["starting_nodes"]}
        """)

    return state


def graph_traversal_node(state: RAGState, neo4j_driver, qdrant: QdrantClient) -> RAGState:
    #Guided BFS for graph searching (max depth = MAX_DEPTH = 2)
    query_vec = encoder.encode(state["enriched_query"]).tolist()
    paths: list[dict] = []

    def get_semantic_score(chunk_ids: list[int]) -> float:
        if not chunk_ids:
            return 0.0
        chunk_id = chunk_ids[0]
        # find this chunk in initial_chunks by id
        for c in state["initial_chunks"]:
            if c["id"] == chunk_id:
                return c["score"]
        return 0.0

    def get_neighbors(node_name: str) -> list[dict]:
        with neo4j_driver.session() as session:
            result = session.run(
                """
                MATCH (a:Entity {name: $name})-[r]->(b:Entity)
                RETURN b.name AS name, b.embedding AS embedding, b.chunk_ids AS chunk_ids,
                       type(r) AS rel_type, r.weight AS weight, r.type AS relationship_type
                """,
                name=node_name,
            )
            return result.data()

    for start in state["starting_nodes"]:
        # frontier entries: (path, edges, visited_entities, accumulated_chunk_ids)
        # edges is a list of {"type": str, "weight": float} — one per hop
        frontier = [([start], [], {start}, set())]

        for depth in range(1, MAX_DEPTH + 1):
            next_frontier = []
            for path, edges, ents, chunk_ids in frontier:
                current = path[-1]
                neighbors = get_neighbors(current)

                # rank neighbors by similarity to query for guided BFS
                scored = []
                for nb in neighbors:
                    if nb["name"] in ents:
                        continue
                    sim = cosine_sim(query_vec, nb["embedding"]) if nb["embedding"] else 0.0
                    scored.append((nb, sim))

                scored.sort(key=lambda x: x[1], reverse=True)
                for nb, sim in scored[:TOP_K_NEIGHBORS]:
                    new_edge = {
                        "type": nb.get("relationship_type") or "related_to",
                        "weight": float(nb.get("weight") or 0.0),
                    }
                    new_path = path + [nb["name"]]
                    new_edges = edges + [new_edge]
                    new_ents = ents | {nb["name"]}
                    new_chunks = chunk_ids | set(nb["chunk_ids"] or [])
                    next_frontier.append((new_path, new_edges, new_ents, new_chunks))

                    paths.append({
                        "path": new_path,
                        "edges": new_edges,
                        "entities": new_ents,
                        "chunk_ids": list(new_chunks),
                        "depth": depth,
                        "semantic_score": get_semantic_score(list(new_chunks)),
                    })

            frontier = next_frontier
            if not frontier:
                break

    # filter duplicate paths by frozenset of entities
    seen = set()
    unique_paths = []
    for p in paths:
        key = frozenset(p["entities"])
        if key not in seen:
            seen.add(key)
            unique_paths.append(p)

    state["paths"] = unique_paths

    logger.info(f"""\n
        3. Find Path
        {paths}
        
        Check for duplicate entities path:
        {unique_paths}
        """)

    return state


def rerank_node(state: RAGState) -> RAGState:
    """Manual filtering:
    - Graph paths: score = W_SEMANTIC * semantic + W_GRAPH * (1/path_len) + W_ENTITY_IOU * iou
    - Fused chunks without graph paths: score = W_SEMANTIC * qdrant_score + W_ENTITY_IOU * iou
    Both are ranked together; top RERANK_TOP_N paths are kept for cross-encoder.
    """
    query_entities_set = {e.lower() for e in state["query_entities"]}

    # Build a quick lookup: chunk_id → qdrant score from vector search
    chunk_score_map: dict[int, float] = {c["id"]: c["score"] for c in state["initial_chunks"]}

    # Score graph paths
    scored = []
    path_chunk_ids: set[int] = set()
    for p in state["paths"]:
        semantic = p["semantic_score"]
        graph_score = 1.0 / max(len(p["path"]), 1)
        path_ents = {e.lower() for e in p["entities"]}
        iou = entity_iou(path_ents, query_entities_set)
        final_score = W_SEMANTIC * semantic + W_GRAPH * graph_score + W_ENTITY_IOU * iou
        scored.append({**p, "final_score": final_score, "iou": iou})
        path_chunk_ids.update(p.get("chunk_ids", []))

    # Score fused chunks not covered by any graph path
    for chunk in state["initial_chunks"]:
        if chunk["id"] in path_chunk_ids:
            continue
        semantic = chunk_score_map.get(chunk["id"], 0.0)
        chunk_ents = {e.lower() for e in chunk.get("entities", [])}
        iou = entity_iou(chunk_ents, query_entities_set)
        final_score = W_SEMANTIC * semantic + W_ENTITY_IOU * iou
        # Represent as a pseudo-path so downstream nodes stay compatible
        scored.append({
            "path": [str(chunk["id"])],
            "edges": [],
            "entities": set(chunk.get("entities", [])),
            "chunk_ids": [chunk["id"]],
            "depth": 0,
            "semantic_score": semantic,
            "final_score": final_score,
            "iou": iou,
        })

    scored.sort(key=lambda x: x["final_score"], reverse=True)
    state["ranked_paths"] = scored[:RERANK_TOP_N]

    logger.info(f"""\n
        4. Rerank — top {RERANK_TOP_N} candidates
        Weights: w_semantic={W_SEMANTIC}, w_graph={W_GRAPH}, w_iou={W_ENTITY_IOU}
        Results: {state["ranked_paths"]}
    """)

    return state


def cross_encode_node(state: RAGState, qdrant: QdrantClient) -> RAGState:
    #Cross Encoder, narrowing the top_path
    query = state["query"]
    candidates = []

    for p in state["ranked_paths"]:
        # build a short passage from path entities
        passage = " → ".join(p["path"])
        # fetch chunk texts if available
        if p["chunk_ids"]:
            results = qdrant.retrieve(
                collection_name=QDRANT_COLLECTION,
                ids=p["chunk_ids"][:2],
                with_payload=True,
            )
            texts = [r.payload.get("text", "") for r in results]
            passage = " ".join(texts)[:400]  # truncate
        candidates.append(passage)

    if not candidates:
        state["top_paths"] = state["ranked_paths"][:CROSS_ENCODER_TOP_N]
        return state

    pairs = [[query, c] for c in candidates]
    ce_scores = cross_encoder.predict(pairs)

    for i, p in enumerate(state["ranked_paths"]):
        p["ce_score"] = float(ce_scores[i])

    state["ranked_paths"].sort(key=lambda x: x.get("ce_score", 0.0), reverse=True)
    state["top_paths"] = state["ranked_paths"][:CROSS_ENCODER_TOP_N]

    logger.info(f"""\n
        5. Choosing top:{CROSS_ENCODER_TOP_N} with cross encoder model: ms-marco-MiniLM-L-6-v2
        Results"
        {state["ranked_paths"]}
    """)

    return state


def generate_context_node(state: RAGState, qdrant: QdrantClient) -> RAGState:
    # ── Build graph_context: render each top path as a relationship chain ──────
    path_lines = []
    for p in state["top_paths"]:
        rendered = _render_path(p["path"], p.get("edges", []))
        score = p.get("final_score", 0.0)
        path_lines.append(f"[score={score:.3f}] {rendered}")
    state["graph_context"] = "\n".join(path_lines)

    # ── Collect chunk texts from top paths + initial vector hits ──────────────
    chunk_ids: list[int] = []
    for p in state["top_paths"]:
        for cid in p["chunk_ids"]:
            if cid not in chunk_ids:
                chunk_ids.append(cid)

    for c in state["initial_chunks"]:
        if c["id"] not in chunk_ids:
            chunk_ids.append(c["id"])

    if not chunk_ids:
        state["context"] = ""
        return state

    results = qdrant.retrieve(
        collection_name=QDRANT_COLLECTION,
        ids=chunk_ids,
        with_payload=True,
    )
    texts = [r.payload.get("text", "") for r in results if r.payload]
    state["context"] = "\n\n---\n\n".join(texts)
    return state


def llm_answer_node(state: RAGState, llm: ChatOllama) -> RAGState:
    graph_section = (
        f"KNOWLEDGE GRAPH — entity relationship paths discovered from the documents\n"
        f"(format: EntityA --[relationship (weight)]--> EntityB --[…]--> EntityN)\n\n"
        f"{state['graph_context']}"
        if state.get("graph_context")
        else "KNOWLEDGE GRAPH — no relationship paths found"
    )

    prompt = f"""
    Here are relevant context for Question: {state["query"]}
    Please use this as a primary source to assist you analysis
    DOCUMENT CONTEXT:
    {state["context"]}
    """

    logger.info(f"\n6. Generate prompt for LLM:\n {prompt}")


    state["answer"] = prompt
    return state


def _load_lookup_index(lookup_index_path: str | None) -> dict[str, list[float]]:
    """Load lookup index JSON. If a directory is given, merge all *_lookup_index.json files found."""
    if not lookup_index_path:
        return {}
    if os.path.isdir(lookup_index_path):
        merged: dict[str, list[float]] = {}
        for fpath in glob.glob(os.path.join(lookup_index_path, "**", "*_lookup_index.json"), recursive=True):
            with open(fpath, encoding="utf-8") as f:
                merged.update(json.load(f))
        return merged
    if os.path.isfile(lookup_index_path):
        with open(lookup_index_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def build_retrieve_graph(qdrant: QdrantClient, neo4j_driver, llm: ChatOllama, lookup_index: dict) -> Any:
    graph = StateGraph(RAGState)

    graph.add_node("enrich_query", lambda s: enrich_query_node(s, llm))
    graph.add_node("lookup_search", lambda s: lookup_search_node(s, lookup_index))
    graph.add_node("vector_search", lambda s: vector_search_node(s, qdrant))
    graph.add_node("extract_query_entities",lambda s: extract_query_entities_node(s, llm))
    graph.add_node("find_starting_nodes", lambda s: find_starting_nodes_node(s, neo4j_driver))
    graph.add_node("graph_traversal", lambda s: graph_traversal_node(s, neo4j_driver, qdrant))
    graph.add_node("fuse_chunks", lambda s: fuse_chunks_node(s, qdrant))
    graph.add_node("rerank", rerank_node)
    graph.add_node("cross_encode", lambda s: cross_encode_node(s, qdrant))
    graph.add_node("generate_context", lambda s: generate_context_node(s, qdrant))
    graph.add_node("llm_answer", lambda s: llm_answer_node(s, llm))

    graph.set_entry_point("enrich_query")
    graph.add_edge("enrich_query", "lookup_search")
    graph.add_edge("lookup_search", "vector_search")
    graph.add_edge("vector_search", "extract_query_entities")
    graph.add_edge("extract_query_entities","find_starting_nodes")
    graph.add_edge("find_starting_nodes", "graph_traversal")
    graph.add_edge("graph_traversal", "fuse_chunks")
    graph.add_edge("fuse_chunks", "rerank")
    graph.add_edge("rerank", "cross_encode")
    graph.add_edge("cross_encode","generate_context")
    graph.add_edge("generate_context","llm_answer")
    graph.add_edge("llm_answer", END)

    return graph.compile()


def run_query(query: str, lookup_index_path: str | None = None) -> str:
    """Run the hybrid retrieval pipeline.

    Args:
        query: User's question.
        lookup_index_path: Path to a *_lookup_index.json file or a directory
            containing such files. If None, the lookup retrieval leg is skipped.
    """
    qdrant = QdrantClient(os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"))
    llm = ChatOllama(model="llama3")
    neo4j_driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")),
    )

    lookup_index = _load_lookup_index(lookup_index_path)
    app = build_retrieve_graph(qdrant, neo4j_driver, llm, lookup_index)

    initial_state: RAGState = {
        "query": query,
        "enriched_query": "",
        "lookup_chunk_ids": [],
        "initial_chunks": [],
        "query_entities": [],
        "starting_nodes": [],
        "paths": [],
        "ranked_paths": [],
        "top_paths": [],
        "context": "",
        "graph_context": "",
        "answer": "",
    }

    result = app.invoke(initial_state)
    neo4j_driver.close()
    return result["answer"]

if __name__ == "__main__":
    import sys
    query = sys.argv[1] if len(sys.argv) > 1 else None
    logger.info(f"User Question: {query}")

    answer = run_query(query, lookup_index_path="_lookup_index.json")
    with open("response.txt", "w") as f:
        f.write(str(answer))

