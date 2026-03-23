"""Deterministic demo-mode helpers for local tool-backed market analysis."""

from __future__ import annotations

import re
from collections.abc import Mapping
from statistics import mean
from typing import Any

from .config import DEFAULT_MARKET
from .schemas import ResearchScope
from .tools import pricing_intelligence, review_corpus, review_sentiment, trend_signals

_GENERIC_CATEGORY = "consumer product"
_ACTION_PREFIXES = (
    "analyze",
    "analyse",
    "review",
    "compare",
    "research",
    "assess",
    "show me",
    "give me",
    "market analysis for",
    "market analysis of",
)
_MARKET_PATTERNS = (
    (re.compile(r"\b(canada|canadian market|ca market|market ca)\b", re.IGNORECASE), "CA"),
    (re.compile(r"\b(us|usa|united states|american market|market us)\b", re.IGNORECASE), "US"),
)
_CATEGORY_HINTS = (
    ("vacuum", "cordless stick vacuum"),
    ("airpods", "wireless earbuds"),
    ("earbuds", "wireless earbuds"),
    ("headphones", "noise-cancelling headphones"),
    ("iphone", "smartphone"),
    ("pixel", "smartphone"),
    ("galaxy", "smartphone"),
    ("shoe", "running shoes"),
    ("sneaker", "running shoes"),
    ("laptop", "laptop"),
    ("notebook", "laptop"),
)
_COMPETITOR_LIBRARY: dict[str, list[dict[str, Any]]] = {
    "cordless stick vacuum": [
        {"brand": "Shark", "model": "Detect Pro", "confidence": 0.91},
        {"brand": "Tineco", "model": "Pure One S15", "confidence": 0.88},
        {"brand": "Samsung", "model": "Bespoke Jet", "confidence": 0.84},
    ],
    "wireless earbuds": [
        {"brand": "Sony", "model": "WF-1000XM5", "confidence": 0.91},
        {"brand": "Bose", "model": "QuietComfort Ultra Earbuds", "confidence": 0.88},
        {"brand": "Samsung", "model": "Galaxy Buds3 Pro", "confidence": 0.82},
    ],
    "noise-cancelling headphones": [
        {"brand": "Sony", "model": "WH-1000XM5", "confidence": 0.92},
        {"brand": "Bose", "model": "QuietComfort Ultra", "confidence": 0.9},
        {"brand": "Sennheiser", "model": "Momentum 4", "confidence": 0.83},
    ],
    "smartphone": [
        {"brand": "Samsung", "model": "Galaxy S24", "confidence": 0.91},
        {"brand": "Google", "model": "Pixel 9", "confidence": 0.88},
        {"brand": "OnePlus", "model": "12", "confidence": 0.8},
    ],
    "running shoes": [
        {"brand": "Adidas", "model": "Ultraboost", "confidence": 0.9},
        {"brand": "Asics", "model": "Gel-Nimbus", "confidence": 0.86},
        {"brand": "Hoka", "model": "Clifton", "confidence": 0.82},
    ],
    "laptop": [
        {"brand": "Dell", "model": "XPS 13", "confidence": 0.89},
        {"brand": "HP", "model": "Spectre x360", "confidence": 0.86},
        {"brand": "Lenovo", "model": "Yoga 9i", "confidence": 0.83},
    ],
    _GENERIC_CATEGORY: [
        {"brand": "Brand B", "model": "Compete X", "confidence": 0.79},
        {"brand": "Brand C", "model": "Compete Pro", "confidence": 0.74},
        {"brand": "Brand D", "model": "Compete Max", "confidence": 0.7},
    ],
}


def build_demo_research_scope(request_text: str) -> ResearchScope:
    """Resolve a deterministic research scope without calling a model."""
    text = _normalize_request_text(request_text)
    if not text:
        return ResearchScope(
            market=DEFAULT_MARKET,
            requires_clarification=True,
            resolution_confidence=0.0,
        )

    market = _extract_market(text) or DEFAULT_MARKET
    product_text = _strip_market_markers(text)
    if not product_text:
        return ResearchScope(
            market=market,
            requires_clarification=True,
            resolution_confidence=0.0,
        )

    brand = product_text.split()[0] if product_text else ""
    category = _infer_category(product_text)
    return ResearchScope(
        canonical_product_name=product_text,
        brand=brand,
        category=category,
        market=market,
        requires_clarification=False,
        resolution_confidence=0.91 if category != _GENERIC_CATEGORY else 0.78,
    )


def build_demo_competitor_set(scope: ResearchScope) -> dict[str, Any]:
    """Return deterministic competitors for the resolved demo research scope."""
    competitor_templates = _COMPETITOR_LIBRARY.get(
        scope.category,
        _COMPETITOR_LIBRARY[_GENERIC_CATEGORY],
    )
    return {
        "primary_product": scope.canonical_product_name,
        "competitors": competitor_templates,
    }


def build_demo_pricing_state(
    scope: ResearchScope,
    competitor_set: Mapping[str, Any],
) -> dict[str, Any]:
    """Return tool-backed pricing intelligence formatted like the live state."""
    product_names = _product_names(scope, competitor_set)
    tool_payload = pricing_intelligence(product_names, scope.market)
    priced_products = tool_payload.get("products", [])
    currency = priced_products[0]["currency"] if priced_products else "USD"

    return {
        "currency": currency,
        "primary_product": scope.canonical_product_name,
        "products": [
            {
                "product": product["product"],
                "msrp_when_found": product.get("msrp"),
                "representative_prices": product.get("offers", []),
                "pricing_summary": _build_pricing_summary(product),
                "source_notes": [
                    "Demo pricing generated by the local fixture-backed pricing tool.",
                ],
                "freshness_note": "Demo mode uses deterministic mocked pricing data.",
            }
            for product in priced_products
        ],
    }


def build_demo_review_states(
    scope: ResearchScope,
    competitor_set: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return tool-backed review-corpus and sentiment state payloads."""
    product_names = _product_names(scope, competitor_set)
    raw_corpus = review_corpus(product_names, scope.market)
    raw_sentiment = review_sentiment(raw_corpus)
    sentiment_by_product = {
        product["product"]: product
        for product in raw_sentiment.get("products", [])
    }

    corpus_payload = {
        "primary_product": scope.canonical_product_name,
        "products": [],
    }
    sentiment_payload = {
        "primary_product": scope.canonical_product_name,
        "products": [],
    }

    for product_name, entries in raw_corpus.get("reviews", {}).items():
        rating_values = [entry["rating"] for entry in entries]
        corpus_payload["products"].append(
            {
                "product": product_name,
                "review_sources": _review_sources(entries),
                "rating_signals": {
                    "average_rating": round(mean(rating_values), 1),
                    "sample_size": len(entries),
                },
                "volume_signals": {
                    "review_count": len(entries),
                },
                "review_highlights": [entry["text"] for entry in entries],
                "freshness_note": "Demo mode uses deterministic mocked review data.",
            }
        )

        sentiment = sentiment_by_product.get(product_name, {})
        sentiment_payload["products"].append(
            {
                "product": product_name,
                "overall_sentiment": sentiment.get("overall_sentiment", "mixed"),
                "top_praise_themes": sentiment.get("top_praise_themes", []),
                "top_pain_points": sentiment.get("top_pain_points", []),
                "sentiment_confidence_note": (
                    "Demo mode sentiment is derived from fixture-backed reviews."
                ),
            }
        )

    return corpus_payload, sentiment_payload


def build_demo_trend_state(scope: ResearchScope) -> dict[str, Any]:
    """Return tool-backed trend signals formatted like the live state."""
    trend_payload = trend_signals(scope.category, scope.market)
    return {
        "category": trend_payload["category"],
        "market": trend_payload["market"],
        "demand_signal": trend_payload["demand_signal"],
        "price_pressure": trend_payload["price_pressure"],
        "trend_summary": trend_payload["trend_summary"],
        "supporting_signals": [
            "Demo trend signal generated by the local fixture-backed trend tool.",
        ],
        "freshness_note": "Demo mode uses deterministic mocked trend data.",
    }


def build_demo_report(state: Mapping[str, Any]) -> str:
    """Return a deterministic Markdown report from demo-mode state."""
    research_scope = _mapping_value(state.get("research_scope"))
    competitor_set = _mapping_value(state.get("competitor_set"))
    pricing_state = _mapping_value(state.get("pricing_intelligence"))
    review_sentiment_state = _mapping_value(state.get("review_sentiment"))
    trend_state = _mapping_value(state.get("trend_signals"))

    product_name = _string_value(
        research_scope.get("canonical_product_name"),
        "the requested product",
    )
    category = _string_value(research_scope.get("category"), _GENERIC_CATEGORY)
    market = _string_value(research_scope.get("market"), DEFAULT_MARKET)

    competitors = [
        f"{competitor.get('brand', '')} {competitor.get('model', '')}".strip()
        for competitor in competitor_set.get("competitors", [])
    ]
    competitor_text = ", ".join(filter(None, competitors)) or "No competitors were selected."

    pricing_products = pricing_state.get("products", [])
    primary_pricing = next(
        (
            product
            for product in pricing_products
            if product.get("product") == product_name
        ),
        pricing_products[0] if pricing_products else {},
    )
    pricing_summary = _string_value(
        primary_pricing.get("pricing_summary"),
        "Pricing signals were generated from demo fixture data.",
    )

    sentiment_products = review_sentiment_state.get("products", [])
    primary_sentiment = next(
        (
            product
            for product in sentiment_products
            if product.get("product") == product_name
        ),
        sentiment_products[0] if sentiment_products else {},
    )
    praise_themes = ", ".join(primary_sentiment.get("top_praise_themes", [])) or "ease of use"
    pain_points = ", ".join(primary_sentiment.get("top_pain_points", [])) or "price"
    overall_sentiment = _string_value(
        primary_sentiment.get("overall_sentiment"),
        "mixed_positive",
    )

    trend_summary = _string_value(
        trend_state.get("trend_summary"),
        f"The {category} category shows stable demand in {market}.",
    )
    demand_signal = _string_value(trend_state.get("demand_signal"), "stable_growth")
    price_pressure = _string_value(trend_state.get("price_pressure"), "moderate")

    return "\n".join(
        [
            "# Market Analysis Report",
            "",
            "## executive_summary",
            (
                f"{product_name} is positioned in the {category} segment for {market}. "
                f"Demo mode indicates {demand_signal} demand with {price_pressure} price pressure."
            ),
            "",
            "## competitor_landscape",
            f"Primary comparison set: {competitor_text}.",
            "",
            "## pricing_summary",
            pricing_summary,
            "",
            "## customer_sentiment",
            (
                f"Overall sentiment is {overall_sentiment}. Review themes lean positive around "
                f"{praise_themes}, with the main friction point being {pain_points}."
            ),
            "",
            "## market_trends",
            trend_summary,
            "",
            "## recommendations",
            (
                f"Position {product_name} against {competitors[0] if competitors else 'the main competitor'} "
                f"on the strongest praise themes, monitor {pain_points}, and use price discipline "
                "to protect margin while demand remains healthy."
            ),
        ]
    )


def _normalize_request_text(request_text: str) -> str:
    """Remove helper verbs so the demo scope can focus on the product text."""
    text = re.sub(r"\s+", " ", request_text).strip()
    lowered = text.lower()
    for prefix in _ACTION_PREFIXES:
        if lowered.startswith(prefix):
            return text[len(prefix) :].strip(" :,-")
    return text


def _extract_market(request_text: str) -> str | None:
    """Return an inferred market code from the request text when present."""
    for pattern, market in _MARKET_PATTERNS:
        if pattern.search(request_text):
            return market
    return None


def _strip_market_markers(request_text: str) -> str:
    """Remove market phrases from the request text after market detection."""
    text = request_text
    for pattern, _market in _MARKET_PATTERNS:
        text = pattern.sub("", text)
    return re.sub(r"\s+", " ", text).strip(" ,:-")


def _infer_category(product_text: str) -> str:
    """Infer a stable category from simple keyword hints in the product text."""
    lowered = product_text.lower()
    for hint, category in _CATEGORY_HINTS:
        if hint in lowered:
            return category
    return _GENERIC_CATEGORY


def _product_names(
    scope: ResearchScope,
    competitor_set: Mapping[str, Any],
) -> list[str]:
    """Return the primary product plus competitors formatted as product names."""
    names = [scope.canonical_product_name]
    for competitor in competitor_set.get("competitors", []):
        brand = competitor.get("brand", "")
        model = competitor.get("model", "")
        formatted_name = f"{brand} {model}".strip()
        if formatted_name:
            names.append(formatted_name)
    return names


def _build_pricing_summary(product: Mapping[str, Any]) -> str:
    """Return a short summary sentence for a deterministic pricing record."""
    offers = product.get("offers", [])
    if not offers:
        return "No offer data was generated for this product."

    prices = [offer["price"] for offer in offers]
    return (
        f"Observed demo offers range from {min(prices):.2f} to {max(prices):.2f} "
        f"across {len(offers)} sellers."
    )


def _review_sources(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return one source record per unique review source in the corpus."""
    seen_sources: set[tuple[str, str]] = set()
    sources: list[dict[str, Any]] = []
    for entry in entries:
        key = (entry["source"], entry["market"])
        if key in seen_sources:
            continue
        seen_sources.add(key)
        sources.append({"source": entry["source"], "market": entry["market"]})
    return sources


def _mapping_value(value: Any) -> Mapping[str, Any]:
    """Return a mapping value or an empty mapping when the value is missing."""
    return value if isinstance(value, Mapping) else {}


def _string_value(value: Any, fallback: str = "") -> str:
    """Return a string value or a fallback when the value is empty."""
    if value is None:
        return fallback

    text = value if isinstance(value, str) else str(value)
    return text or fallback
