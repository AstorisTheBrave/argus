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

"""Read side of the analytical path: per-guild queries for /api/analytics.

Parameterised queries against the events table. The client is any object with
an async ``query(sql, parameters=...)`` returning an object with
``result_rows`` (clickhouse-connect's async client, or a fake in tests).
"""

from __future__ import annotations

from typing import Any


class AnalyticsQuery:
    def __init__(self, client: Any, *, table: str = "argus_events") -> None:
        self._client = client
        self._table = table

    async def interaction_volume(self, guild_id: str, *, since_days: int = 30) -> list[Any]:
        sql = (
            f"SELECT toDate(ts) AS day, count() AS count FROM {self._table} "
            "WHERE guild_id = %(guild_id)s AND ts >= now() - INTERVAL %(days)s DAY "
            "GROUP BY day ORDER BY day"
        )
        result = await self._client.query(
            sql, parameters={"guild_id": guild_id, "days": since_days}
        )
        return list(result.result_rows)

    async def top_commands(self, guild_id: str, *, limit: int = 10) -> list[Any]:
        sql = (
            f"SELECT command, count() AS count FROM {self._table} "
            "WHERE guild_id = %(guild_id)s AND event = 'app_command' "
            "GROUP BY command ORDER BY count DESC LIMIT %(limit)s"
        )
        result = await self._client.query(sql, parameters={"guild_id": guild_id, "limit": limit})
        return list(result.result_rows)

    async def command_stats(self, guild_id: str, *, limit: int = 50) -> list[Any]:
        """Per-command count + average duration (ms) for a guild."""
        sql = (
            f"SELECT command, count() AS count, avg(duration_ms) AS avg_ms FROM {self._table} "
            "WHERE guild_id = %(guild_id)s AND event = 'app_command' "
            "GROUP BY command ORDER BY count DESC LIMIT %(limit)s"
        )
        result = await self._client.query(sql, parameters={"guild_id": guild_id, "limit": limit})
        return list(result.result_rows)

    async def avg_duration(self, guild_id: str) -> float:
        """Overall average application command duration (ms) for a guild."""
        sql = (
            f"SELECT avg(duration_ms) AS avg_ms FROM {self._table} "
            "WHERE guild_id = %(guild_id)s AND event = 'app_command'"
        )
        result = await self._client.query(sql, parameters={"guild_id": guild_id})
        rows = list(result.result_rows)
        if rows and rows[0] and rows[0][0] is not None:
            return float(rows[0][0])
        return 0.0
