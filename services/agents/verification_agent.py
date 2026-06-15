"""
Agent 4 — Verification + Answer Agent (hard gate).

Steps:
  1. Format context from expanded chunks
  2. Call Groq Llama 3.3 70B to generate answer with [CITE:doc_id] tags
  3. Verify every tag against SQLite (hard gate)
  4. Replace verified tags with formatted citations
  5. Strip/warn unverified tags
  6. Compute confidence → COMPLETE or LOW_CONFIDENCE
"""

import logging
import re
from functools import lru_cache

from sqlalchemy.orm import Session

from services.agents.llm_client import GROQ_ANSWER, invoke
from services.agents.state import CitationRef, PipelineState, TraceEntry
from services.config import settings, settings as _settings
from services.api.database import SessionLocal
from services.api.models import Judgment
from services.retrieval.search import ChunkResult

logger = logging.getLogger(__name__)

DISCLAIMER = settings.disclaimer
CITE_PATTERN = re.compile(r"\[CITE:([^\]]+)\]")


@lru_cache(maxsize=1)
def _get_db_session() -> Session:
    return SessionLocal()


def run_verification_answer(state: PipelineState) -> PipelineState:
    """LangGraph node: generate + verify answer."""
    query = state["query"]
    chunks = state.get("traversal_results") or state.get("retrieved_chunks", [])
    overruled_ids = state.get("overruled_warnings", [])

    # ── Format context for LLM ────────────────────────────────────────────
    context = _format_context(chunks)
    overruled_str = (
        ", ".join(overruled_ids) if overruled_ids else "None"
    )

    # ── Generate draft answer ──────────────────────────────────────────────
    try:
        draft, usage = invoke(
            prompt_name="answer_v1",
            user_message="Generate the answer now.",
            model=GROQ_ANSWER,
            extra_vars={
                "context": context,
                "overruled_warnings": overruled_str,
                "query": query,
            },
        )
    except Exception as exc:
        logger.error("answer generation failed: %s", exc)
        return _insufficient_context(state, f"LLM error: {exc}")

    if "INSUFFICIENT_CONTEXT" in draft:
        return _insufficient_context(state, "Model returned INSUFFICIENT_CONTEXT")

    # ── Verify citations ───────────────────────────────────────────────────
    db = _get_db_session()
    answer, verified_citations, unverified_claims = _verify_citations(
        draft, overruled_ids, db
    )

    total_tags = len(CITE_PATTERN.findall(draft))
    verified_count = len(verified_citations)
    confidence = verified_count / max(total_tags, 1)

    status: str
    if verified_count == 0:
        status = "LOW_CONFIDENCE"
    elif confidence >= _settings.verification_threshold:
        status = "COMPLETE"
    elif verified_count >= _settings.verification_min_verified:
        # At least one real citation verified — answer is usable even if LLM over-cited
        status = "COMPLETE"
    else:
        status = "LOW_CONFIDENCE"

    trace_entry: TraceEntry = {
        "agent": "VerificationAnswer",
        "action": "verified",
        "detail": (
            f"tags={total_tags} verified={verified_count} "
            f"confidence={confidence:.2f} status={status}"
        ),
    }

    return {
        **state,
        "draft_answer": answer + f"\n\n---\n*{DISCLAIMER}*",
        "verified_citations": verified_citations,
        "unverified_claims": unverified_claims,
        "confidence": round(confidence, 4),
        "status": status,  # type: ignore[typeddict-item]
        "trace": state.get("trace", []) + [trace_entry],
        "total_tokens_in": state.get("total_tokens_in", 0) + (usage.get("tokens_in") or 0),
        "total_tokens_out": state.get("total_tokens_out", 0) + (usage.get("tokens_out") or 0),
        "total_latency_ms": state.get("total_latency_ms", 0) + (usage.get("latency_ms") or 0),
    }


def _format_context(chunks: list[ChunkResult]) -> str:
    import re as _re

    def _strip_html(text: str) -> str:
        """Remove HTML tags and decode common entities."""
        clean = _re.sub(r"<[^>]+>", " ", text)
        clean = clean.replace("&nbsp;", " ").replace("&amp;", "&")
        clean = clean.replace("&lt;", "<").replace("&gt;", ">")
        # Collapse whitespace / blank lines
        clean = _re.sub(r"\s{3,}", "\n\n", clean)
        return clean.strip()

    parts = []
    for c in chunks:
        meta = c.metadata or {}
        case_name = meta.get("case_name") or "Unknown"
        citation = meta.get("citation", "")
        # Clear header so the model knows exactly which doc_id to cite
        header = f"SOURCE [CITE:{c.doc_id}]  {case_name}"
        if citation:
            header += f"  |  {citation}"
        clean_text = _strip_html(c.text)
        parts.append(f"{header}\n{clean_text}")
    return "\n\n---\n\n".join(parts) if parts else "No context available."


def _verify_citations(
    answer: str,
    overruled_ids: list[str],
    db: Session,
) -> tuple[str, list[CitationRef], list[str]]:
    """
    Replace [CITE:doc_id] tags with:
      - verified: [CaseName, Citation]
      - overruled: [⚠️ OVERRULED: CaseName — verify current position]
      - not found: [CITATION REMOVED]
    """
    tags = CITE_PATTERN.findall(answer)
    verified: list[CitationRef] = []
    unverified: list[str] = []

    for doc_id in dict.fromkeys(tags):  # process each unique tag once
        row: Judgment | None = db.query(Judgment).filter(Judgment.doc_id == doc_id).first()

        if row is None:
            unverified.append(doc_id)
            answer = answer.replace(f"[CITE:{doc_id}]", "[CITATION REMOVED]")
            logger.warning("unverified citation stripped: doc_id=%s", doc_id)
        elif doc_id in overruled_ids or row.is_overruled:
            replacement = f"[⚠️ OVERRULED: {row.case_name} — verify current position]"
            answer = answer.replace(f"[CITE:{doc_id}]", replacement)
            verified.append(
                CitationRef(
                    doc_id=doc_id,
                    case_name=row.case_name,
                    citation=row.citation,
                    kanoon_url=row.kanoon_url,
                    is_overruled=True,
                    excerpt="",
                )
            )
        else:
            citation_str = row.citation or ""
            replacement = f"[{row.case_name}{', ' + citation_str if citation_str else ''}]"
            answer = answer.replace(f"[CITE:{doc_id}]", replacement)
            verified.append(
                CitationRef(
                    doc_id=doc_id,
                    case_name=row.case_name,
                    citation=row.citation,
                    kanoon_url=row.kanoon_url,
                    is_overruled=False,
                    excerpt="",
                )
            )

    return answer, verified, unverified


def _insufficient_context(state: PipelineState, reason: str) -> PipelineState:
    logger.info("insufficient context: %s", reason)
    trace_entry: TraceEntry = {
        "agent": "VerificationAnswer",
        "action": "insufficient_context",
        "detail": reason,
    }
    return {
        **state,
        "draft_answer": (
            "CaseMinds could not find sufficient authority in its corpus to answer "
            "this query confidently. Please search Indian Kanoon directly or consult "
            f"a senior colleague.\n\n---\n*{DISCLAIMER}*"
        ),
        "verified_citations": [],
        "unverified_claims": [],
        "confidence": 0.0,
        "status": "LOW_CONFIDENCE",
        "trace": state.get("trace", []) + [trace_entry],
    }
