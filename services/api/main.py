"""
FastAPI application — CaseMinds API.

Endpoints:
  POST /api/v1/query           — full pipeline (blocking)
  POST /api/v1/query/stream    — streaming pipeline (SSE)
  GET  /api/v1/judgments/{id}  — judgment metadata
  GET  /api/v1/judgments/{id}/related — citation neighbours
  POST /api/v1/feedback        — user feedback
  GET  /api/v1/health          — system health
  GET  /api/v1/eval/latest     — latest eval run summary
"""

import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from services.agents.logger import configure_logging, set_trace_id
from services.api.database import SessionLocal, get_db, init_db
from services.api.models import Feedback, JudgmentCitation, QueryLog
from services.api.schemas import (
    CitationResponse,
    EvalLatestResponse,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    JudgmentResponse,
    OverruledWarning,
    QueryRequest,
    QueryResponse,
    RelatedJudgment,
    RelatedResponse,
)
from services.config import settings

logger = logging.getLogger(__name__)

# ── Rate limiting (in-memory, per-IP) ────────────────────────────────────────
# Swap to Redis in V2 for multi-instance deployments.
_rate_limit_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_REQUESTS = 20   # requests
RATE_LIMIT_WINDOW_S = 60   # per 60 seconds


def _check_rate_limit(client_ip: str) -> None:
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW_S
    hits = _rate_limit_store[client_ip]
    # Evict old hits
    _rate_limit_store[client_ip] = [t for t in hits if t > window_start]
    if len(_rate_limit_store[client_ip]) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW_S}s.",
        )
    _rate_limit_store[client_ip].append(now)


# ── Startup / shutdown ────────────────────────────────────────────────────────

_graph_store = None  # lazy — avoids blocking port bind on Render cold start


def _get_graph_store():
    """Load citation graph on first use (not at startup)."""
    global _graph_store
    if _graph_store is None:
        from services.graph.graph_store import GraphStore

        _graph_store = GraphStore()
    return _graph_store


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging(settings.log_level)
    init_db()
    logger.info("CaseMinds API started", extra={"environment": settings.environment})
    yield
    logger.info("CaseMinds API shutting down")


app = FastAPI(
    title="CaseMinds API",
    description="GraphRAG legal research assistant for Indian law",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    import traceback
    logger.error(
        "unhandled exception on %s %s: %s\n%s",
        request.method, request.url.path, exc, traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred."}},
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_query_response(data: dict, trace_id: str, latency_ms: int, db: Session) -> QueryResponse:
    from services.api.models import Judgment

    final_state = data

    citations: list[CitationResponse] = []
    for c in final_state.get("verified_citations", []):
        row = db.query(Judgment).filter(Judgment.doc_id == c["doc_id"]).first()
        citations.append(
            CitationResponse(
                doc_id=c["doc_id"],
                case_name=c["case_name"],
                citation=c.get("citation"),
                court=row.court if row else "",
                date=str(row.date) if row and row.date else None,
                kanoon_url=c.get("kanoon_url", ""),
                excerpt=c.get("excerpt", ""),
                is_overruled=c.get("is_overruled", False),
            )
        )

    overruled: list[OverruledWarning] = []
    for doc_id in final_state.get("overruled_warnings", []):
        row = db.query(Judgment).filter(Judgment.doc_id == doc_id).first()
        overruled.append(
            OverruledWarning(
                doc_id=doc_id,
                case_name=row.case_name if row else doc_id,
                overruled_by=row.overruled_by_doc_id if row else None,
            )
        )

    status = final_state.get("status", "COMPLETE")
    answer = final_state.get("draft_answer")
    if not answer:
        if status == "NO_RESULTS":
            answer = (
                "CaseMinds could not find relevant authority in its corpus for this query. "
                "Try rephrasing, or search Indian Kanoon directly."
            )
        else:
            answer = ""

    return QueryResponse(
        status=status,
        answer=answer,
        citations=citations,
        overruled_warnings=overruled,
        confidence=final_state.get("confidence", 0.0),
        query_type=final_state.get("query_type"),
        disclaimer=settings.disclaimer,
        trace_id=trace_id,
        latency_ms=latency_ms,
    )


def _log_query(trace_id: str, query: str, final_state: dict, latency_ms: int, db: Session) -> None:
    import json as _json
    try:
        log = QueryLog(
            id=trace_id,
            query=query,
            query_type=final_state.get("query_type"),
            status=final_state.get("status", "COMPLETE"),
            confidence=final_state.get("confidence", 0.0),
            answer=final_state.get("draft_answer", ""),
            # Serialize lists explicitly (SQLAlchemy _JSONColumn not always applied)
            cited_doc_ids=_json.dumps([c["doc_id"] for c in final_state.get("verified_citations", [])]),  # type: ignore[arg-type]
            retrieval_scores=_json.dumps([c.score for c in final_state.get("retrieved_chunks", [])]),      # type: ignore[arg-type]
            latency_ms=latency_ms,
            model_used=settings.groq_answer_model,
            groq_tokens_in=final_state.get("total_tokens_in"),
            groq_tokens_out=final_state.get("total_tokens_out"),
        )
        db.add(log)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("failed to log query: %s", exc)


# ── POST /api/v1/query ────────────────────────────────────────────────────────

@app.post("/api/v1/query", response_model=QueryResponse)
async def query_endpoint(
    request: Request,
    body: QueryRequest,
    db: Session = Depends(get_db),
) -> QueryResponse:
    """Run the 4-agent pipeline in a threadpool so the event loop stays unblocked."""
    from fastapi.concurrency import run_in_threadpool
    from services.agents.pipeline import run_pipeline

    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)
    start_ms = time.time() * 1000

    if not body.query.strip():
        raise HTTPException(status_code=422, detail="Query cannot be empty.")
    if len(body.query) > 1000:
        raise HTTPException(status_code=422, detail="Query too long (max 1000 characters).")

    final_state = await run_in_threadpool(run_pipeline, body.query.strip())
    latency_ms = int(time.time() * 1000 - start_ms)

    _log_query(trace_id, body.query, final_state, latency_ms, db)
    return _build_query_response(final_state, trace_id, latency_ms, db)


# ── POST /api/v1/query/stream ─────────────────────────────────────────────────

@app.post("/api/v1/query/stream")
async def query_stream_endpoint(
    request: Request,
    body: QueryRequest,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """
    Server-Sent Events stream.

    Emits progress events as each agent completes, then the final answer.
    Client receives incremental updates instead of waiting 12s for the full response.

    Event types:
      {"event": "agent_start",    "agent": "QueryClassifier"}
      {"event": "agent_complete", "agent": "QueryClassifier", "detail": "..."}
      {"event": "answer",         "data": <QueryResponse JSON>}
      {"event": "error",          "detail": "..."}
    """
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    if not body.query.strip():
        raise HTTPException(status_code=422, detail="Query cannot be empty.")
    if len(body.query) > 1000:
        raise HTTPException(status_code=422, detail="Query too long (max 1000 characters).")

    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)

    async def event_generator() -> AsyncGenerator[str, None]:
        start_ms = time.time() * 1000
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[dict | None] = asyncio.Queue()

        def _sse(event: str, data: dict) -> str:
            return f"data: {json.dumps({'event': event, **data})}\n\n"

        from services.api.models import Judgment

        corpus_size = db.query(Judgment).count()
        yield _sse(
            "pipeline_start",
            {
                "detail": "Starting pipeline…",
                "corpus_size": corpus_size,
                "trace_id": trace_id,
            },
        )

        if corpus_size < 1:
            yield _sse(
                "error",
                {
                    "detail": (
                        "Corpus not seeded yet (0 judgments). "
                        "In Render Shell run: python scripts/seed.py --fast --incremental "
                        "&& python scripts/seed_statutes.py (~30–60 min)."
                    ),
                    "trace_id": trace_id,
                },
            )
            return

        def _produce_events() -> None:
            from services.agents.pipeline import run_pipeline_events

            try:
                for ev in run_pipeline_events(body.query.strip()):
                    loop.call_soon_threadsafe(queue.put_nowait, ev)
            except Exception as exc:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {"event": "error", "detail": str(exc), "trace_id": trace_id},
                )
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        producer = loop.run_in_executor(None, _produce_events)

        try:
            final_state: dict = {}

            while True:
                ev = await queue.get()
                if ev is None:
                    break

                if ev.get("event") == "error":
                    yield _sse("error", {k: v for k, v in ev.items() if k != "event"})
                    return

                if ev["event"] == "pipeline_done":
                    final_state = ev["state"]
                    continue

                yield _sse(ev["event"], {k: v for k, v in ev.items() if k != "event"})

            latency_ms = int(time.time() * 1000 - start_ms)

            response = _build_query_response(final_state, trace_id, latency_ms, db)
            _log_query(trace_id, body.query, final_state, latency_ms, db)
            yield _sse("answer", {"data": response.model_dump()})

        except Exception as exc:
            logger.error("stream pipeline error: %s", exc, extra={"trace_id": trace_id})
            yield _sse("error", {"detail": str(exc), "trace_id": trace_id})
        finally:
            await producer

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Trace-Id": trace_id,
        },
    )


# ── GET /api/v1/judgments/{doc_id} ────────────────────────────────────────────

@app.get("/api/v1/judgments/{doc_id}", response_model=JudgmentResponse)
def get_judgment(doc_id: str, db: Session = Depends(get_db)) -> JudgmentResponse:
    from services.api.models import Judgment

    row = db.query(Judgment).filter(Judgment.doc_id == doc_id).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Judgment {doc_id!r} not found in corpus.")

    return JudgmentResponse(
        doc_id=row.doc_id,
        case_name=row.case_name,
        citation=row.citation,
        court=row.court,
        date=str(row.date) if row.date else None,
        judges=row.judges or [],
        acts_cited=row.acts_cited or [],
        is_overruled=row.is_overruled,
        kanoon_url=row.kanoon_url,
    )


# ── GET /api/v1/judgments/{doc_id}/related ────────────────────────────────────

@app.get("/api/v1/judgments/{doc_id}/related", response_model=RelatedResponse)
def get_related(doc_id: str, db: Session = Depends(get_db)) -> RelatedResponse:
    from services.api.models import Judgment

    cites_rows = (
        db.query(JudgmentCitation)
        .filter(JudgmentCitation.citing_doc_id == doc_id)
        .all()
    )
    cited_by_rows = (
        db.query(JudgmentCitation)
        .filter(JudgmentCitation.cited_doc_id == doc_id)
        .all()
    )

    def _to_related(j_doc_id: str) -> RelatedJudgment:
        row = db.query(Judgment).filter(Judgment.doc_id == j_doc_id).first()
        return RelatedJudgment(
            doc_id=j_doc_id,
            case_name=row.case_name if row else j_doc_id,
            citation=row.citation if row else None,
            is_overruled=row.is_overruled if row else False,
        )

    return RelatedResponse(
        cites=[_to_related(r.cited_doc_id) for r in cites_rows],
        cited_by=[_to_related(r.citing_doc_id) for r in cited_by_rows],
    )


# ── POST /api/v1/feedback ─────────────────────────────────────────────────────

@app.post("/api/v1/feedback", response_model=FeedbackResponse, status_code=201)
def submit_feedback(
    body: FeedbackRequest,
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    valid_ratings = {"HELPFUL", "NOT_HELPFUL", "PARTIALLY_HELPFUL"}
    if body.rating not in valid_ratings:
        raise HTTPException(
            status_code=422, detail=f"rating must be one of {sorted(valid_ratings)}"
        )
    log = db.query(QueryLog).filter(QueryLog.id == body.trace_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="trace_id not found.")

    fb = Feedback(
        id=str(uuid.uuid4()),
        query_log_id=body.trace_id,
        rating=body.rating,
        citation_correct=body.citation_correct,
        comment=body.comment,
    )
    db.add(fb)
    db.commit()
    logger.info(
        "feedback received",
        extra={"trace_id": body.trace_id, "rating": body.rating},
    )
    return FeedbackResponse(feedback_id=fb.id)


# ── GET /api/v1/health ────────────────────────────────────────────────────────

@app.get("/api/v1/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    from services.api.models import Judgment

    corpus_size = db.query(Judgment).count()
    graph_stats = _graph_store.stats() if _graph_store is not None else {"nodes": 0, "edges": 0}

    return HealthResponse(
        status="ok",
        corpus_size=corpus_size,
        graph_nodes=graph_stats["nodes"],
        graph_edges=graph_stats["edges"],
    )


# ── GET /api/v1/eval/latest ───────────────────────────────────────────────────

@app.get("/api/v1/eval/latest", response_model=EvalLatestResponse)
def eval_latest() -> EvalLatestResponse:
    results_dir = Path("services/eval/results")
    if not results_dir.exists():
        return EvalLatestResponse(
            run_id=None, citation_accuracy=None, overruled_detection=None,
            retrieval_precision_at_5=None, adversarial_abstention=None,
        )
    report_files = sorted(results_dir.glob("*/summary.json"), reverse=True)
    if not report_files:
        return EvalLatestResponse(
            run_id=None, citation_accuracy=None, overruled_detection=None,
            retrieval_precision_at_5=None, adversarial_abstention=None,
        )
    data = json.loads(report_files[0].read_text())
    return EvalLatestResponse(**data)


# ── GET /api/v1/pipeline/meta ─────────────────────────────────────────────────

@app.get("/api/v1/pipeline/meta")
def pipeline_meta() -> dict:
    """Agent labels for UI. Step details are streamed live per query."""
    from services.agents.pipeline import get_pipeline_meta

    return {"agents": get_pipeline_meta()}

@app.get("/api/v1/admin/corpus-status")
def corpus_status(db: Session = Depends(get_db)) -> dict:
    """Corpus health + instructions for manual refresh (judgments are NOT auto-updated)."""
    from services.api.models import Judgment

    size = db.query(Judgment).count()
    graph_stats = _get_graph_store().stats()
    return {
        "corpus_size": size,
        "graph_nodes": graph_stats["nodes"],
        "graph_edges": graph_stats["edges"],
        "ready": size >= 50,
        "auto_updates": False,
        "refresh_instructions": (
            "Judgments are NOT added automatically. To expand the corpus, run locally: "
            "python scripts/seed.py --fast --incremental && python scripts/seed_statutes.py, "
            "then copy data/ to the Render disk, OR run the same commands in Render Shell."
        ),
    }


# ── Serve React frontend (production) ─────────────────────────────────────────

_frontend_dir = Path(settings.frontend_dist)
if _frontend_dir.is_dir() and (_frontend_dir / "index.html").is_file():
    _assets_dir = _frontend_dir / "assets"
    if _assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="frontend-assets")

    @app.get("/")
    def serve_spa_root() -> FileResponse:
        return FileResponse(_frontend_dir / "index.html")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str) -> FileResponse:
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(status_code=404, detail="Not found")
        candidate = _frontend_dir / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_frontend_dir / "index.html")
