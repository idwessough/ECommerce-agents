"""Mock provider implementations backed by package fixtures."""

from __future__ import annotations

import json
from collections.abc import Sequence
from functools import lru_cache
from importlib.resources import files

FIXTURE_PACKAGE = "ecommerce_agents.data"


@lru_cache(maxsize=None)
def _load_fixture(filename: str) -> dict:
    """Load a JSON fixture from the package data directory.

    Args:
        filename: Name of the JSON fixture to load.

    Returns:
        The decoded JSON payload.
    """
    fixture_path = files(FIXTURE_PACKAGE).joinpath(filename)
    return json.loads(fixture_path.read_text(encoding="utf-8"))


class MockPricingProvider:
    """Fixture-backed pricing provider for local development."""

    def get_pricing(self, product_names: Sequence[str], market: str) -> list[dict]:
        """Return mocked pricing records for the requested products."""
        pricing_fixture = _load_fixture("pricing.json")
        base_prices = pricing_fixture["base_prices"]
        seller_templates = pricing_fixture["seller_templates"]
        msrp_markup = pricing_fixture["msrp_markup"]
        products: list[dict] = []

        for index, product_name in enumerate(product_names):
            base_price = base_prices[index % len(base_prices)]
            offers = [
                {
                    "seller": seller_template["seller"],
                    "price": round(base_price + seller_template["price_offset"], 2),
                    "availability": seller_template["availability"],
                }
                for seller_template in seller_templates
            ]
            products.append(
                {
                    "product": product_name,
                    "market": market,
                    "currency": pricing_fixture["currency"],
                    "msrp": {
                        "amount": round(base_price + msrp_markup, 2),
                        "source": pricing_fixture["msrp_source"],
                    },
                    "offers": offers,
                }
            )

        return products


class MockReviewProvider:
    """Fixture-backed review provider for local development."""

    def get_reviews(self, product_names: Sequence[str], market: str) -> dict[str, list[dict]]:
        """Return mocked reviews keyed by product name."""
        review_fixture = _load_fixture("reviews.json")
        reviews: dict[str, list[dict]] = {}

        for product_name in product_names:
            reviews[product_name] = [
                {
                    "rating": review_template["rating"],
                    "text": review_template["text_template"].format(
                        product_name=product_name,
                    ),
                    "source": review_template["source"],
                    "market": market,
                }
                for review_template in review_fixture["entries"]
            ]

        return reviews

    def summarize_sentiment(self, review_corpus: dict) -> list[dict]:
        """Return a deterministic sentiment summary for the supplied corpus."""
        summary_template = _load_fixture("reviews.json")["sentiment_summary_template"]
        return [
            {
                "product": product_name,
                "review_count": len(entries),
                "top_praise_themes": summary_template["top_praise_themes"],
                "top_pain_points": summary_template["top_pain_points"],
                "overall_sentiment": summary_template["overall_sentiment"],
            }
            for product_name, entries in review_corpus.get("reviews", {}).items()
        ]


class MockTrendProvider:
    """Fixture-backed trend provider for local development."""

    def get_trends(self, category: str, market: str) -> dict:
        """Return mocked trend signals for the requested category."""
        trend_fixture = _load_fixture("trends.json")["default"]
        return {
            "category": category,
            "market": market,
            "demand_signal": trend_fixture["demand_signal"],
            "price_pressure": trend_fixture["price_pressure"],
            "trend_summary": trend_fixture["trend_summary_template"].format(
                category=category,
                market=market,
            ),
        }