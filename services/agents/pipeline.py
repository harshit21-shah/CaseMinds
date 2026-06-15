"""
LangGraph pipeline — wires all 4 agents into a state machine.

Flow:
  QueryClassifier → RetrievalAgent → [NO_RESULTS exit] → GraphTraversal → VerificationAnswer
"""

import logging

from langgraph.graph import END, START, StateGraph

from services.agents.graph_traversal_agent import run_graph_traversal
from services.agents.query_classifier import run_query_classifier
from services.agents.retrieval_agent import run_retrieval_agent
from services.agents.state import PipelineState
from services.agents.verification_agent import run_verification_answer

logger = logging.getLogger(__name__)


def _route_after_retrieval(state: PipelineState) -> str:
    """After retrieval: exit early if no results, otherwise continue."""
    if state.get("status") == "NO_RESULTS":
        return END
    return "graph_traversal"


def build_pipeline() -> StateGraph:
    graph = StateGraph(PipelineState)

    # Add nodes
    graph.add_node("query_classifier", run_query_classifier)
    graph.add_node("retrieval_agent", run_retrieval_agent)
    graph.add_node("graph_traversal", run_graph_traversal)
    graph.add_node("verification_answer", run_verification_answer)

    # Edges
    graph.add_edge(START, "query_classifier")
    graph.add_edge("query_classifier", "retrieval_agent")
    graph.add_conditional_edges(
        "retrieval_agent",
        _route_after_retrieval,
        {"graph_traversal": "graph_traversal", END: END},
    )
    graph.add_edge("graph_traversal", "verification_answer")
    graph.add_edge("verification_answer", END)

    return graph


# ── Compiled singleton ────────────────────────────────────────────────────────

_compiled_pipeline = None


def get_pipeline():  # type: ignore[return]
    global _compiled_pipeline
    if _compiled_pipeline is None:
        _compiled_pipeline = build_pipeline().compile()
        logger.info("LangGraph pipeline compiled")
    return _compiled_pipeline


def run_pipeline(query: str) -> PipelineState:
    """Run the full 4-agent pipeline for a query. Returns final state."""
    pipeline = get_pipeline()

    initial_state: PipelineState = {
        "query": query,
        "query_type": None,
        "statute_refs": [],
        "case_refs": [],
        "retrieval_strategy": "HYBRID_EQUAL",
        "rewritten_query": query,
        "retrieved_chunks": [],
        "traversal_results": [],
        "overruled_warnings": [],
        "draft_answer": None,
        "verified_citations": [],
        "unverified_claims": [],
        "confidence": 0.0,
        "status": "IN_PROGRESS",
        "trace": [],
        "total_tokens_in": 0,
        "total_tokens_out": 0,
        "total_latency_ms": 0,
    }

    logger.info("pipeline start query='%s'", query[:80])
    final_state: PipelineState = pipeline.invoke(initial_state)
    logger.info(
        "pipeline end status=%s confidence=%.2f",
        final_state.get("status"),
        final_state.get("confidence", 0.0),
    )
    return final_state
