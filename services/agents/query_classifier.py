"""
Agent 1 — Query Classifier.

Uses Groq Llama 3.3 8B (fast, free) with structured output.
Classifies query type and determines retrieval strategy.
"""

import logging

from pydantic import BaseModel

from services.agents.llm_client import GROQ_CLASSIFIER, invoke_structured
from services.agents.state import PipelineState, TraceEntry

logger = logging.getLogger(__name__)


class ClassifiedQuery(BaseModel):
    query_type: str  # STATUTE | CASE_LAW | GENERAL
    statute_refs: list[str]
    case_refs: list[str]
    retrieval_strategy: str  # BM25_FIRST | DENSE_FIRST | HYBRID_EQUAL
    rewritten_query: str


def run_query_classifier(state: PipelineState) -> PipelineState:
    """
    LangGraph node: classify the query and update state.
    """
    query = state["query"]
    logger.info("query_classifier query='%s'", query[:80])

    try:
        result, usage = invoke_structured(
            prompt_name="query_classifier_v1",
            user_message=f"Query: {query}",
            model=GROQ_CLASSIFIER,
            schema=ClassifiedQuery,
        )
        classified: ClassifiedQuery = result  # type: ignore[assignment]
    except Exception as exc:
        logger.warning("query_classifier failed: %s — using GENERAL fallback", exc)
        classified = ClassifiedQuery(
            query_type="GENERAL",
            statute_refs=[],
            case_refs=[],
            retrieval_strategy="HYBRID_EQUAL",
            rewritten_query=query,
        )
        usage = {"latency_ms": 0, "tokens_in": 0, "tokens_out": 0}

    # Validate and normalise
    valid_types = {"STATUTE", "CASE_LAW", "GENERAL"}
    valid_strategies = {"BM25_FIRST", "DENSE_FIRST", "HYBRID_EQUAL"}

    query_type = classified.query_type if classified.query_type in valid_types else "GENERAL"
    strategy = (
        classified.retrieval_strategy
        if classified.retrieval_strategy in valid_strategies
        else "HYBRID_EQUAL"
    )

    trace_entry: TraceEntry = {
        "agent": "QueryClassifier",
        "action": "classify",
        "detail": f"type={query_type} strategy={strategy} refs={classified.statute_refs}",
    }

    return {
        **state,
        "query_type": query_type,  # type: ignore[typeddict-item]
        "statute_refs": classified.statute_refs,
        "case_refs": classified.case_refs,
        "retrieval_strategy": strategy,  # type: ignore[typeddict-item]
        "rewritten_query": classified.rewritten_query or query,
        "status": "IN_PROGRESS",
        "trace": state.get("trace", []) + [trace_entry],
        "total_tokens_in": state.get("total_tokens_in", 0) + (usage.get("tokens_in") or 0),
        "total_tokens_out": state.get("total_tokens_out", 0) + (usage.get("tokens_out") or 0),
        "total_latency_ms": state.get("total_latency_ms", 0) + (usage.get("latency_ms") or 0),
    }
