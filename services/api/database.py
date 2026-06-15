"""Database engine, session factory, and helper utilities."""

import os
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from services.api.models import Base
from services.config import settings

_engine = create_engine(
    settings.database_url,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,   # wait up to 30s for any lock to clear
    },
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def init_db() -> None:
    """Create all tables if they don't exist. Called on startup."""
    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(bind=_engine)
    # Enable WAL mode for concurrent access — non-fatal if already locked
    try:
        with _engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA synchronous=NORMAL"))
            conn.execute(text("PRAGMA busy_timeout=30000"))
            conn.commit()
    except Exception:
        pass  # WAL setup is best-effort; DB works without it


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_judgment(db: Session, doc_id: str) -> "services.api.models.Judgment | None":  # type: ignore[name-defined]
    from services.api.models import Judgment

    return db.query(Judgment).filter(Judgment.doc_id == doc_id).first()
