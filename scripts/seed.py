"""
Seed script — builds the full corpus from scratch.

Steps:
  1. Scrape ~200 SC judgments from Indian Kanoon (5 act-topics)
  2. Parse + normalize each judgment
  3. Extract citations (regex pass 1; LLM pass 2 unless --fast)
  4. Build NetworkX graph → save data/graph.pkl
  5. Embed chunks → ChromaDB + BM25 index
  6. Upsert metadata → SQLite

Run: python scripts/seed.py          # full (LLM citation extraction)
     python scripts/seed.py --fast   # skip LLM citations (regex only, much faster)
     OR: make seed
"""

import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.api.database import SessionLocal, init_db
from services.config import settings
from services.graph.graph_store import GraphStore
from services.ingestion.citation_extractor import extract_citations_llm
from services.ingestion.db_writer import upsert_citation, upsert_judgment
from services.ingestion.embedder import Embedder
from services.ingestion.parser import parse_judgment
from services.ingestion.scraper import IndianKanoonScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("seed")

# ── Query topics to seed ─────────────────────────────────────────────────────
# Add topics here to expand the corpus; each tuple is (query, max_pages).
SEED_QUERIES = [
    # ── Already seeded (Phase 1) ─────────────────────────────────────────────
    ("Section 138 Negotiable Instruments Act cheque bounce", 5),
    ("Section 302 IPC murder", 3),
    ("Section 420 IPC cheating fraud", 3),
    ("Order 39 CPC temporary injunction", 3),
    ("Section 9 Hindu Marriage Act divorce restitution conjugal rights", 3),
    # ── Phase 2 — common IPC sections ────────────────────────────────────────
    ("Section 370 IPC human trafficking", 3),
    ("Section 376 IPC rape sexual assault", 3),
    ("Section 498A IPC cruelty husband wife dowry", 3),
    ("Section 304B IPC dowry death", 3),
    ("Section 307 IPC attempt to murder", 3),
    ("Section 406 IPC criminal breach of trust", 3),
    # ── Phase 2 — constitutional / bail ──────────────────────────────────────
    ("Article 21 Constitution right to life personal liberty", 3),
    ("bail anticipatory bail Section 438 CrPC", 3),
    ("Section 482 CrPC inherent powers High Court quash FIR", 3),
    # ── Phase 2 — property / contract ────────────────────────────────────────
    ("Section 17 Specific Relief Act specific performance", 3),
    ("Section 106 Transfer of Property Act lease tenancy", 3),
]


def main(fast: bool = False, incremental: bool = False) -> None:
    mode_parts = []
    if fast:
        mode_parts.append("FAST (regex citations only)")
    if incremental:
        mode_parts.append("INCREMENTAL (skip existing docs)")
    mode = " + ".join(mode_parts) if mode_parts else "FULL"
    logger.info("=== CaseMinds seed starting [%s] ===", mode)

    # 1. Init DB
    init_db()
    db = SessionLocal()

    # 2. Scrape
    scraper = IndianKanoonScraper()
    all_doc_ids: list[str] = []
    for query, max_pages in SEED_QUERIES:
        logger.info("searching: '%s' (max_pages=%d)", query, max_pages)
        ids = scraper.search(query, max_pages=max_pages)
        logger.info("found %d doc_ids for '%s'", len(ids), query)
        all_doc_ids.extend(ids)

    # Deduplicate
    unique_ids = list(dict.fromkeys(all_doc_ids))
    logger.info("total unique doc_ids: %d", len(unique_ids))

    # In incremental mode, skip doc_ids already in the DB
    if incremental:
        from services.api.models import Judgment as _J
        existing = {row.doc_id for row in db.query(_J.doc_id).all()}
        before = len(unique_ids)
        unique_ids = [d for d in unique_ids if d not in existing]
        logger.info("incremental: skipping %d existing docs, fetching %d new", before - len(unique_ids), len(unique_ids))

    # 3. Fetch + Parse + Store
    graph = GraphStore()
    embedder = Embedder()
    parsed_judgments = []

    for i, doc_id in enumerate(unique_ids):
        try:
            raw = scraper.fetch(doc_id)
            judgment = parse_judgment(raw)
            parsed_judgments.append(judgment)

            # Upsert to SQLite
            upsert_judgment(db, judgment)

            # Add node to graph
            graph.add_judgment(judgment)

            logger.info("[%d/%d] parsed doc_id=%s '%s'", i + 1, len(unique_ids), doc_id, judgment.case_name[:60])
        except Exception as exc:
            logger.warning("failed doc_id=%s: %s", doc_id, exc)

    # 4. Build citation edges
    logger.info("building citation edges...")
    for judgment in parsed_judgments:
        # Regex-extracted citations (Pass 1)
        for raw_citation in judgment.cases_cited_raw:
            # Try to resolve to a doc_id via SQLite case_name / citation fuzzy match
            matched_id = _resolve_citation(db, raw_citation)
            if matched_id and matched_id != judgment.doc_id:
                graph.add_edge(judgment.doc_id, matched_id, rel="CITES", confidence=1.0, extracted_by="regex")
                upsert_citation(db, judgment.doc_id, matched_id, "CITES", 1.0)

        # LLM-assisted citations (Pass 2) — skip in fast mode
        llm_citations = [] if fast else extract_citations_llm(judgment)
        for c in llm_citations:
            matched_id = _resolve_citation_by_name(db, c.case_name)
            if matched_id and matched_id != judgment.doc_id:
                graph.add_edge(judgment.doc_id, matched_id, rel=c.relationship, confidence=0.8, extracted_by="llm")
                upsert_citation(db, judgment.doc_id, matched_id, c.relationship, 0.8)

    # 5. Save graph
    graph.save()

    # 6. Embed → ChromaDB + BM25
    logger.info("embedding %d judgments...", len(parsed_judgments))
    embedder.embed_many(parsed_judgments)

    logger.info("=== seed complete: %d judgments ingested ===", len(parsed_judgments))
    db.close()


def _resolve_citation(db: object, raw_citation: str) -> str | None:
    """Try to find a doc_id matching a raw citation string (e.g. '(2010) 11 SCC 441')."""
    from services.api.models import Judgment
    from sqlalchemy.orm import Session
    if not isinstance(db, Session):
        return None
    row = db.query(Judgment).filter(Judgment.citation == raw_citation).first()
    return row.doc_id if row else None


def _resolve_citation_by_name(db: object, case_name: str) -> str | None:
    """Fuzzy match a case name to a doc_id using rapidfuzz."""
    from rapidfuzz import fuzz, process
    from services.api.models import Judgment
    from sqlalchemy.orm import Session

    if not isinstance(db, Session) or not case_name:
        return None

    rows = db.query(Judgment.doc_id, Judgment.case_name).all()
    if not rows:
        return None

    names = [r.case_name for r in rows]
    result = process.extractOne(case_name, names, scorer=fuzz.token_sort_ratio)
    if result and result[1] >= settings.citation_fuzzy_threshold:
        idx = names.index(result[0])
        return rows[idx].doc_id
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the CaseMinds corpus")
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip LLM citation extraction (regex only). Much faster for dev/CI.",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Skip doc_ids already in the database. Add new topics without re-processing existing ones.",
    )
    args = parser.parse_args()
    main(fast=args.fast, incremental=args.incremental)
