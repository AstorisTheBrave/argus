"""Fleet server: register/heartbeat/view happy paths, auth, and shape."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from argus.fleet.config import FleetConfig
from argus.fleet.registry import Registry
from argus.fleet.server import build_fleet_app
from argus.fleet.sources.push import PushSource


def _app(tmp_path: Path, token: str | None = None) -> Any:
    config = FleetConfig.resolve(
        token=token, environ={"ARGUS_FLEET_STATE": str(tmp_path / "s.json")}
    )
    registry = Registry(config.state_path, config.heartbeat_interval, config.ttl_factor)
    return build_fleet_app(config, registry, PushSource(config.namespace))


async def test_register_returns_number(aiohttp_client: Any, tmp_path: Path) -> None:
    client = await aiohttp_client(_app(tmp_path))
    resp = await client.post("/fleet/register", json={"identity": "a", "fleet": "asia"})
    assert resp.status == 200
    assert (await resp.json()) == {"number": 1}


async def test_heartbeat_204_and_view_shape(aiohttp_client: Any, tmp_path: Path) -> None:
    client = await aiohttp_client(_app(tmp_path))
    await client.post("/fleet/register", json={"identity": "a", "fleet": "asia"})
    snapshot = {
        "metrics": {
            "discord_guilds": {
                "type": "gauge",
                "samples": [
                    {"name": "discord_guilds", "labels": {"cluster": "default"}, "value": 7}
                ],
            }
        }
    }
    resp = await client.post("/fleet/heartbeat", json={"identity": "a", "snapshot": snapshot})
    assert resp.status == 204

    view = await (await client.get("/api/fleet/view")).json()
    assert "global" in view
    assert view["fleets"][0]["name"] == "asia"
    assert view["fleets"][0]["clusters"][0]["metrics"]["guilds"] == 7


async def test_register_requires_identity(aiohttp_client: Any, tmp_path: Path) -> None:
    client = await aiohttp_client(_app(tmp_path))
    resp = await client.post("/fleet/register", json={"fleet": "asia"})
    assert resp.status == 400


async def test_invalid_json_body_is_400(aiohttp_client: Any, tmp_path: Path) -> None:
    client = await aiohttp_client(_app(tmp_path))
    resp = await client.post("/fleet/register", data="not json")
    assert resp.status == 400


async def test_healthz_open_other_routes_gated(aiohttp_client: Any, tmp_path: Path) -> None:
    client = await aiohttp_client(_app(tmp_path, token="secret"))
    assert (await client.get("/healthz")).status == 200
    # No token -> 401 on a gated route.
    assert (await client.get("/api/fleet/view")).status == 401
    # Correct token via query param -> allowed.
    ok = await client.get("/api/fleet/view?token=secret")
    assert ok.status == 200


async def test_register_with_token(aiohttp_client: Any, tmp_path: Path) -> None:
    client = await aiohttp_client(_app(tmp_path, token="secret"))
    resp = await client.post(
        "/fleet/register",
        json={"identity": "a", "fleet": "asia"},
        headers={"Authorization": "Bearer secret"},
    )
    assert resp.status == 200


async def test_cluster_view_found_and_missing(aiohttp_client: Any, tmp_path: Path) -> None:
    client = await aiohttp_client(_app(tmp_path))
    await client.post("/fleet/register", json={"identity": "a", "fleet": "asia"})
    ok = await client.get("/api/fleet/cluster?fleet=asia&number=1")
    assert ok.status == 200
    body = await ok.json()
    assert body["cluster"]["number"] == 1
    assert body["history"] == []
    missing = await client.get("/api/fleet/cluster?fleet=asia&number=99")
    assert missing.status == 404


async def test_cluster_view_bad_query(aiohttp_client: Any, tmp_path: Path) -> None:
    client = await aiohttp_client(_app(tmp_path))
    assert (await client.get("/api/fleet/cluster?fleet=asia")).status == 400


async def test_heartbeat_requires_identity(aiohttp_client: Any, tmp_path: Path) -> None:
    client = await aiohttp_client(_app(tmp_path))
    assert (await client.post("/fleet/heartbeat", json={})).status == 400


async def test_index_route_responds(aiohttp_client: Any, tmp_path: Path) -> None:
    client = await aiohttp_client(_app(tmp_path))
    # 200 when the SPA is built, 404 ("assets not built") otherwise; never 500.
    assert (await client.get("/")).status in (200, 404)


async def test_api_config_reports_fleet_mode(aiohttp_client: Any, tmp_path: Path) -> None:
    client = await aiohttp_client(_app(tmp_path))
    body = await (await client.get("/api/config")).json()
    assert body["fleet"] is True
    assert body["auth_required"] is False
