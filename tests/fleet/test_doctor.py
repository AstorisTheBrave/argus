"""The doctor: reachability, auth, and cluster-health probing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from argus.fleet import doctor
from argus.fleet.config import FleetConfig
from argus.fleet.registry import Registry
from argus.fleet.server import build_fleet_app
from argus.fleet.sources.push import PushSource


def _fleet(tmp_path: Path, token: str | None = None) -> Any:
    config = FleetConfig.resolve(
        token=token, view_cache_ms=0, environ={"ARGUS_FLEET_STATE": str(tmp_path / "s.json")}
    )
    registry = Registry(config.state_path, config.heartbeat_interval, config.ttl_factor)
    return build_fleet_app(config, registry, PushSource(config.namespace))


async def test_doctor_healthy_empty_fleet(aiohttp_server: Any, tmp_path: Path) -> None:
    server = await aiohttp_server(_fleet(tmp_path))
    report = await doctor.check(str(server.make_url("")))
    assert report.ok is True
    assert any("0/0 clusters up" in f for f in report.findings)


async def test_doctor_missing_token_is_flagged(aiohttp_server: Any, tmp_path: Path) -> None:
    server = await aiohttp_server(_fleet(tmp_path, token="secret"))
    report = await doctor.check(str(server.make_url("")))  # no token
    assert report.ok is False
    assert any("401" in f for f in report.findings)


async def test_doctor_with_token_ok(aiohttp_server: Any, tmp_path: Path) -> None:
    server = await aiohttp_server(_fleet(tmp_path, token="secret"))
    report = await doctor.check(str(server.make_url("")), "secret")
    assert report.ok is True


async def test_doctor_unreachable() -> None:
    report = await doctor.check("http://127.0.0.1:1", timeout=0.5)
    assert report.ok is False
    assert any("cannot reach" in f for f in report.findings)


async def test_doctor_flags_namespace_mismatch(aiohttp_server: Any, tmp_path: Path) -> None:
    server = await aiohttp_server(_fleet(tmp_path))  # namespace defaults to "discord"
    report = await doctor.check(str(server.make_url("")), namespace="wrongns")
    assert report.ok is False
    assert any("expected 'wrongns'" in f for f in report.findings)


async def test_doctor_namespace_match_ok(aiohttp_server: Any, tmp_path: Path) -> None:
    server = await aiohttp_server(_fleet(tmp_path))
    report = await doctor.check(str(server.make_url("")), namespace="discord")
    assert report.ok is True


def test_inspect_view_flags_down_clusters() -> None:
    report = doctor.DoctorReport()
    view: dict[str, object] = {"fleets": [{"name": "asia", "clusters_total": 3, "clusters_up": 1}]}
    doctor._inspect_view(view, report)
    assert report.ok is False
    assert any("2 cluster(s) down" in f for f in report.findings)
