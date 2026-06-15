"""
Two-pass citation extractor.

Pass 1 — Regex (fast, ~70-80% recall): handled inside parser.py
Pass 2 — LLM batch (Groq, for paragraphs with relational phrases but no regex match)

Output: list[CitationExtraction] per judgment
"""

import logging
import re
from dataclasses import dataclass
from typing import Literal

from services.agents.llm_client import GROQ_CLASSIFIER, invoke
from services.config import settings
from services.ingestion.parser import ParsedJudgment

logger = logging.getLogger(__name__)

# Paragraphs containing these phrases go to LLM pass
RELATIONAL_PHRASES = re.compile(
    r"\b(relying on|as held in|following|distinguished|overruled|relied upon|"
    r"approved in|dissented from|reversed by|affirmed by|referred to)\b",
    re.IGNORECASE,
)

BATCH_SIZE = settings.citation_llm_batch_size


@dataclass
class CitationExtraction:
    case_name: str
    year: str | None
    relationship: Literal["CITES", "DISTINGUISHES", "OVERRULES", "CITED_BY"]
    raw_text: str  # source paragraph for debugging


def extract_citations_llm(judgment: ParsedJudgment) -> list[CitationExtraction]:
    """
    Pass 2: Send candidate paragraphs to Groq Llama 3.3 8B for citation extraction.
    Batches 5 paragraphs per call to minimise API cost.
    """
    paragraphs = _get_candidate_paragraphs(judgment.full_text)
    if not paragraphs:
        return []

    results: list[CitationExtraction] = []
    for i in range(0, len(paragraphs), BATCH_SIZE):
        batch = paragraphs[i : i + BATCH_SIZE]
        batch_results = _extract_batch(batch)
        results.extend(batch_results)

    logger.info(
        "llm citation pass2 doc_id=%s paragraphs=%d citations=%d",
        judgment.doc_id,
        len(paragraphs),
        len(results),
    )
    return results


def _get_candidate_paragraphs(text: str) -> list[str]:
    """Return paragraphs that have relational phrases but are not already caught by regex."""
    paras = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 50]
    return [p for p in paras if RELATIONAL_PHRASES.search(p)][:settings.citation_llm_max_paragraphs]


def _extract_batch(paragraphs: list[str]) -> list[CitationExtraction]:
    """Send a batch of paragraphs to Groq and parse citation extractions."""
    numbered = "\n\n".join(f"[{i+1}] {p}" for i, p in enumerate(paragraphs))
    user_message = f"Extract citations from these paragraphs:\n\n{numbered}"

    try:
        response_text, _ = invoke(
            prompt_name="citation_extractor_v1",
            user_message=user_message,
            model=GROQ_CLASSIFIER,
        )
        return _parse_llm_response(response_text, paragraphs)
    except Exception as exc:
        logger.warning("LLM citation extraction failed: %s", exc)
        return []


def _parse_llm_response(response: str, paragraphs: list[str]) -> list[CitationExtraction]:
    """Parse JSON array response from LLM into CitationExtraction objects."""
    import json

    extractions: list[CitationExtraction] = []
    try:
        # LLM should return a JSON array
        json_match = re.search(r"\[.*\]", response, re.DOTALL)
        if not json_match:
            return []

        items = json.loads(json_match.group(0))
        for item in items:
            if not isinstance(item, dict):
                continue
            relationship = (item.get("relationship") or "CITES").upper()
            if relationship not in ("CITES", "DISTINGUISHES", "OVERRULES", "CITED_BY"):
                relationship = "CITES"
            para_idx = item.get("paragraph_index", 1) - 1
            raw_text = paragraphs[para_idx] if 0 <= para_idx < len(paragraphs) else ""
            extractions.append(
                CitationExtraction(
                    case_name=item.get("case_name", ""),
                    year=str(item.get("year", "")) or None,
                    relationship=relationship,  # type: ignore[arg-type]
                    raw_text=raw_text,
                )
            )
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        logger.debug("Failed to parse LLM citation response: %s", exc)

    return extractions
