# CaseMinds — Deploy Guide

## Quick answers

| Question | Answer |
|---|---|
| **Do judgments auto-update?** | **No.** Corpus is built by `scripts/seed.py`. You must re-run seed manually (locally or on Render Shell). |
| **Why LOW_CONFIDENCE?** | The LLM sometimes cites wrong doc_ids; unverified cites are stripped. Status is `COMPLETE` when ≥1 citation verifies. Set `VERIFICATION_THRESHOLD=0.50` in env. |
| **What gets deployed?** | One Render service: FastAPI API + React UI (built from `frontend/`). |

---

## Local (dev)

```bash
# Terminal 1 — API
make run                    # http://localhost:8080

# Terminal 2 — React UI (hot reload)
make frontend               # http://localhost:5173

# Or serve UI from API (production-like):
cd frontend && npm run build
make run                    # http://localhost:8080 serves UI + API
```

---

## Render deploy (free tier)

### 1. Push to GitHub

Ensure `frontend/package-lock.json` is committed (run `npm install` in `frontend/` once).

### 2. Create Render Web Service

- Connect your GitHub repo
- **Blueprint:** use `render.yaml` (or manual settings below)
- **Build:** `cd frontend && npm ci && npm run build && cd .. && pip install poetry && poetry install --no-dev`
- **Start:** `uvicorn services.api.main:app --host 0.0.0.0 --port $PORT`
- **Health check:** `/api/v1/health`
- **Disk:** 1 GB mounted at `/app/data`

### 3. Environment variables (Render dashboard)

| Variable | Value |
|---|---|
| `GROQ_API_KEY` | your key |
| `INDIAN_KANOON_API_KEY` | your key |
| `DATABASE_URL` | `sqlite:////app/data/caseminds.db` |
| `CHROMA_PERSIST_DIR` | `/app/data/chroma` |
| `GRAPH_PATH` | `/app/data/graph.pkl` |
| `BM25_PATH` | `/app/data/bm25.pkl` |
| `VERIFICATION_THRESHOLD` | `0.50` |
| `VERIFICATION_MIN_VERIFIED` | `1` |
| `ENVIRONMENT` | `production` |

### 4. Seed corpus on Render (one-time, required)

Render starts with an **empty disk**. Judgments do not appear automatically.

**Option A — Render Shell (recommended first deploy):**

```bash
# In Render dashboard → Shell
python scripts/seed.py --fast --incremental
python scripts/seed_statutes.py
```

Takes ~30–60 min on free tier. Data persists on the 1 GB disk.

**Option B — Upload from local:**

```bash
# Local machine (after make seed locally)
# Copy data/caseminds.db, data/chroma/, data/graph.pkl, data/bm25.pkl
# to Render disk via Shell or rsync/scp if available
```

**Option C — Incremental updates later:**

```bash
python scripts/seed.py --fast --incremental   # skips existing doc_ids
python scripts/seed_statutes.py
```

There is **no cron job** on Render free tier — schedule manual re-seeds or upgrade to a paid cron worker.

### 5. Verify deploy

```bash
curl https://YOUR-APP.onrender.com/api/v1/health
curl https://YOUR-APP.onrender.com/api/v1/admin/corpus-status
```

Open `https://YOUR-APP.onrender.com/` for the React UI.

---

## Confidence / LOW_CONFIDENCE

Status logic (after fix):

- `COMPLETE` if **≥1 citation** verifies against SQLite **or** confidence ≥ `VERIFICATION_THRESHOLD`
- `LOW_CONFIDENCE` only when **zero** citations verify, or model returns `INSUFFICIENT_CONTEXT`

Update your `.env.local`:

```
VERIFICATION_THRESHOLD=0.50
VERIFICATION_MIN_VERIFIED=1
```

Restart API after changing env.

---

## Cold start

Render free tier sleeps after 15 min idle. First request after sleep takes ~30s (loads ChromaDB + graph). Normal for portfolio demos.
