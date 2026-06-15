# TASKS.md

Task IDs: `CM-<phase>-<num>`. Reference in commits.

## Phase 0 — Foundations (Day 1-2)

- [ ] `CM-0-01` Scaffold repo structure per CLAUDE.md
- [ ] `CM-0-02` `pyproject.toml` with all dependencies
- [ ] `CM-0-03` `.env.example`, `Makefile`, `docker-compose.yml` (optional)
- [ ] `CM-0-04` SQLite schema + Alembic init + `make migrate`
- [ ] `CM-0-05` ChromaDB collection setup script
- [ ] `CM-0-06` `llm_client.py` (Groq primary, Claude Haiku fallback, cost log)
- [ ] `CM-0-07` GitHub Actions CI skeleton (lint + typecheck + test)
- [ ] `CM-0-08` `render.yaml`

## Phase 1 — Data Pipeline (Day 3-6)

- [ ] `CM-1-01` Indian Kanoon scraper (`services/ingestion/scraper.py`)
- [ ] `CM-1-02` Judgment parser → `ParsedJudgment` Pydantic model
- [ ] `CM-1-03` Citation extractor (regex pass 1)
- [ ] `CM-1-04` LLM citation extractor (Groq, batch, pass 2)
- [ ] `CM-1-05` Overruled detection (phrase patterns)
- [ ] `CM-1-06` SQLite upsert for `judgments` + `judgment_citations` tables
- [ ] `CM-1-07` NetworkX graph builder + pickle persist
- [ ] `CM-1-08` BM25 index builder + pickle persist
- [ ] `CM-1-09` ChromaDB embedder (bge-small, chunk + upsert)
- [ ] `CM-1-10` `scripts/seed.py` end-to-end seed script
- [ ] `CM-1-11` Unit tests for parser + citation extractor (20 fixture judgments)

## Phase 2 — Retrieval Layer (Day 7-9)

- [ ] `CM-2-01` BM25 search function
- [ ] `CM-2-02` ChromaDB dense search function with metadata filters
- [ ] `CM-2-03` RRF fusion (BM25 + dense → top-25)
- [ ] `CM-2-04` CrossEncoder reranker (ms-marco-MiniLM-L-6-v2)
- [ ] `CM-2-05` Hybrid search orchestrator (`services/retrieval/search.py`)
- [ ] `CM-2-06` Graph traversal (`services/graph/graph_store.py`) — BFS, overruled flag
- [ ] `CM-2-07` Retrieval eval: 20 queries, precision@5 (target ≥75%)

## Phase 3 — Agent Pipeline (Day 10-15)

- [ ] `CM-3-01` LangGraph state schema (`PipelineState`)
- [ ] `CM-3-02` Query Classifier Agent + prompt v1
- [ ] `CM-3-03` Retrieval Agent (calls hybrid search)
- [ ] `CM-3-04` Graph Traversal Agent (calls graph_store.traverse)
- [ ] `CM-3-05` Verification + Answer Agent + prompt v1
- [ ] `CM-3-06` Verification gate (SQLite lookup, overruled flagging, strip unverified)
- [ ] `CM-3-07` LOW_CONFIDENCE + NO_RESULTS handling
- [ ] `CM-3-08` Full pipeline wiring in LangGraph
- [ ] `CM-3-09` FastAPI `/query` endpoint
- [ ] `CM-3-10` FastAPI `/judgments/{doc_id}` + `/related` endpoints
- [ ] `CM-3-11` Agent unit tests (mock retrievals, verify gate behavior)

## Phase 4 — UI + Eval + Deploy (Day 16-21)

- [ ] `CM-4-01` Streamlit UI (`services/ui/app.py`) — query box, answer, citations panel
- [ ] `CM-4-02` Citation cards in UI (case name, citation, excerpt, kanoon link)
- [ ] `CM-4-03` Overruled warning display (amber banner)
- [ ] `CM-4-04` LOW_CONFIDENCE display (grey, abstention message)
- [ ] `CM-4-05` 30-case golden eval set (`services/eval/datasets/golden_qa.json`)
- [ ] `CM-4-06` Citation accuracy eval harness (`tests/eval/test_citation_accuracy.py`)
- [ ] `CM-4-07` Overruled detection eval (15-case set)
- [ ] `CM-4-08` Adversarial hallucination set (10 cases)
- [ ] `CM-4-09` GitHub Actions eval gate
- [ ] `CM-4-10` Render deploy + smoke test
- [ ] `CM-4-11` README: demo GIF, eval badge, quickstart
- [ ] `CM-4-12` `/api/v1/feedback` endpoint + SQLite store
- [ ] `CM-4-13` `/api/v1/eval/latest` endpoint

## Phase 5 — V2 Polish (Week 4-6, post-MVP)

- [ ] `CM-5-01` HC judgment ingestion (Bombay + Delhi)
- [ ] `CM-5-02` Query type routing refinement (statute vs case vs general)
- [ ] `CM-5-03` Next.js frontend (replace Streamlit)
- [ ] `CM-5-04` Langfuse tracing integration
- [ ] `CM-5-05` Raise citation accuracy target to 94%
- [ ] `CM-5-06` RESUME_IMPACT.md with final metrics
