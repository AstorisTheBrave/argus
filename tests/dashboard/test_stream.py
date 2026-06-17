"""SSE metric stream (plan task 2.2)."""

from __future__ import annotations

import json
from typing import Any

from prometheus_client import CollectorRegistry

import argus
from argus.adapters.prometheus import PrometheusAdapter
from argus.config import ArgusConfig
from argus.core.collector import MetricRegistry
from argus.core.metrics import define_metrics
from argus.dashboard.server import register_dashboard
from argus.exposition.server import build_app


def _app() -> Any:
    bot_registry = MetricRegistry()
    from tests.conftest import FakeBot

    define_metrics(bot_registry, FakeBot(), ArgusConfig.resolve(environ={}))
    adapter = PrometheusAdapter()
    bot_registry.attach(adapter)
    config = ArgusConfig.resolve(dashboard_interval=1, environ={})
    registrar = register_dashboard(config, registry=adapter.registry, version=argus.__version__)
    return build_app(CollectorRegistry(), config.metrics_path, dashboard=registrar)


async def test_stream_emits_a_snapshot_event(aiohttp_client: Any) -> None:
    client = await aiohttp_client(_app())
    resp = await client.get("/api/stream")
    assert resp.status == 200
    assert resp.headers["Content-Type"].startswith("text/event-stream")
    # Read the first SSE event (emitted immediately, before the interval sleep).
    line = await resp.content.readuntil(b"\n\n")
    text = line.decode()
    assert text.startswith("data: ")
    payload = json.loads(text[len("data: ") :].strip())
    assert "discord_guilds" in payload["metrics"]
    resp.close()
