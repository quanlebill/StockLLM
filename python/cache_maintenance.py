"""
cache_maintenance.py — Scheduled cleanup for Neo4j policies and Qdrant cache.

Runs two jobs every 10 minutes:
  1. Neo4j cleanup  : delete Policy nodes with created_at older than 2 weeks
  2. Cache eviction : delete bottom 100 cache entries by hit_count from Qdrant

Start with:  python python/cache_maintenance.py
"""

import os
import time
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

import cache_query
import self_improvement

load_dotenv(Path(os.environ["STOCKLLM_ROOT"]) / ".env")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

INTERVAL_SECONDS = 600   # 10 minutes
POLICY_MAX_AGE   = timedelta(weeks=2)
EVICT_BOTTOM_N   = 100

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("cache_maintenance")

_neo4j_driver = None


def _neo4j():
    global _neo4j_driver
    if _neo4j_driver is None:
        _neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    return _neo4j_driver


# ---------------------------------------------------------------------------
# Job 1 — Neo4j: delete stale Policy nodes
# ---------------------------------------------------------------------------

def clean_old_policies() -> int:
    """
    Delete Policy nodes in Neo4j whose created_at is older than 2 weeks,
    then delete the corresponding Qdrant KG_NOTES points.
    Returns the number of policies deleted.
    """
    cutoff = (datetime.now(timezone.utc) - POLICY_MAX_AGE).isoformat()
    with _neo4j().session() as session:
        # Collect qdrant_ids before deletion so we can clean Qdrant too
        rows = session.run(
            "MATCH (p:Policy) WHERE p.created_at < $cutoff RETURN p.qdrant_id AS qdrant_id",
            cutoff=cutoff,
        ).data()
        qdrant_ids = [r["qdrant_id"] for r in rows if r.get("qdrant_id")]

        result = session.run(
            """
            MATCH (p:Policy)
            WHERE p.created_at < $cutoff
            DETACH DELETE p
            RETURN count(*) AS deleted
            """,
            cutoff=cutoff,
        )
        record = result.single()
        deleted = record["deleted"] if record else 0

    if qdrant_ids:
        try:
            self_improvement.delete_policy_qdrant_points(qdrant_ids)
        except Exception as e:
            log.error(f"Qdrant policy point cleanup failed: {e}")

    return deleted


# ---------------------------------------------------------------------------
# Job 2 — Qdrant: evict lowest-hit cache entries
# ---------------------------------------------------------------------------

def evict_low_hit_cache() -> dict:
    """Delete bottom EVICT_BOTTOM_N entries by hit_count from both cache collections."""
    return cache_query.evict_bottom_hits(EVICT_BOTTOM_N)


# ---------------------------------------------------------------------------
# Scheduler loop
# ---------------------------------------------------------------------------

def run_once() -> None:
    log.info("Running maintenance cycle...")

    # Neo4j policy cleanup
    try:
        deleted = clean_old_policies()
        log.info(f"Neo4j + Qdrant — deleted {deleted} stale Policy node(s) (older than 2 weeks)")
    except Exception as e:
        log.error(f"Neo4j cleanup failed: {e}")

    # Qdrant cache eviction
    try:
        result = evict_low_hit_cache()
        counts = result.get("deleted", {})
        log.info(
            f"Qdrant — evicted bottom {EVICT_BOTTOM_N}: "
            f"ANSWER_CACHE={counts.get('ANSWER_CACHE', 0)}, "
            f"DOCUMENT_CACHE={counts.get('DOCUMENT_CACHE', 0)}"
        )
    except Exception as e:
        log.error(f"Qdrant eviction failed: {e}")

    log.info("Maintenance cycle complete. Next run in 10 minutes.")


def main() -> None:
    log.info(f"cache_maintenance started — interval={INTERVAL_SECONDS}s, "
             f"policy_max_age=2 weeks, evict_n={EVICT_BOTTOM_N}")
    while True:
        run_once()
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
