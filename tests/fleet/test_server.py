"""Fleet server: register/heartbeat/view happy paths, auth, and shape."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from argus.fleet.config import FleetConfig
from argus.fleet.registry import Registry
from argus.fleet.server import build_fleet_app
from argus.fleet.sources.push import PushSource


def _app(tmp_path: Path, token: str | None = None, **kwargs: Any) -> Any:
    # Disable the view cache by default so tests see fresh state deterministically;
    # a dedicated test exercises the cache with a real TTL.
    kwargs.setdefault("view_cache_ms", 0)
    config = FleetConfig.resolve(
        token=token,
        environ={"ARGUS_FLEET_STATE": str(tmp_path / "s.json")},
        **kwargs,
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


async def test_split_tokens_gate_their_surfaces(aiohttp_client: Any, tmp_path: Path) -> None:
    client = await aiohttp_client(_app(tmp_path, ingest_token="ing", viewer_token="view"))
    # Register (ingest path) accepts the ingest token, rejects the viewer token.
    ok = await client.post(
        "/fleet/register",
        json={"identity": "a", "fleet": "asia"},
        headers={"Authorization": "Bearer ing"},
    )
    assert ok.status == 200
    bad = await client.post(
        "/fleet/register",
        json={"identity": "b", "fleet": "asia"},
        headers={"Authorization": "Bearer view"},
    )
    assert bad.status == 401
    # The view (viewer path) accepts the viewer token, rejects the ingest token.
    assert (await client.get("/api/fleet/view?token=view")).status == 200
    assert (await client.get("/api/fleet/view?token=ing")).status == 401


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


async def test_security_headers_and_banner(aiohttp_client: Any, tmp_path: Path) -> None:
    client = await aiohttp_client(_app(tmp_path))
    resp = await client.get("/healthz")
    assert resp.headers["Server"] == "argus-fleet"  # version banner stripped
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert "Content-Security-Policy" in resp.headers


async def test_readyz_open_even_with_token(aiohttp_client: Any, tmp_path: Path) -> None:
    client = await aiohttp_client(_app(tmp_path, token="secret"))
    assert (await client.get("/readyz")).status == 200


async def test_body_cap_rejects_large_payload(aiohttp_client: Any, tmp_path: Path) -> None:
    client = await aiohttp_client(_app(tmp_path, max_body_bytes=50))
    big = {"identity": "a", "fleet": "asia", "pad": "x" * 1000}
    assert (await client.post("/fleet/register", json=big)).status == 413


async def test_cors_preflight_and_allowlist(aiohttp_client: Any, tmp_path: Path) -> None:
    origins = ("https://ui.example",)
    client = await aiohttp_client(_app(tmp_path, token="secret", cors_origins=origins))
    # Preflight is not auth-gated and echoes only an allowlisted origin.
    pre = await client.options("/api/fleet/view", headers={"Origin": "https://ui.example"})
    assert pre.status == 204
    assert pre.headers["Access-Control-Allow-Origin"] == "https://ui.example"
    # A non-listed origin gets no allow header.
    other = await client.options("/api/fleet/view", headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in other.headers


async def test_no_cors_headers_when_disabled(aiohttp_client: Any, tmp_path: Path) -> None:
    client = await aiohttp_client(_app(tmp_path))
    resp = await client.get("/healthz", headers={"Origin": "https://ui.example"})
    assert "Access-Control-Allow-Origin" not in resp.headers


async def test_self_metrics_exposes_fleet_gauges(aiohttp_client: Any, tmp_path: Path) -> None:
    client = await aiohttp_client(_app(tmp_path))
    await client.post("/fleet/register", json={"identity": "a", "fleet": "asia"})
    await client.post("/fleet/heartbeat", json={"identity": "a"})
    body = await (await client.get("/metrics")).text()
    assert "argus_fleet_registrations_total" in body
    assert "argus_fleet_heartbeats_total" in body
    assert 'argus_fleet_clusters{fleet="asia",status="up"}' in body
    assert "argus_fleet_registry_entries" in body


async def test_self_metrics_gated_by_token(aiohttp_client: Any, tmp_path: Path) -> None:
    client = await aiohttp_client(_app(tmp_path, token="secret"))
    assert (await client.get("/metrics")).status == 401
    assert (await client.get("/metrics?token=secret")).status == 200


async def test_view_is_cached_within_ttl(aiohttp_client: Any, tmp_path: Path) -> None:
    # A long TTL: a cluster registered after the first view is not yet visible.
    client = await aiohttp_client(_app(tmp_path, view_cache_ms=60000))
    await client.post("/fleet/register", json={"identity": "a", "fleet": "asia"})
    first = await (await client.get("/api/fleet/view")).json()
    assert first["fleets"][0]["clusters_total"] == 1
    await client.post("/fleet/register", json={"identity": "b", "fleet": "asia"})
    cached = await (await client.get("/api/fleet/view")).json()
    # Served from cache: the second cluster is not reflected until the TTL lapses.
    assert cached["fleets"][0]["clusters_total"] == 1
