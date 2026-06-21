"""PrometheusSource maps a fake query client to per-cluster FleetView values."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from aiohttp import web

from argus.fleet.promql import error_total_queries, shard_queries
from argus.fleet.registry import Registry
from argus.fleet.sources.prometheus import HTTPQueryClient, PrometheusSource, _by_cluster


class _FakeClient:
    """Returns canned rows per PromQL substring match."""

    def __init__(self, namespace: str = "discord") -> None:
        self._errors_q, self._commands_q = error_total_queries(namespace)
        self._shard_up_q, self._shard_latency_q = shard_queries(namespace)
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True

    async def query(self, promql: str) -> list[tuple[dict[str, str], float]]:
        if promql == self._errors_q:
            return [({"cluster": "a"}, 2.0), ({"cluster": "b"}, 0.0)]
        if promql == self._commands_q:
            return [({"cluster": "a"}, 100.0), ({"cluster": "b"}, 50.0)]
        if promql == self._shard_up_q:
            return [({"cluster": "a", "shard": "0"}, 1.0), ({"cluster": "a", "shard": "1"}, 0.0)]
        if promql == self._shard_latency_q:
            return [({"cluster": "a", "shard": "0"}, 0.07)]
        if "discord_guilds" in promql:
            return [({"cluster": "a"}, 10.0), ({"cluster": "b"}, 5.0)]
        if "discord_shard_up" in promql:
            return [({"cluster": "a"}, 2.0)]
        return []


def test_by_cluster_ignores_rows_without_label() -> None:
    rows = [({"cluster": "a"}, 1.0), ({"instance": "x"}, 9.0)]
    assert _by_cluster(rows) == {"a": 1.0}


async def test_prometheus_source_maps_values(tmp_path: Path) -> None:
    reg = Registry(tmp_path / "s.json")
    reg.register("a", "asia", now=0.0)
    reg.register("b", "asia", now=0.0)
    source = PrometheusSource("http://prom", "discord", client=_FakeClient())

    values = await source.cluster_values(reg)
    assert values.metrics["a"]["guilds"] == 10.0
    assert values.metrics["b"]["guilds"] == 5.0
    assert values.metrics["a"]["shards_up"] == 2.0
    assert values.metrics["b"]["shards_up"] == 0.0  # missing row -> 0
    assert values.error_totals["a"] == (2.0, 100.0)


async def test_prometheus_source_builds_shards(tmp_path: Path) -> None:
    reg = Registry(tmp_path / "s.json")
    reg.register("a", "asia", now=0.0)
    source = PrometheusSource("http://prom", "discord", client=_FakeClient())
    values = await source.cluster_values(reg)
    shards = values.shards["a"]
    assert [(s.shard_id, s.status) for s in shards] == [("0", "up"), ("1", "down")]
    assert shards[0].latency_seconds == 0.07


async def test_prometheus_source_full_view_rollup(tmp_path: Path) -> None:
    reg = Registry(tmp_path / "s.json")
    reg.register("a", "asia", now=0.0)
    reg.register("b", "asia", now=0.0)
    source = PrometheusSource("http://prom", "discord", client=_FakeClient())

    view = await source.fleet_snapshot(reg)
    asia = view.fleets[0]
    assert asia.rollup["guilds"] == 15.0  # 10 + 5
    # error_rate recomputed from summed totals: (2+0)/(100+50).
    assert asia.rollup["error_rate"] == pytest.approx(2 / 150)


async def test_http_query_client_parses_prometheus_response(aiohttp_server: Any) -> None:
    async def handler(request: web.Request) -> web.StreamResponse:
        assert request.query["query"] == "up"
        return web.json_response(
            {
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [
                        {"metric": {"cluster": "a"}, "value": [1.0, "3"]},
                        {"metric": {"cluster": "b"}, "value": [1.0, "7"]},
                        {"metric": {"cluster": "c"}, "value": [1.0, None]},  # skipped
                    ],
                },
            }
        )

    app = web.Application()
    app.router.add_get("/api/v1/query", handler)
    server = await aiohttp_server(app)
    client = HTTPQueryClient(str(server.make_url("")))

    rows = await client.query("up")
    assert _by_cluster(rows) == {"a": 3.0, "b": 7.0}
    # The session is reused across queries, then closed.
    await client.query("up")
    await client.aclose()


async def test_prometheus_source_aclose_closes_client(tmp_path: Path) -> None:
    client = _FakeClient()
    source = PrometheusSource("http://prom", "discord", client=client)
    await source.aclose()
    assert client.closed is True
