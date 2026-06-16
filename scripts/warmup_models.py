"""Pre-download sentence-transformers models during Render build (avoids startup timeout)."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

cache = ROOT / "data" / "hf_cache"
cache.mkdir(parents=True, exist_ok=True)
os.environ["HF_HOME"] = str(cache)
os.environ["TRANSFORMERS_CACHE"] = str(cache)
os.environ["SENTENCE_TRANSFORMERS_HOME"] = str(cache)

from sentence_transformers import CrossEncoder, SentenceTransformer  # noqa: E402

from services.config import settings  # noqa: E402

print(f"Downloading embedding model: {settings.embedding_model}")
SentenceTransformer(settings.embedding_model)
print(f"Downloading reranker: {settings.reranker_model}")
CrossEncoder(settings.reranker_model)
print("ML models cached OK")
