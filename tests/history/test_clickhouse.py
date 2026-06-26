"""ClickHouse sink + analytics queries against a fake client."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from argus.history.clickhouse import COLUMNS, ClickHouseSink
from argus.history.query import AnalyticsQuery


class FakeClient:
    def __init__(self, rows: list[Any] | None = None) -> None:
        self.inserts: list[tuple[str, list[Any], list[str]]] = []
        self.queries: list[tuple[str, dict[str, Any]]] = []
        self.commands: list[str] = []
        self.closed = False
        self._rows = rows if rows is not None else [("2026-06-17", 5)]

    async def command(self, sql: str) -> None:
        self.commands.append(sql)

    async def insert(
        self,
        table: str,
        rows: list[Any],
        column_names: list[str],
        settings: dict[str, Any] | None = None,
    ) -> None:
        self.inserts.append((table, rows, column_names))
        self.insert_settings = settings or {}

    async def query(self, sql: str, parameters: dict[str, Any] | None = None) -> Any:
        self.queries.append((sql, parameters or {}))
        return SimpleNamespace(result_rows=self._rows)

    async def close(self) -> None:
        self.closed = True


async def test_sink_creates_table_then_batches_insert() -> None:
    fake = FakeClient()

    async def factory() -> FakeClient:
        return fake

    sink = ClickHouseSink("http://ch", client_factory=factory, batch_size=2, flush_interval=10.0)
    await sink.record(
        {"guild_id": "1", "event": "app_command", "command": "ping", "duration_ms": 12.5}
    )
    await sink.record({"guild_id": "2", "event": "interaction", "type": "x"})
    await asyncio.sleep(0.05)
    await sink.aclose()

    assert any("CREATE TABLE IF NOT EXISTS argus_events" in c for c in fake.commands)
    assert len(fake.inserts) == 1
    table, rows, columns = fake.inserts[0]
    assert table == "argus_events"
    assert columns == COLUMNS
    # ts/command/cluster_id default to "", duration_ms is numeric (0.0 when absent).
    assert rows[0] == ["", "app_command", "1", "", "ping", 12.5, ""]
    assert rows[1] == ["", "interaction", "2", "x", "", 0.0, ""]
    # Durable, server-batched insert settings are applied.
    assert fake.insert_settings == {"async_insert": 1, "wait_for_async_insert": 1}
    assert fake.closed


async def test_interaction_volume_query() -> None:
    fake = FakeClient()
    rows = await AnalyticsQuery(fake).interaction_volume("42", since_days=7)
    sql, params = fake.queries[0]
    assert "argus_events" in sql
    assert params == {"guild_id": "42", "days": 7}
    assert rows == [("2026-06-17", 5)]


async def test_top_commands_query() -> None:
    fake = FakeClient()
    await AnalyticsQuery(fake).top_commands("42", limit=5)
    sql, params = fake.queries[0]
    assert "ORDER BY count DESC" in sql
    assert params == {"guild_id": "42", "limit": 5}


async def test_query_scoped_by_cluster_id() -> None:
    fake = FakeClient()
    await AnalyticsQuery(fake).top_commands("42", limit=5, cluster_id="asia-0")
    sql, params = fake.queries[0]
    assert "cluster_id = %(cluster_id)s" in sql
    assert params == {"guild_id": "42", "limit": 5, "cluster_id": "asia-0"}


async def test_command_stats_query() -> None:
    fake = FakeClient(rows=[("ping", 10, 12.5)])
    rows = await AnalyticsQuery(fake).command_stats("42")
    sql, params = fake.queries[0]
    assert "avg(duration_ms)" in sql
    assert params == {"guild_id": "42", "limit": 50}
    assert rows == [("ping", 10, 12.5)]


async def test_avg_duration_query() -> None:
    fake = FakeClient(rows=[(42.0,)])
    avg = await AnalyticsQuery(fake).avg_duration("42")
    sql, _ = fake.queries[0]
    assert "avg(duration_ms)" in sql
    assert avg == 42.0


async def test_malicious_guild_id_is_inert_parameter_not_sql() -> None:
    # Regression guard against SQL injection (audit Finding 3): a hostile value
    # must travel as a bound parameter, never be interpolated into the SQL text.
    evil = "1'; DROP TABLE argus_events; --"
    fake = FakeClient()
    await AnalyticsQuery(fake).interaction_volume(evil, cluster_id=evil)
    sql, params = fake.queries[0]
    assert evil not in sql  # not concatenated into the query
    assert "DROP TABLE" not in sql.upper().replace("ARGUS_EVENTS", "")
    assert params["guild_id"] == evil  # passed as a parameter instead
    assert params["cluster_id"] == evil
    # SQL only contains placeholders, never the raw value.
    assert "%(guild_id)s" in sql and "%(cluster_id)s" in sql
