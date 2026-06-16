"""
Seed script — builds the full corpus from scratch.

Run: python scripts/seed.py
     python scripts/seed.py --fast --incremental
     python scripts/seed.py --demo          # quick portfolio subset (~15 min)
     OR: make seed
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.ingestion.corpus_seed import run_full_seed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)


def main(fast: bool = False, incremental: bool = False, demo: bool = False) -> None:
    result = run_full_seed(fast=fast, incremental=incremental, demo=demo)
    print(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the CaseMinds corpus")
    parser.add_argument("--fast", action="store_true", help="Skip LLM citation extraction")
    parser.add_argument("--incremental", action="store_true", help="Skip existing doc_ids")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Small subset only (4 topics, 1 page each) — good for Render free tier",
    )
    args = parser.parse_args()
    main(fast=args.fast, incremental=args.incremental, demo=args.demo)
