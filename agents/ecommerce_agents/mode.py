"""Helpers for parsing and normalizing the user-selected execution mode."""

from __future__ import annotations

import re

MODE_KEY = "mode"
DEMO_MODE = "demo"
LIVE_MODE = "live"
VALID_MODES = {DEMO_MODE, LIVE_MODE}

_MODE_INLINE_PATTERN = re.compile(r"\bmode\s*[:=]\s*(demo|live)\b", re.IGNORECASE)
_MODE_PREFIX_PATTERN = re.compile(
    r"^\s*(demo|live)\b(?:\s*[:|\-]\s*|\s+)",
    re.IGNORECASE,
)


def normalize_mode(raw_mode: str | None) -> str | None:
    """Return a normalized mode value when it is supported."""
    if raw_mode is None:
        return None

    candidate = raw_mode.strip().lower()
    return candidate if candidate in VALID_MODES else None


def extract_mode_and_clean_text(raw_text: str) -> tuple[str | None, str]:
    """Extract an inline mode selector and the remaining user request text."""
    text = raw_text.strip()
    if not text:
        return None, ""

    mode_match = _MODE_INLINE_PATTERN.search(text)
    if mode_match:
        mode = normalize_mode(mode_match.group(1))
        cleaned_text = f"{text[:mode_match.start()]} {text[mode_match.end():]}".strip()
        return mode, _normalize_whitespace(cleaned_text.strip(" |,-:"))

    exact_mode = normalize_mode(text)
    if exact_mode:
        return exact_mode, ""

    prefix_match = _MODE_PREFIX_PATTERN.match(text)
    if prefix_match:
        mode = normalize_mode(prefix_match.group(1))
        cleaned_text = text[prefix_match.end() :]
        return mode, _normalize_whitespace(cleaned_text.strip(" |,-:"))

    return None, _normalize_whitespace(text)


def build_mode_selection_message(has_live_mode: bool) -> str:
    """Return the user-facing message used to select the current mode."""
    if has_live_mode:
        return (
            "Choose a mode before starting: reply with `demo` or `live`, or send "
            "one message like `mode: demo Analyze Dyson V15`."
        )

    return (
        "Choose a mode before starting: reply with `demo`, or use "
        "`mode: demo Analyze Dyson V15`. Live mode needs a valid Gemini API key."
    )


def build_live_mode_unavailable_message() -> str:
    """Return the user-facing message shown when live mode cannot be used."""
    return (
        "Live mode is unavailable because no valid Gemini API key is configured. "
        "Choose `demo` instead or add a valid key in `docker-compose.yml`."
    )


def _normalize_whitespace(raw_text: str) -> str:
    """Collapse repeated whitespace to keep parsed user requests stable."""
    return re.sub(r"\s+", " ", raw_text).strip()
