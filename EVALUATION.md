# EVALUATION.md

## 1. Why Evaluation Matters More Here

In a legal tool, a wrong citation isn't just a quality problem — it's a
professional liability issue. The eval suite is the only thing that stands
between "impressive portfolio project" and "tool that gets a lawyer sanctioned."

## 2. Eval Layers

### Layer 1 — Unit Tests (every commit)
- Parser: correct extraction of citation, judges, acts_cited from 20 sample judgments.
- Citation extractor: known citation patterns correctly identified.
- Graph traversal: BFS returns correct nodes, cycle guard works, limit enforced.
- Verification gate: unverified doc_ids are stripped, not passed through.

### Layer 2 — Retrieval Eval

**Metric:** Precision@5 — for a given query, how many of the top-5 retrieved chunks are actually relevant?

**Dataset:** 20 queries with manually labeled relevant doc_ids.

```python
# services/eval/retrieval_eval.py
def eval_retrieval(queries: list[EvalQuery]) -> RetrievalMetrics:
    precision_scores = []
    for q in queries:
        results = hybrid_search(q.query, q.statute_refs, "HYBRID_EQUAL")
        retrieved_ids = {r.doc_id for r in results}
        relevant_ids = set(q.relevant_doc_ids)
        precision = len(retrieved_ids & relevant_ids) / len(retrieved_ids)
        precision_scores.append(precision)
    return RetrievalMetrics(precision_at_5=mean(precision_scores))
```

**Target:** Precision@5 ≥ 75%.

### Layer 3 — Citation Accuracy Benchmark (the headline metric)

**Definition:** For every citation `[CaseName, Citation]` in a generated
answer, the cited judgment must:
1. Exist in the corpus (hard check — SQLite lookup).
2. Actually support the proposition it's cited for (soft check — LLM judge).

**Dataset:** 30-case golden set (`services/eval/datasets/golden_qa.json`):

```json
[
  {
    "id": "NI_001",
    "query": "Does Section 138 NI Act apply to post-dated cheques?",
    "expected_citations": ["doc_id_rangappa_2010", "doc_id_bir_singh_2019"],
    "expected_answer_contains": ["post-dated", "Section 138", "legally enforceable debt"],
    "should_not_cite": ["doc_id_overruled_xyz"]
  }
]
```

**Evaluation process:**
1. Run full pipeline on each golden query.
2. Hard check: every cited doc_id exists in SQLite → Citation Existence Rate.
3. Soft check: LLM judge (`claude-haiku`): "Does this excerpt from
   [case] support this proposition?" → Entailment Rate.
4. Overruled check: no overruled judgment presented as current good law.

```
Citation Accuracy = Citation Existence Rate × Entailment Rate
```

**Target:** ≥ 90% at V1, ≥ 94% at V2.

### Layer 4 — Overruled Detection Eval

**Dataset:** 15 queries where the most "obvious" retrieved case is actually
overruled by a later SC judgment (curated manually).

**Metric:** What % of overruled cases are flagged with `⚠️ OVERRULED:` rather
than presented silently as current law?

**Target:** ≥ 88%.

### Layer 5 — Adversarial / Hallucination Set

10 queries designed to induce hallucination:
- Queries about fictional cases with real-sounding names ("XYZ v. ABC 2023 SCC").
- Queries where no relevant case exists in corpus (system must abstain).
- Queries with conflicting retrieval results (system must surface uncertainty).

**Target:** 0 confident wrong answers. System must output `LOW_CONFIDENCE` on
all adversarial queries. Any confident hallucination = release blocker.

## 3. Golden Set Construction Methodology

(Document this even for a portfolio project — interviewers ask.)

1. Select 30 real legal questions across 5 act categories (NI Act, IPC, CPC,
   Specific Relief Act, Hindu Marriage Act).
2. Research each question manually on Indian Kanoon to find ground-truth cases.
3. For each question, record: correct cases, key propositions, cases that must
   NOT be cited (overruled / irrelevant).
4. Have a second pass: re-verify each ground-truth case is actually cited for
   the right proposition (not just tangentially related).
5. Store in `services/eval/datasets/golden_qa.json` (versioned).

## 4. CI Eval Gate

```yaml
# .github/workflows/eval.yml
on:
  push:
    paths: ["services/agents/**", "services/retrieval/**"]

jobs:
  eval:
    steps:
      - run: make eval-citations
      - run: python scripts/check_eval_regression.py
        # fails if citation_accuracy < 0.90 OR overruled_detection < 0.88
```

## 5. Reporting

After each eval run, generate `services/eval/results/<timestamp>/report.md`:

```markdown
## Eval Run — 2026-06-15

| Metric | Score | Target | Status |
|---|---|---|---|
| Citation existence rate | 97% | 100% | ✅ |
| Entailment rate | 94% | 90% | ✅ |
| Citation accuracy (combined) | 91% | 90% | ✅ |
| Overruled detection | 91% | 88% | ✅ |
| Adversarial abstention | 10/10 | 10/10 | ✅ |
| Retrieval precision@5 | 78% | 75% | ✅ |
```

Pin the latest report badge to README.

## 6. Online / Production Eval

Once deployed:
- Sample 10% of queries, run async citation-existence check (non-LLM, fast).
- Alert (Slack/email) if existence rate drops below 95% over any 24h window.
- User feedback button ("Was this citation correct?") → stores in SQLite
  `feedback` table → reviewed weekly.
