# Argus — discord.py observability SDK
# Copyright (C) 2026 AstorisTheBrave
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Reference ClickHouse sink (the ``clickhouse`` extra).

Batched, non-blocking inserts via clickhouse-connect's async client. The client
is created lazily on first flush so importing this module does not require the
optional dependency; tests inject a fake client via ``client_factory``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from argus.history.sink import BatchingSink, Event

COLUMNS = ["ts", "event", "guild_id", "type", "command", "duration_ms", "cluster_id"]
_NUMERIC = frozenset({"duration_ms"})
# Durable, server-batched insert: async_insert lets ClickHouse coalesce writes
# (avoiding the "too many parts" failure), and wait_for_async_insert=1 waits for
# the durable write so a node crash mid-buffer cannot silently lose the batch.
_INSERT_SETTINGS = {"async_insert": 1, "wait_for_async_insert": 1}

ClientFactory = Callable[[], Awaitable[Any]]


def _create_table_sql(table: str) -> str:
    # ts is stored as the ISO-8601 string the hooks emit; queries parse it with
    # parseDateTimeBestEffort. This keeps inserts trivial and timezone-safe.
    return (
        f"CREATE TABLE IF NOT EXISTS {table} ("
        "ts String, "
        "event LowCardinality(String), "
        "guild_id String, "
        "type LowCardinality(String), "
        "command String, "
        "duration_ms Float64, "
        "cluster_id LowCardinality(String)"
        ") ENGINE = MergeTree() ORDER BY (guild_id, ts)"
    )


def _migrate_sql(table: str) -> str:
    # Idempotent: adds cluster_id to a table created before the column existed.
    return f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS cluster_id LowCardinality(String)"


class ClickHouseSink(BatchingSink):
    def __init__(
        self,
        dsn: str,
        *,
        table: str = "argus_events",
        client_factory: ClientFactory | None = None,
        batch_size: int = 100,
        flush_interval: float = 5.0,
        max_queue: int = 10_000,
    ) -> None:
        super().__init__(batch_size=batch_size, flush_interval=flush_interval, max_queue=max_queue)
        self._dsn = dsn
        self._table = table
        self._client_factory = client_factory
        self._client: Any = None
        self._schema_ready = False

    async def _get_client(self) -> Any:
        if self._client is None:
            if self._client_factory is not None:
                self._client = await self._client_factory()
            else:
                import clickhouse_connect  # type: ignore[import-not-found]

                self._client = await clickhouse_connect.get_async_client(dsn=self._dsn)
        if not self._schema_ready:
            await self._client.command(_create_table_sql(self._table))
            await self._client.command(_migrate_sql(self._table))
            self._schema_ready = True
        return self._client

    @staticmethod
    def _row(event: Event) -> list[Any]:
        return [
            float(event.get(column, 0.0) or 0.0) if column in _NUMERIC else event.get(column, "")
            for column in COLUMNS
        ]

    async def _flush(self, batch: list[Event]) -> None:
        client = await self._get_client()
        rows = [self._row(event) for event in batch]
        await client.insert(self._table, rows, column_names=COLUMNS, settings=_INSERT_SETTINGS)

    async def aclose(self) -> None:
        await super().aclose()
        if self._client is not None:
            await self._client.close()
            self._client = None
