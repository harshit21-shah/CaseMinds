# TECH_STACK.md

## Stack at a Glance

| Layer | Technology | Cost | Why |
|---|---|---|---|
| LLM (generation) | Groq Llama 3.3 70B | Free tier | <150ms first token, free, good reasoning |
| LLM (classifier) | Groq Llama 3.3 8B | Free tier | Tiny task, structured output |
| LLM (fallback) | Claude Haiku (Anthropic) | Pay-per-use | If Groq down |
| Embeddings | BAAI/bge-small-en-v1.5 | Free (local) | 33MB, CPU-friendly, strong semantic quality |
| Sparse retrieval | rank-bm25 (BM25Okapi) | Free (local) | Exact statute/citation matching |
| Vector store | ChromaDB (persistent) | Free (local) | No infra, persists to disk |
| Reranker | cross-encoder/ms-marco-MiniLM-L-6-v2 | Free (local) | Cheap, effective, fits CPU |
| Graph | NetworkX (in-memory, pickle) | Free (local) | No infra, 10K-50K nodes fits in RAM |
| Relational DB | SQLite | Free (local) | Metadata, audit, feedback — zero ops |
| Backend | FastAPI (async, Python 3.12) | Free | Standard, well-known by interviewers |
| UI (V1) | Streamlit | Free | Ships in hours |
| UI (V2) | Next.js + Tailwind | Free | Replace Streamlit post-MVP |
| Deployment | Render (free tier) | Free | Persistent disk for SQLite + ChromaDB |
| CI | GitHub Actions | Free | Lint + typecheck + eval gate |
| Tracing | Simple JSON logs (→ Langfuse in V2) | Free | Trace every agent run for debugging |

## Why These Choices Beat the "Enterprise" Stack Here

**ChromaDB over Qdrant:** For 500–10K judgment chunks, ChromaDB is
indistinguishable in quality from Qdrant. The difference matters at 1M+ chunks.
Using ChromaDB removes one infra dependency, keeps the repo runnable with
`git clone && make seed && make run` on any machine.

**NetworkX over Neo4j:** The Indian Supreme Court citation graph for 500–10K
judgments has at most ~30K nodes and ~100K edges. NetworkX holds this in
~50MB RAM, saves/loads via pickle in <1s. Cypher queries are cleaner for
complex traversals, but BFS in Python is readable, testable, and zero-cost.
The architecture note in ARCHITECTURE.md explains the production swap path.

**Groq over OpenAI:** Groq's free tier is genuinely generous and the latency
(~150ms first token for 70B) is better than OpenAI for chat UX. For a
portfolio project demonstrating production awareness, noting "I chose Groq
for its inference speed characteristics" is a strong signal.

**rank-bm25 over Elasticsearch:** BM25 for 500–10K documents fits in memory
as a pickled object. Elasticsearch needs Docker, JVM, 512MB RAM minimum.
For a portfolio project demoed on Render free tier, this is the correct call.

## Local Model Sizes (ensure your machine can run these)

| Model | Size | RAM Required |
|---|---|---|
| BAAI/bge-small-en-v1.5 | 33MB | ~200MB |
| cross-encoder/ms-marco-MiniLM-L-6-v2 | 85MB | ~300MB |
| Both together | ~120MB | ~500MB |

These run comfortably on any 4GB+ RAM machine. No GPU required.

## Python Dependencies (`pyproject.toml`)

```toml
[tool.poetry.dependencies]
python = "^3.12"

# API
fastapi = "^0.115"
uvicorn = "^0.32"
streamlit = "^1.40"

# AI / RAG
langchain-groq = "^0.2"
langgraph = "^0.2"
chromadb = "^0.6"
sentence-transformers = "^3.3"
rank-bm25 = "^0.2"

# Graph
networkx = "^3.4"

# Data / Parsing
httpx = "^0.28"
pydantic = "^2.10"
pydantic-settings = "^2.7"
rapidfuzz = "^3.10"       # fuzzy citation matching
python-dotenv = "^1.0"

# DB
sqlalchemy = "^2.0"       # SQLite ORM
alembic = "^1.14"

# Eval
ragas = "^0.2"            # optional, for faithfulness metrics

[tool.poetry.dev-dependencies]
pytest = "^8.3"
ruff = "^0.8"
black = "^24.10"
mypy = "^1.13"
pytest-asyncio = "^0.24"
```

## Environment Variables (`.env.example`)

```bash
# Required
GROQ_API_KEY=your_groq_api_key_here
INDIAN_KANOON_API_KEY=your_kanoon_api_key_here   # free at indiankanoon.org

# Optional (fallback LLM)
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Config
DATABASE_URL=sqlite:///./data/caseminds.db
CHROMA_PERSIST_DIR=./data/chroma
GRAPH_PATH=./data/graph.pkl
BM25_PATH=./data/bm25.pkl
MIN_RETRIEVAL_SCORE=0.30
VERIFICATION_THRESHOLD=0.85
LOG_LEVEL=INFO
```
