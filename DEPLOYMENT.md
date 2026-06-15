# DEPLOYMENT.md

## Philosophy

Zero cost, one command deploy. No credit card. No Docker registry.
No Kubernetes. The entire system — SQLite, ChromaDB, NetworkX graph,
BM25 index — persists on Render's free 1GB disk.

## Local Development

```bash
# 1. Clone and install
git clone https://github.com/harshit21-shah/caseminds
cd caseminds
cp .env.example .env.local
# Fill in GROQ_API_KEY and INDIAN_KANOON_API_KEY

# 2. Install dependencies
pip install poetry
poetry install

# 3. Build corpus (first run ~8-12 min)
make seed
# Downloads ~500 judgments, builds graph, embeds, indexes

# 4. Run API
make run
# → http://localhost:8000

# 5. Run Streamlit UI (V1)
make ui
# → http://localhost:8501
```

## Render Deployment (Free Tier)

### Setup (one-time)

1. Push repo to GitHub.
2. Go to render.com → New → Web Service → Connect GitHub repo.
3. Set:
   - **Build Command:** `pip install poetry && poetry install --no-dev`
   - **Start Command:** `uvicorn services.api.main:app --host 0.0.0.0 --port $PORT`
   - **Python Version:** 3.12
4. Add a **Disk** (under Advanced):
   - Name: `caseminds-data`
   - Mount Path: `/app/data`
   - Size: 1 GB (free)
5. Set environment variables in Render dashboard:
   - `GROQ_API_KEY`
   - `INDIAN_KANOON_API_KEY`
   - `ANTHROPIC_API_KEY` (optional)
   - `DATABASE_URL=sqlite:////app/data/caseminds.db`
   - `CHROMA_PERSIST_DIR=/app/data/chroma`
   - `GRAPH_PATH=/app/data/graph.pkl`
   - `BM25_PATH=/app/data/bm25.pkl`

### `render.yaml` (Infrastructure as Code)

```yaml
services:
  - type: web
    name: caseminds-api
    runtime: python
    region: oregon
    plan: free
    buildCommand: pip install poetry && poetry install --no-dev
    startCommand: uvicorn services.api.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: GROQ_API_KEY
        sync: false
      - key: INDIAN_KANOON_API_KEY
        sync: false
      - key: DATABASE_URL
        value: sqlite:////app/data/caseminds.db
      - key: CHROMA_PERSIST_DIR
        value: /app/data/chroma
      - key: GRAPH_PATH
        value: /app/data/graph.pkl
      - key: BM25_PATH
        value: /app/data/bm25.pkl
      - key: MIN_RETRIEVAL_SCORE
        value: "0.30"
      - key: VERIFICATION_THRESHOLD
        value: "0.85"
    disk:
      name: caseminds-data
      mountPath: /app/data
      sizeGB: 1
    healthCheckPath: /api/v1/health
```

### Seeding on Render (first deploy only)

Render free tier has no cron job support. Seed the corpus locally and
upload the pre-built data files:

```bash
# Local: build corpus
make seed

# Upload to Render disk via their shell (Render dashboard → Shell tab):
# Or: commit data files to a private S3 bucket and download on startup

# Alternative (simplest): add a /admin/seed endpoint (protected by a
# secret header) that triggers seeding on first deploy.
```

The simplest approach for portfolio: commit a small pre-built corpus
(50 judgments) to the repo in `data/seed/` and have startup copy it
to the disk mount if `data/caseminds.db` doesn't exist.

## CI/CD (GitHub Actions)

### `.github/workflows/ci.yml`
```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install poetry && poetry install
      - run: make lint
      - run: make typecheck
      - run: make test
```

### `.github/workflows/eval.yml`
```yaml
name: Eval Gate
on:
  push:
    paths: ["services/agents/**", "services/retrieval/**"]
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install poetry && poetry install
      - run: make eval-citations
        env:
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
      - run: python scripts/check_eval_regression.py
```

## Makefile

```makefile
.PHONY: install lint typecheck test seed run ui eval-citations

install:
	poetry install

lint:
	ruff check services/ tests/
	black --check services/ tests/

typecheck:
	mypy --strict services/

test:
	pytest tests/unit tests/integration -v

seed:
	python scripts/seed.py

run:
	uvicorn services.api.main:app --reload --port 8000

ui:
	streamlit run services/ui/app.py

eval-citations:
	pytest tests/eval/test_citation_accuracy.py -v
```

## Monitoring (zero-cost)

- `/api/v1/health` — returns corpus size + graph stats. Uptime monitored
  free via UptimeRobot (no account required for basic pings).
- Query logs in SQLite `query_logs` table — viewable via
  `sqlite3 data/caseminds.db "SELECT * FROM query_logs ORDER BY created_at DESC LIMIT 20"`.
- Render dashboard shows request logs, memory usage, CPU.
- No Langfuse/LangSmith in V1 — plain JSON structured logs to stdout,
  visible in Render's log viewer.

## Cold Start Warning

Render free tier spins down after 15 min of inactivity. First request after
spin-down takes ~30s (ChromaDB + NetworkX graph load). Add a note in the UI:
"Loading model... (first request may take 30s)" — this is fine for a portfolio
demo and shows production awareness.
