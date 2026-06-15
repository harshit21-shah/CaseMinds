"""
LangGraph pipeline — wires all 4 agents into a state machine.

Flow:
  QueryClassifier → RetrievalAgent → [NO_RESULTS exit] → GraphTraversal → VerificationAnswer
"""

import logging
from collections.abc import Iterator
from typing import Any

from langgraph.graph import END, START, StateGraph

from services.agents.graph_traversal_agent import run_graph_traversal
from services.agents.query_classifier import run_query_classifier
from services.agents.retrieval_agent import run_retrieval_agent
from services.agents.state import PipelineState, TraceEntry
from services.agents.verification_agent import run_verification_answer

logger = logging.getLogger(__name__)

# LangGraph node id → trace agent name (used by SSE + UI)
NODE_TO_AGENT: dict[str, str] = {
    "query_classifier": "QueryClassifier",
    "retrieval_agent": "RetrievalAgent",
    "graph_traversal": "GraphTraversal",
    "verification_answer": "VerificationAnswer",
}

AGENT_ORDER = list(NODE_TO_AGENT.keys())

# Human labels — descriptions come from live trace detail, not hardcoded fluff
AGENT_META: dict[str, dict[str, str]] = {
    "QueryClassifier": {"label": "Query Classifier", "icon": "brain"},
    "RetrievalAgent": {"label": "Retrieval Agent", "icon": "book"},
    "GraphTraversal": {"label": "Graph Traversal", "icon": "graph"},
    "VerificationAnswer": {"label": "Verification + Answer", "icon": "shield"},
}


def _route_after_retrieval(state: PipelineState) -> str:
    """After retrieval: exit early if no results, otherwise continue."""
    if state.get("status") == "NO_RESULTS":
        return END
    return "graph_traversal"


def build_pipeline() -> StateGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("query_classifier", run_query_classifier)
    graph.add_node("retrieval_agent", run_retrieval_agent)
    graph.add_node("graph_traversal", run_graph_traversal)
    graph.add_node("verification_answer", run_verification_answer)

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


_compiled_pipeline = None


def get_pipeline():  # type: ignore[return]
    global _compiled_pipeline
    if _compiled_pipeline is None:
        _compiled_pipeline = build_pipeline().compile()
        logger.info("LangGraph pipeline compiled")
    return _compiled_pipeline


def _initial_state(query: str) -> PipelineState:
    return {
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


def _latest_trace(update: dict[str, Any]) -> TraceEntry | None:
    trace = update.get("trace")
    if trace and isinstance(trace, list):
        return trace[-1]
    return None


def run_pipeline(query: str) -> PipelineState:
    """Run the full 4-agent pipeline for a query. Returns final state."""
    final: PipelineState | None = None
    for event in run_pipeline_events(query):
        if event["event"] == "pipeline_done":
            final = event["state"]
    assert final is not None
    return final


def run_pipeline_events(query: str) -> Iterator[dict[str, Any]]:
    """
    Stream real pipeline progress — one event per LangGraph node completion.

    Yields dicts:
      {"event": "agent_start", "agent": "QueryClassifier", ...}
      {"event": "agent_complete", "agent": "...", "action": "...", "detail": "..."}
      {"event": "pipeline_done", "state": PipelineState}
    """
    pipeline = get_pipeline()
    initial = _initial_state(query)

    logger.info("pipeline start query='%s'", query[:80])

    final_state: PipelineState = initial
    started: set[str] = set()

    for update in pipeline.stream(initial, stream_mode="updates"):
        for node_name, node_output in update.items():
            if node_name == "__end__":
                continue

            agent = NODE_TO_AGENT.get(node_name, node_name)

            if agent not in started:
                started.add(agent)
                meta = AGENT_META.get(agent, {"label": agent, "icon": "circle"})
                yield {
                    "event": "agent_start",
                    "agent": agent,
                    "label": meta["label"],
                    "step": len(started),
                    "total_steps": len(AGENT_ORDER),
                }

            entry = _latest_trace(node_output)
            if entry:
                yield {
                    "event": "agent_complete",
                    "agent": entry["agent"],
                    "action": entry["action"],
                    "detail": entry["detail"],
                }

            final_state = {**final_state, **node_output}

    logger.info(
        "pipeline end status=%s confidence=%.2f",
        final_state.get("status"),
        final_state.get("confidence", 0.0),
    )
    yield {"event": "pipeline_done", "state": final_state}


def get_pipeline_meta() -> list[dict[str, str]]:
    """Agent metadata for UI — labels only; details are live from trace."""
    return [
        {
            "id": NODE_TO_AGENT[node],
            "label": AGENT_META[NODE_TO_AGENT[node]]["label"],
            "node": node,
        }
        for node in AGENT_ORDER
    ]
