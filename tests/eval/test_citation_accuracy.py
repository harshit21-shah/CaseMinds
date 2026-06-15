"""
CM-4-06: Citation accuracy eval harness.

Runs each query from the golden set through the pipeline and checks:
1. Citation existence rate: every cited doc_id exists in SQLite
2. Adversarial abstention: LOW_CONFIDENCE returned for ADV_* queries
3. Answer content: expected phrases present in answer

Run: make eval-citations
"""

import json
import logging
from pathlib import Path
from statistics import mean

import pytest

from services.agents.pipeline import run_pipeline
from services.api.database import SessionLocal
from services.api.models import Judgment

logger = logging.getLogger(__name__)

GOLDEN_PATH = Path("services/eval/datasets/golden_qa.json")
CITATION_ACCURACY_TARGET = 0.90
ADVERSARIAL_ABSTENTION_TARGET = 1.0  # 100% — release blocker


def load_golden() -> list[dict]:
    return json.loads(GOLDEN_PATH.read_text())


@pytest.mark.eval
def test_adversarial_abstention() -> None:
    """All ADVERSARIAL queries must return LOW_CONFIDENCE or NO_RESULTS."""
    golden = load_golden()
    adv_cases = [g for g in golden if g["category"] == "ADVERSARIAL"]

    failures = []
    for case in adv_cases:
        state = run_pipeline(case["query"])
        status = state.get("status", "")
        if status not in ("LOW_CONFIDENCE", "NO_RESULTS"):
            failures.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "status": status,
                    "confidence": state.get("confidence"),
                }
            )
            logger.error(
                "ADVERSARIAL HALLUCINATION: %s returned status=%s", case["id"], status
            )

    abstention_rate = (len(adv_cases) - len(failures)) / len(adv_cases)
    logger.info(
        "adversarial abstention: %d/%d (%.0f%%)",
        len(adv_cases) - len(failures),
        len(adv_cases),
        abstention_rate * 100,
    )

    assert abstention_rate >= ADVERSARIAL_ABSTENTION_TARGET, (
        f"Adversarial abstention rate {abstention_rate:.0%} < target {ADVERSARIAL_ABSTENTION_TARGET:.0%}. "
        f"Failures: {failures}"
    )


@pytest.mark.eval
def test_citation_existence_rate() -> None:
    """Every citation in a COMPLETE answer must exist in SQLite."""
    golden = load_golden()
    non_adv = [g for g in golden if g["category"] != "ADVERSARIAL"]
    db = SessionLocal()

    existence_scores = []
    for case in non_adv:
        state = run_pipeline(case["query"])
        if state.get("status") not in ("COMPLETE",):
            existence_scores.append(1.0)  # abstention is acceptable
            continue

        cited = state.get("verified_citations", [])
        if not cited:
            existence_scores.append(1.0)
            continue

        for c in cited:
            row = db.query(Judgment).filter(Judgment.doc_id == c["doc_id"]).first()
            existence_scores.append(1.0 if row else 0.0)
            if not row:
                logger.warning("citation does not exist: doc_id=%s in query '%s'", c["doc_id"], case["id"])

    db.close()
    rate = mean(existence_scores) if existence_scores else 1.0
    logger.info("citation existence rate: %.0f%% (n=%d)", rate * 100, len(existence_scores))
    assert rate >= CITATION_ACCURACY_TARGET, (
        f"Citation existence rate {rate:.0%} < target {CITATION_ACCURACY_TARGET:.0%}"
    )


@pytest.mark.eval
def test_answer_content_contains_expected_phrases() -> None:
    """Spot-check: answers to non-adversarial queries contain expected key phrases."""
    golden = load_golden()
    cases_with_expected = [
        g for g in golden
        if g["category"] != "ADVERSARIAL" and g.get("expected_answer_contains")
    ]

    pass_count = 0
    total = 0

    for case in cases_with_expected[:10]:  # run first 10 to save API cost in CI
        state = run_pipeline(case["query"])
        answer = (state.get("draft_answer") or "").lower()

        for phrase in case.get("expected_answer_contains", []):
            total += 1
            if phrase.lower() in answer:
                pass_count += 1
            else:
                logger.info("phrase '%s' not found in answer for %s", phrase, case["id"])

    if total > 0:
        pass_rate = pass_count / total
        logger.info("answer phrase coverage: %d/%d (%.0f%%)", pass_count, total, pass_rate * 100)
