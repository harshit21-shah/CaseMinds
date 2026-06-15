"""
Agent 3 — Graph Traversal Agent.

No LLM call — pure graph BFS.
Expands retrieved chunks via citation graph (2 hops).
Detects overruled cases on traversal path.
"""

import logging
from functools import lru_cache

from services.agents.state import PipelineState, TraceEntry
from services.config import settings
from services.graph.graph_store import GraphStore
from services.retrieval.search import ChunkResult

logger = logging.getLogger(__name__)

MAX_TRAVERSAL_CHUNKS = settings.max_traversal_chunks
MAX_TOTAL_CHUNKS = settings.max_total_context_chunks


@lru_cache(maxsize=1)
def _get_graph() -> GraphStore:
    return GraphStore()


def run_graph_traversal(state: PipelineState) -> PipelineState:
    """
    LangGraph node: expand context via citation graph.
    """
    retrieved = state.get("retrieved_chunks", [])
    if not retrieved:
        return {
            **state,
            "traversal_results": [],
            "overruled_warnings": [],
        }

    graph = _get_graph()
    already_seen = {c.doc_id for c in retrieved}
    overruled_warnings: list[str] = []
    traversal_chunks: list[ChunkResult] = []

    for chunk in retrieved:
        traversal = graph.traverse(
            chunk.doc_id,
            directions=["CITES", "CITED_BY"],
            max_hops=settings.graph_max_hops,
            limit=settings.graph_traversal_limit,
        )
        for node in traversal:
            if node.is_overruled and node.doc_id not in overruled_warnings:
                overruled_warnings.append(node.doc_id)
                logger.info(
                    "overruled flag: doc_id=%s case='%s'",
                    node.doc_id,
                    node.case_name,
                )

            if node.doc_id not in already_seen and len(traversal_chunks) < MAX_TRAVERSAL_CHUNKS:
                # Build a pseudo-ChunkResult for traversal node
                traversal_chunks.append(
                    ChunkResult(
                        chunk_id=f"{node.doc_id}_traversal",
                        doc_id=node.doc_id,
                        text=f"[Via graph traversal — {node.hops} hop(s) from {chunk.doc_id}] {node.case_name}",
                        score=0.5 / node.hops,  # closer = higher score
                        metadata={
                            "doc_id": node.doc_id,
                            "case_name": node.case_name,
                            "citation": node.citation or "",
                            "is_overruled": node.is_overruled,
                            "source": "graph_traversal",
                            "hops": node.hops,
                        },
                    )
                )
                already_seen.add(node.doc_id)

    combined = (retrieved + traversal_chunks)[:MAX_TOTAL_CHUNKS]

    trace_entry: TraceEntry = {
        "agent": "GraphTraversal",
        "action": "traversed",
        "detail": (
            f"traversal_chunks={len(traversal_chunks)} "
            f"overruled={len(overruled_warnings)} "
            f"total_context={len(combined)}"
        ),
    }

    return {
        **state,
        "traversal_results": combined,
        "overruled_warnings": overruled_warnings,
        "trace": state.get("trace", []) + [trace_entry],
    }
