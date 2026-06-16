"""Background corpus seed job — trigger via HTTP (Render free tier has no Shell)."""

from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_state: dict[str, Any] = {
    "running": False,
    "phase": "idle",
    "error": None,
    "result": None,
}


def get_seed_status() -> dict[str, Any]:
    with _lock:
        return dict(_state)


def start_seed_job(*, fast: bool = True, incremental: bool = True, demo: bool = False) -> bool:
    """Start seed in a background thread. Returns False if already running."""
    with _lock:
        if _state["running"]:
            return False
        _state.update({"running": True, "phase": "starting", "error": None, "result": None})

    def _worker() -> None:
        try:
            with _lock:
                _state["phase"] = "judgments"
            from services.ingestion.corpus_seed import run_full_seed

            result = run_full_seed(fast=fast, incremental=incremental, demo=demo)
            with _lock:
                _state["phase"] = "complete"
                _state["result"] = result
            logger.info("background seed complete: %s", result)
        except Exception as exc:
            logger.exception("background seed failed")
            with _lock:
                _state["phase"] = "failed"
                _state["error"] = str(exc)
        finally:
            with _lock:
                _state["running"] = False

    threading.Thread(target=_worker, daemon=True, name="corpus-seed").start()
    return True
