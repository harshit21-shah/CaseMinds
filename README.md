# ⚖️ CaseMinds

> GraphRAG legal research assistant for Indian law.
> Answers natural-language legal queries with verified SC/HC judgment citations.

<!-- Eval badge — auto-updated by CI -->
<!-- ![Citation Accuracy](https://img.shields.io/badge/citation_accuracy-pending-lightgrey) -->

---

## What it does

1. You ask a legal question: *"Does Section 138 NI Act apply to post-dated cheques?"*
2. CaseMinds retrieves relevant SC judgments via **BM25 + dense hybrid search**
3. Expands context via a **NetworkX citation graph** (2-hop traversal)
4. Detects any **overruled cases** on the traversal path
5. Generates a grounded answer with `[CITE:doc_id]` tags
6. **Verifies every citation** against SQLite before the answer reaches you
7. Returns answer with formatted citations, overruled warnings, and confidence score

**Core invariant:** Every cited judgment is verified to exist in the corpus. The system abstains (`LOW_CONFIDENCE`) rather than hallucinating.

---

## Quick start

```bash
# 1. Clone
git clone https://github.com/your-username/caseminds
cd caseminds

# 2. Configure
cp .env.example .env.local
# Fill in GROQ_API_KEY (free at console.groq.com)
# Fill in INDIAN_KANOON_API_KEY (free at indiankanoon.org)

# 3. Install
pip install poetry && poetry install

# 4. Build corpus (~8-12 min first time)
make seed

# 5. Run API
make run        # → http://localhost:8000

# 6. Run UI
make ui         # → http://localhost:8501
```

---

## Architecture

```
User → Streamlit UI → FastAPI
                        ↓
              QueryClassifier (Groq 8B)
                        ↓
              RetrievalAgent (BM25 + ChromaDB + CrossEncoder)
                        ↓
              GraphTraversal (NetworkX, 2-hop BFS)
                        ↓
              VerificationAnswer (Groq 70B + SQLite hard gate)
                        ↓
              Verified answer with citations
```

## Eval metrics (latest run)

| Metric | Score | Target |
|---|---|---|
| Citation accuracy | — | ≥ 90% |
| Overruled detection | — | ≥ 88% |
| Retrieval Precision@5 | — | ≥ 75% |
| Adversarial abstention | — | 10/10 |

Run `make eval-all` to reproduce.

---

## Tech stack

| Layer | Technology |
|---|---|
| LLM | Groq Llama 3.3 70B / 8B (free tier) |
| Embeddings | BAAI/bge-small-en-v1.5 (local, 33MB) |
| Vector store | ChromaDB (local, persistent) |
| Sparse retrieval | rank-bm25 (BM25Okapi) |
| Reranker | cross-encoder/ms-marco-MiniLM-L-6-v2 |
| Citation graph | NetworkX (in-memory pickle) |
| Relational DB | SQLite + SQLAlchemy + Alembic |
| Agent pipeline | LangGraph |
| API | FastAPI |
| UI | Streamlit (V1) |
| Deployment | Render free tier |

---

## Project structure

```
services/
├── ingestion/      # scraper, parser, citation extractor, embedder
├── graph/          # NetworkX graph store + traversal
├── retrieval/      # BM25 + ChromaDB + CrossEncoder hybrid search
├── agents/         # LangGraph 4-agent pipeline
│   ├── prompts/    # versioned .txt prompt files
│   └── tools/      # LangGraph tool definitions
├── api/            # FastAPI app + SQLAlchemy models + Alembic
├── eval/           # eval harness + golden datasets
└── ui/             # Streamlit app
```

---

## Development

```bash
make lint          # ruff + black check
make typecheck     # mypy --strict
make test          # unit + integration tests
make eval-all      # full eval suite
```

---

*CaseMinds is a research aid. Verify all citations independently. Not legal advice.*
