"""
CM-4-09: CI eval regression gate.

Reads the latest eval results and fails if any metric is below threshold.
Called by: make eval-all → GitHub Actions eval gate.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from services.config import settings  # noqa: E402

RESULTS_DIR = Path("services/eval/results")

THRESHOLDS = {
    "citation_accuracy": settings.eval_citation_accuracy_target,
    "overruled_detection": settings.eval_overruled_detection_target,
    "retrieval_precision_at_5": settings.eval_retrieval_precision_target,
}


def main() -> None:
    if not RESULTS_DIR.exists():
        print("No eval results directory found — skipping regression check")
        sys.exit(0)

    report_files = sorted(RESULTS_DIR.glob("*/summary.json"), reverse=True)
    if not report_files:
        print("No eval summary found — skipping regression check")
        sys.exit(0)

    data = json.loads(report_files[0].read_text())
    print(f"Checking eval run: {data.get('run_id', 'unknown')}")

    failures = []
    for metric, threshold in THRESHOLDS.items():
        value = data.get(metric)
        if value is None:
            print(f"  {metric}: N/A (skipping)")
            continue
        status = "✅" if value >= threshold else "❌"
        print(f"  {status} {metric}: {value:.0%} (threshold: {threshold:.0%})")
        if value < threshold:
            failures.append(f"{metric} = {value:.0%} < {threshold:.0%}")

    if failures:
        print("\nREGRESSION DETECTED — blocking deployment:")
        for f in failures:
            print(f"  • {f}")
        sys.exit(1)
    else:
        print("\nAll metrics pass. Eval gate green. ✅")
        sys.exit(0)


if __name__ == "__main__":
    main()
