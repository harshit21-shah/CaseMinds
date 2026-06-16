"""Seed bare Act section texts from Indian Kanoon. Run: python scripts/seed_statutes.py"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.ingestion.corpus_seed import run_statute_seed

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")


def main() -> None:
    count = run_statute_seed()
    print(f"statutes indexed: {count}")


if __name__ == "__main__":
    main()
