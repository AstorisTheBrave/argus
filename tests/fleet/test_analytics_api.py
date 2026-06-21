"""Fleet analytics API: mounted only with analytics, gated, cluster-scoped."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from argus.fleet.config import FleetConfig
from argus.fleet.registry import Registry
from argus.fleet.server import build_fleet_app
from argus.fleet.sources.push import PushSource


class _FakeAnalytics:
    """Records the guild/cluster it was called with and returns canned rows."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str | None]] = []

    async def interaction_volume(
        self, guild_id: str, *, cluster_id: str | None = None
    ) -> list[Any]:
        self.calls.append(("volume", guild_id, cluster_id))
        return [("2026-06-21", 5)]

    async def top_commands(self, guild_id: str, *, cluster_id: str | None = None) -> list[Any]:
        self.calls.append(("top", guild_id, cluster_id))
        return [("ping", 10)]

    async def command_stats(self, guild_id: str, *, cluster_id: str | None = None) -> list[Any]:
        self.calls.append(("stats", guild_id, cluster_id))
        return [("ping", 10, 12.5)]

    async def avg_duration(self, guild_id: str, *, cluster_id: str | None = None) -> float:
        self.calls.append(("avg", guild_id, cluster_id))
        return 12.5


def _app(tmp_path: Path, *, token: str | None, analytics: Any) -> Any:
    config = FleetConfig.resolve(
        token=token, environ={"ARGUS_FLEET_STATE": str(tmp_path / "s.json")}
    )
    registry = Registry(config.state_path)
    return build_fleet_app(config, registry, PushSource(), analytics)


async def test_analytics_routes_absent_without_analytics(
    aiohttp_client: Any, tmp_path: Path
) -> None:
    client = await aiohttp_client(_app(tmp_path, token="t", analytics=None))
    resp = await client.get("/api/fleet/analytics/top-commands?guild_id=1&token=t")
    assert resp.status == 404  # not mounted
    cfg = await (await client.get("/api/config?token=t")).json()
    assert cfg["analytics_enabled"] is False


async def test_analytics_top_commands_with_cluster(aiohttp_client: Any, tmp_path: Path) -> None:
    fake = _FakeAnalytics()
    client = await aiohttp_client(_app(tmp_path, token="t", analytics=fake))
    resp = await client.get("/api/fleet/analytics/top-commands?guild_id=42&cluster=asia-0&token=t")
    assert resp.status == 200
    assert (await resp.json())["rows"] == [["ping", 10]]
    assert fake.calls[-1] == ("top", "42", "asia-0")


async def test_analytics_requires_guild_id(aiohttp_client: Any, tmp_path: Path) -> None:
    client = await aiohttp_client(_app(tmp_path, token="t", analytics=_FakeAnalytics()))
    assert (await client.get("/api/fleet/analytics/avg-duration?token=t")).status == 400


async def test_analytics_fails_closed_without_viewer_token(
    aiohttp_client: Any, tmp_path: Path
) -> None:
    # No token configured: the plane is open, but analytics still refuses (403).
    client = await aiohttp_client(_app(tmp_path, token=None, analytics=_FakeAnalytics()))
    resp = await client.get("/api/fleet/analytics/top-commands?guild_id=1")
    assert resp.status == 403


async def test_analytics_gated_by_viewer_token(aiohttp_client: Any, tmp_path: Path) -> None:
    client = await aiohttp_client(_app(tmp_path, token="secret", analytics=_FakeAnalytics()))
    assert (await client.get("/api/fleet/analytics/top-commands?guild_id=1")).status == 401
    ok = await client.get("/api/fleet/analytics/top-commands?guild_id=1&token=secret")
    assert ok.status == 200
