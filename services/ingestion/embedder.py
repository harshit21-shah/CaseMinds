"""
Embedding pipeline.

Model: BAAI/bge-small-en-v1.5 (33MB, CPU-friendly, 384 dimensions).
Upserts chunks to ChromaDB with full metadata.
Also feeds the BM25 store for hybrid retrieval.
"""

import logging
from typing import Any

from sentence_transformers import SentenceTransformer

from services.config import settings
from services.ingestion.parser import ParsedJudgment
from services.retrieval.bm25_store import BM25Store
from services.retrieval.chroma_store import get_or_create_collection

logger = logging.getLogger(__name__)

EMBED_MODEL = settings.embedding_model
BATCH_SIZE = settings.embedding_batch_size


class Embedder:
    def __init__(self) -> None:
        logger.info("loading embedding model %s", EMBED_MODEL)
        self._model = SentenceTransformer(EMBED_MODEL)
        self._collection = get_or_create_collection()
        self._bm25 = BM25Store()
        self._bm25_buffer: list[dict] = []  # accumulate for batch BM25 rebuild

    def embed_judgment(self, judgment: ParsedJudgment) -> None:
        """Embed all chunks of one judgment and upsert to ChromaDB."""
        if not judgment.chunks:
            logger.debug("no chunks for doc_id=%s — skipping", judgment.doc_id)
            return

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for i, chunk_text in enumerate(judgment.chunks):
            chunk_id = f"{judgment.doc_id}_chunk_{i}"
            ids.append(chunk_id)
            documents.append(chunk_text)
            metadatas.append(
                {
                    "doc_id": judgment.doc_id,
                    "case_name": judgment.case_name,
                    "citation": judgment.citation or "",
                    "court": judgment.court,
                    "date": str(judgment.date) if judgment.date else "",
                    "acts_cited": ",".join(judgment.acts_cited),  # ChromaDB needs str
                    "is_overruled": judgment.is_overruled,
                    "chunk_index": i,
                    "chunk_total": len(judgment.chunks),
                }
            )
            self._bm25_buffer.append(
                {"doc_id": judgment.doc_id, "chunk_id": chunk_id, "text": chunk_text}
            )

        # Embed in batches
        all_embeddings: list[list[float]] = []
        for start in range(0, len(documents), BATCH_SIZE):
            batch = documents[start : start + BATCH_SIZE]
            vecs = self._model.encode(batch, normalize_embeddings=True)
            all_embeddings.extend(vecs.tolist())

        self._collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=all_embeddings,
            metadatas=metadatas,
        )
        logger.debug(
            "embedded doc_id=%s chunks=%d", judgment.doc_id, len(judgment.chunks)
        )

    def flush_bm25(self) -> None:
        """
        Rebuild BM25 from accumulated buffer merged with any previously indexed chunks.
        Safe to call in incremental mode — existing chunks are preserved.
        """
        if not self._bm25_buffer:
            return

        # Merge with existing BM25 data so incremental runs don't wipe old chunks
        existing_chunks: list[dict] = []
        if self._bm25._data is not None:
            new_chunk_ids = {c["chunk_id"] for c in self._bm25_buffer}
            for doc_id, chunk_id, text in zip(
                self._bm25._data.doc_ids,
                self._bm25._data.chunk_ids,
                self._bm25._data.texts,
            ):
                if chunk_id not in new_chunk_ids:  # don't duplicate updated chunks
                    existing_chunks.append({"doc_id": doc_id, "chunk_id": chunk_id, "text": text})

        all_chunks = existing_chunks + self._bm25_buffer
        self._bm25.build(all_chunks)
        logger.info("bm25 rebuilt total_chunks=%d (new=%d existing=%d)", len(all_chunks), len(self._bm25_buffer), len(existing_chunks))

    def embed_many(self, judgments: list[ParsedJudgment]) -> None:
        """Embed a list of judgments and rebuild BM25 at the end."""
        for i, j in enumerate(judgments):
            self.embed_judgment(j)
            logger.info("embedded %d/%d doc_id=%s", i + 1, len(judgments), j.doc_id)
        self.flush_bm25()
