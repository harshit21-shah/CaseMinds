"""
Corpus seeding — shared by CLI scripts and the admin HTTP API (no Render Shell needed).
"""

from __future__ import annotations

import logging
from typing import TypedDict

from sqlalchemy.orm import Session

from services.api.database import SessionLocal, init_db
from services.config import settings
from services.graph.graph_store import GraphStore
from services.ingestion.citation_extractor import extract_citations_llm
from services.ingestion.db_writer import upsert_citation, upsert_judgment
from services.ingestion.embedder import Embedder
from services.ingestion.parser import parse_judgment
from services.ingestion.scraper import IndianKanoonScraper

logger = logging.getLogger(__name__)

SEED_QUERIES: list[tuple[str, int]] = [
    ("Section 138 Negotiable Instruments Act cheque bounce", 5),
    ("Section 302 IPC murder", 3),
    ("Section 420 IPC cheating fraud", 3),
    ("Order 39 CPC temporary injunction", 3),
    ("Section 9 Hindu Marriage Act divorce restitution conjugal rights", 3),
    ("Section 370 IPC human trafficking", 3),
    ("Section 376 IPC rape sexual assault", 3),
    ("Section 498A IPC cruelty husband wife dowry", 3),
    ("Section 304B IPC dowry death", 3),
    ("Section 307 IPC attempt to murder", 3),
    ("Section 406 IPC criminal breach of trust", 3),
    ("Article 21 Constitution right to life personal liberty", 3),
    ("bail anticipatory bail Section 438 CrPC", 3),
    ("Section 482 CrPC inherent powers High Court quash FIR", 3),
    ("Section 17 Specific Relief Act specific performance", 3),
    ("Section 106 Transfer of Property Act lease tenancy", 3),
]

DEMO_SEED_QUERIES: list[tuple[str, int]] = [
    ("Section 138 Negotiable Instruments Act cheque bounce", 1),
    ("Section 370 IPC human trafficking", 1),
    ("Order 39 CPC temporary injunction", 1),
    ("bail anticipatory bail Section 438 CrPC", 1),
]

STATUTE_DOC_IDS = [
    "1153041",
    "1560742",
    "37788",
    "27844",
    "629786",
    "1369",
    "26589",
    "25290",
    "1823824",
    "74140",
    "445167",
    "481551",
    "39049",
]


class SeedResult(TypedDict):
    judgments_ingested: int
    statutes_ingested: int
    mode: str


def run_judgment_seed(
    *,
    fast: bool = True,
    incremental: bool = True,
    demo: bool = False,
) -> int:
    """Fetch, parse, graph, embed judgments. Returns count ingested this run."""
    queries = DEMO_SEED_QUERIES if demo else SEED_QUERIES
    mode_parts = []
    if demo:
        mode_parts.append("DEMO")
    if fast:
        mode_parts.append("FAST")
    if incremental:
        mode_parts.append("INCREMENTAL")
    logger.info("judgment seed starting [%s]", " + ".join(mode_parts) or "FULL")

    init_db()
    db = SessionLocal()
    scraper = IndianKanoonScraper()
    all_doc_ids: list[str] = []

    for query, max_pages in queries:
        logger.info("searching: '%s' (max_pages=%d)", query, max_pages)
        ids = scraper.search(query, max_pages=max_pages)
        all_doc_ids.extend(ids)

    unique_ids = list(dict.fromkeys(all_doc_ids))
    if incremental:
        from services.api.models import Judgment as _J

        existing = {row.doc_id for row in db.query(_J.doc_id).all()}
        unique_ids = [d for d in unique_ids if d not in existing]

    graph = GraphStore()
    embedder = Embedder()
    parsed_judgments = []

    for i, doc_id in enumerate(unique_ids):
        try:
            raw = scraper.fetch(doc_id)
            judgment = parse_judgment(raw)
            parsed_judgments.append(judgment)
            upsert_judgment(db, judgment)
            graph.add_judgment(judgment)
            logger.info("[%d/%d] parsed doc_id=%s", i + 1, len(unique_ids), doc_id)
        except Exception as exc:
            logger.warning("failed doc_id=%s: %s", doc_id, exc)

    for judgment in parsed_judgments:
        for raw_citation in judgment.cases_cited_raw:
            matched_id = _resolve_citation(db, raw_citation)
            if matched_id and matched_id != judgment.doc_id:
                graph.add_edge(judgment.doc_id, matched_id, rel="CITES", confidence=1.0, extracted_by="regex")
                upsert_citation(db, judgment.doc_id, matched_id, "CITES", 1.0)

        if not fast:
            for c in extract_citations_llm(judgment):
                matched_id = _resolve_citation_by_name(db, c.case_name)
                if matched_id and matched_id != judgment.doc_id:
                    graph.add_edge(
                        judgment.doc_id, matched_id, rel=c.relationship, confidence=0.8, extracted_by="llm"
                    )
                    upsert_citation(db, judgment.doc_id, matched_id, c.relationship, 0.8)

    if parsed_judgments:
        graph.save()
        embedder.embed_many(parsed_judgments)

    db.close()
    logger.info("judgment seed complete: %d ingested", len(parsed_judgments))
    return len(parsed_judgments)


def run_statute_seed() -> int:
    """Index bare Act section texts. Returns count ingested this run."""
    logger.info("statute seed starting (%d sections)", len(STATUTE_DOC_IDS))
    init_db()
    db = SessionLocal()

    from services.api.models import Judgment as _J

    existing = {row.doc_id for row in db.query(_J.doc_id).all()}
    scraper = IndianKanoonScraper()
    graph = GraphStore()
    embedder = Embedder()
    parsed = []

    for doc_id in STATUTE_DOC_IDS:
        if doc_id in existing:
            continue
        try:
            raw = scraper.fetch(doc_id)
            judgment = parse_judgment(raw)
            parsed.append(judgment)
            upsert_judgment(db, judgment)
            graph.add_judgment(judgment)
        except Exception as exc:
            logger.warning("statute doc_id=%s failed: %s", doc_id, exc)

    if parsed:
        graph.save()
        embedder.embed_many(parsed)

    db.close()
    logger.info("statute seed complete: %d ingested", len(parsed))
    return len(parsed)


def run_full_seed(*, fast: bool = True, incremental: bool = True, demo: bool = False) -> SeedResult:
    """Judgments then statutes."""
    mode = "demo" if demo else ("fast" if fast else "full")
    judgments = run_judgment_seed(fast=fast, incremental=incremental, demo=demo)
    statutes = run_statute_seed()
    return SeedResult(judgments_ingested=judgments, statutes_ingested=statutes, mode=mode)


def _resolve_citation(db: Session, raw_citation: str) -> str | None:
    from services.api.models import Judgment

    row = db.query(Judgment).filter(Judgment.citation == raw_citation).first()
    return row.doc_id if row else None


def _resolve_citation_by_name(db: Session, case_name: str) -> str | None:
    from rapidfuzz import fuzz, process

    from services.api.models import Judgment

    if not case_name:
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
