"""ClickHouse sink + analytics queries against a fake client (plan task 4.1)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from argus.history.clickhouse import COLUMNS, ClickHouseSink
from argus.history.query import AnalyticsQuery


class FakeClient:
    def __init__(self) -> None:
        self.inserts: list[tuple[str, list[Any], list[str]]] = []
        self.queries: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    async def insert(self, table: str, rows: list[Any], column_names: list[str]) -> None:
        self.inserts.append((table, rows, column_names))

    async def query(self, sql: str, parameters: dict[str, Any] | None = None) -> Any:
        self.queries.append((sql, parameters or {}))
        return SimpleNamespace(result_rows=[("2026-06-17", 5)])

    async def close(self) -> None:
        self.closed = True


async def test_sink_batches_insert_and_closes_client() -> None:
    fake = FakeClient()

    async def factory() -> FakeClient:
        return fake

    sink = ClickHouseSink("http://ch", client_factory=factory, batch_size=2, flush_interval=10.0)
    await sink.record({"guild_id": "1", "event": "interaction", "type": "x"})
    await sink.record({"guild_id": "2", "event": "interaction", "type": "y"})
    await asyncio.sleep(0.05)
    await sink.aclose()

    assert len(fake.inserts) == 1
    table, rows, columns = fake.inserts[0]
    assert table == "argus_events"
    assert columns == COLUMNS
    assert len(rows) == 2
    assert rows[0] == ["", "interaction", "1", "x", ""]  # ts/command default to ""
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
