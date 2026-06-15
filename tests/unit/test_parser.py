"""Unit tests for the judgment parser and citation extractor."""

import pytest

from services.ingestion.parser import (
    ParsedJudgment,
    _clean_case_name,
    _detect_overruled,
    _extract_citation_strings,
    _extract_first_citation,
    _extract_statute_refs,
    chunk_text,
    parse_judgment,
)
from services.ingestion.scraper import RawJudgment


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_raw(
    doc_id: str = "123",
    title: str = "Rangappa v. Sri Mohan",
    text: str = "",
    date: str | None = "2010-08-20",
    court: str | None = "Supreme Court of India",
    citation: str | None = "(2010) 11 SCC 441",
) -> RawJudgment:
    return RawJudgment(
        doc_id=doc_id,
        title=title,
        text=text,
        date=date,
        court=court,
        citation=citation,
        raw={},
    )


# ── Case name cleaning ────────────────────────────────────────────────────────

def test_clean_case_name_strips_date_suffix() -> None:
    assert _clean_case_name("Rangappa v. Sri Mohan on 20 August, 2010") == "Rangappa v. Sri Mohan"


def test_clean_case_name_preserves_vs() -> None:
    assert _clean_case_name("Bir Singh v. Mukesh Kumar") == "Bir Singh v. Mukesh Kumar"


def test_clean_case_name_empty() -> None:
    result = _clean_case_name("")
    assert result == "Unknown"


# ── Citation extraction ───────────────────────────────────────────────────────

def test_extract_first_citation_scc() -> None:
    text = "The court in (2010) 11 SCC 441 held that..."
    assert _extract_first_citation(text) == "(2010) 11 SCC 441"


def test_extract_first_citation_air() -> None:
    text = "As stated in AIR 1990 SC 123, the position is..."
    assert _extract_first_citation(text) == "AIR 1990 SC 123"


def test_extract_first_citation_none() -> None:
    assert _extract_first_citation("No citation here.") is None


def test_extract_multiple_citations() -> None:
    text = "(2010) 11 SCC 441 was followed in (2019) 4 SCC 197"
    citations = _extract_citation_strings(text)
    assert len(citations) == 2
    assert "(2010) 11 SCC 441" in citations
    assert "(2019) 4 SCC 197" in citations


# ── Statute reference extraction ──────────────────────────────────────────────

def test_extract_section_138_ni_act() -> None:
    text = "Liability under Section 138 of the Negotiable Instruments Act arises when..."
    refs = _extract_statute_refs(text)
    assert any("138" in r and ("NI" in r or "Negotiable" in r) for r in refs)


def test_extract_ipc_section() -> None:
    text = "Accused was charged under Section 302 of the IPC for murder."
    refs = _extract_statute_refs(text)
    assert any("302" in r and "IPC" in r for r in refs)


def test_extract_no_refs() -> None:
    text = "The court considered the factual matrix of the case."
    assert _extract_statute_refs(text) == []


# ── Overruled detection ────────────────────────────────────────────────────────

def test_detect_overruled_explicit() -> None:
    text = "The earlier decision is hereby overruled."
    assert _detect_overruled(text) is True


def test_detect_overruled_phrase() -> None:
    text = "This view is no longer good law after the Constitution Bench decision."
    assert _detect_overruled(text) is True


def test_detect_overruled_negative() -> None:
    text = "The court upheld the conviction and dismissed the appeal."
    assert _detect_overruled(text) is False


# ── Chunking ─────────────────────────────────────────────────────────────────

def test_chunk_text_basic() -> None:
    # 1000 words → multiple chunks of ~307 words each with 38-word overlap
    words = ["word"] * 1000
    text = " ".join(words)
    chunks = chunk_text(text, max_tokens=400, overlap_tokens=50)
    assert len(chunks) > 1
    # Each chunk should have roughly 307 words
    for c in chunks:
        assert len(c.split()) > 10


def test_chunk_text_small_input() -> None:
    text = "This is a short text with only fifteen words in it total here."
    chunks = chunk_text(text)
    assert len(chunks) == 1


# ── Full parse ────────────────────────────────────────────────────────────────

def test_parse_judgment_basic() -> None:
    text = (
        "Section 138 of the Negotiable Instruments Act applies here. "
        "Relying on (2010) 11 SCC 441. The accused is hereby convicted. "
        "The earlier decision AIR 1990 SC 200 stands overruled."
    ) * 20  # repeat to create enough content for multiple chunks

    raw = make_raw(text=text)
    result = parse_judgment(raw)

    assert isinstance(result, ParsedJudgment)
    assert result.doc_id == "123"
    assert result.case_name == "Rangappa v. Sri Mohan"
    assert result.citation == "(2010) 11 SCC 441"
    assert result.is_overruled is True
    assert any("138" in r for r in result.acts_cited)
    assert len(result.chunks) >= 1
    assert result.version_hash != ""
    assert result.kanoon_url == "https://indiankanoon.org/doc/123/"


def test_parse_judgment_no_citation() -> None:
    raw = make_raw(citation=None, text="Plain text with no citation markers present.")
    result = parse_judgment(raw)
    assert result.citation is None


def test_parse_judgment_court_normalisation() -> None:
    raw = make_raw(court="SC of India (3 Judge Bench)")
    result = parse_judgment(raw)
    assert result.court == "Supreme Court of India"
