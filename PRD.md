# PRD.md — Product Requirements Document

## 1. Vision

Give every independent lawyer in India the research capability of a BigLaw
associate with a Westlaw subscription — at zero cost, in plain English, with
citations they can trust.

## 2. Target Users

| Persona | Description | Primary Pain |
|---|---|---|
| **Solo Advocate** | Independent practitioner, district/HC level, 5–20 years experience | Spends hours on manual case research per filing |
| **Junior Associate** | 0–3 years at a small firm, assigned research tasks | No access to premium tools, relies on seniors |
| **Law Student (Moot)** | Preparing moot arguments, needs precedent chains | Overwhelming volume, no structured citation traversal |

## 3. Core Problem (detailed)

Three layers of difficulty in Indian legal research:

**Layer 1 — Volume:** Indian Kanoon has 2M+ documents. SC alone publishes
~800 judgments/month. No solo practitioner can monitor this.

**Layer 2 — Citation chains:** Indian judgments cite and distinguish previous
judgments recursively. To know the current legal position on any point, you
must trace the full chain — "Rangappa v. Sri Mohan (2010) distinguished in
Bir Singh v. Mukesh Kumar (2019) which is now the binding position." Keyword
search cannot do this.

**Layer 3 — Overruled/distinguished cases:** A judgment retrieved by keyword
may have been explicitly overruled by a later bench. Using it in a brief
without knowing this is a professional error.

## 4. Goals

### V1 (MVP — 3 weeks)
- Ingest 500+ Supreme Court judgments (NI Act, IPC common sections) from
  Indian Kanoon API (free, public).
- Hybrid retrieval: dense semantic + BM25 exact-match for statute references.
- Citation graph (NetworkX): judgment → cites → judgment.
- Basic answer generation (Groq) with cited judgment IDs.
- Streamlit UI (fast to ship, looks professional).
- 30-case golden eval set with citation accuracy measurement.

### V2 (weeks 4–6)
- Overruled/distinguished detection in graph traversal.
- High Court judgments for 2–3 HCs (Bombay, Delhi, Madras).
- Query classification (statute lookup / case law / general principle).
- CrossEncoder reranking.
- FastAPI backend + proper frontend (replace Streamlit).
- Verification Agent as hard gate.

### Non-Goals (V1)
- No pleading drafting.
- No case outcome prediction.
- No filing/e-court integration.
- Not a substitute for a lawyer's judgment — product explicitly says so.

## 5. User Stories

1. As a solo advocate, I type "cheque bounce limitation period" and get a
   cited answer with SC judgment references I can verify, in under 10 seconds.
2. As a junior associate, I ask "is XYZ case still good law?" and the system
   tells me if it's been overruled or distinguished.
3. As a user, I click any cited case name and see the source excerpt + a link
   to the full judgment on Indian Kanoon.
4. As a user, when the system is uncertain, it says so clearly rather than
   fabricating a confident-sounding wrong answer.

## 6. Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-1 | Ingest and index SC judgments from Indian Kanoon API | P0 |
| FR-2 | BM25 + dense hybrid retrieval for queries | P0 |
| FR-3 | Citation graph traversal (multi-hop, up to 3 hops) | P0 |
| FR-4 | Groq LLM answer generation with inline citation tags | P0 |
| FR-5 | Verification: every cited judgment confirmed in corpus | P0 |
| FR-6 | 30-case golden eval set + citation accuracy measurement | P0 |
| FR-7 | Overruled/distinguished detection via graph metadata | P1 |
| FR-8 | Query classifier (statute / case / general) routing | P1 |
| FR-9 | CrossEncoder reranking of top-k results | P1 |
| FR-10 | HC judgment ingestion (Bombay, Delhi, Madras) | P2 |
| FR-11 | Source excerpt display + Indian Kanoon deep link | P1 |
| FR-12 | LOW_CONFIDENCE abstention when retrieval is weak | P0 |

## 7. Non-Functional Requirements

- **Citation accuracy:** ≥90% on 30-case golden set (every cited judgment
  must exist in corpus and support the stated proposition).
- **Latency:** Answers in <12s p95 (Groq is fast; retrieval + graph adds ~2s).
- **Abstention:** System must output LOW_CONFIDENCE and decline to answer
  rather than hallucinate when retrieval score is below threshold.
- **Disclaimer:** Every response includes: *"CaseMinds is a research aid. Verify
  all citations independently. This is not legal advice."*

## 8. Success Metrics

- Citation accuracy ≥ 90% at launch, ≥ 94% at V2.
- Overruled detection ≥ 88%.
- Retrieval precision@5 ≥ 75%.
- System abstains (LOW_CONFIDENCE) rather than hallucinating on adversarial queries.
