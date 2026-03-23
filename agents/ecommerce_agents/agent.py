"""Root ADK agent definition for the market analysis scaffold."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any, AsyncGenerator

from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.events import Event
from google.adk.tools import google_search
from google.genai import types

from .config import ANALYSIS_DB_PATH, APP_NAME, DEFAULT_MARKET, DEFAULT_MODEL
from .prompts import (
    CLARIFICATION_PROMPT,
    COMPETITOR_DISCOVERY_PROMPT,
    MARKET_ANALYSIS_PROMPT,
    PRICING_INTELLIGENCE_PROMPT,
    REVIEW_CORPUS_PROMPT,
    REVIEW_SENTIMENT_PROMPT,
    TREND_SIGNALS_PROMPT,
    build_research_scope_prompt,
)
from .routing import parse_research_scope, should_request_clarification
from .storage import (
    AnalysisSnapshot,
    AnalysisStore,
    SQLiteAnalysisStore,
    build_analysis_snapshot,
)

LOGGER = logging.getLogger(__name__)

_PARALLEL_STAGE_MESSAGES = {
    "PricingIntelligenceAgent": "Pricing research complete.",
    "ReviewCorpusAgent": "Review-source collection complete.",
    "ReviewSentimentAgent": "Sentiment analysis complete.",
    "TrendSignalsAgent": "Trend research complete.",
}
_PERSISTED_STATE_KEYS = (
    "research_scope",
    "competitor_set",
    "pricing_intelligence",
    "review_corpus",
    "review_sentiment",
    "trend_signals",
    "final_report",
)

research_scope_agent = LlmAgent(
    name="ResearchScopeAgent",
    model=DEFAULT_MODEL,
    description=(
        "Resolves the request into a structured research scope and flags "
        "clarification when needed."
    ),
    instruction=build_research_scope_prompt(DEFAULT_MARKET),
    tools=[google_search],
    output_key="research_scope",
)

clarification_agent = LlmAgent(
    name="ClarificationAgent",
    model=DEFAULT_MODEL,
    description="Asks one short follow-up question when the request is ambiguous.",
    instruction=CLARIFICATION_PROMPT,
)

competitor_discovery_agent = LlmAgent(
    name="CompetitorDiscoveryAgent",
    model=DEFAULT_MODEL,
    description="Discovers relevant competitors for the normalized product.",
    instruction=COMPETITOR_DISCOVERY_PROMPT,
    tools=[google_search],
    output_key="competitor_set",
)

pricing_intelligence_agent = LlmAgent(
    name="PricingIntelligenceAgent",
    model=DEFAULT_MODEL,
    description="Collects live pricing signals for the primary product and competitors.",
    instruction=PRICING_INTELLIGENCE_PROMPT,
    tools=[google_search],
    output_key="pricing_intelligence",
)

review_corpus_agent = LlmAgent(
    name="ReviewCorpusAgent",
    model=DEFAULT_MODEL,
    description="Collects live review-source evidence for the primary product and competitors.",
    instruction=REVIEW_CORPUS_PROMPT,
    tools=[google_search],
    output_key="review_corpus",
)

review_sentiment_agent = LlmAgent(
    name="ReviewSentimentAgent",
    model=DEFAULT_MODEL,
    description="Collects live sentiment signals for the primary product and competitors.",
    instruction=REVIEW_SENTIMENT_PROMPT,
    tools=[google_search],
    output_key="review_sentiment",
)

trend_signals_agent = LlmAgent(
    name="TrendSignalsAgent",
    model=DEFAULT_MODEL,
    description="Collects live trend and demand signals for the target category.",
    instruction=TREND_SIGNALS_PROMPT,
    tools=[google_search],
    output_key="trend_signals",
)

parallel_market_research_agent = ParallelAgent(
    name="ParallelMarketResearchAgent",
    description="Runs live pricing, review, sentiment, and trend research in parallel.",
    sub_agents=[
        pricing_intelligence_agent,
        review_corpus_agent,
        review_sentiment_agent,
        trend_signals_agent,
    ],
)

market_analysis_agent = LlmAgent(
    name="MarketAnalysisAgent",
    model=DEFAULT_MODEL,
    description="Synthesizes live research outputs into the final market report.",
    instruction=MARKET_ANALYSIS_PROMPT,
    output_key="final_report",
)


def build_analysis_snapshot_from_context(ctx: Any) -> AnalysisSnapshot | None:
    """Build a durable snapshot from the current ADK invocation context."""
    session = _read_value(ctx, "session")
    state = _mapping_from_value(_read_value(session, "state"))
    state_snapshot = {
        key: state[key]
        for key in _PERSISTED_STATE_KEYS
        if key in state
    }

    final_report = _content_to_text(state_snapshot.get("final_report")).strip()
    if not final_report:
        return None

    state_snapshot["final_report"] = final_report
    user_id = _string_value(_read_value(session, "user_id", "userId"))
    if not user_id:
        user_id = _string_value(_read_value(ctx, "user_id", "userId"))

    return build_analysis_snapshot(
        session_id=_string_value(_read_value(session, "id", "session_id", "sessionId")),
        user_id=user_id,
        request_text=extract_request_text(ctx),
        state_snapshot=state_snapshot,
    )


def extract_request_text(ctx: Any) -> str:
    """Return the latest user request text visible from the invocation context."""
    session = _read_value(ctx, "session")
    direct_candidates = (
        _read_value(ctx, "user_content"),
        _read_value(ctx, "new_message"),
        _read_value(ctx, "newMessage"),
        _read_value(ctx, "user_message"),
        _read_value(ctx, "content"),
        _read_value(_read_value(ctx, "request"), "new_message", "newMessage", "content"),
        _read_value(session, "last_user_message"),
        _read_value(session, "last_user_content"),
    )

    for candidate in direct_candidates:
        text = _content_to_text(candidate).strip()
        if text:
            return text

    events = _sequence_from_value(_read_value(session, "events", "history"))
    for event in reversed(events):
        author = _string_value(_read_value(event, "author")).lower()
        content = _read_value(event, "content")
        role = _string_value(_read_value(content, "role")).lower()
        if author == "user" or role == "user":
            text = _content_to_text(content).strip()
            if text:
                return text

    return ""


def _read_value(source: Any, *names: str) -> Any:
    """Return the first matching attribute or mapping value from a source object."""
    for name in names:
        if isinstance(source, Mapping) and name in source:
            return source[name]
        if hasattr(source, name):
            return getattr(source, name)
    return None


def _mapping_from_value(value: Any) -> dict[str, Any]:
    """Normalize mapping-like values into a plain dictionary."""
    if isinstance(value, Mapping):
        return dict(value)

    if hasattr(value, "items"):
        try:
            return dict(value.items())
        except TypeError:
            return {}

    return {}


def _sequence_from_value(value: Any) -> list[Any]:
    """Normalize sequence-like values into a list."""
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _content_to_text(value: Any) -> str:
    """Extract human-readable text from ADK or dict-like content payloads."""
    if value is None:
        return ""

    if isinstance(value, str):
        return value

    if isinstance(value, Mapping):
        if "text" in value and isinstance(value["text"], str):
            return value["text"]
        if "content" in value:
            return _content_to_text(value["content"])
        if "parts" in value:
            return "\n".join(
                filter(
                    None,
                    (_content_to_text(part) for part in _sequence_from_value(value["parts"])),
                )
            )

    text = _read_value(value, "text")
    if isinstance(text, str):
        return text

    content = _read_value(value, "content")
    if content is not None:
        return _content_to_text(content)

    parts = _read_value(value, "parts")
    if parts is not None:
        return "\n".join(
            filter(None, (_content_to_text(part) for part in _sequence_from_value(parts)))
        )

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return "\n".join(filter(None, (_content_to_text(item) for item in value)))

    return ""


def _string_value(value: Any) -> str:
    """Normalize potentially missing metadata values into strings."""
    if value is None:
        return ""
    return value if isinstance(value, str) else str(value)


class MarketAnalysisOrchestrator(BaseAgent):
    """Custom ADK orchestrator for intake, clarification, discovery, and analysis.

    The research-scope step writes ``research_scope`` into session state. This
    orchestrator inspects that structured output and either asks a short
    clarification question or continues into competitor discovery, parallel live
    market research, and the final market analysis agent.
    """

    research_scope_agent: LlmAgent
    clarification_agent: LlmAgent
    competitor_discovery_agent: LlmAgent
    parallel_market_research_agent: ParallelAgent
    market_analysis_agent: LlmAgent
    analysis_store: AnalysisStore | None

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        name: str,
        description: str,
        research_scope_agent: LlmAgent,
        clarification_agent: LlmAgent,
        competitor_discovery_agent: LlmAgent,
        parallel_market_research_agent: ParallelAgent,
        market_analysis_agent: LlmAgent,
        analysis_store: AnalysisStore | None = None,
    ) -> None:
        """Initialize the orchestrator and register its top-level sub-agents."""
        super().__init__(
            name=name,
            description=description,
            research_scope_agent=research_scope_agent,
            clarification_agent=clarification_agent,
            competitor_discovery_agent=competitor_discovery_agent,
            parallel_market_research_agent=parallel_market_research_agent,
            market_analysis_agent=market_analysis_agent,
            analysis_store=analysis_store,
            sub_agents=[
                research_scope_agent,
                clarification_agent,
                competitor_discovery_agent,
                parallel_market_research_agent,
                market_analysis_agent,
            ],
        )

    def _build_status_event(self, ctx: Any, message: str) -> Event:
        """Return a lightweight user-visible progress event for the current run."""
        return Event(
            author=self.name,
            invocation_id=getattr(ctx, "invocation_id", ""),
            content=types.Content(
                role="model",
                parts=[types.Part(text=message)],
            ),
        )

    @staticmethod
    def _hide_content(event: Event) -> Event:
        """Preserve state updates while removing internal JSON from the chat stream."""
        return event.model_copy(update={"content": None})

    def _persist_completed_analysis(self, ctx: Any) -> str | None:
        """Persist the final report snapshot without interrupting the user response."""
        if self.analysis_store is None:
            return None

        snapshot = build_analysis_snapshot_from_context(ctx)
        if snapshot is None:
            return None

        return self.analysis_store.save(snapshot)

    async def _run_async_impl(self, ctx: Any) -> AsyncGenerator[Any, None]:
        """Run research scoping first, then branch to clarification or full analysis."""
        yield self._build_status_event(ctx, "Resolving the product scope...")

        async for event in self.research_scope_agent.run_async(ctx):
            yield self._hide_content(event)

        scope = parse_research_scope(ctx.session.state.get("research_scope"))
        ctx.session.state["research_scope"] = scope.model_dump()

        if should_request_clarification(scope):
            yield self._build_status_event(
                ctx,
                "I need one quick clarification before I start the research.",
            )
            async for event in self.clarification_agent.run_async(ctx):
                yield event
            return

        yield self._build_status_event(
            ctx,
            f"Scope resolved for {scope.canonical_product_name}. Finding competitors...",
        )

        async for event in self.competitor_discovery_agent.run_async(ctx):
            yield self._hide_content(event)

        yield self._build_status_event(
            ctx,
            "Competitors found. Running pricing, review, sentiment, and trend research in parallel...",
        )

        completed_parallel_agents: set[str] = set()
        async for event in self.parallel_market_research_agent.run_async(ctx):
            yield self._hide_content(event)
            if not event.partial and event.author in _PARALLEL_STAGE_MESSAGES:
                if event.author not in completed_parallel_agents:
                    completed_parallel_agents.add(event.author)
                    yield self._build_status_event(
                        ctx,
                        _PARALLEL_STAGE_MESSAGES[event.author],
                    )

        yield self._build_status_event(
            ctx,
            "Research complete. Writing the final market analysis...",
        )

        async for event in self.market_analysis_agent.run_async(ctx):
            yield event

        try:
            self._persist_completed_analysis(ctx)
        except Exception:
            LOGGER.exception("Failed to persist completed analysis.")


root_agent = MarketAnalysisOrchestrator(
    name=APP_NAME,
    description=(
        "Coordinates research scoping, clarification, competitor discovery, "
        "parallel live market research, and final synthesis."
    ),
    research_scope_agent=research_scope_agent,
    clarification_agent=clarification_agent,
    competitor_discovery_agent=competitor_discovery_agent,
    parallel_market_research_agent=parallel_market_research_agent,
    market_analysis_agent=market_analysis_agent,
    analysis_store=SQLiteAnalysisStore(ANALYSIS_DB_PATH),
)
