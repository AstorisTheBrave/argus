"""Member FleetClient: identity, register + heartbeat round-trip, fail-open."""

from __future__ import annotations

import asyncio
import stat
import sys
from pathlib import Path
from typing import Any

import pytest

from argus.config import ArgusConfig
from argus.fleet.client import FleetClient
from argus.fleet.config import FleetConfig
from argus.fleet.registry import Registry
from argus.fleet.server import build_fleet_app
from argus.fleet.sources.push import PushSource


def _member_config(url: str, tmp_path: Path, scrape_target: str | None = None) -> ArgusConfig:
    return ArgusConfig.resolve(
        fleet_url=url,
        fleet_group="asia",
        fleet_state_dir=str(tmp_path),
        fleet_scrape_target=scrape_target,
        environ={},
    )


def test_identity_uses_configured_id(tmp_path: Path) -> None:
    cfg = ArgusConfig.resolve(fleet_id="fixed-id", fleet_state_dir=str(tmp_path), environ={})
    assert FleetClient(cfg).identity == "fixed-id"


def test_identity_falls_back_to_cluster_id(tmp_path: Path) -> None:
    # No fleet_id: the identity is the cluster_id, so it matches the Prometheus
    # `cluster` label and both sources join the same cluster.
    cfg = ArgusConfig.resolve(cluster_id="asia-0", fleet_state_dir=str(tmp_path), environ={})
    assert FleetClient(cfg).identity == "asia-0"


def test_fleet_id_beats_cluster_id(tmp_path: Path) -> None:
    cfg = ArgusConfig.resolve(
        fleet_id="fixed-id", cluster_id="asia-0", fleet_state_dir=str(tmp_path), environ={}
    )
    assert FleetClient(cfg).identity == "fixed-id"


def test_identity_persists_uuid(tmp_path: Path) -> None:
    cfg = ArgusConfig.resolve(fleet_state_dir=str(tmp_path), environ={})
    first = FleetClient(cfg).identity
    # A fresh client over the same state dir reuses the persisted identity.
    assert FleetClient(cfg).identity == first
    assert (tmp_path / "argus-fleet-id").read_text(encoding="utf-8").strip() == first


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file mode")
def test_identity_file_is_owner_only(tmp_path: Path) -> None:
    FleetClient(ArgusConfig.resolve(fleet_state_dir=str(tmp_path), environ={}))
    assert stat.S_IMODE((tmp_path / "argus-fleet-id").stat().st_mode) == 0o600


async def test_register_and_heartbeat_round_trip(aiohttp_server: Any, tmp_path: Path) -> None:
    registry = Registry(tmp_path / "server-state.json")
    app = build_fleet_app(FleetConfig.resolve(environ={}), registry, PushSource())
    server = await aiohttp_server(app)
    url = str(server.make_url("")).rstrip("/")

    cfg = _member_config(url, tmp_path, scrape_target="10.0.0.5:9191")
    client = FleetClient(cfg, heartbeat_interval=0.01)
    await client.start(lambda: {"metrics": {}})
    # Registered immediately on start, advertising its scrape target.
    entries = registry.entries()
    assert len(entries) == 1
    assert entries[0].fleet == "asia"
    assert entries[0].scrape_target == "10.0.0.5:9191"
    # A heartbeat lands a snapshot within a couple of ticks.
    for _ in range(50):
        await asyncio.sleep(0.01)
        if registry.entries()[0].last_snapshot is not None:
            break
    assert registry.entries()[0].last_snapshot == {"metrics": {}}
    await client.aclose()


async def test_fail_open_on_broken_snapshot_provider(aiohttp_server: Any, tmp_path: Path) -> None:
    registry = Registry(tmp_path / "server-state.json")
    app = build_fleet_app(FleetConfig.resolve(environ={}), registry, PushSource())
    server = await aiohttp_server(app)
    url = str(server.make_url("")).rstrip("/")

    def boom() -> dict[str, Any]:
        raise ValueError("snapshot provider is broken")

    client = FleetClient(_member_config(url, tmp_path), heartbeat_interval=0.01)
    await client.start(boom)  # register still succeeds
    await asyncio.sleep(0.05)  # several heartbeat ticks with a raising provider
    # The bot is unaffected: registration landed and nothing propagated.
    assert len(registry.entries()) == 1
    await client.aclose()


async def test_fail_open_when_fleet_unreachable(tmp_path: Path) -> None:
    # Nothing is listening on this port; start + heartbeat must not raise.
    cfg = _member_config("http://127.0.0.1:1", tmp_path)
    client = FleetClient(cfg, heartbeat_interval=0.01)
    await client.start(lambda: {"metrics": {}})
    await asyncio.sleep(0.05)
    await client.aclose()  # no exception is the assertion
