"""Configuration-level tests for the market analysis scaffold."""

from ecommerce_agents import config


def test_default_market_matches_architecture_examples() -> None:
    """The scaffold should default to the Canadian market when none is provided."""
    assert config.DEFAULT_MARKET == "CA"


def test_default_model_uses_gemini_3_1_pro_preview_for_search_grounding() -> None:
    """The scaffold should default to the current Gemini 3.1 search-grounding model."""
    assert config.DEFAULT_MODEL == "gemini-3.1-pro-preview"


def test_analysis_db_path_defaults_to_repo_local_adk_storage() -> None:
    """Completed analyses should persist under the repo-local ADK directory by default."""
    assert config.ANALYSIS_DB_PATH.endswith(".adk/analysis_history.db")
