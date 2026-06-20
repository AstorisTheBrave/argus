"""Analytics API: disabled, fail-closed, and served (plan task 4.2)."""

from __future__ import annotations

from typing import Any

from prometheus_client import CollectorRegistry

import argus
from argus.config import ArgusConfig
from argus.dashboard.auth import make_auth_middleware
from argus.dashboard.server import register_dashboard
from argus.exposition.server import build_app
from argus.history.query import AnalyticsQuery
from tests.history.test_clickhouse import FakeClient


def _app(config: ArgusConfig, analytics: AnalyticsQuery | None) -> Any:
    registry = CollectorRegistry()
    middlewares = []
    if config.dashboard_auth_token is not None:
        middlewares.append(
            make_auth_middleware(
                config.dashboard_auth_token,
                frozenset({"/healthz", config.metrics_path}),
            )
        )
    registrar = register_dashboard(
        config, registry=registry, version=argus.__version__, analytics=analytics
    )
    return build_app(registry, config.metrics_path, dashboard=registrar, middlewares=middlewares)


def _authed() -> ArgusConfig:
    return ArgusConfig.resolve(enable_per_guild=True, dashboard_auth_token="secret", environ={})


_HDR = {"Authorization": "Bearer secret"}


async def test_analytics_404_when_disabled(aiohttp_client: Any) -> None:
    client = await aiohttp_client(_app(ArgusConfig.resolve(environ={}), None))
    resp = await client.get("/api/analytics/interaction-volume?guild_id=1")
    assert resp.status == 404


async def test_command_stats_served(aiohttp_client: Any) -> None:
    analytics = AnalyticsQuery(FakeClient(rows=[("ping", 10, 12.5)]))
    client = await aiohttp_client(_app(_authed(), analytics))
    resp = await client.get("/api/analytics/command-stats?guild_id=1", headers=_HDR)
    assert resp.status == 200
    assert (await resp.json())["rows"] == [["ping", 10, 12.5]]


async def test_avg_duration_served(aiohttp_client: Any) -> None:
    analytics = AnalyticsQuery(FakeClient(rows=[(42.0,)]))
    client = await aiohttp_client(_app(_authed(), analytics))
    resp = await client.get("/api/analytics/avg-duration?guild_id=1", headers=_HDR)
    assert resp.status == 200
    assert (await resp.json())["avg_ms"] == 42.0


async def test_analytics_fail_closed_without_token(aiohttp_client: Any) -> None:
    config = ArgusConfig.resolve(enable_per_guild=True, environ={})  # no auth token
    client = await aiohttp_client(_app(config, AnalyticsQuery(FakeClient())))
    resp = await client.get("/api/analytics/interaction-volume?guild_id=1")
    assert resp.status == 403


async def test_analytics_served_with_token(aiohttp_client: Any) -> None:
    config = ArgusConfig.resolve(enable_per_guild=True, dashboard_auth_token="secret", environ={})
    client = await aiohttp_client(_app(config, AnalyticsQuery(FakeClient())))
    headers = {"Authorization": "Bearer secret"}
    resp = await client.get("/api/analytics/interaction-volume?guild_id=1", headers=headers)
    assert resp.status == 200
    assert (await resp.json())["rows"] == [["2026-06-17", 5]]
    bad = await client.get("/api/analytics/interaction-volume", headers=headers)
    assert bad.status == 400  # missing guild_id
