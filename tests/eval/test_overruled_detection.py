"""
CM-4-07: Overruled detection eval.

Verifies that when overruled cases appear in context, they are
flagged with ⚠️ OVERRULED rather than presented as current law.

Target: ≥ 88% detection rate.
"""

import logging

import pytest

from services.agents.verification_agent import _verify_citations

logger = logging.getLogger(__name__)

OVERRULED_DETECTION_TARGET = 0.88


@pytest.mark.eval
def test_overruled_flag_in_verified_citations() -> None:
    """
    When a cited doc_id is in overruled_ids, the verification agent
    must flag it — never silently present as current law.
    """
    from unittest.mock import MagicMock

    overruled_doc_id = "overruled_doc_1"

    mock_judgment = MagicMock()
    mock_judgment.doc_id = overruled_doc_id
    mock_judgment.case_name = "Hiten P. Dalal v. Bratindranath Banerjee"
    mock_judgment.citation = "AIR 2001 SC 3402"
    mock_judgment.kanoon_url = "https://indiankanoon.org/doc/overruled_doc_1/"
    mock_judgment.is_overruled = True

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_judgment

    answer = f"As held in [CITE:{overruled_doc_id}], the cheque is covered."
    result_answer, verified, unverified = _verify_citations(
        answer, [overruled_doc_id], mock_db
    )

    assert "⚠️ OVERRULED" in result_answer, "Overruled case must show ⚠️ warning"
    assert verified[0]["is_overruled"] is True
    assert "Hiten P. Dalal" in result_answer
    assert len(unverified) == 0


@pytest.mark.eval
def test_overruled_case_not_in_clean_answer() -> None:
    """Overruled case must NOT be presented as [CaseName, Citation] without warning."""
    from unittest.mock import MagicMock

    mock_judgment = MagicMock()
    mock_judgment.doc_id = "overruled_doc_2"
    mock_judgment.case_name = "Some Overruled Case"
    mock_judgment.citation = "(2005) 3 SCC 100"
    mock_judgment.kanoon_url = ""
    mock_judgment.is_overruled = True

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_judgment

    answer = "The law was settled in [CITE:overruled_doc_2]."
    result_answer, _, _ = _verify_citations(answer, ["overruled_doc_2"], mock_db)

    # Must NOT look like a clean citation
    assert "[Some Overruled Case, (2005) 3 SCC 100]" not in result_answer
    # Must have overruled warning
    assert "⚠️ OVERRULED" in result_answer
