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


async def test_stream_rejects_when_at_capacity(aiohttp_client: Any, monkeypatch: Any) -> None:
    import argus.dashboard.server as ds

    monkeypatch.setattr(ds, "_MAX_SSE_CONNECTIONS", 0)
    client = await aiohttp_client(_app())
    resp = await client.get("/api/stream")
    assert resp.status == 503


async def test_stream_snapshot_is_cached_across_viewers(
    aiohttp_client: Any, monkeypatch: Any
) -> None:
    from argus.dashboard.snapshot import build_snapshot as real

    calls = {"n": 0}

    def counting(registry: Any) -> Any:
        calls["n"] += 1
        return real(registry)

    monkeypatch.setattr("argus.dashboard.server.build_snapshot", counting)
    client = await aiohttp_client(_app())

    r1 = await client.get("/api/stream")
    await r1.content.readuntil(b"\n\n")
    r2 = await client.get("/api/stream")
    await r2.content.readuntil(b"\n\n")
    # Two viewers within the TTL share one build (single-flight + short cache).
    assert calls["n"] == 1
    r1.close()
    r2.close()
