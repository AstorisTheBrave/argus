"""Argus(bot) wiring + cog lifecycle (D7 gate)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import aiohttp
from prometheus_client import generate_latest

from argus import Argus, ArgusCog
from argus.config import ArgusConfig
from argus.fleet.config import FleetConfig
from argus.fleet.registry import Registry
from argus.fleet.server import build_fleet_app
from argus.fleet.sources.push import PushSource
from tests.conftest import FakeBot

_LISTENER_NAMES = {
    "on_interaction",
    "on_app_command_completion",
    "on_command",
    "on_command_completion",
    "on_command_error",
    "on_socket_event_type",
    "on_shard_connect",
    "on_shard_resumed",
    "on_shard_disconnect",
}


def test_argus_registers_listeners_synchronously_and_chains_setup_hook() -> None:
    bot = FakeBot()
    original = bot.setup_hook
    argus = Argus(bot, host="127.0.0.1", port=9876)
    assert set(bot.listeners) == _LISTENER_NAMES
    assert bot.setup_hook is not original  # chained
    assert isinstance(argus.cog, ArgusCog)
    assert bot.cogs == []  # not added until the loop runs


async def test_argus_one_line_serves_then_cleans_up(free_port: int) -> None:
    bot = FakeBot()
    argus = Argus(bot, host="127.0.0.1", port=free_port)

    await bot.setup_hook()  # simulate discord lifecycle: add_cog -> cog_load -> server
    assert bot.cogs == [argus.cog]

    url = f"http://127.0.0.1:{free_port}"
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{url}/metrics") as resp:
            assert resp.status == 200
            assert "discord_guilds" in await resp.text()
        async with session.get(f"{url}/healthz") as resp:
            assert resp.status == 200

    await argus.cog.cog_unload()
    assert bot.listeners == {name: [] for name in _LISTENER_NAMES}


async def test_cog_can_be_added_directly(free_port: int) -> None:
    bot = FakeBot()
    cog = ArgusCog(bot, ArgusConfig.resolve(host="127.0.0.1", port=free_port, environ={}))
    assert set(bot.listeners) == _LISTENER_NAMES  # registered at construction
    await cog.cog_load()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://127.0.0.1:{free_port}/metrics") as resp:
                assert resp.status == 200
    finally:
        await cog.cog_unload()


async def test_dashboard_served_by_default(free_port: int) -> None:
    bot = FakeBot()
    cog = ArgusCog(bot, ArgusConfig.resolve(host="127.0.0.1", port=free_port, environ={}))
    await cog.cog_load()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://127.0.0.1:{free_port}/") as resp:
                assert resp.status == 200
            async with session.get(f"http://127.0.0.1:{free_port}/api/config") as resp:
                assert resp.status == 200
                assert (await resp.json())["namespace"] == "discord"
            async with session.get(f"http://127.0.0.1:{free_port}/metrics") as resp:
                assert resp.status == 200
    finally:
        await cog.cog_unload()


async def test_cog_registers_with_fleet_when_configured(
    aiohttp_server: Any, free_port: int, tmp_path: Path
) -> None:
    fleet_registry = Registry(tmp_path / "fleet-state.json")
    fleet = await aiohttp_server(
        build_fleet_app(FleetConfig.resolve(environ={}), fleet_registry, PushSource())
    )
    fleet_url = str(fleet.make_url("")).rstrip("/")

    cog = ArgusCog(
        FakeBot(),
        ArgusConfig.resolve(
            host="127.0.0.1",
            port=free_port,
            dashboard=False,
            fleet_url=fleet_url,
            fleet_group="asia",
            fleet_state_dir=str(tmp_path),
            environ={},
        ),
    )
    await cog.cog_load()
    try:
        # The opt-in client registered the process into the fleet on load.
        entries = fleet_registry.entries()
        assert len(entries) == 1
        assert entries[0].fleet == "asia"
    finally:
        await cog.cog_unload()
        assert cog._fleet_client is None


async def test_cog_load_is_fail_open_when_server_cannot_bind(
    free_port: int, monkeypatch: Any
) -> None:
    # A metrics server that cannot start must never crash the bot (invariant 5).
    import argus.exposition.server as exposition

    async def boom(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("address already in use")

    monkeypatch.setattr(exposition, "start_server", boom)

    bot = FakeBot()
    cog = ArgusCog(bot, ArgusConfig.resolve(host="127.0.0.1", port=free_port, environ={}))
    await cog.cog_load()  # must not raise

    assert cog.health.server_up is False
    assert cog._runner is None
    text = generate_latest(cog.adapter.registry).decode()
    assert 'hook="cog_load"' in text  # the failure was counted
    assert 'argus_subsystem_up{subsystem="server"} 0.0' in text
    await cog.cog_unload()


async def test_cog_load_marks_server_healthy(free_port: int) -> None:
    cog = ArgusCog(FakeBot(), ArgusConfig.resolve(host="127.0.0.1", port=free_port, environ={}))
    await cog.cog_load()
    try:
        assert cog.health.server_up is True
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://127.0.0.1:{free_port}/metrics") as resp:
                assert 'argus_subsystem_up{subsystem="server"} 1.0' in await resp.text()
    finally:
        await cog.cog_unload()
        assert cog.health.server_up is False


async def test_dashboard_can_be_disabled(free_port: int) -> None:
    bot = FakeBot()
    cog = ArgusCog(
        bot, ArgusConfig.resolve(host="127.0.0.1", port=free_port, dashboard=False, environ={})
    )
    await cog.cog_load()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://127.0.0.1:{free_port}/") as resp:
                assert resp.status == 404
            async with session.get(f"http://127.0.0.1:{free_port}/metrics") as resp:
                assert resp.status == 200
    finally:
        await cog.cog_unload()
