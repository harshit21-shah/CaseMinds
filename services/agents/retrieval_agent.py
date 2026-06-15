"""
Agent 2 — Retrieval Agent.

No LLM call — pure algorithmic hybrid retrieval.
Calls hybrid_search → top-5 ChunkResults.
Sets status=NO_RESULTS if max score < MIN_RETRIEVAL_SCORE.
"""

import logging

from services.agents.state import PipelineState, TraceEntry
from services.retrieval.search import hybrid_search

logger = logging.getLogger(__name__)


def run_retrieval_agent(state: PipelineState) -> PipelineState:
    """
    LangGraph node: run hybrid retrieval and update state.
    """
    query = state.get("rewritten_query") or state["query"]
    statute_refs = state.get("statute_refs", [])
    strategy = state.get("retrieval_strategy", "HYBRID_EQUAL")

    logger.info(
        "retrieval_agent query='%s' strategy=%s statute_refs=%s",
        query[:80],
        strategy,
        statute_refs,
    )

    chunks = hybrid_search(
        query=query,
        statute_refs=statute_refs if statute_refs else None,
        strategy=strategy,
        top_k=5,
    )

    if not chunks:
        trace_entry: TraceEntry = {
            "agent": "RetrievalAgent",
            "action": "no_results",
            "detail": f"0 chunks above threshold for query='{query[:60]}'",
        }
        return {
            **state,
            "retrieved_chunks": [],
            "status": "NO_RESULTS",
            "trace": state.get("trace", []) + [trace_entry],
        }

    max_score = max(c.score for c in chunks)
    trace_entry = {
        "agent": "RetrievalAgent",
        "action": "retrieved",
        "detail": f"chunks={len(chunks)} max_score={max_score:.3f} strategy={strategy}",
    }

    return {
        **state,
        "retrieved_chunks": chunks,
        "status": "IN_PROGRESS",
        "trace": state.get("trace", []) + [trace_entry],
    }
