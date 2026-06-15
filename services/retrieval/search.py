"""
Hybrid search orchestrator.

Pipeline:
  BM25 (top-25) + ChromaDB dense (top-25)
  → RRF fusion (top-25 unique)
  → CrossEncoder rerank
  → top-5 ChunkResult

This is the retrieval backbone called by the Retrieval Agent.
"""

import logging
from dataclasses import dataclass, field
from functools import lru_cache

from sentence_transformers import CrossEncoder

from services.config import settings
from services.retrieval.bm25_store import BM25Store
from services.retrieval.chroma_store import get_or_create_collection

logger = logging.getLogger(__name__)

CROSS_ENCODER_MODEL = settings.reranker_model
RRF_K = settings.rrf_k


@dataclass
class ChunkResult:
    chunk_id: str
    doc_id: str
    text: str
    score: float
    metadata: dict = field(default_factory=dict)


# ── Lazy singletons ────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _get_bm25() -> BM25Store:
    return BM25Store()


@lru_cache(maxsize=1)
def _get_reranker() -> CrossEncoder:
    logger.info("loading cross-encoder %s", CROSS_ENCODER_MODEL)
    return CrossEncoder(CROSS_ENCODER_MODEL)


# ── BM25 search ────────────────────────────────────────────────────────────


def bm25_search(query: str, n: int = 25) -> list[ChunkResult]:
    store = _get_bm25()
    raw = store.search(query, n=n)
    return [
        ChunkResult(
            chunk_id=r["chunk_id"],
            doc_id=r["doc_id"],
            text=r["text"],
            score=r["score"],
        )
        for r in raw
    ]


# ── ChromaDB dense search ─────────────────────────────────────────────────


def chroma_search(
    query: str,
    statute_refs: list[str] | None = None,
    n: int = 25,
) -> list[ChunkResult]:
    collection = get_or_create_collection()

    where: dict | None = None
    if statute_refs:
        # Build OR filter: any chunk whose acts_cited contains any statute_ref
        if len(statute_refs) == 1:
            where = {"acts_cited": {"$contains": statute_refs[0]}}
        else:
            where = {
                "$or": [{"acts_cited": {"$contains": ref}} for ref in statute_refs]
            }

    query_result = collection.query(
        query_texts=[query],
        n_results=min(n, max(collection.count(), 1)),
        where=where if where else None,
        include=["documents", "metadatas", "distances"],
    )

    results: list[ChunkResult] = []
    ids = query_result.get("ids", [[]])[0]
    docs = query_result.get("documents", [[]])[0]
    metas = query_result.get("metadatas", [[]])[0]
    dists = query_result.get("distances", [[]])[0]

    for chunk_id, text, meta, dist in zip(ids, docs, metas, dists):
        # ChromaDB cosine distance: 0 = identical, 2 = opposite. Convert to similarity.
        score = 1.0 - (dist / 2.0)
        results.append(
            ChunkResult(
                chunk_id=chunk_id,
                doc_id=meta.get("doc_id", ""),
                text=text,
                score=score,
                metadata=meta,
            )
        )

    return results


# ── RRF fusion ─────────────────────────────────────────────────────────────


def reciprocal_rank_fusion(
    *result_lists: list[ChunkResult],
    k: int = RRF_K,
) -> list[ChunkResult]:
    """
    Fuse multiple ranked lists using Reciprocal Rank Fusion.
    Returns deduplicated list sorted by fused score descending.
    """
    scores: dict[str, float] = {}
    chunk_map: dict[str, ChunkResult] = {}

    for results in result_lists:
        for rank, chunk in enumerate(results):
            rrf_score = 1.0 / (k + rank + 1)
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + rrf_score
            chunk_map[chunk.chunk_id] = chunk

    fused = sorted(chunk_map.values(), key=lambda c: scores[c.chunk_id], reverse=True)
    # Attach fused score for transparency
    for c in fused:
        c.score = scores[c.chunk_id]
    return fused


# ── CrossEncoder rerank ────────────────────────────────────────────────────


def rerank(
    query: str,
    chunks: list[ChunkResult],
    top_k: int = 5,
) -> list[ChunkResult]:
    if not chunks:
        return []

    reranker = _get_reranker()
    pairs = [(query, c.text) for c in chunks]
    ce_scores: list[float] = reranker.predict(pairs).tolist()

    ranked = sorted(
        zip(chunks, ce_scores), key=lambda x: x[1], reverse=True
    )
    results = []
    for chunk, score in ranked[:top_k]:
        chunk.score = float(score)
        results.append(chunk)
    return results


# ── Orchestrator ───────────────────────────────────────────────────────────


def build_chroma_filters(statute_refs: list[str]) -> list[str]:
    return statute_refs


def hybrid_search(
    query: str,
    statute_refs: list[str] | None = None,
    strategy: str = "HYBRID_EQUAL",
    top_k: int | None = None,
) -> list[ChunkResult]:
    top_k = top_k if top_k is not None else settings.retrieval_top_k
    """
    Full hybrid retrieval pipeline.

    strategy:
      BM25_FIRST  — BM25 top-25 + dense top-10, RRF, rerank
      DENSE_FIRST — dense top-25 + BM25 top-10, RRF, rerank
      HYBRID_EQUAL — both top-25, RRF, rerank
    """
    refs = statute_refs or []

    full_n = settings.bm25_top_n
    reduced_n = full_n // 2

    if strategy == "BM25_FIRST":
        bm25_n, dense_n = full_n, reduced_n
    elif strategy == "DENSE_FIRST":
        bm25_n, dense_n = reduced_n, full_n
    else:  # HYBRID_EQUAL
        bm25_n, dense_n = full_n, settings.dense_top_n

    bm25_results = bm25_search(query, n=bm25_n)
    dense_results = chroma_search(query, statute_refs=refs if refs else None, n=dense_n)

    fused = reciprocal_rank_fusion(bm25_results, dense_results)[:25]

    ranked = rerank(query, fused, top_k=top_k)

    max_score = max((r.score for r in ranked), default=0.0)
    if max_score < settings.min_retrieval_score:
        logger.info(
            "hybrid_search: max_score=%.3f below threshold=%.3f — NO_RESULTS",
            max_score,
            settings.min_retrieval_score,
        )
        return []

    logger.info(
        "hybrid_search query='%s' strategy=%s results=%d max_score=%.3f",
        query[:60],
        strategy,
        len(ranked),
        max_score,
    )
    return ranked
