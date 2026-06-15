"""
Central configuration — single source of truth for CaseMinds.

Every constant, threshold, model name, and path lives here.
No hardcoded values anywhere else in the codebase.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM API keys ──────────────────────────────────────────────────────────
    groq_api_key: str = ""
    anthropic_api_key: str = ""
    indian_kanoon_api_key: str = ""

    # ── LLM model names ───────────────────────────────────────────────────────
    groq_classifier_model: str = "llama-3.1-8b-instant"
    groq_answer_model: str = "llama-3.3-70b-versatile"
    groq_answer_fallback_model: str = "llama-3.1-8b-instant"
    claude_fallback_model: str = "claude-haiku-4-5"

    # ── Embedding + reranking models ─────────────────────────────────────────
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    embedding_batch_size: int = 64

    # ── Storage paths ─────────────────────────────────────────────────────────
    database_url: str = "sqlite:///./data/caseminds.db"
    chroma_persist_dir: str = "./data/chroma"
    chroma_collection_name: str = "caseminds_clauses_v1"
    graph_path: str = "./data/graph.pkl"
    bm25_path: str = "./data/bm25.pkl"

    # ── Chunking ──────────────────────────────────────────────────────────────
    chunk_max_tokens: int = 400
    chunk_overlap_tokens: int = 50

    # ── Retrieval ─────────────────────────────────────────────────────────────
    bm25_top_n: int = 25
    dense_top_n: int = 25
    rrf_k: int = 60                     # RRF constant (higher = gentler rank penalty)
    retrieval_top_k: int = 5            # final chunks after reranking
    min_retrieval_score: float = 0.30   # below this → NO_RESULTS

    # ── Graph traversal ───────────────────────────────────────────────────────
    graph_max_hops: int = 2
    graph_traversal_limit: int = 20
    max_traversal_chunks: int = 5       # extra chunks from graph
    max_total_context_chunks: int = 10  # cap passed to answer agent

    # ── Verification ─────────────────────────────────────────────────────────
    verification_threshold: float = 0.50   # fraction of [CITE:] tags verified in DB
    verification_min_verified: int = 1       # COMPLETE if this many cites verify (even below threshold)

    # ── Deployment ────────────────────────────────────────────────────────────
    frontend_dist: str = "./frontend/dist"
    seed_admin_secret: str = ""              # set to enable POST /api/v1/admin/seed-status

    # ── Citation extraction ───────────────────────────────────────────────────
    citation_llm_batch_size: int = 5       # paragraphs per Groq call
    citation_llm_max_paragraphs: int = 30  # max candidate paragraphs per judgment
    citation_fuzzy_threshold: int = 85     # rapidfuzz score for case name match

    # ── Scraper ───────────────────────────────────────────────────────────────
    scraper_polite_delay_s: float = 1.2
    scraper_timeout_s: float = 30.0

    # ── Eval targets ──────────────────────────────────────────────────────────
    eval_citation_accuracy_target: float = 0.90
    eval_overruled_detection_target: float = 0.88
    eval_retrieval_precision_target: float = 0.75

    # ── App ───────────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    environment: str = "development"
    disclaimer: str = (
        "CaseMinds is a research aid. "
        "Verify all citations independently. "
        "This is not legal advice."
    )


settings = Settings()


def has_valid_anthropic_key() -> bool:
    """True only when a real Anthropic key is configured (not .env placeholder text)."""
    key = settings.anthropic_api_key.strip()
    if not key:
        return False
    lowered = key.lower()
    if lowered.startswith("your_") or lowered in {"change_me", "changeme", "xxx"}:
        return False
    return key.startswith("sk-ant-")
