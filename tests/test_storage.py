"""Tests for durable storage and snapshot helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ecommerce_agents.storage import SQLiteAnalysisStore, build_analysis_snapshot


def test_build_analysis_snapshot_extracts_scope_report_and_citations() -> None:
    """Snapshot building should normalize scope metadata and extract source URLs."""
    snapshot = build_analysis_snapshot(
        session_id="s_123",
        user_id="u_123",
        request_text="Analyze Dyson V15",
        state_snapshot={
            "research_scope": {
                "canonical_product_name": "Dyson V15 Detect",
                "category": "cordless stick vacuum",
                "market": "US",
            },
            "pricing_intelligence": {
                "products": [
                    {
                        "source_notes": [
                            "Official listing https://example.com/dyson-v15",
                            "Retail listing https://retailer.example/dyson-v15.",
                        ]
                    }
                ]
            },
            "final_report": "# Final report",
        },
    )

    assert snapshot.product_name == "Dyson V15 Detect"
    assert snapshot.category == "cordless stick vacuum"
    assert snapshot.market == "US"
    assert snapshot.final_report_markdown == "# Final report"
    assert [citation.url for citation in snapshot.citations_json] == [
        "https://example.com/dyson-v15",
        "https://retailer.example/dyson-v15",
    ]


def test_sqlite_analysis_store_round_trips_snapshots_and_filters_recent(tmp_path) -> None:
    """SQLite storage should save, reload, and filter recent analysis snapshots."""
    store = SQLiteAnalysisStore(tmp_path / "analysis_history.db")
    first_snapshot = build_analysis_snapshot(
        session_id="s_123",
        user_id="u_123",
        request_text="Analyze Dyson V15",
        state_snapshot={
            "research_scope": {
                "canonical_product_name": "Dyson V15 Detect",
                "category": "cordless stick vacuum",
                "market": "US",
            },
            "final_report": "# Report A",
        },
        created_at=datetime(2026, 3, 22, 10, 0, tzinfo=timezone.utc),
    )
    second_snapshot = build_analysis_snapshot(
        session_id="s_456",
        user_id="u_456",
        request_text="Analyze AirPods Pro",
        state_snapshot={
            "research_scope": {
                "canonical_product_name": "AirPods Pro 2",
                "category": "wireless earbuds",
                "market": "CA",
            },
            "final_report": "# Report B",
        },
        created_at=datetime(2026, 3, 22, 10, 5, tzinfo=timezone.utc),
    )

    first_id = store.save(first_snapshot)
    second_id = store.save(second_snapshot)

    reloaded = store.get(first_id)
    recent = store.list_recent(limit=10)
    filtered = store.list_recent(limit=10, product_name="AirPods Pro 2", market="CA")

    assert reloaded is not None
    assert reloaded.analysis_id == first_id
    assert reloaded.state_snapshot_json["final_report"] == "# Report A"
    assert [snapshot.analysis_id for snapshot in recent] == [second_id, first_id]
    assert [snapshot.analysis_id for snapshot in filtered] == [second_id]


def test_sqlite_analysis_store_keeps_multiple_runs_for_same_session(tmp_path) -> None:
    """Repeated runs in the same session should create distinct durable records."""
    store = SQLiteAnalysisStore(tmp_path / "analysis_history.db")
    first_snapshot = build_analysis_snapshot(
        session_id="s_123",
        user_id="u_123",
        request_text="Analyze Dyson V15",
        state_snapshot={
            "research_scope": {
                "canonical_product_name": "Dyson V15 Detect",
                "category": "cordless stick vacuum",
                "market": "US",
            },
            "final_report": "# First report",
        },
        created_at=datetime.now(timezone.utc),
    )
    second_snapshot = build_analysis_snapshot(
        session_id="s_123",
        user_id="u_123",
        request_text="Analyze Dyson V15 again",
        state_snapshot={
            "research_scope": {
                "canonical_product_name": "Dyson V15 Detect",
                "category": "cordless stick vacuum",
                "market": "US",
            },
            "final_report": "# Second report",
        },
        created_at=datetime.now(timezone.utc) + timedelta(minutes=1),
    )

    first_id = store.save(first_snapshot)
    second_id = store.save(second_snapshot)
    recent = store.list_recent(limit=10, product_name="Dyson V15 Detect", market="US")

    assert first_id != second_id
    assert len(recent) == 2
    assert {snapshot.analysis_id for snapshot in recent} == {first_id, second_id}
