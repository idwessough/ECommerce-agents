"""Agent-definition tests for the live research workflow."""

from ecommerce_agents import root_agent
from ecommerce_agents.agent import (
    competitor_discovery_agent,
    market_analysis_agent,
    parallel_market_research_agent,
    pricing_intelligence_agent,
    research_scope_agent,
    review_corpus_agent,
    review_sentiment_agent,
    trend_signals_agent,
)
from ecommerce_agents.storage import SQLiteAnalysisStore


def test_root_agent_and_parallel_research_agents_import_cleanly() -> None:
    """The ADK agent graph should import with the parallel live research stage."""
    assert root_agent.name == "ecommerce_agents"
    assert isinstance(root_agent.analysis_store, SQLiteAnalysisStore)
    assert research_scope_agent.name == "ResearchScopeAgent"
    assert competitor_discovery_agent.name == "CompetitorDiscoveryAgent"
    assert parallel_market_research_agent.name == "ParallelMarketResearchAgent"
    assert pricing_intelligence_agent.name == "PricingIntelligenceAgent"
    assert review_corpus_agent.name == "ReviewCorpusAgent"
    assert review_sentiment_agent.name == "ReviewSentimentAgent"
    assert trend_signals_agent.name == "TrendSignalsAgent"
    assert market_analysis_agent.name == "MarketAnalysisAgent"
    assert market_analysis_agent.output_key == "final_report"
