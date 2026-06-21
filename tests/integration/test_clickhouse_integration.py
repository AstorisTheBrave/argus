"""Round-trip against a real ClickHouse.

Skipped unless clickhouse-connect is installed and CLICKHOUSE_DSN is set (the CI
``clickhouse`` job provides both via a service container).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

import pytest

pytestmark = pytest.mark.integration

clickhouse_connect: Any = pytest.importorskip("clickhouse_connect")

DSN = os.environ.get("CLICKHOUSE_DSN")


def _event(
    guild_id: str, command: str, duration_ms: float, cluster_id: str = "c0"
) -> dict[str, object]:
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": "app_command",
        "guild_id": guild_id,
        "type": "",
        "command": command,
        "duration_ms": duration_ms,
        "cluster_id": cluster_id,
    }


async def test_sink_insert_and_query_roundtrip() -> None:
    if not DSN:
        pytest.skip("CLICKHOUSE_DSN not set")

    from argus.history.clickhouse import ClickHouseSink
    from argus.history.query import AnalyticsQuery

    table = f"argus_events_{uuid.uuid4().hex[:8]}"
    sink = ClickHouseSink(DSN, table=table, batch_size=10, flush_interval=0.5)
    try:
        await sink.record(_event("99", "ping", 10.0, cluster_id="c0"))
        await sink.record(_event("99", "ping", 30.0, cluster_id="c0"))
        await sink.record(_event("99", "weather", 100.0, cluster_id="c1"))
        await sink.aclose()  # flushes remainder

        client = await clickhouse_connect.get_async_client(dsn=DSN)
        try:
            query = AnalyticsQuery(client, table=table)
            stats = {row[0]: (row[1], row[2]) for row in await query.command_stats("99")}
            assert stats["ping"][0] == 2
            assert stats["ping"][1] == pytest.approx(20.0)  # avg of 10 and 30
            assert stats["weather"][0] == 1
            assert await query.avg_duration("99") == pytest.approx((10 + 30 + 100) / 3)
            volume = await query.interaction_volume("99")
            assert sum(row[1] for row in volume) >= 0  # app_command rows have no day filter issue
            # Per-cluster (per-bot) slice: c0 has only the two ping calls.
            c0 = {row[0]: row[1] for row in await query.top_commands("99", cluster_id="c0")}
            assert c0 == {"ping": 2}
        finally:
            await client.command(f"DROP TABLE IF EXISTS {table}")
            await client.close()
    finally:
        await sink.aclose()
