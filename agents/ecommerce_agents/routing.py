"""Routing helpers for the market analysis orchestration flow."""

from __future__ import annotations

import json
from typing import Any

from .config import DEFAULT_MARKET
from .schemas import ResearchScope


def parse_research_scope(raw_scope: Any) -> ResearchScope:
    """Return a normalized research scope from raw session-state data.

    The product scoping agent may store a dictionary or a JSON string in state.
    This helper keeps orchestration resilient by accepting both formats and
    falling back to a clarification-required scope when parsing fails.

    Args:
        raw_scope: The raw ``research_scope`` value read from session state.

    Returns:
        A normalized ``ResearchScope`` instance.
    """
    if isinstance(raw_scope, ResearchScope):
        return raw_scope

    payload: dict[str, Any]
    if isinstance(raw_scope, dict):
        payload = raw_scope
    elif isinstance(raw_scope, str):
        payload = _parse_json_object(raw_scope)
    else:
        payload = {}

    payload.setdefault("market", DEFAULT_MARKET)

    try:
        return ResearchScope.model_validate(payload)
    except Exception:
        return ResearchScope(
            market=DEFAULT_MARKET,
            requires_clarification=True,
            resolution_confidence=0.0,
        )


def should_request_clarification(scope: ResearchScope) -> bool:
    """Return whether orchestration should stop and ask a follow-up question.

    Args:
        scope: The normalized research scope produced by the product scoping step.

    Returns:
        ``True`` when the workflow should pause for clarification instead of
        starting competitor discovery and downstream research.
    """
    if scope.requires_clarification:
        return True

    if not scope.canonical_product_name.strip():
        return True

    if scope.resolution_confidence < 0.6:
        return True

    return False


def _parse_json_object(raw_text: str) -> dict[str, Any]:
    """Extract a JSON object from a raw model response string.

    Args:
        raw_text: Raw response text that may include surrounding prose or fences.

    Returns:
        The decoded JSON object when parsing succeeds, otherwise an empty dict.
    """
    text = raw_text.strip()
    if not text:
        return {}

    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}

    candidate = text[start : end + 1]

    try:
        loaded = json.loads(candidate)
    except json.JSONDecodeError:
        return {}

    return loaded if isinstance(loaded, dict) else {}