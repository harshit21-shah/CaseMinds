"""
Seed bare Act section texts from Indian Kanoon.

These are the actual statutory definitions (doctype=11 in IK).
Seeding them ensures "what is Section X?" queries return the statute text itself,
not just case law that mentions the section in passing.

Run: python scripts/seed_statutes.py
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.api.database import SessionLocal, init_db
from services.graph.graph_store import GraphStore
from services.ingestion.db_writer import upsert_judgment
from services.ingestion.embedder import Embedder
from services.ingestion.parser import parse_judgment
from services.ingestion.scraper import IndianKanoonScraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("seed_statutes")

# ── Key statute section doc_ids from Indian Kanoon (Acts, doctype=11) ─────────
# These are the bare text of the sections, not case law.
STATUTE_DOC_IDS = [
    # IPC sections
    "1153041",   # Section 370 IPC - Trafficking
    "1560742",   # Section 302 IPC - Murder
    "37788",     # Section 420 IPC - Cheating
    "27844",     # Section 498A IPC - Cruelty by husband
    "629786",    # Section 304B IPC - Dowry death
    "1369",      # Section 307 IPC - Attempt to murder
    "26589",     # Section 406 IPC - Criminal breach of trust
    "25290",     # Section 376 IPC - Rape
    # NI Act
    "1823824",   # Section 138 NI Act - Cheque dishonour
    # CPC
    "74140",     # Order 39 CPC - Temporary injunctions
    # CrPC
    "445167",    # Section 438 CrPC - Anticipatory bail
    "481551",    # Section 482 CrPC - Inherent powers
    # Constitution
    "39049",     # Article 21 - Right to life
]


def main() -> None:
    logger.info("=== Statute text seed starting (%d sections) ===", len(STATUTE_DOC_IDS))
    init_db()
    db = SessionLocal()

    # Skip already-indexed
    from services.api.models import Judgment as _J
    existing = {row.doc_id for row in db.query(_J.doc_id).all()}

    scraper = IndianKanoonScraper()
    graph = GraphStore()
    embedder = Embedder()
    parsed = []

    for i, doc_id in enumerate(STATUTE_DOC_IDS):
        if doc_id in existing:
            logger.info("[%d/%d] skip (already indexed) doc_id=%s", i + 1, len(STATUTE_DOC_IDS), doc_id)
            continue
        try:
            raw = scraper.fetch(doc_id)
            judgment = parse_judgment(raw)
            parsed.append(judgment)
            upsert_judgment(db, judgment)
            graph.add_judgment(judgment)
            logger.info("[%d/%d] indexed statute doc_id=%s '%s'", i + 1, len(STATUTE_DOC_IDS), doc_id, judgment.case_name[:60])
        except Exception as exc:
            logger.warning("failed doc_id=%s: %s", doc_id, exc)

    if parsed:
        graph.save()
        embedder.embed_many(parsed)
        logger.info("=== Statute seed complete: %d sections indexed ===", len(parsed))
    else:
        logger.info("No new statute sections to index.")

    db.close()


if __name__ == "__main__":
    main()
