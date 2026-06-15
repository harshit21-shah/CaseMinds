"""Pydantic request/response schemas for FastAPI endpoints."""

from pydantic import BaseModel


class QueryRequest(BaseModel):
    query: str
    session_id: str | None = None


class CitationResponse(BaseModel):
    doc_id: str
    case_name: str
    citation: str | None
    court: str
    date: str | None
    kanoon_url: str
    excerpt: str
    is_overruled: bool


class OverruledWarning(BaseModel):
    doc_id: str
    case_name: str
    overruled_by: str | None


class QueryResponse(BaseModel):
    status: str
    answer: str
    citations: list[CitationResponse]
    overruled_warnings: list[OverruledWarning]
    confidence: float
    query_type: str | None
    disclaimer: str
    trace_id: str
    latency_ms: int


class JudgmentResponse(BaseModel):
    doc_id: str
    case_name: str
    citation: str | None
    court: str
    date: str | None
    judges: list[str]
    acts_cited: list[str]
    is_overruled: bool
    kanoon_url: str


class RelatedJudgment(BaseModel):
    doc_id: str
    case_name: str
    citation: str | None
    is_overruled: bool


class RelatedResponse(BaseModel):
    cites: list[RelatedJudgment]
    cited_by: list[RelatedJudgment]


class FeedbackRequest(BaseModel):
    trace_id: str
    rating: str  # HELPFUL | NOT_HELPFUL | PARTIALLY_HELPFUL
    citation_correct: bool | None = None
    comment: str | None = None


class FeedbackResponse(BaseModel):
    feedback_id: str


class HealthResponse(BaseModel):
    status: str
    corpus_size: int
    graph_nodes: int
    graph_edges: int


class EvalLatestResponse(BaseModel):
    run_id: str | None
    citation_accuracy: float | None
    overruled_detection: float | None
    retrieval_precision_at_5: float | None
    adversarial_abstention: str | None
