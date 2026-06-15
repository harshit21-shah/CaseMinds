"""
BM25 index builder and search.

Stores a pickled BM25Okapi object alongside parallel doc_id / chunk_id / text lists.
Rebuilt on any new ingestion (incremental rebuild planned for V2 at >10K judgments).
"""

import logging
import os
import pickle
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

from services.config import settings

logger = logging.getLogger(__name__)


@dataclass
class BM25IndexData:
    index: BM25Okapi
    doc_ids: list[str]
    chunk_ids: list[str]
    texts: list[str]
    built_at: str


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + lowercase tokenizer."""
    return text.lower().split()


class BM25Store:
    def __init__(self, path: str | None = None) -> None:
        self._path = Path(path or settings.bm25_path)
        self._data: BM25IndexData | None = None
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            with open(self._path, "rb") as f:
                self._data = pickle.load(f)
            logger.info("bm25 index loaded docs=%d", len(self._data.doc_ids))

    def build(self, chunks: list[dict]) -> None:
        """
        Build index from scratch.

        chunks: list of dicts with keys: doc_id, chunk_id, text
        """
        from datetime import datetime, timezone

        doc_ids = [c["doc_id"] for c in chunks]
        chunk_ids = [c["chunk_id"] for c in chunks]
        texts = [c["text"] for c in chunks]
        tokenized = [_tokenize(t) for t in texts]

        index = BM25Okapi(tokenized)
        self._data = BM25IndexData(
            index=index,
            doc_ids=doc_ids,
            chunk_ids=chunk_ids,
            texts=texts,
            built_at=datetime.now(timezone.utc).isoformat(),
        )
        self._save()
        logger.info("bm25 index built chunks=%d", len(chunks))

    def _save(self) -> None:
        os.makedirs(self._path.parent, exist_ok=True)
        with open(self._path, "wb") as f:
            pickle.dump(self._data, f, protocol=pickle.HIGHEST_PROTOCOL)
        logger.info("bm25 index saved path=%s", self._path)

    def search(self, query: str, n: int = 25) -> list[dict]:
        """
        Return top-n chunks for query.
        Returns list of dicts: {doc_id, chunk_id, text, score}.
        """
        if self._data is None:
            logger.warning("BM25 index not loaded — returning empty results")
            return []

        tokenized_query = _tokenize(query)
        scores = self._data.index.get_scores(tokenized_query)

        # Pair with metadata and sort descending
        scored = sorted(
            zip(scores, self._data.doc_ids, self._data.chunk_ids, self._data.texts),
            key=lambda x: x[0],
            reverse=True,
        )

        return [
            {"doc_id": doc_id, "chunk_id": chunk_id, "text": text, "score": float(score)}
            for score, doc_id, chunk_id, text in scored[:n]
            if score > 0
        ]

    @property
    def is_ready(self) -> bool:
        return self._data is not None
