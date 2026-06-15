"""SQLAlchemy ORM models — source of truth for SQLite schema."""

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class _JSONColumn(Text):
    """Store Python lists/dicts as JSON text in SQLite."""

    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:  # type: ignore[override]
        return json.dumps(value) if value is not None else None

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        return json.loads(value) if value is not None else None


class Judgment(Base):
    __tablename__ = "judgments"

    doc_id = Column(String, primary_key=True)
    case_name = Column(String, nullable=False)
    citation = Column(String, nullable=True)
    court = Column(String, nullable=False, default="")
    date = Column(Date, nullable=True)
    judges = Column(_JSONColumn, nullable=False, default="[]")
    acts_cited = Column(_JSONColumn, nullable=False, default="[]")
    is_overruled = Column(Boolean, nullable=False, default=False)
    overruled_by_doc_id = Column(String, ForeignKey("judgments.doc_id"), nullable=True)
    kanoon_url = Column(String, nullable=False, default="")
    ingested_at = Column(DateTime, nullable=False, default=func.now())
    version_hash = Column(String, nullable=True)

    # Relationships
    overruled_by = relationship("Judgment", remote_side="Judgment.doc_id", foreign_keys=[overruled_by_doc_id])
    citations_made = relationship(
        "JudgmentCitation",
        foreign_keys="JudgmentCitation.citing_doc_id",
        back_populates="citing_judgment",
    )
    citations_received = relationship(
        "JudgmentCitation",
        foreign_keys="JudgmentCitation.cited_doc_id",
        back_populates="cited_judgment",
    )


class JudgmentCitation(Base):
    __tablename__ = "judgment_citations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    citing_doc_id = Column(String, ForeignKey("judgments.doc_id"), nullable=False)
    cited_doc_id = Column(String, ForeignKey("judgments.doc_id"), nullable=False)
    relationship_type = Column(String, nullable=False, default="CITES")
    confidence = Column(Float, nullable=False, default=1.0)

    citing_judgment = relationship(
        "Judgment", foreign_keys=[citing_doc_id], back_populates="citations_made"
    )
    cited_judgment = relationship(
        "Judgment", foreign_keys=[cited_doc_id], back_populates="citations_received"
    )


class QueryLog(Base):
    __tablename__ = "query_logs"

    id = Column(String, primary_key=True)
    query = Column(Text, nullable=False)
    query_type = Column(String, nullable=True)
    status = Column(String, nullable=False)
    confidence = Column(Float, nullable=False, default=0.0)
    answer = Column(Text, nullable=True)
    cited_doc_ids = Column(_JSONColumn, nullable=False, default="[]")
    retrieval_scores = Column(_JSONColumn, nullable=False, default="[]")
    latency_ms = Column(Integer, nullable=True)
    model_used = Column(String, nullable=True)
    groq_tokens_in = Column(Integer, nullable=True)
    groq_tokens_out = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())

    feedbacks = relationship("Feedback", back_populates="query_log")


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(String, primary_key=True)
    query_log_id = Column(String, ForeignKey("query_logs.id"), nullable=False)
    rating = Column(String, nullable=False)
    citation_correct = Column(Boolean, nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())

    query_log = relationship("QueryLog", back_populates="feedbacks")
