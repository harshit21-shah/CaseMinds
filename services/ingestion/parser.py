"""
Judgment parser — converts RawJudgment → ParsedJudgment.

Responsibilities:
  - Structured field extraction (case_name, citation, court, date, judges)
  - Statute reference extraction (acts_cited)
  - Overruled detection via phrase patterns (CM-1-05)
  - Text chunking for embedding
"""

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import date

from services.config import settings
from services.ingestion.scraper import RawJudgment

logger = logging.getLogger(__name__)

# ── Citation regex patterns ────────────────────────────────────────────────

CITATION_PATTERNS = [
    re.compile(r"\(\d{4}\)\s+\d+\s+SCC\s+\d+"),           # (2010) 11 SCC 441
    re.compile(r"AIR\s+\d{4}\s+SC\s+\d+"),                  # AIR 2010 SC 123
    re.compile(r"\d{4}\s+\(\d+\)\s+SCC\s+\d+"),             # 2010 (11) SCC 441
    re.compile(r"\(\d{4}\)\s+\d+\s+SCR\s+\d+"),             # (2010) 5 SCR 100
    re.compile(r"\d{4}\s+SCC\s+\(\w+\)\s+\d+"),             # 2010 SCC (Cri) 1
]

# ── Overruled detection patterns (CM-1-05) ────────────────────────────────

OVERRULED_PATTERNS = [
    re.compile(r"overruled\s+in\s+.{1,80}", re.IGNORECASE),
    re.compile(r"expressly\s+overruled\s+by", re.IGNORECASE),
    re.compile(r"no\s+longer\s+good\s+law", re.IGNORECASE),
    re.compile(r"not\s+follow\s+.{0,50}(earlier|previous)\s+decision", re.IGNORECASE),
    re.compile(r"hereby\s+overruled", re.IGNORECASE),
    re.compile(r"stands?\s+overruled", re.IGNORECASE),
]

# ── Statute reference patterns ─────────────────────────────────────────────

STATUTE_PATTERNS = [
    re.compile(r"[Ss]ection\s+\d+[A-Z]?\s+(?:of\s+the\s+)?(?:NI\s+Act|Negotiable\s+Instruments\s+Act)", re.IGNORECASE),
    re.compile(r"[Ss]\.?\s*\d+[A-Z]?\s+NI\s+Act", re.IGNORECASE),
    re.compile(r"[Ss]ection\s+\d+[A-Z]?\s+(?:of\s+the\s+)?(?:IPC|Indian\s+Penal\s+Code)", re.IGNORECASE),
    re.compile(r"[Ss]ection\s+\d+[A-Z]?\s+(?:of\s+the\s+)?(?:CPC|Code\s+of\s+Civil\s+Procedure)", re.IGNORECASE),
    re.compile(r"Order\s+\d+\s+Rule\s+\d+\s+CPC", re.IGNORECASE),
    re.compile(r"[Ss]ection\s+\d+[A-Z]?\s+(?:of\s+the\s+)?(?:Evidence\s+Act|Indian\s+Evidence\s+Act)", re.IGNORECASE),
    re.compile(r"[Ss]ection\s+\d+[A-Z]?\s+(?:of\s+the\s+)?(?:Hindu\s+Marriage\s+Act|HMA)", re.IGNORECASE),
    re.compile(r"[Ss]ection\s+\d+[A-Z]?\s+(?:of\s+the\s+)?Specific\s+Relief\s+Act", re.IGNORECASE),
    re.compile(r"Article\s+\d+[A-Z]?\s+(?:of\s+the\s+)?Constitution", re.IGNORECASE),
]

# ── Judge name extraction ──────────────────────────────────────────────────

JUDGE_PATTERN = re.compile(
    r"(?:JUSTICE|J\.)\s+([A-Z][A-Z\.\s]+?)(?:\s+AND|\s+J\b|,|\n|$)"
)


@dataclass
class ActRef:
    act: str
    section: str

    def __str__(self) -> str:
        return f"{self.section} {self.act}"


@dataclass
class ParsedJudgment:
    doc_id: str
    case_name: str
    citation: str | None
    court: str
    date: date | None
    judges: list[str]
    acts_cited: list[str]           # list of "Section X NI Act" strings
    cases_cited_raw: list[str]      # raw citation strings found in text
    is_overruled: bool
    overruled_by: str | None        # doc_id of overruling judgment if known
    full_text: str
    chunks: list[str]
    version_hash: str
    kanoon_url: str = field(default="")


# ── Chunking ───────────────────────────────────────────────────────────────

def chunk_text(text: str, max_tokens: int = 400, overlap_tokens: int = 50) -> list[str]:
    """
    Split text into overlapping chunks by approximate token count.
    Uses words as a proxy (1 word ≈ 1.3 tokens for Indian legal text).
    """
    words = text.split()
    chunk_size = int(max_tokens / 1.3)
    overlap = int(overlap_tokens / 1.3)
    chunks: list[str] = []

    i = 0
    while i < len(words):
        chunk = words[i : i + chunk_size]
        chunks.append(" ".join(chunk))
        i += chunk_size - overlap

    return [c for c in chunks if len(c.split()) > 10]  # skip tiny trailing chunks


# ── Main parser ────────────────────────────────────────────────────────────

def parse_judgment(raw: RawJudgment) -> ParsedJudgment:
    """Convert a RawJudgment into a structured ParsedJudgment."""
    text = raw.text or ""

    # Case name — prefer title from API
    case_name = _clean_case_name(raw.title or "")

    # Citation — try API field first, then regex scan
    citation = raw.citation or _extract_first_citation(text)

    # Court
    court = _normalize_court(raw.court or "")

    # Date
    parsed_date = _parse_date(raw.date or "")

    # Judges
    judges = _extract_judges(text)

    # Statute references
    acts_cited = _extract_statute_refs(text)

    # Inline citation strings (for graph building)
    cases_cited_raw = _extract_citation_strings(text)

    # Overruled detection
    is_overruled = _detect_overruled(text)

    # Chunks
    chunks = chunk_text(text, max_tokens=settings.chunk_max_tokens, overlap_tokens=settings.chunk_overlap_tokens)

    # Stable hash for change detection
    version_hash = hashlib.sha256(text.encode()).hexdigest()[:16]

    kanoon_url = f"https://indiankanoon.org/doc/{raw.doc_id}/"

    return ParsedJudgment(
        doc_id=raw.doc_id,
        case_name=case_name,
        citation=citation,
        court=court,
        date=parsed_date,
        judges=judges,
        acts_cited=acts_cited,
        cases_cited_raw=cases_cited_raw,
        is_overruled=is_overruled,
        overruled_by=None,  # resolved later by citation extractor
        full_text=text,
        chunks=chunks,
        version_hash=version_hash,
        kanoon_url=kanoon_url,
    )


# ── Helpers ────────────────────────────────────────────────────────────────

def _clean_case_name(title: str) -> str:
    title = re.sub(r"\s+", " ", title).strip()
    # Remove common suffixes like "on 15 June, 2010"
    title = re.sub(r"\s+on\s+\d{1,2}\s+\w+,?\s+\d{4}.*$", "", title)
    return title or "Unknown"


def _extract_first_citation(text: str) -> str | None:
    for pattern in CITATION_PATTERNS:
        m = pattern.search(text)
        if m:
            return m.group(0).strip()
    return None


def _extract_citation_strings(text: str) -> list[str]:
    found: list[str] = []
    for pattern in CITATION_PATTERNS:
        found.extend(m.group(0).strip() for m in pattern.finditer(text))
    return list(dict.fromkeys(found))  # deduplicate preserving order


def _normalize_court(court: str) -> str:
    court_lower = court.lower()
    if "supreme" in court_lower or court_lower.startswith("sc ") or " sc " in court_lower:
        return "Supreme Court of India"
    if "bombay" in court_lower or "mumbai" in court_lower:
        return "Bombay High Court"
    if "delhi" in court_lower:
        return "Delhi High Court"
    if "madras" in court_lower or "chennai" in court_lower:
        return "Madras High Court"
    if "calcutta" in court_lower or "kolkata" in court_lower:
        return "Calcutta High Court"
    return court.strip() or "Unknown"


def _parse_date(date_str: str) -> date | None:
    if not date_str:
        return None
    # Try common formats: "2010-08-20", "20 August 2010", "August 20, 2010"
    formats = ["%Y-%m-%d", "%d %B %Y", "%B %d, %Y", "%d-%m-%Y", "%Y/%m/%d"]
    for fmt in formats:
        try:
            from datetime import datetime as dt

            return dt.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    logger.debug("Could not parse date: %s", date_str)
    return None


def _extract_judges(text: str) -> list[str]:
    judges: list[str] = []
    for m in JUDGE_PATTERN.finditer(text[:2000]):  # header area only
        name = m.group(1).strip().title()
        if len(name) > 3 and name not in judges:
            judges.append(name)
    return judges[:10]  # cap at 10


def _extract_statute_refs(text: str) -> list[str]:
    refs: list[str] = []
    for pattern in STATUTE_PATTERNS:
        for m in pattern.finditer(text):
            ref = re.sub(r"\s+", " ", m.group(0)).strip()
            if ref not in refs:
                refs.append(ref)
    return refs


def _detect_overruled(text: str) -> bool:
    for pattern in OVERRULED_PATTERNS:
        if pattern.search(text):
            return True
    return False
