"""
SQLite upsert layer for ingestion pipeline.
Writes ParsedJudgment → judgments + judgment_citations tables.

Note: lists (judges, acts_cited) are explicitly JSON-serialized because
SQLAlchemy's custom TypeDecorator is not reliably applied on all INSERT paths.
"""

import json
import logging

from sqlalchemy.orm import Session

from services.api.models import Judgment, JudgmentCitation
from services.ingestion.parser import ParsedJudgment

logger = logging.getLogger(__name__)


def _jdump(val: list) -> str:
    """Safely JSON-serialize a list to string for SQLite storage."""
    return json.dumps(val if isinstance(val, list) else [])


def upsert_judgment(db: Session, judgment: ParsedJudgment) -> None:
    """Insert or update a judgment row. Explicitly serializes list fields."""
    try:
        existing = db.get(Judgment, judgment.doc_id)

        if existing:
            existing.case_name = judgment.case_name
            existing.citation = judgment.citation
            existing.court = judgment.court
            existing.date = judgment.date
            existing.judges = _jdump(judgment.judges)          # type: ignore[assignment]
            existing.acts_cited = _jdump(judgment.acts_cited)  # type: ignore[assignment]
            existing.is_overruled = judgment.is_overruled
            existing.overruled_by_doc_id = judgment.overruled_by
            existing.version_hash = judgment.version_hash
        else:
            db.add(Judgment(
                doc_id=judgment.doc_id,
                case_name=judgment.case_name,
                citation=judgment.citation,
                court=judgment.court,
                date=judgment.date,
                judges=_jdump(judgment.judges),          # type: ignore[arg-type]
                acts_cited=_jdump(judgment.acts_cited),  # type: ignore[arg-type]
                is_overruled=judgment.is_overruled,
                overruled_by_doc_id=judgment.overruled_by,
                kanoon_url=judgment.kanoon_url,
                version_hash=judgment.version_hash,
            ))

        db.commit()
        logger.debug("upserted judgment doc_id=%s", judgment.doc_id)

    except Exception as exc:
        db.rollback()
        raise exc


def upsert_citation(
    db: Session,
    citing_doc_id: str,
    cited_doc_id: str,
    relationship: str = "CITES",
    confidence: float = 1.0,
) -> None:
    """Insert a citation edge. Skips if the exact (citing, cited, rel) triple already exists."""
    try:
        existing = (
            db.query(JudgmentCitation)
            .filter_by(
                citing_doc_id=citing_doc_id,
                cited_doc_id=cited_doc_id,
                relationship_type=relationship,
            )
            .first()
        )
        if existing:
            return

        db.add(JudgmentCitation(
            citing_doc_id=citing_doc_id,
            cited_doc_id=cited_doc_id,
            relationship_type=relationship,
            confidence=confidence,
        ))
        db.commit()
        logger.debug(
            "citation %s -[%s]-> %s (conf=%.2f)",
            citing_doc_id, relationship, cited_doc_id, confidence,
        )
    except Exception as exc:
        db.rollback()
        logger.warning("citation upsert failed: %s", exc)
