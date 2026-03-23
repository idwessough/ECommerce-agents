"""Persistence-flow tests for the market-analysis orchestrator."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from google.adk.agents import BaseAgent
from pydantic import BaseModel

from ecommerce_agents.agent import (
    MarketAnalysisOrchestrator,
    _content_to_text,
    build_analysis_snapshot_from_context,
)
from ecommerce_agents.storage import AnalysisSnapshot


class StubEvent(BaseModel):
    """Minimal event model used to exercise orchestrator control flow."""

    author: str
    partial: bool = False
    content: Any = None


class FakeRuntimeAgent(BaseAgent):
    """Deterministic agent double that writes state and emits canned events."""

    state_updates: dict[str, Any]
    emitted_events: list[StubEvent]

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        name: str,
        *,
        state_updates: dict[str, Any] | None = None,
        emitted_events: list[StubEvent] | None = None,
    ) -> None:
        """Initialize a fake agent with optional state updates and events."""
        super().__init__(
            name=name,
            description=f"Fake agent for {name}.",
            state_updates=state_updates or {},
            emitted_events=emitted_events or [],
        )

    async def _run_async_impl(self, ctx: Any):
        """Apply the configured state updates and emit fake events."""
        ctx.session.state.update(self.state_updates)
        for event in self.emitted_events:
            yield event


class RecordingStore:
    """Simple in-memory store that records saved snapshots."""

    def __init__(self) -> None:
        """Initialize an empty snapshot list."""
        self.saved_snapshots: list[AnalysisSnapshot] = []

    def save(self, snapshot: AnalysisSnapshot) -> str:
        """Record the saved snapshot and return its identifier."""
        self.saved_snapshots.append(snapshot)
        return snapshot.analysis_id

    def get(self, analysis_id: str) -> AnalysisSnapshot | None:
        """Return a saved snapshot when present."""
        for snapshot in self.saved_snapshots:
            if snapshot.analysis_id == analysis_id:
                return snapshot
        return None

    def list_recent(
        self,
        limit: int,
        product_name: str | None = None,
        market: str | None = None,
    ) -> list[AnalysisSnapshot]:
        """Return saved snapshots, applying the same filters as the real store."""
        snapshots = list(reversed(self.saved_snapshots))
        if product_name:
            snapshots = [
                snapshot
                for snapshot in snapshots
                if snapshot.product_name == product_name
            ]
        if market:
            snapshots = [
                snapshot
                for snapshot in snapshots
                if snapshot.market == market
            ]
        return snapshots[:limit]


class FailingStore(RecordingStore):
    """Store double that raises during save to verify graceful failure handling."""

    def save(self, snapshot: AnalysisSnapshot) -> str:
        """Raise a storage error without suppressing the final report event."""
        raise RuntimeError("sqlite unavailable")


@dataclass
class FakeSession:
    """Minimal ADK-session shape used by persistence helper tests."""

    id: str = "s_123"
    user_id: str = "u_123"
    state: dict[str, Any] = field(default_factory=dict)
    events: list[Any] = field(default_factory=list)


@dataclass
class FakeContext:
    """Minimal invocation context with request metadata and session state."""

    session: FakeSession = field(default_factory=FakeSession)
    invocation_id: str = "inv_123"
    request: dict[str, Any] = field(
        default_factory=lambda: {
            "newMessage": {
                "role": "user",
                "parts": [{"text": "Analyze Dyson V15"}],
            }
        }
    )


def test_build_analysis_snapshot_from_context_reads_final_report_and_request() -> None:
    """The context helper should build a durable snapshot once final_report exists."""
    ctx = FakeContext(
        session=FakeSession(
            state={
                "research_scope": {
                    "canonical_product_name": "Dyson V15 Detect",
                    "category": "cordless stick vacuum",
                    "market": "US",
                },
                "final_report": "# Final report",
                "pricing_intelligence": {
                    "products": [
                        {
                            "source_notes": [
                                "Official listing: https://example.com/dyson-v15",
                            ]
                        }
                    ]
                },
            }
        )
    )

    snapshot = build_analysis_snapshot_from_context(ctx)

    assert snapshot is not None
    assert snapshot.request_text == "Analyze Dyson V15"
    assert snapshot.product_name == "Dyson V15 Detect"
    assert snapshot.final_report_markdown == "# Final report"
    assert snapshot.citations_json[0].url == "https://example.com/dyson-v15"


def test_full_run_persists_completed_analysis_snapshot() -> None:
    """A successful full run should persist one completed snapshot after synthesis."""
    store = RecordingStore()
    orchestrator = _build_orchestrator(store)
    ctx = FakeContext()

    events = asyncio.run(_collect_events(orchestrator, ctx))

    assert any(_content_to_text(getattr(event, "content", None)) == "# Final report" for event in events)
    assert len(store.saved_snapshots) == 1
    snapshot = store.saved_snapshots[0]
    assert snapshot.session_id == "s_123"
    assert snapshot.user_id == "u_123"
    assert snapshot.request_text == "Analyze Dyson V15"
    assert set(snapshot.state_snapshot_json) >= {
        "research_scope",
        "competitor_set",
        "pricing_intelligence",
        "review_corpus",
        "review_sentiment",
        "trend_signals",
        "final_report",
    }


def test_clarification_path_does_not_persist_analysis() -> None:
    """Clarification-only runs should stop before persistence."""
    store = RecordingStore()
    orchestrator = _build_orchestrator(
        store,
        research_scope={
            "canonical_product_name": "",
            "brand": "",
            "category": "",
            "market": "US",
            "requires_clarification": True,
            "resolution_confidence": 0.0,
        },
    )
    ctx = FakeContext()

    asyncio.run(_collect_events(orchestrator, ctx))

    assert store.saved_snapshots == []


def test_persistence_failure_keeps_final_report_in_event_stream() -> None:
    """Storage errors should be swallowed after the final report is yielded."""
    orchestrator = _build_orchestrator(FailingStore())
    ctx = FakeContext()

    events = asyncio.run(_collect_events(orchestrator, ctx))

    assert any(_content_to_text(getattr(event, "content", None)) == "# Final report" for event in events)


async def _collect_events(
    orchestrator: MarketAnalysisOrchestrator,
    ctx: FakeContext,
) -> list[Any]:
    """Collect all events from the orchestrator's async run implementation."""
    return [event async for event in orchestrator._run_async_impl(ctx)]


def _build_orchestrator(
    store: RecordingStore,
    *,
    research_scope: dict[str, Any] | None = None,
) -> MarketAnalysisOrchestrator:
    """Construct an orchestrator with deterministic fake agents for tests."""
    resolved_scope = research_scope or {
        "canonical_product_name": "Dyson V15 Detect",
        "brand": "Dyson",
        "category": "cordless stick vacuum",
        "market": "US",
        "requires_clarification": False,
        "resolution_confidence": 0.93,
    }
    clarification_event = StubEvent(
        author="ClarificationAgent",
        content={
            "role": "model",
            "parts": [{"text": "Which AirPods model should I analyze?"}],
        },
    )
    final_report_event = StubEvent(
        author="MarketAnalysisAgent",
        content={
            "role": "model",
            "parts": [{"text": "# Final report"}],
        },
    )

    return MarketAnalysisOrchestrator(
        name="test_orchestrator",
        description="Test orchestrator.",
        research_scope_agent=FakeRuntimeAgent(
            "ResearchScopeAgent",
            state_updates={"research_scope": resolved_scope},
            emitted_events=[
                StubEvent(author="ResearchScopeAgent", content={"text": "scope"}),
            ],
        ),
        clarification_agent=FakeRuntimeAgent(
            "ClarificationAgent",
            emitted_events=[clarification_event],
        ),
        competitor_discovery_agent=FakeRuntimeAgent(
            "CompetitorDiscoveryAgent",
            state_updates={
                "competitor_set": {
                    "primary_product": "Dyson V15 Detect",
                    "competitors": [
                        {"brand": "Shark", "model": "Detect Pro", "confidence": 0.91},
                    ],
                }
            },
            emitted_events=[
                StubEvent(author="CompetitorDiscoveryAgent", content={"text": "competitors"}),
            ],
        ),
        parallel_market_research_agent=FakeRuntimeAgent(
            "ParallelMarketResearchAgent",
            state_updates={
                "pricing_intelligence": {
                    "products": [
                        {
                            "product": "Dyson V15 Detect",
                            "source_notes": ["https://example.com/dyson-v15"],
                        }
                    ]
                },
                "review_corpus": {"products": [{"product": "Dyson V15 Detect"}]},
                "review_sentiment": {"products": [{"product": "Dyson V15 Detect"}]},
                "trend_signals": {"category": "cordless stick vacuum", "market": "US"},
            },
            emitted_events=[
                StubEvent(author="PricingIntelligenceAgent"),
                StubEvent(author="ReviewCorpusAgent"),
                StubEvent(author="ReviewSentimentAgent"),
                StubEvent(author="TrendSignalsAgent"),
            ],
        ),
        market_analysis_agent=FakeRuntimeAgent(
            "MarketAnalysisAgent",
            state_updates={"final_report": "# Final report"},
            emitted_events=[final_report_event],
        ),
        analysis_store=store,
    )
