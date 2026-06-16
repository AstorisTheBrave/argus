"""Exposition endpoint tests via the aiohttp_client fixture (D6 gate)."""

from __future__ import annotations

from typing import Any

from argus.adapters.prometheus import PrometheusAdapter
from argus.config import ArgusConfig
from argus.core.collector import MetricRegistry
from argus.core.metrics import define_metrics
from argus.exposition.server import build_app
from tests.conftest import FakeBot


def _registry() -> Any:
    bot = FakeBot()
    registry = MetricRegistry()
    define_metrics(registry, bot, ArgusConfig.resolve(environ={}))
    adapter = PrometheusAdapter()
    registry.attach(adapter)
    return adapter.registry


async def test_metrics_endpoint_serves_exposition(aiohttp_client: Any) -> None:
    client = await aiohttp_client(build_app(_registry()))
    resp = await client.get("/metrics")
    assert resp.status == 200
    assert resp.headers["Content-Type"].startswith("text/plain")
    body = await resp.text()
    assert "discord_guilds" in body
    assert "# TYPE discord_app_command_duration_seconds histogram" in body
    assert "argus_up" in body


async def test_healthz_returns_200(aiohttp_client: Any) -> None:
    client = await aiohttp_client(build_app(_registry()))
    resp = await client.get("/healthz")
    assert resp.status == 200
    assert (await resp.text()).strip() == "ok"


async def test_custom_metrics_path(aiohttp_client: Any) -> None:
    client = await aiohttp_client(build_app(_registry(), metrics_path="/m"))
    assert (await client.get("/m")).status == 200
    assert (await client.get("/metrics")).status == 404
