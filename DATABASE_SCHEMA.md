# DATABASE_SCHEMA.md

CaseMinds uses three storage layers:
- **SQLite** — relational metadata, audit, feedback (via SQLAlchemy)
- **ChromaDB** — vector embeddings (persisted to `data/chroma/`)
- **NetworkX pickle** — citation graph (persisted to `data/graph.pkl`)

---

## 1. SQLite Schema

### `judgments`
Primary metadata store. Source of truth for citation verification.

| Column | Type | Notes |
|---|---|---|
| doc_id | TEXT PK | Indian Kanoon document ID |
| case_name | TEXT | "Rangappa v. Sri Mohan" |
| citation | TEXT NULLABLE | "(2010) 11 SCC 441" |
| court | TEXT | "Supreme Court of India" |
| date | DATE NULLABLE | |
| judges | JSON | list of judge names |
| acts_cited | JSON | list of act+section strings |
| is_overruled | BOOLEAN | default False |
| overruled_by_doc_id | TEXT NULLABLE FK -> judgments.doc_id | |
| kanoon_url | TEXT | |
| ingested_at | TIMESTAMP | |
| version_hash | TEXT | hash of full_text, for update detection |

### `judgment_citations`
Flattened edge table (mirrors NetworkX graph — for fast SQL queries).

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| citing_doc_id | TEXT FK -> judgments.doc_id | |
| cited_doc_id | TEXT FK -> judgments.doc_id | |
| relationship | TEXT | CITES / DISTINGUISHES / OVERRULES |
| confidence | REAL | 1.0 if regex-extracted, 0.7-0.9 if LLM-extracted |

### `query_logs`
Every pipeline run logged for tracing and eval.

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | UUID |
| query | TEXT | |
| query_type | TEXT | STATUTE/CASE_LAW/GENERAL |
| status | TEXT | COMPLETE/LOW_CONFIDENCE/NO_RESULTS |
| confidence | REAL | |
| answer | TEXT | |
| cited_doc_ids | JSON | list of doc_ids in final answer |
| retrieval_scores | JSON | top-5 chunk scores |
| latency_ms | INTEGER | |
| model_used | TEXT | |
| groq_tokens_in | INTEGER | |
| groq_tokens_out | INTEGER | |
| created_at | TIMESTAMP | |

### `feedback`
| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | UUID |
| query_log_id | TEXT FK -> query_logs.id | |
| rating | TEXT | HELPFUL/NOT_HELPFUL/PARTIALLY_HELPFUL |
| citation_correct | BOOLEAN NULLABLE | |
| comment | TEXT NULLABLE | |
| created_at | TIMESTAMP | |

### Alembic Migrations

`services/api/migrations/` — standard Alembic structure.

```bash
alembic upgrade head    # in Makefile as `make migrate`
```

---

## 2. ChromaDB Schema

**Collection:** `caseminds_clauses_v1`

```python
client.create_collection(
    name="caseminds_clauses_v1",
    metadata={"hnsw:space": "cosine", "hnsw:construction_ef": 200}
)
```

**Document format (per chunk):**
- `id`: `{doc_id}_chunk_{n}` (deterministic, enables idempotent upsert)
- `document`: chunk text (400 tokens, 50-token overlap)
- `embedding`: bge-small-en-v1.5 (384 dimensions)
- `metadata`:
  ```json
  {
    "doc_id": "1249564",
    "case_name": "Rangappa v. Sri Mohan",
    "citation": "(2010) 11 SCC 441",
    "court": "Supreme Court of India",
    "date": "2010-08-20",
    "acts_cited": ["S.138 NI Act", "S.139 NI Act"],
    "is_overruled": false,
    "chunk_index": 2,
    "chunk_total": 8
  }
  ```

**Retrieval filters used:**
- `acts_cited` contains query statute ref (when statute_refs detected)
- `is_overruled = false` (default — overruled cases excluded from primary retrieval)
- `court` = "Supreme Court of India" (V1 — adds HC when corpus expands)

---

## 3. NetworkX Graph Schema

```python
# Node attributes
G.nodes["1249564"] == {
    "type": "judgment",
    "case_name": "Rangappa v. Sri Mohan",
    "citation": "(2010) 11 SCC 441",
    "court": "Supreme Court of India",
    "date": "2010-08-20",
    "is_overruled": False,
    "overruled_by": None,
}

# Edge attributes
G.edges["old_doc_id", "1249564"] == {
    "rel": "CITES",           # CITES / DISTINGUISHES / OVERRULES
    "confidence": 1.0,
    "extracted_by": "regex",  # or "llm"
}
```

**Graph persistence:**
```python
# Save
with open("data/graph.pkl", "wb") as f:
    pickle.dump(G, f, protocol=pickle.HIGHEST_PROTOCOL)

# Load
with open("data/graph.pkl", "rb") as f:
    G = pickle.load(f)
```

Load time for 10K nodes, 50K edges: ~0.3s.

---

## 4. BM25 Index

```python
# Stored as pickled BM25Okapi object
# data/bm25.pkl contains:
{
    "index": BM25Okapi(tokenized_corpus),
    "doc_ids": [...],      # parallel list — index i → doc_id
    "chunk_ids": [...],    # parallel list — index i → chunk_id
    "texts": [...],        # parallel list — for excerpt retrieval
    "built_at": "2026-06-15T10:00:00"
}
```

Rebuilt on any new ingestion. Incremental rebuild (only new chunks) planned
for V2 when corpus exceeds 10K judgments.
