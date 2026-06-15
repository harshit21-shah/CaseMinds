"""
Structured JSON logger for CaseMinds.

Every agent run emits a machine-readable JSON log line with:
  trace_id, agent, action, latency_ms, tokens, confidence, status

Makes it trivial to grep/aggregate logs in production.
Swap to Langfuse in V2 without changing call sites.
"""

import json
import logging
import sys
import time
from contextvars import ContextVar
from typing import Any

# Context variable — set once per request, available across all agents
_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


def set_trace_id(trace_id: str) -> None:
    _trace_id_var.set(trace_id)


def get_trace_id() -> str:
    return _trace_id_var.get()


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON for structured log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        log: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "trace_id": get_trace_id(),
            "msg": record.getMessage(),
        }
        if record.exc_info:
            log["exc"] = self.formatException(record.exc_info)
        # Attach any extra fields passed via extra={}
        for key, val in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            ):
                log[key] = val
        return json.dumps(log, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Call once at application startup."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


class AgentTimer:
    """Context manager: measures elapsed time and logs a structured event."""

    def __init__(self, agent: str, action: str, trace_id: str = "") -> None:
        self.agent = agent
        self.action = action
        self.trace_id = trace_id or get_trace_id()
        self._start = 0.0
        self._logger = logging.getLogger(f"caseminds.{agent.lower()}")

    def __enter__(self) -> "AgentTimer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_: object) -> None:
        elapsed_ms = round((time.perf_counter() - self._start) * 1000)
        self._logger.info(
            "%s.%s completed",
            self.agent,
            self.action,
            extra={"agent": self.agent, "action": self.action, "elapsed_ms": elapsed_ms},
        )
