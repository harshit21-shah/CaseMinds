"""
Shared LangGraph pipeline state.

Every agent reads from and writes to PipelineState.
TypedDict enforces the contract across all 4 agents.
"""

from typing import Literal, TypedDict

from services.retrieval.search import ChunkResult


class CitationRef(TypedDict):
    doc_id: str
    case_name: str
    citation: str | None
    kanoon_url: str
    is_overruled: bool
    excerpt: str


class TraceEntry(TypedDict):
    agent: str
    action: str
    detail: str


class PipelineState(TypedDict):
    # Input
    query: str

    # After Query Classifier
    query_type: Literal["STATUTE", "CASE_LAW", "GENERAL"] | None
    statute_refs: list[str]
    case_refs: list[str]
    retrieval_strategy: Literal["BM25_FIRST", "DENSE_FIRST", "HYBRID_EQUAL"]
    rewritten_query: str

    # After Retrieval Agent
    retrieved_chunks: list[ChunkResult]

    # After Graph Traversal Agent
    traversal_results: list[ChunkResult]
    overruled_warnings: list[str]

    # After Verification + Answer Agent
    draft_answer: str | None
    verified_citations: list[CitationRef]
    unverified_claims: list[str]
    confidence: float

    # Pipeline control
    status: Literal["IN_PROGRESS", "COMPLETE", "LOW_CONFIDENCE", "NO_RESULTS"]
    trace: list[TraceEntry]

    # Cost tracking
    total_tokens_in: int
    total_tokens_out: int
    total_latency_ms: int
