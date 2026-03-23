"""Routing tests for the market analysis scaffold."""

from ecommerce_agents.routing import parse_research_scope, should_request_clarification


def test_greeting_scope_requires_clarification() -> None:
    """A greeting-only scope should stop the workflow and ask a follow-up."""
    scope = parse_research_scope(
        {
            "canonical_product_name": "",
            "brand": "",
            "category": "",
            "market": "US",
            "requires_clarification": True,
            "resolution_confidence": 0.0,
        }
    )

    assert should_request_clarification(scope) is True


def test_valid_scope_continues_research() -> None:
    """A confident, normalized scope should continue into research."""
    scope = parse_research_scope(
        {
            "canonical_product_name": "Dyson V15 Detect",
            "brand": "Dyson",
            "category": "cordless stick vacuum",
            "market": "US",
            "requires_clarification": False,
            "resolution_confidence": 0.91,
        }
    )

    assert should_request_clarification(scope) is False


def test_parse_research_scope_accepts_fenced_json() -> None:
    """Routing should parse JSON payloads wrapped in markdown fences."""
    raw_scope = """```json
    {
      \"canonical_product_name\": \"Dyson V15 Detect\",
      \"brand\": \"Dyson\",
      \"category\": \"cordless stick vacuum\",
      \"market\": \"US\",
      \"requires_clarification\": false,
      \"resolution_confidence\": 0.88
    }
    ```"""

    scope = parse_research_scope(raw_scope)

    assert scope.canonical_product_name == "Dyson V15 Detect"
    assert scope.market == "US"
    assert should_request_clarification(scope) is False


def test_invalid_scope_defaults_to_clarification() -> None:
    """Unparseable scope payloads should fail safely into clarification mode."""
    scope = parse_research_scope("not-json")

    assert scope.market == "CA"
    assert should_request_clarification(scope) is True
