# API_SPEC.md

Base URL: `http://localhost:8000/api/v1` (local) / `https://caseminds.onrender.com/api/v1` (prod)

All responses include `request_id` for tracing.

---

## POST /query

The primary endpoint. Runs the full 4-agent pipeline.

**Request:**
```json
{
  "query": "Does Section 138 NI Act apply to post-dated cheques?",
  "session_id": "optional-uuid-for-conversation-context"
}
```

**Response 200 — COMPLETE:**
```json
{
  "status": "COMPLETE",
  "answer": "Yes. Post-dated cheques are covered under Section 138 of the Negotiable Instruments Act, 1881. The Supreme Court in Rangappa v. Sri Mohan [Rangappa v. Sri Mohan, (2010) 11 SCC 441] held that a post-dated cheque, once presented on or after the date mentioned and dishonoured, attracts liability under S.138, provided the debt or legally enforceable liability exists at the time of issuance. This position was affirmed in Bir Singh v. Mukesh Kumar [Bir Singh v. Mukesh Kumar, (2019) 4 SCC 197].",
  "citations": [
    {
      "case_name": "Rangappa v. Sri Mohan",
      "citation": "(2010) 11 SCC 441",
      "court": "Supreme Court of India",
      "date": "2010-08-20",
      "kanoon_url": "https://indiankanoon.org/doc/1249564/",
      "excerpt": "A post-dated cheque is a bill of exchange...",
      "is_overruled": false
    },
    {
      "case_name": "Bir Singh v. Mukesh Kumar",
      "citation": "(2019) 4 SCC 197",
      "court": "Supreme Court of India",
      "date": "2019-01-30",
      "kanoon_url": "https://indiankanoon.org/doc/8234891/",
      "excerpt": "We reaffirm the position in Rangappa...",
      "is_overruled": false
    }
  ],
  "overruled_warnings": [],
  "confidence": 0.96,
  "query_type": "STATUTE",
  "disclaimer": "CaseMinds is a research aid. Verify all citations independently. This is not legal advice.",
  "trace_id": "uuid",
  "latency_ms": 4821
}
```

**Response 200 — LOW_CONFIDENCE:**
```json
{
  "status": "LOW_CONFIDENCE",
  "answer": "CaseMinds could not find sufficient authority in its corpus to answer this confidently. Please search Indian Kanoon directly.",
  "citations": [],
  "confidence": 0.0,
  "disclaimer": "...",
  "trace_id": "uuid"
}
```

**Response 200 — with overruled warning:**
```json
{
  "status": "COMPLETE",
  "answer": "...[⚠️ OVERRULED: Hiten P. Dalal v. Bratindranath Banerjee — verify current position]...",
  "overruled_warnings": [
    {
      "case_name": "Hiten P. Dalal v. Bratindranath Banerjee",
      "overruled_by": "Rangappa v. Sri Mohan (2010) 11 SCC 441"
    }
  ],
  "confidence": 0.88
}
```

---

## GET /judgments/{doc_id}

Fetch metadata for a specific judgment.

**Response 200:**
```json
{
  "doc_id": "1249564",
  "case_name": "Rangappa v. Sri Mohan",
  "citation": "(2010) 11 SCC 441",
  "court": "Supreme Court of India",
  "date": "2010-08-20",
  "judges": ["R.V. Raveendran", "B. Sudershan Reddy"],
  "acts_cited": ["Section 138 NI Act", "Section 139 NI Act"],
  "is_overruled": false,
  "kanoon_url": "https://indiankanoon.org/doc/1249564/"
}
```

---

## GET /judgments/{doc_id}/related

Citation graph neighbors (one-hop).

**Response 200:**
```json
{
  "cites": [
    {"doc_id": "...", "case_name": "...", "citation": "...", "is_overruled": false}
  ],
  "cited_by": [
    {"doc_id": "...", "case_name": "...", "citation": "..."}
  ]
}
```

---

## POST /feedback

User feedback on an answer.

**Request:**
```json
{
  "trace_id": "uuid",
  "rating": "HELPFUL",
  "citation_correct": true,
  "comment": "Missed Bir Singh distinction for corporate cheques"
}
```

**Response 201:** `{ "feedback_id": "uuid" }`

---

## GET /health

```json
{ "status": "ok", "corpus_size": 847, "graph_nodes": 921, "graph_edges": 3241 }
```

---

## GET /eval/latest

Latest eval run summary (for README badge + monitoring).

```json
{
  "run_id": "2026-06-15T10:00:00",
  "citation_accuracy": 0.94,
  "overruled_detection": 0.91,
  "retrieval_precision_at_5": 0.78,
  "adversarial_abstention": "10/10"
}
```

---

## Error Format

```json
{
  "error": {
    "code": "RETRIEVAL_FAILED",
    "message": "...",
    "request_id": "uuid"
  }
}
```

Standard codes: `INVALID_QUERY`, `RETRIEVAL_FAILED`, `LOW_CONFIDENCE`,
`RATE_LIMITED` (Groq API), `INTERNAL_ERROR`.
