"""Tests for user-visible orchestration events."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from google.adk.events import Event
from google.genai import types

from ecommerce_agents.agent import MarketAnalysisOrchestrator, root_agent


class FakeAgent:
    """Minimal async agent stub used to drive orchestrator tests."""

    def __init__(self, events: list[Event], state_updates: dict[str, object] | None = None) -> None:
        """Store the events and session-state updates to emit during a run."""
        self._events = events
        self._state_updates = state_updates or {}
        self.calls = 0

    async def run_async(self, ctx: SimpleNamespace):  # type: ignore[override]
        """Yield prebuilt events after applying the configured state updates."""
        self.calls += 1
        ctx.session.state.update(self._state_updates)
        for event in self._events:
            yield event


def _text_event(author: str, text: str, *, branch: str | None = None) -> Event:
    """Create a simple text event for test scenarios."""
    return Event(
        author=author,
        invocation_id="inv-test",
        branch=branch,
        content=types.Content(parts=[types.Part(text=text)], role="model"),
    )


async def _collect_events(
    orchestrator: MarketAnalysisOrchestrator,
    ctx: SimpleNamespace,
) -> list[Event]:
    """Collect every event yielded by the orchestrator under test."""
    events: list[Event] = []
    async for event in orchestrator._run_async_impl(ctx):
        events.append(event)
    return events


def test_internal_research_events_are_hidden_but_progress_is_visible(
    monkeypatch,
) -> None:
    """Internal JSON stages should become progress updates plus state-only events."""
    ctx = SimpleNamespace(
        invocation_id="inv-test",
        session=SimpleNamespace(state={}),
    )
    research_scope = {
        "canonical_product_name": "Apple iPhone 11",
        "brand": "Apple",
        "category": "Smartphone",
        "market": "CA",
        "requires_clarification": False,
        "resolution_confidence": 0.95,
    }

    monkeypatch.setattr(
        root_agent,
        "research_scope_agent",
        FakeAgent(
            [_text_event("ResearchScopeAgent", '{"canonical_product_name": "Apple iPhone 11"}')],
            state_updates={"research_scope": research_scope},
        ),
    )
    monkeypatch.setattr(
        root_agent,
        "clarification_agent",
        FakeAgent([_text_event("ClarificationAgent", "Which model do you mean?")]),
    )
    monkeypatch.setattr(
        root_agent,
        "competitor_discovery_agent",
        FakeAgent(
            [_text_event("CompetitorDiscoveryAgent", '{"competitors": ["Galaxy S10"]}')],
            state_updates={"competitor_set": {"competitors": ["Galaxy S10"]}},
        ),
    )
    monkeypatch.setattr(
        root_agent,
        "parallel_market_research_agent",
        FakeAgent(
            [
                _text_event(
                    "PricingIntelligenceAgent",
                    '{"pricing": "done"}',
                    branch="ParallelMarketResearchAgent.PricingIntelligenceAgent",
                ),
                _text_event(
                    "TrendSignalsAgent",
                    '{"trends": "done"}',
                    branch="ParallelMarketResearchAgent.TrendSignalsAgent",
                ),
            ],
        ),
    )
    monkeypatch.setattr(
        root_agent,
        "market_analysis_agent",
        FakeAgent([_text_event("MarketAnalysisAgent", "# Final report")]),
    )

    events = asyncio.run(_collect_events(root_agent, ctx))

    visible_messages = [
        event.content.parts[0].text
        for event in events
        if event.content and event.content.parts and event.content.parts[0].text
    ]

    assert visible_messages[0] == "Resolving the product scope..."
    assert any(
        message == "Scope resolved for Apple iPhone 11. Finding competitors..."
        for message in visible_messages
    )
    assert any(
        message
        == "Competitors found. Running pricing, review, sentiment, and trend research in parallel..."
        for message in visible_messages
    )
    assert "Pricing research complete." in visible_messages
    assert "Trend research complete." in visible_messages
    assert "Research complete. Writing the final market analysis..." in visible_messages
    assert "# Final report" in visible_messages

    hidden_internal_events = [
        event for event in events if event.author in {"ResearchScopeAgent", "CompetitorDiscoveryAgent"}
    ]
    assert hidden_internal_events
    assert all(event.content is None for event in hidden_internal_events)

    hidden_parallel_events = [
        event
        for event in events
        if event.author in {"PricingIntelligenceAgent", "TrendSignalsAgent"}
    ]
    assert hidden_parallel_events
    assert all(event.content is None for event in hidden_parallel_events)


def test_clarification_branch_keeps_follow_up_visible(monkeypatch) -> None:
    """Clarification should still surface the user-facing follow-up question."""
    ctx = SimpleNamespace(
        invocation_id="inv-test",
        session=SimpleNamespace(state={}),
    )
    research_scope = {
        "canonical_product_name": "",
        "brand": "",
        "category": "",
        "market": "CA",
        "requires_clarification": True,
        "resolution_confidence": 0.0,
    }
    clarification_agent = FakeAgent(
        [_text_event("ClarificationAgent", "Which iPhone model should I analyze?")],
    )

    monkeypatch.setattr(
        root_agent,
        "research_scope_agent",
        FakeAgent(
            [_text_event("ResearchScopeAgent", '{"requires_clarification": true}')],
            state_updates={"research_scope": research_scope},
        ),
    )
    monkeypatch.setattr(root_agent, "clarification_agent", clarification_agent)

    events = asyncio.run(_collect_events(root_agent, ctx))
    visible_messages = [
        event.content.parts[0].text
        for event in events
        if event.content and event.content.parts and event.content.parts[0].text
    ]

    assert "I need one quick clarification before I start the research." in visible_messages
    assert "Which iPhone model should I analyze?" in visible_messages
    assert clarification_agent.calls == 1
