"""Tool logic for the market analysis scaffold.

The public tool functions stay thin: they call provider implementations and
normalize results into the structures used by the agent workflow.
"""

from __future__ import annotations

from collections.abc import Sequence

from .config import DEFAULT_MARKET
from .providers import MockPricingProvider, MockReviewProvider, MockTrendProvider

_PRICING_PROVIDER = MockPricingProvider()
_REVIEW_PROVIDER = MockReviewProvider()
_TREND_PROVIDER = MockTrendProvider()


def pricing_intelligence(
    product_names: Sequence[str],
    market: str = DEFAULT_MARKET,
) -> dict:
    """Return mocked MSRP and observed prices for one or more products.

    Args:
        product_names: Product names to collect pricing for.
        market: Market identifier, such as ``CA`` or ``US``.

    Returns:
        A pricing intelligence payload with MSRP and observed seller offers for
        each product.
    """
    return {
        "market": market,
        "products": _PRICING_PROVIDER.get_pricing(product_names, market),
    }


def review_corpus(
    product_names: Sequence[str],
    market: str = DEFAULT_MARKET,
) -> dict:
    """Return a mocked review corpus for one or more products.

    Args:
        product_names: Product names to collect reviews for.
        market: Market identifier, such as ``CA`` or ``US``.

    Returns:
        A deterministic review corpus keyed by product name.
    """
    return {
        "market": market,
        "reviews": _REVIEW_PROVIDER.get_reviews(product_names, market),
    }


def review_sentiment(review_corpus: dict) -> dict:
    """Return deterministic sentiment insights from a review corpus.

    Args:
        review_corpus: Review payload returned by ``review_corpus``.

    Returns:
        A compact summary of praise themes, pain points, and overall polarity.
    """
    return {"products": _REVIEW_PROVIDER.summarize_sentiment(review_corpus)}


def trend_signals(category: str, market: str = DEFAULT_MARKET) -> dict:
    """Return mocked trend signals for a category.

    Args:
        category: Product category to analyze.
        market: Market identifier, such as ``CA`` or ``US``.

    Returns:
        A deterministic summary of demand, trend direction, and price pressure.
    """
    return _TREND_PROVIDER.get_trends(category, market)
