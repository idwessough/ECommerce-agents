"""Tests for parsing and messaging around the user-selected execution mode."""

from ecommerce_agents.mode import (
    build_live_mode_unavailable_message,
    build_mode_selection_message,
    extract_mode_and_clean_text,
    normalize_mode,
)


def test_normalize_mode_accepts_supported_values_case_insensitively() -> None:
    """Supported mode labels should normalize to lowercase canonical values."""
    assert normalize_mode(" Demo ") == "demo"
    assert normalize_mode("LIVE") == "live"
    assert normalize_mode("offline") is None


def test_extract_mode_and_clean_text_handles_inline_mode_selection() -> None:
    """Inline mode selectors should keep only the product request text."""
    mode, cleaned_text = extract_mode_and_clean_text(
        "mode: demo Analyze Dyson V15 vacuum",
    )

    assert mode == "demo"
    assert cleaned_text == "Analyze Dyson V15 vacuum"


def test_extract_mode_and_clean_text_handles_mode_only_messages() -> None:
    """Mode-only messages should leave the downstream request text empty."""
    mode, cleaned_text = extract_mode_and_clean_text("live")

    assert mode == "live"
    assert cleaned_text == ""


def test_mode_messages_reflect_live_key_availability() -> None:
    """User guidance should mention live mode only when it is actually available."""
    assert "reply with `demo` or `live`" in build_mode_selection_message(True)
    assert "Live mode needs a valid Gemini API key." in build_mode_selection_message(False)
    assert "Choose `demo` instead" in build_live_mode_unavailable_message()
