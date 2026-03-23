"""Provider-level tests for the market analysis scaffold."""

from ecommerce_agents.providers.mock import (
    MockPricingProvider,
    MockReviewProvider,
    MockTrendProvider,
)


def test_mock_pricing_provider_returns_products() -> None:
    """The pricing provider should return one record per requested product."""
    provider = MockPricingProvider()

    products = provider.get_pricing(["Dyson V15", "Shark Detect Pro"], "US")

    assert len(products) == 2
    assert products[0]["product"] == "Dyson V15"
    assert products[0]["msrp"]["source"] == "official_brand_site"
    assert products[0]["offers"]


def test_mock_review_provider_injects_product_name() -> None:
    """Review templates should be rendered with the target product name."""
    provider = MockReviewProvider()

    reviews = provider.get_reviews(["Dyson V15"], "US")

    assert "Dyson V15" in reviews
    assert any("Dyson V15" in entry["text"] for entry in reviews["Dyson V15"])


def test_mock_trend_provider_formats_summary() -> None:
    """Trend summaries should interpolate the requested category and market."""
    provider = MockTrendProvider()

    trend_payload = provider.get_trends("cordless stick vacuum", "US")

    assert trend_payload["category"] == "cordless stick vacuum"
    assert trend_payload["market"] == "US"
    assert "cordless stick vacuum" in trend_payload["trend_summary"]