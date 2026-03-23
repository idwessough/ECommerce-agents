"""Persistence models and storage adapters for completed market analyses."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from pydantic import BaseModel, Field

URL_PATTERN = re.compile(r"https?://[^\s<>\]\"')]+")


class CitationRecord(BaseModel):
    """A single source URL extracted from a completed analysis snapshot."""

    state_key: str = Field(
        description="Top-level session-state key that contains the citation.",
    )
    url: str = Field(
        description="Normalized source URL.",
    )
    context_path: str = Field(
        default="",
        description="Dot path to the field that contained the URL.",
    )


class AnalysisSnapshot(BaseModel):
    """Structured durable record for one completed market-analysis run."""

    analysis_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Stable identifier for this saved analysis.",
    )
    session_id: str = Field(
        default="",
        description="ADK session identifier for the run.",
    )
    user_id: str = Field(
        default="",
        description="ADK user identifier associated with the run.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the durable record was created.",
    )
    request_text: str = Field(
        default="",
        description="Original user request text for the analysis run.",
    )
    product_name: str = Field(
        default="",
        description="Normalized primary product name from research scope.",
    )
    category: str = Field(
        default="",
        description="Normalized category from research scope.",
    )
    market: str = Field(
        default="",
        description="Normalized market from research scope.",
    )
    status: str = Field(
        default="completed",
        description="High-level persistence status for the saved analysis.",
    )
    final_report_markdown: str = Field(
        default="",
        description="Final Markdown report returned to the user.",
    )
    state_snapshot_json: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON-safe snapshot of persisted session-state data.",
    )
    citations_json: list[CitationRecord] = Field(
        default_factory=list,
        description="Extracted source URLs associated with the snapshot.",
    )


@runtime_checkable
class AnalysisStore(Protocol):
    """Persistence interface for completed market analyses."""

    def save(self, snapshot: AnalysisSnapshot) -> str:
        """Persist one completed analysis and return its identifier."""

    def get(self, analysis_id: str) -> AnalysisSnapshot | None:
        """Fetch one saved analysis by identifier."""

    def list_recent(
        self,
        limit: int,
        product_name: str | None = None,
        market: str | None = None,
    ) -> list[AnalysisSnapshot]:
        """List recent completed analyses, optionally filtered."""


class SQLiteAnalysisStore:
    """SQLite-backed durable store for completed market analyses."""

    def __init__(self, db_path: str | Path) -> None:
        """Store the target SQLite path without touching disk eagerly."""
        self.db_path = Path(db_path)

    def save(self, snapshot: AnalysisSnapshot) -> str:
        """Insert a completed analysis snapshot into SQLite."""
        normalized_citations = [
            citation
            if isinstance(citation, CitationRecord)
            else CitationRecord.model_validate(citation)
            for citation in snapshot.citations_json
        ]
        normalized_snapshot = snapshot.model_copy(
            update={
                "state_snapshot_json": make_json_safe(snapshot.state_snapshot_json),
                "citations_json": normalized_citations,
            }
        )

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO analyses (
                    analysis_id,
                    session_id,
                    user_id,
                    created_at,
                    request_text,
                    product_name,
                    category,
                    market,
                    status,
                    final_report_markdown,
                    state_snapshot_json,
                    citations_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_snapshot.analysis_id,
                    normalized_snapshot.session_id,
                    normalized_snapshot.user_id,
                    normalized_snapshot.created_at.isoformat(),
                    normalized_snapshot.request_text,
                    normalized_snapshot.product_name,
                    normalized_snapshot.category,
                    normalized_snapshot.market,
                    normalized_snapshot.status,
                    normalized_snapshot.final_report_markdown,
                    json.dumps(normalized_snapshot.state_snapshot_json, sort_keys=True),
                    json.dumps(
                        [
                            citation.model_dump(mode="json")
                            for citation in normalized_snapshot.citations_json
                        ],
                        sort_keys=True,
                    ),
                ),
            )

        return normalized_snapshot.analysis_id

    def get(self, analysis_id: str) -> AnalysisSnapshot | None:
        """Return one persisted snapshot when it exists."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    analysis_id,
                    session_id,
                    user_id,
                    created_at,
                    request_text,
                    product_name,
                    category,
                    market,
                    status,
                    final_report_markdown,
                    state_snapshot_json,
                    citations_json
                FROM analyses
                WHERE analysis_id = ?
                """,
                (analysis_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_snapshot(row)

    def list_recent(
        self,
        limit: int,
        product_name: str | None = None,
        market: str | None = None,
    ) -> list[AnalysisSnapshot]:
        """Return recent persisted snapshots, optionally filtered."""
        safe_limit = max(1, limit)
        clauses: list[str] = []
        params: list[Any] = []

        if product_name:
            clauses.append("product_name = ?")
            params.append(product_name)

        if market:
            clauses.append("market = ?")
            params.append(market)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(safe_limit)

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    analysis_id,
                    session_id,
                    user_id,
                    created_at,
                    request_text,
                    product_name,
                    category,
                    market,
                    status,
                    final_report_markdown,
                    state_snapshot_json,
                    citations_json
                FROM analyses
                {where_sql}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

        return [self._row_to_snapshot(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        """Open the database connection and ensure the schema exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                analysis_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                request_text TEXT NOT NULL,
                product_name TEXT NOT NULL,
                category TEXT NOT NULL,
                market TEXT NOT NULL,
                status TEXT NOT NULL,
                final_report_markdown TEXT NOT NULL,
                state_snapshot_json TEXT NOT NULL,
                citations_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_analyses_created_at
            ON analyses (created_at DESC)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_analyses_product_market
            ON analyses (product_name, market)
            """
        )
        return connection

    @staticmethod
    def _row_to_snapshot(row: sqlite3.Row) -> AnalysisSnapshot:
        """Convert a SQLite row back into a typed analysis snapshot."""
        return AnalysisSnapshot.model_validate(
            {
                "analysis_id": row["analysis_id"],
                "session_id": row["session_id"],
                "user_id": row["user_id"],
                "created_at": row["created_at"],
                "request_text": row["request_text"],
                "product_name": row["product_name"],
                "category": row["category"],
                "market": row["market"],
                "status": row["status"],
                "final_report_markdown": row["final_report_markdown"],
                "state_snapshot_json": json.loads(row["state_snapshot_json"]),
                "citations_json": json.loads(row["citations_json"]),
            }
        )


def build_analysis_snapshot(
    *,
    session_id: str,
    user_id: str,
    request_text: str,
    state_snapshot: Mapping[str, Any],
    status: str = "completed",
    created_at: datetime | None = None,
) -> AnalysisSnapshot:
    """Build a durable snapshot from a JSON-safe session-state payload."""
    normalized_state = make_json_safe(dict(state_snapshot))
    research_scope = normalized_state.get("research_scope", {})
    if not isinstance(research_scope, Mapping):
        research_scope = {}

    return AnalysisSnapshot(
        session_id=session_id,
        user_id=user_id,
        created_at=created_at or datetime.now(timezone.utc),
        request_text=request_text,
        product_name=_string_value(research_scope.get("canonical_product_name")),
        category=_string_value(research_scope.get("category")),
        market=_string_value(research_scope.get("market")),
        status=status,
        final_report_markdown=_string_value(normalized_state.get("final_report")),
        state_snapshot_json=normalized_state,
        citations_json=extract_citations(normalized_state),
    )


def extract_citations(state_snapshot: Mapping[str, Any]) -> list[CitationRecord]:
    """Extract stable citation records from a JSON-safe state snapshot."""
    citations: list[CitationRecord] = []
    seen: set[tuple[str, str, str]] = set()

    def walk(value: Any, *, state_key: str, context_path: str) -> None:
        if isinstance(value, Mapping):
            for key, nested_value in value.items():
                next_path = f"{context_path}.{key}" if context_path else str(key)
                walk(
                    nested_value,
                    state_key=state_key or str(key),
                    context_path=next_path,
                )
            return

        if isinstance(value, Sequence) and not isinstance(
            value,
            (str, bytes, bytearray),
        ):
            for index, item in enumerate(value):
                next_path = f"{context_path}[{index}]"
                walk(item, state_key=state_key, context_path=next_path)
            return

        if not isinstance(value, str):
            return

        for match in URL_PATTERN.findall(value):
            normalized_url = match.rstrip(".,;:")
            identity = (state_key, normalized_url, context_path)
            if identity in seen:
                continue
            seen.add(identity)
            citations.append(
                CitationRecord(
                    state_key=state_key,
                    url=normalized_url,
                    context_path=context_path,
                )
            )

    for top_level_key, top_level_value in state_snapshot.items():
        walk(top_level_value, state_key=top_level_key, context_path=top_level_key)

    return citations


def make_json_safe(value: Any) -> Any:
    """Convert nested values into JSON-safe primitives."""
    if isinstance(value, BaseModel):
        return make_json_safe(value.model_dump(mode="json"))

    if isinstance(value, Mapping):
        return {str(key): make_json_safe(item) for key, item in value.items()}

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [make_json_safe(item) for item in value]

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    if hasattr(value, "model_dump"):
        return make_json_safe(value.model_dump(mode="json"))

    if hasattr(value, "dict"):
        return make_json_safe(value.dict())

    return str(value)


def _string_value(value: Any) -> str:
    """Normalize potentially missing values into a plain string."""
    if value is None:
        return ""
    return value if isinstance(value, str) else str(value)
