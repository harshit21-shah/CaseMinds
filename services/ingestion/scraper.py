"""
Indian Kanoon API scraper.

Politely fetches judgment list + full text from the free Indian Kanoon API.
All raw responses cached to data/raw/{doc_id}.json — never re-fetched.
"""

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from services.config import settings

logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw")
BASE_URL = "https://api.indiankanoon.org"
POLITE_DELAY_S = settings.scraper_polite_delay_s


@dataclass
class RawJudgment:
    doc_id: str
    title: str
    text: str
    date: str | None
    court: str | None
    citation: str | None
    raw: dict  # full API response for debugging


class IndianKanoonScraper:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.indian_kanoon_api_key
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers={"Authorization": f"Token {self.api_key}"},
            timeout=settings.scraper_timeout_s,
        )
        RAW_DIR.mkdir(parents=True, exist_ok=True)

    # ── Search ─────────────────────────────────────────────────────────────

    def search(self, query: str, max_pages: int = 5) -> list[str]:
        """
        Search Indian Kanoon and return a list of doc_ids.
        Paginates up to max_pages (10 results/page).
        """
        doc_ids: list[str] = []
        for page in range(max_pages):
            try:
                resp = self._client.post(
                    "/search/",
                    data={"formInput": query, "pagenum": page},
                )
                resp.raise_for_status()
                data = resp.json()
                page_ids = [str(d["tid"]) for d in data.get("docs", []) if d.get("tid")]
                doc_ids.extend(page_ids)
                logger.debug("search page=%d query='%s' found=%d", page, query, len(page_ids))
                if not page_ids:
                    break
                time.sleep(POLITE_DELAY_S)
            except httpx.HTTPError as exc:
                logger.warning("search failed page=%d: %s", page, exc)
                break

        return list(dict.fromkeys(doc_ids))  # deduplicate preserving order

    # ── Fetch single judgment ──────────────────────────────────────────────

    def fetch(self, doc_id: str) -> RawJudgment:
        """
        Fetch full judgment text + metadata.
        Reads from cache (data/raw/{doc_id}.json) if available.
        """
        cache_path = RAW_DIR / f"{doc_id}.json"

        if cache_path.exists():
            raw = json.loads(cache_path.read_text(encoding="utf-8"))
            logger.debug("cache hit doc_id=%s", doc_id)
        else:
            logger.info("fetching doc_id=%s", doc_id)
            try:
                resp = self._client.post(f"/doc/{doc_id}/")
                resp.raise_for_status()
                raw = resp.json()
                cache_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
                time.sleep(POLITE_DELAY_S)
            except httpx.HTTPError as exc:
                raise RuntimeError(f"Failed to fetch doc_id={doc_id}: {exc}") from exc

        return RawJudgment(
            doc_id=doc_id,
            title=raw.get("title", ""),
            text=raw.get("doc", ""),
            date=raw.get("publishdate"),
            court=raw.get("docsource"),
            citation=raw.get("citation"),
            raw=raw,
        )

    # ── Batch fetch ────────────────────────────────────────────────────────

    def fetch_many(self, doc_ids: list[str]) -> list[RawJudgment]:
        """Fetch a list of doc_ids, skipping any that fail."""
        results: list[RawJudgment] = []
        for i, doc_id in enumerate(doc_ids):
            try:
                results.append(self.fetch(doc_id))
                logger.info("fetched %d/%d doc_id=%s", i + 1, len(doc_ids), doc_id)
            except RuntimeError as exc:
                logger.warning("skipping doc_id=%s: %s", doc_id, exc)
        return results

    def __enter__(self) -> "IndianKanoonScraper":
        return self

    def __exit__(self, *_: object) -> None:
        self._client.close()
