"""Dashboard serving + /api/config + auth gating (plan task 1.3)."""

from __future__ import annotations

from typing import Any

import pytest
from prometheus_client import CollectorRegistry

import argus
from argus.config import ArgusConfig
from argus.dashboard.auth import make_auth_middleware
from argus.dashboard.server import register_dashboard
from argus.exposition.server import build_app


def _make_app(config: ArgusConfig) -> Any:
    registry = CollectorRegistry()
    middlewares = []
    if config.dashboard_auth_token is not None:
        middlewares.append(
            make_auth_middleware(
                config.dashboard_auth_token,
                frozenset({"/healthz", config.metrics_path}),
            )
        )
    registrar = (
        register_dashboard(config, registry=registry, version=argus.__version__)
        if config.dashboard
        else None
    )
    return build_app(registry, config.metrics_path, dashboard=registrar, middlewares=middlewares)


async def test_serves_index_metrics_health_and_config(aiohttp_client: Any) -> None:
    client = await aiohttp_client(_make_app(ArgusConfig.resolve(environ={})))
    assert (await client.get("/")).status == 200
    assert (await client.get("/metrics")).status == 200
    assert (await client.get("/healthz")).status == 200
    resp = await client.get("/api/config")
    assert resp.status == 200
    body = await resp.json()
    assert body == {
        "namespace": "discord",
        "metrics_path": "/metrics",
        "grafana_url": None,
        "analytics_enabled": False,
        "version": argus.__version__,
        "auth_required": False,
    }


async def test_dashboard_disabled_404_but_metrics_live(aiohttp_client: Any) -> None:
    client = await aiohttp_client(_make_app(ArgusConfig.resolve(dashboard=False, environ={})))
    assert (await client.get("/")).status == 404
    assert (await client.get("/metrics")).status == 200


async def test_auth_gates_dashboard_not_metrics(aiohttp_client: Any) -> None:
    config = ArgusConfig.resolve(dashboard_auth_token="secret", environ={})
    client = await aiohttp_client(_make_app(config))
    assert (await client.get("/")).status == 401
    assert (await client.get("/api/config")).status == 401
    ok = await client.get("/", headers={"Authorization": "Bearer secret"})
    assert ok.status == 200
    assert (await client.get("/metrics")).status == 200  # open for scraping
    assert (await client.get("/healthz")).status == 200
    cfg = await client.get("/api/config", headers={"Authorization": "Bearer secret"})
    assert (await cfg.json())["auth_required"] is True


def test_path_collision_raises() -> None:
    with pytest.raises(ValueError, match="collides"):
        register_dashboard(
            ArgusConfig.resolve(dashboard_path="/metrics", environ={}),
            registry=CollectorRegistry(),
            version=argus.__version__,
        )
