"""
Central LLM client for CaseMinds.

All LLM calls must go through this module — never call Groq/Anthropic SDKs
directly in agent code. This enforces:
  - Cost logging
  - Prompt versioning
  - Automatic fallback (Groq → Claude Haiku)
"""

import logging
import time
from pathlib import Path
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from services.config import settings

logger = logging.getLogger(__name__)

# ── Model identifiers ────────────────────────────────────────────────────────

GROQ_CLASSIFIER = settings.groq_classifier_model
GROQ_ANSWER = settings.groq_answer_model
CLAUDE_FALLBACK = settings.claude_fallback_model

# ── Prompt loading ────────────────────────────────────────────────────────────

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(name: str) -> str:
    """Load a versioned prompt from services/agents/prompts/<name>.txt"""
    path = _PROMPTS_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


# ── Client factory ─────────────────────────────────────────────────────────────

def _get_groq_client(model: str, temperature: float = 0.0) -> ChatGroq:
    return ChatGroq(
        model=model,
        temperature=temperature,
        api_key=settings.groq_api_key,
    )


def _get_anthropic_client(temperature: float = 0.0) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic  # lazy import — optional dependency

    return ChatAnthropic(
        model=CLAUDE_FALLBACK,
        temperature=temperature,
        api_key=settings.anthropic_api_key,  # type: ignore[arg-type]
    )


# ── Invoke with logging + fallback ────────────────────────────────────────────

def invoke(
    *,
    prompt_name: str,
    user_message: str,
    model: str = GROQ_ANSWER,
    temperature: float = 0.0,
    extra_vars: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """
    Invoke an LLM using a named prompt file.

    Returns:
        (response_text, usage_dict)
    """
    system_prompt = load_prompt(prompt_name)
    if extra_vars:
        system_prompt = system_prompt.format(**extra_vars)

    messages: list[BaseMessage] = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]

    start = time.perf_counter()
    usage: dict[str, Any] = {"model": model, "prompt_name": prompt_name}

    try:
        client = _get_groq_client(model, temperature)
        response = client.invoke(messages)
        elapsed = (time.perf_counter() - start) * 1000

        usage.update(
            {
                "latency_ms": round(elapsed),
                "tokens_in": getattr(response.usage_metadata, "input_tokens", None),
                "tokens_out": getattr(response.usage_metadata, "output_tokens", None),
                "fallback_used": False,
            }
        )
        logger.info(
            "llm_invoke model=%s prompt=%s latency_ms=%d",
            model,
            prompt_name,
            elapsed,
        )
        return str(response.content), usage

    except Exception as groq_err:
        logger.warning("Groq failed (%s), falling back to Claude Haiku", groq_err)

        if not settings.anthropic_api_key:
            raise RuntimeError(
                f"Groq failed and no ANTHROPIC_API_KEY set. Original error: {groq_err}"
            ) from groq_err

        client_fb = _get_anthropic_client(temperature)
        response_fb = client_fb.invoke(messages)
        elapsed = (time.perf_counter() - start) * 1000

        usage.update(
            {
                "model": CLAUDE_FALLBACK,
                "latency_ms": round(elapsed),
                "tokens_in": getattr(response_fb.usage_metadata, "input_tokens", None),
                "tokens_out": getattr(response_fb.usage_metadata, "output_tokens", None),
                "fallback_used": True,
            }
        )
        logger.info(
            "llm_invoke(fallback) model=%s prompt=%s latency_ms=%d",
            CLAUDE_FALLBACK,
            prompt_name,
            elapsed,
        )
        return str(response_fb.content), usage


def invoke_structured(
    *,
    prompt_name: str,
    user_message: str,
    model: str = GROQ_CLASSIFIER,
    schema: type,
    temperature: float = 0.0,
) -> tuple[Any, dict[str, Any]]:
    """
    Invoke an LLM and parse the response into a Pydantic schema.
    Uses structured output (with_structured_output) when available.
    """
    system_prompt = load_prompt(prompt_name)

    messages: list[BaseMessage] = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]

    start = time.perf_counter()
    usage: dict[str, Any] = {"model": model, "prompt_name": prompt_name}

    try:
        client = _get_groq_client(model, temperature).with_structured_output(schema)
        result = client.invoke(messages)
        elapsed = (time.perf_counter() - start) * 1000
        usage["latency_ms"] = round(elapsed)
        usage["fallback_used"] = False
        return result, usage

    except Exception as groq_err:
        logger.warning("Groq structured output failed (%s), falling back", groq_err)

        if not settings.anthropic_api_key:
            raise RuntimeError(str(groq_err)) from groq_err

        client_fb = _get_anthropic_client(temperature).with_structured_output(schema)
        result_fb = client_fb.invoke(messages)
        elapsed = (time.perf_counter() - start) * 1000
        usage["latency_ms"] = round(elapsed)
        usage["model"] = CLAUDE_FALLBACK
        usage["fallback_used"] = True
        return result_fb, usage
