"""ChromaDB client wrapper — collection setup and query helpers."""

from __future__ import annotations

import os
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from services.config import settings

COLLECTION_NAME = settings.chroma_collection_name


def get_chroma_client() -> chromadb.PersistentClient:
    os.makedirs(settings.chroma_persist_dir, exist_ok=True)
    return chromadb.PersistentClient(
        path=settings.chroma_persist_dir,
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def get_or_create_collection(
    client: chromadb.PersistentClient | None = None,
) -> chromadb.Collection:
    """Return (or create) the main clauses collection."""
    c = client or get_chroma_client()
    return c.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={
            "hnsw:space": "cosine",
            "hnsw:construction_ef": 200,
        },
    )


def setup_collection() -> chromadb.Collection:
    """Idempotent setup — safe to call on every startup."""
    client = get_chroma_client()
    collection = get_or_create_collection(client)
    return collection


if __name__ == "__main__":
    col = setup_collection()
    print(f"Collection '{COLLECTION_NAME}' ready. Count: {col.count()}")
