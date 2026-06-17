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

COLUMNS = ["ts", "event", "guild_id", "type", "command"]

ClientFactory = Callable[[], Awaitable[Any]]


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

    async def _get_client(self) -> Any:
        if self._client is None:
            if self._client_factory is not None:
                self._client = await self._client_factory()
            else:
                import clickhouse_connect  # type: ignore[import-not-found]

                self._client = await clickhouse_connect.get_async_client(dsn=self._dsn)
        return self._client

    @staticmethod
    def _row(event: Event) -> list[Any]:
        return [event.get(column, "") for column in COLUMNS]

    async def _flush(self, batch: list[Event]) -> None:
        client = await self._get_client()
        rows = [self._row(event) for event in batch]
        await client.insert(self._table, rows, column_names=COLUMNS)

    async def aclose(self) -> None:
        await super().aclose()
        if self._client is not None:
            await self._client.close()
            self._client = None
