"""Hook wiring, counter movement, fail-open behaviour."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

from argus.core import hooks
from tests.conftest import Env

_LISTENER_NAMES = {
    "on_interaction",
    "on_app_command_completion",
    "on_command_completion",
    "on_command_error",
    "on_socket_event_type",
    "on_shard_connect",
    "on_shard_resumed",
    "on_shard_disconnect",
}

C = "default"  # the cluster label every counter carries


def _interaction(itype: str = "application_command", *, command: Any = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=12345,
        type=SimpleNamespace(name=itype),
        command=command,
        created_at=datetime.now(timezone.utc) - timedelta(milliseconds=20),
    )


# --- registration / teardown ---


def test_register_attaches_listeners_chains_tree_and_log_handler(env: Env) -> None:
    discord_logger = logging.getLogger("discord")
    original_handlers = list(discord_logger.handlers)

    reg = hooks.register(env.bot, env.instr)
    chained = env.bot.tree.on_error

    assert set(env.bot.listeners) == _LISTENER_NAMES
    assert all(len(v) == 1 for v in env.bot.listeners.values())
    assert reg.log_handler in discord_logger.handlers

    reg.remove()
    assert env.bot.listeners == {k: [] for k in _LISTENER_NAMES}
    assert discord_logger.handlers == original_handlers
    assert env.bot.tree.on_error is not chained  # chained handler removed
    reg.remove()  # idempotent, must not raise


# --- counter movement ---


async def test_on_interaction_counts_received(env: Env) -> None:
    await env.instr.on_interaction(_interaction("modal_submit"))
    assert (
        env.backend.count(
            env.names.interactions_total, type="modal_submit", status="received", cluster=C
        )
        == 1
    )


async def test_app_command_completion_success_and_duration(env: Env) -> None:
    command = SimpleNamespace(qualified_name="ping")
    await env.instr.on_app_command_completion(_interaction(command=command), command)
    assert (
        env.backend.count(env.names.app_commands_total, command="ping", status="success", cluster=C)
        == 1
    )
    observed = env.backend.observations[env.names.app_command_duration_seconds]
    assert len(observed) == 1 and observed[0] >= 0


async def test_app_command_error_counts_error_and_error_type(env: Env) -> None:
    interaction = _interaction(command=SimpleNamespace(qualified_name="ping"))
    env.instr.app_command_error(interaction, ValueError("bad"))
    assert (
        env.backend.count(env.names.app_commands_total, command="ping", status="error", cluster=C)
        == 1
    )
    assert (
        env.backend.count(
            env.names.command_errors_total, command="ping", error_type="ValueError", cluster=C
        )
        == 1
    )


async def test_prefix_command_completion_and_error(env: Env) -> None:
    ctx = SimpleNamespace(command=SimpleNamespace(qualified_name="sync"))
    await env.instr.on_command_completion(ctx)
    await env.instr.on_command_error(ctx, KeyError("x"))
    assert (
        env.backend.count(env.names.commands_total, command="sync", status="success", cluster=C)
        == 1
    )
    assert (
        env.backend.count(env.names.commands_total, command="sync", status="error", cluster=C) == 1
    )
    assert (
        env.backend.count(
            env.names.command_errors_total, command="sync", error_type="KeyError", cluster=C
        )
        == 1
    )


async def test_gateway_and_shard_events(env: Env) -> None:
    await env.instr.on_socket_event_type("MESSAGE_CREATE")
    await env.instr.on_shard_connect(3)
    await env.instr.on_shard_resumed(3)
    await env.instr.on_shard_disconnect(3)
    assert env.backend.count(env.names.gateway_events_total, event="MESSAGE_CREATE", cluster=C) == 1
    assert env.backend.count(env.names.shard_reconnects_total, shard="3", cluster=C) == 2
    assert env.backend.count(env.names.shard_disconnects_total, shard="3", cluster=C) == 1


# --- fail-open (invariant 5) ---


async def test_hook_failure_is_counted_and_swallowed(env: Env) -> None:
    class Boom:
        @property
        def type(self) -> Any:
            raise RuntimeError("boom")

    await env.instr.on_interaction(Boom())  # must not raise
    assert (
        env.backend.count(env.names.instrumentation_errors_total, hook="on_interaction", cluster=C)
        == 1
    )


# --- chained tree handler still runs the original ---


async def test_chained_tree_on_error_runs_original(env: Env) -> None:
    reg = hooks.register(env.bot, env.instr)
    try:
        interaction = _interaction(command=SimpleNamespace(qualified_name="ping"))
        error = RuntimeError("kaboom")
        await env.bot.tree.on_error(interaction, error)
        assert env.bot.tree.errors == [(interaction, error)]  # original ran
        assert (
            env.backend.count(
                env.names.app_commands_total, command="ping", status="error", cluster=C
            )
            == 1
        )
    finally:
        reg.remove()


# --- log handler -> ratelimit counter ---


def test_log_handler_counts_records_and_ratelimits(env: Env) -> None:
    reg = hooks.register(env.bot, env.instr)
    try:
        logging.getLogger("discord.http").warning("We are being rate limited. Retrying in 1.0s")
        assert (
            env.backend.count(
                env.names.log_records_total, logger="discord.http", level="WARNING", cluster=C
            )
            == 1
        )
        assert env.backend.count(env.names.ratelimits_total, cluster=C) == 1
    finally:
        reg.remove()
