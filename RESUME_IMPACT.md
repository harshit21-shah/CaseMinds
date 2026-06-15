# RESUME_IMPACT.md

## Resume Bullets (use once metrics are real)

1. Built CaseMinds — a GraphRAG legal research assistant (LangGraph, ChromaDB,
   NetworkX citation graph) achieving **[X]% citation accuracy** on a 30-case
   golden benchmark — every cited judgment verified to exist in corpus and
   support the stated proposition.

2. Engineered **hybrid retrieval** (BM25 exact-match + dense semantic +
   CrossEncoder reranking) — BM25 mandatory for exact statute references
   ("Section 138 NI Act") where pure semantic retrieval produces section-wrong
   results; hybrid cuts irrelevant retrievals by [X]% vs dense-only baseline.

3. Built **overruled-case detection** via NetworkX graph traversal — system
   flags judgments marked `OVERRULED_BY` in the citation graph before
   presenting them as current law, achieving [X]% detection rate on a 15-case
   adversarial set.

4. Implemented a **hard-gated Verification Agent** that strips any cited
   judgment not confirmed in SQLite — 0 unverified citations reach users;
   system abstains (`LOW_CONFIDENCE`) rather than hallucinating when retrieval
   confidence is below threshold.

5. Designed a **30-case golden evaluation set** (curated against Indian Kanoon
   ground truth) with citation accuracy, overruled detection, and adversarial
   abstention metrics — CI-gated to block deployment on regression.

## One-Liner (space-tight)

> CaseMinds: GraphRAG Indian legal research assistant — BM25+dense hybrid
> retrieval, NetworkX citation graph with overruled-case detection,
> hard-gated citation verification; [X]% citation accuracy on 30-case eval.

## Interview Talking Points

**"Why not just use ChatGPT for legal research?"**
> ChatGPT will confidently cite cases that don't exist — this is documented
> and has resulted in lawyer sanctions. CaseMinds has a verification gate that
> checks every citation against a real corpus before the answer reaches the
> user. The system abstains rather than guesses.

**"Why BM25 alongside dense retrieval?"**
> "Section 138 NI Act" is an exact statutory reference. Dense embeddings find
> semantically similar content — which might be Section 138 of a different Act,
> or a judgment about NI Act generally without hitting Section 138 specifically.
> BM25 finds exact matches. For legal statute queries, the precision difference
> is significant. I measured this: [X]% precision@5 degradation when removing
> BM25 from the hybrid.

**"How did you build the overruled detection?"**
> Two-layer approach: regex patterns on judgment text ("overruled in",
> "expressly overruled by", "no longer good law") set `is_overruled=True`
> during ingestion. Then the citation graph has `OVERRULED_BY` edges. During
> graph traversal, any node on the path with `is_overruled=True` triggers a
> warning in the final output. The verification agent checks this flag before
> presenting any citation as current law.

**"How big is the corpus?"**
> ~[X] Supreme Court judgments covering NI Act, IPC, and CPC. The NetworkX
> graph has ~[X] nodes and ~[X] edges. The architecture is designed to scale
> to HC judgments (Bombay, Delhi, Madras) — the ingestion adapter and graph
> schema support multiple courts via the `court` metadata field.

## Demo Script (3 min)

1. Type: "Does Section 138 NI Act apply to post-dated cheques?"
2. Show answer appearing with inline citation links.
3. Click a citation → show the source excerpt + Indian Kanoon link.
4. Type a fictional case name ("XYZ v. ABC 2023 SCC 999") → show LOW_CONFIDENCE
   abstention (not a hallucinated answer).
5. Show an overruled case query → ⚠️ OVERRULED warning displayed.
6. Open `/api/v1/eval/latest` → show real citation accuracy metrics.

Step 4 and 6 are your "proof" moments — most legal AI demos skip these.
