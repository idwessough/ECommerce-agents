"""Tool-level tests for the market analysis scaffold."""

from ecommerce_agents import config
from ecommerce_agents.tools import (
    pricing_intelligence,
    review_corpus,
    review_sentiment,
    trend_signals,
)


def test_pricing_intelligence_wraps_provider_payload() -> None:
    """Pricing intelligence should expose a market and product list."""
    payload = pricing_intelligence(["Dyson V15"])

    assert payload["market"] == config.DEFAULT_MARKET
    assert payload["products"][0]["product"] == "Dyson V15"


def test_review_corpus_returns_reviews_by_product() -> None:
    """Review collection should return reviews grouped under each product."""
    payload = review_corpus(["Dyson V15"], "US")

    assert payload["market"] == "US"
    assert "Dyson V15" in payload["reviews"]
    assert len(payload["reviews"]["Dyson V15"]) == 2


def test_review_sentiment_returns_product_summaries() -> None:
    """Sentiment analysis should produce one summary per product."""
    corpus = review_corpus(["Dyson V15"], "US")

    payload = review_sentiment(corpus)

    assert payload["products"][0]["product"] == "Dyson V15"
    assert payload["products"][0]["overall_sentiment"] == "mixed_positive"


def test_trend_signals_returns_category_context() -> None:
    """Trend collection should include the requested category and market."""
    payload = trend_signals("cordless stick vacuum", "US")

    assert payload["category"] == "cordless stick vacuum"
    assert payload["market"] == "US"
