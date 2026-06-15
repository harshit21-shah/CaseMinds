"""Unit tests for the 4-agent pipeline — all LLM calls mocked."""

from unittest.mock import MagicMock, patch

import pytest

from services.agents.query_classifier import ClassifiedQuery, run_query_classifier
from services.agents.retrieval_agent import run_retrieval_agent
from services.agents.state import PipelineState
from services.agents.verification_agent import _verify_citations
from services.retrieval.search import ChunkResult


# ── Fixtures ──────────────────────────────────────────────────────────────────

def base_state(**overrides) -> PipelineState:
    state: PipelineState = {
        "query": "Does Section 138 NI Act apply to post-dated cheques?",
        "query_type": None,
        "statute_refs": [],
        "case_refs": [],
        "retrieval_strategy": "HYBRID_EQUAL",
        "rewritten_query": "",
        "retrieved_chunks": [],
        "traversal_results": [],
        "overruled_warnings": [],
        "draft_answer": None,
        "verified_citations": [],
        "unverified_claims": [],
        "confidence": 0.0,
        "status": "IN_PROGRESS",
        "trace": [],
        "total_tokens_in": 0,
        "total_tokens_out": 0,
        "total_latency_ms": 0,
    }
    state.update(overrides)  # type: ignore[typeddict-item]
    return state


# ── Query Classifier ───────────────────────────────────────────────────────────

@patch("services.agents.query_classifier.invoke_structured")
def test_query_classifier_statute(mock_invoke) -> None:
    mock_invoke.return_value = (
        ClassifiedQuery(
            query_type="STATUTE",
            statute_refs=["Section 138 NI Act"],
            case_refs=[],
            retrieval_strategy="BM25_FIRST",
            rewritten_query="Section 138 Negotiable Instruments Act post-dated cheques",
        ),
        {"latency_ms": 100, "tokens_in": 50, "tokens_out": 30},
    )

    state = run_query_classifier(base_state())

    assert state["query_type"] == "STATUTE"
    assert "Section 138 NI Act" in state["statute_refs"]
    assert state["retrieval_strategy"] == "BM25_FIRST"
    assert len(state["trace"]) == 1
    assert state["trace"][0]["agent"] == "QueryClassifier"


@patch("services.agents.query_classifier.invoke_structured")
def test_query_classifier_fallback_on_error(mock_invoke) -> None:
    mock_invoke.side_effect = RuntimeError("Groq unavailable")

    state = run_query_classifier(base_state())

    assert state["query_type"] == "GENERAL"
    assert state["retrieval_strategy"] == "HYBRID_EQUAL"


# ── Retrieval Agent ────────────────────────────────────────────────────────────

@patch("services.agents.retrieval_agent.hybrid_search")
def test_retrieval_agent_returns_chunks(mock_search) -> None:
    mock_chunk = ChunkResult(
        chunk_id="doc1_chunk_0",
        doc_id="doc1",
        text="Section 138 NI Act...",
        score=0.85,
        metadata={"case_name": "Rangappa v. Sri Mohan"},
    )
    mock_search.return_value = [mock_chunk]

    state = run_retrieval_agent(
        base_state(
            rewritten_query="Section 138 NI Act post-dated cheques",
            statute_refs=["Section 138 NI Act"],
            retrieval_strategy="BM25_FIRST",
        )
    )

    assert state["status"] == "IN_PROGRESS"
    assert len(state["retrieved_chunks"]) == 1
    assert state["retrieved_chunks"][0].doc_id == "doc1"


@patch("services.agents.retrieval_agent.hybrid_search")
def test_retrieval_agent_no_results(mock_search) -> None:
    mock_search.return_value = []

    state = run_retrieval_agent(base_state())

    assert state["status"] == "NO_RESULTS"
    assert state["retrieved_chunks"] == []


# ── Verification Gate ──────────────────────────────────────────────────────────

def test_verify_citations_strips_unknown() -> None:
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    answer = "The court held in [CITE:unknown_doc] that the cheque applies."
    result_answer, verified, unverified = _verify_citations(answer, [], mock_db)

    assert "[CITATION REMOVED]" in result_answer
    assert "unknown_doc" in unverified
    assert len(verified) == 0


def test_verify_citations_verified() -> None:
    from datetime import date

    mock_judgment = MagicMock()
    mock_judgment.doc_id = "doc1"
    mock_judgment.case_name = "Rangappa v. Sri Mohan"
    mock_judgment.citation = "(2010) 11 SCC 441"
    mock_judgment.kanoon_url = "https://indiankanoon.org/doc/doc1/"
    mock_judgment.is_overruled = False

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_judgment

    answer = "Post-dated cheques are covered [CITE:doc1]."
    result_answer, verified, unverified = _verify_citations(answer, [], mock_db)

    assert "Rangappa v. Sri Mohan" in result_answer
    assert "(2010) 11 SCC 441" in result_answer
    assert len(verified) == 1
    assert len(unverified) == 0


def test_verify_citations_overruled() -> None:
    mock_judgment = MagicMock()
    mock_judgment.doc_id = "old_doc"
    mock_judgment.case_name = "Old Case"
    mock_judgment.citation = "AIR 1990 SC 100"
    mock_judgment.kanoon_url = ""
    mock_judgment.is_overruled = True

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_judgment

    answer = "The position was stated in [CITE:old_doc]."
    result_answer, verified, unverified = _verify_citations(answer, ["old_doc"], mock_db)

    assert "⚠️ OVERRULED" in result_answer
    assert verified[0]["is_overruled"] is True
    assert len(unverified) == 0


def test_confidence_below_threshold_gives_low_confidence() -> None:
    """If <85% of citations verified, status should be LOW_CONFIDENCE."""
    from services.agents.verification_agent import run_verification_answer

    chunks = [
        ChunkResult(
            chunk_id="c1",
            doc_id="doc1",
            text="Section 138 NI Act content here",
            score=0.9,
            metadata={"case_name": "Test Case"},
        )
    ]

    state = base_state(
        retrieved_chunks=chunks,
        traversal_results=chunks,
        overruled_warnings=[],
    )

    with patch("services.agents.verification_agent.invoke") as mock_invoke, \
         patch("services.agents.verification_agent._get_db_session") as mock_db:

        mock_invoke.return_value = (
            "Answer text [CITE:doc1] [CITE:fake1] [CITE:fake2]",
            {"latency_ms": 200, "tokens_in": 100, "tokens_out": 80},
        )

        # Only doc1 exists; fake1 and fake2 don't
        def side_effect(*args, **kwargs):
            mock_q = MagicMock()
            doc_id_filter = str(kwargs) + str(args)
            if "doc1" in doc_id_filter:
                j = MagicMock()
                j.doc_id = "doc1"
                j.case_name = "Test Case"
                j.citation = "(2020) 1 SCC 1"
                j.kanoon_url = ""
                j.is_overruled = False
                mock_q.filter.return_value.first.return_value = j
            else:
                mock_q.filter.return_value.first.return_value = None
            return mock_q

        mock_db.return_value.query.side_effect = side_effect

        result = run_verification_answer(state)
        assert result["status"] == "LOW_CONFIDENCE"
