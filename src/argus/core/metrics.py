# Argus — discord.py observability SDK
# Copyright (C) 2026 AstorisTheBrave
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""The metric catalogue.

``define_metrics`` populates a :class:`MetricRegistry` and returns the resolved,
namespaced metric names so hooks never hard-code strings. Gauge callbacks read
live bot state at scrape time (invariant 4), are O(1) (no per-guild iteration),
and are NaN-guarded. Every counter and the duration histogram carry a bounded
``cluster`` label so the same series aggregate cleanly across a clustered
deploy. No metric here carries a ``guild_id``/``user_id``/``channel_id`` label
(invariant 2); per-guild figures live in the analytical path instead.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from argus import __version__
from argus.core.collector import GaugeSample, MetricDef, MetricKind, MetricRegistry

if TYPE_CHECKING:
    from argus.config import ArgusConfig
    from argus.core.health import HealthState

# Duration buckets suited to Discord command flows: deferral, follow-ups, slow
# handlers. +Inf is appended by the backend.
DURATION_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

# Labels that must never appear on an operational metric (invariant 2).
FORBIDDEN_LABELS = frozenset({"guild_id", "user_id", "channel_id"})


@dataclass(frozen=True, slots=True)
class MetricNames:
    """Resolved metric names, so hooks reference fields rather than strings."""

    # scrape-time gauges
    shard_latency_seconds: str
    shard_up: str
    shards_connected: str
    shards_configured: str
    guilds: str
    cached_users: str
    voice_clients: str
    emojis: str
    stickers: str
    private_channels: str
    app_commands_registered: str
    uptime_seconds: str
    bot_info: str
    argus_up: str
    argus_subsystem_up: str
    # event-driven counters
    interactions_total: str
    app_commands_total: str
    commands_total: str
    command_errors_total: str
    gateway_events_total: str
    shard_disconnects_total: str
    shard_reconnects_total: str
    log_records_total: str
    ratelimits_total: str
    instrumentation_errors_total: str
    history_events_dropped_total: str
    # histograms
    app_command_duration_seconds: str
    command_duration_seconds: str


def build_names(namespace: str) -> MetricNames:
    """Build namespaced names. ``argus_*`` internals are never namespaced."""
    ns = namespace
    return MetricNames(
        shard_latency_seconds=f"{ns}_shard_latency_seconds",
        shard_up=f"{ns}_shard_up",
        shards_connected=f"{ns}_shards_connected",
        shards_configured=f"{ns}_shards_configured",
        guilds=f"{ns}_guilds",
        cached_users=f"{ns}_cached_users",
        voice_clients=f"{ns}_voice_clients",
        emojis=f"{ns}_emojis",
        stickers=f"{ns}_stickers",
        private_channels=f"{ns}_private_channels",
        app_commands_registered=f"{ns}_app_commands_registered",
        uptime_seconds=f"{ns}_uptime_seconds",
        bot_info=f"{ns}_bot",  # backend appends `_info` -> discord_bot_info
        argus_up="argus_up",
        argus_subsystem_up="argus_subsystem_up",
        interactions_total=f"{ns}_interactions_total",
        app_commands_total=f"{ns}_app_commands_total",
        commands_total=f"{ns}_commands_total",
        command_errors_total=f"{ns}_command_errors_total",
        gateway_events_total=f"{ns}_gateway_events_total",
        shard_disconnects_total=f"{ns}_shard_disconnects_total",
        shard_reconnects_total=f"{ns}_shard_reconnects_total",
        log_records_total=f"{ns}_log_records_total",
        ratelimits_total=f"{ns}_ratelimits_total",
        instrumentation_errors_total="argus_instrumentation_errors_total",
        history_events_dropped_total="argus_history_events_dropped_total",
        app_command_duration_seconds=f"{ns}_app_command_duration_seconds",
        command_duration_seconds=f"{ns}_command_duration_seconds",
    )


def _count(obj: Any, attr: str) -> float:
    """len() of a cached collection attribute, O(1), defensively guarded."""
    return float(len(getattr(obj, attr, []) or []))


def define_metrics(
    registry: MetricRegistry,
    bot: Any,
    config: ArgusConfig,
    health: HealthState | None = None,
) -> MetricNames:
    """Define every metric into ``registry``; return the resolved names.

    When ``health`` is provided, the ``argus_subsystem_up`` gauge is defined and
    reads it live at scrape time, so operators can alert on Argus' own subsystems
    degrading independently of the bot.
    """
    names = build_names(config.namespace)
    cluster = config.cluster_id or "default"
    started = time.monotonic()

    # --- scrape-time gauges (invariant 4); all O(1) reads off the cache ---
    def shard_latency() -> list[GaugeSample]:
        out: list[GaugeSample] = []
        for shard_id, latency in getattr(bot, "latencies", []):
            value = float(latency)
            if not math.isnan(value):  # latency is NaN before a shard is ready
                out.append(GaugeSample((str(shard_id),), value))
        return out

    def shard_up() -> list[GaugeSample]:
        shards = getattr(bot, "shards", None) or {}
        return [
            GaugeSample((str(sid),), 0.0 if s.is_closed() else 1.0) for sid, s in shards.items()
        ]

    def shards_connected() -> list[GaugeSample]:
        shards = getattr(bot, "shards", None)
        if shards:
            count = sum(1 for s in shards.values() if not s.is_closed())
        else:
            count = 0 if getattr(bot, "is_closed", lambda: True)() else 1
        return [GaugeSample((cluster,), float(count))]

    def shards_configured() -> list[GaugeSample]:
        return [GaugeSample((cluster,), float(getattr(bot, "shard_count", None) or 1))]

    def app_commands_registered() -> list[GaugeSample]:
        tree = getattr(bot, "tree", None)
        getter = getattr(tree, "get_commands", None)
        count = len(getter()) if callable(getter) else 0
        return [GaugeSample((cluster,), float(count))]

    def uptime() -> list[GaugeSample]:
        return [GaugeSample((cluster,), time.monotonic() - started)]

    def cluster_gauge(attr: str) -> Any:
        def cb() -> list[GaugeSample]:
            return [GaugeSample((cluster,), _count(bot, attr))]

        return cb

    registry.define(
        MetricDef(
            names.shard_latency_seconds,
            "Per-shard heartbeat latency in seconds.",
            MetricKind.GAUGE,
            labelnames=("shard",),
            callback=shard_latency,
        )
    )
    registry.define(
        MetricDef(
            names.shard_up,
            "1 if the shard's gateway connection is open, else 0.",
            MetricKind.GAUGE,
            labelnames=("shard",),
            callback=shard_up,
        )
    )
    registry.define(
        MetricDef(
            names.shards_connected,
            "Number of shards whose gateway connection is open.",
            MetricKind.GAUGE,
            labelnames=("cluster",),
            callback=shards_connected,
        )
    )
    registry.define(
        MetricDef(
            names.shards_configured,
            "Number of shards this process is configured to run.",
            MetricKind.GAUGE,
            labelnames=("cluster",),
            callback=shards_configured,
        )
    )
    registry.define(
        MetricDef(
            names.guilds,
            "Number of guilds the bot is in.",
            MetricKind.GAUGE,
            labelnames=("cluster",),
            callback=cluster_gauge("guilds"),
        )
    )
    registry.define(
        MetricDef(
            names.cached_users,
            "Number of users in the cache (requires the members intent to be meaningful).",
            MetricKind.GAUGE,
            labelnames=("cluster",),
            callback=cluster_gauge("users"),
        )
    )
    registry.define(
        MetricDef(
            names.voice_clients,
            "Number of active voice clients.",
            MetricKind.GAUGE,
            labelnames=("cluster",),
            callback=cluster_gauge("voice_clients"),
        )
    )
    registry.define(
        MetricDef(
            names.emojis,
            "Number of cached custom emojis.",
            MetricKind.GAUGE,
            labelnames=("cluster",),
            callback=cluster_gauge("emojis"),
        )
    )
    registry.define(
        MetricDef(
            names.stickers,
            "Number of cached stickers.",
            MetricKind.GAUGE,
            labelnames=("cluster",),
            callback=cluster_gauge("stickers"),
        )
    )
    registry.define(
        MetricDef(
            names.private_channels,
            "Number of cached private channels.",
            MetricKind.GAUGE,
            labelnames=("cluster",),
            callback=cluster_gauge("private_channels"),
        )
    )
    registry.define(
        MetricDef(
            names.app_commands_registered,
            "Number of application commands registered on the tree.",
            MetricKind.GAUGE,
            labelnames=("cluster",),
            callback=app_commands_registered,
        )
    )
    registry.define(
        MetricDef(
            names.uptime_seconds,
            "Seconds since the Argus collector started.",
            MetricKind.GAUGE,
            labelnames=("cluster",),
            callback=uptime,
        )
    )
    registry.define(
        MetricDef(
            names.argus_up,
            "1 while the Argus collector is alive.",
            MetricKind.GAUGE,
            callback=lambda: [GaugeSample((), 1.0)],
        )
    )
    if health is not None:

        def subsystem_up() -> list[GaugeSample]:
            out = [GaugeSample(("server",), 1.0 if health.server_up else 0.0)]
            if health.fleet_enabled:
                out.append(GaugeSample(("fleet",), 1.0 if health.fleet_up else 0.0))
            if health.sink_enabled:
                out.append(GaugeSample(("sink",), 1.0 if health.sink_up else 0.0))
            return out

        registry.define(
            MetricDef(
                names.argus_subsystem_up,
                "1 if the named Argus subsystem is healthy, else 0 "
                "(only configured subsystems are reported).",
                MetricKind.GAUGE,
                labelnames=("subsystem",),
                callback=subsystem_up,
            )
        )
    registry.define(
        MetricDef(
            names.bot_info,
            "Bot and library version info.",
            MetricKind.INFO,
        )
    )

    # --- event-driven counters (invariant 3); cluster label on every one ---
    registry.define(
        MetricDef(
            names.interactions_total,
            "Total interactions received.",
            MetricKind.COUNTER,
            labelnames=("type", "status", "cluster"),
        )
    )
    registry.define(
        MetricDef(
            names.app_commands_total,
            "Total application command invocations by outcome.",
            MetricKind.COUNTER,
            labelnames=("command", "status", "cluster"),
        )
    )
    registry.define(
        MetricDef(
            names.commands_total,
            "Total prefix command invocations by outcome.",
            MetricKind.COUNTER,
            labelnames=("command", "status", "cluster"),
        )
    )
    registry.define(
        MetricDef(
            names.command_errors_total,
            "Total command errors by error type.",
            MetricKind.COUNTER,
            labelnames=("command", "error_type", "cluster"),
        )
    )
    registry.define(
        MetricDef(
            names.gateway_events_total,
            "Total gateway dispatch events by type.",
            MetricKind.COUNTER,
            labelnames=("event", "cluster"),
        )
    )
    registry.define(
        MetricDef(
            names.shard_disconnects_total,
            "Total shard disconnects.",
            MetricKind.COUNTER,
            labelnames=("shard", "cluster"),
        )
    )
    registry.define(
        MetricDef(
            names.shard_reconnects_total,
            "Total shard connects/resumes.",
            MetricKind.COUNTER,
            labelnames=("shard", "cluster"),
        )
    )
    registry.define(
        MetricDef(
            names.log_records_total,
            "Total discord log records by logger and level.",
            MetricKind.COUNTER,
            labelnames=("logger", "level", "cluster"),
        )
    )
    registry.define(
        MetricDef(
            names.ratelimits_total,
            "Total rate-limit warnings observed on the discord.http logger.",
            MetricKind.COUNTER,
            labelnames=("cluster",),
        )
    )
    registry.define(
        MetricDef(
            names.instrumentation_errors_total,
            "Total instrumentation hook failures (swallowed, never raised).",
            MetricKind.COUNTER,
            labelnames=("hook", "cluster"),
        )
    )
    registry.define(
        MetricDef(
            names.history_events_dropped_total,
            "Total per-guild analytical events dropped because the sink queue was full.",
            MetricKind.COUNTER,
            labelnames=("cluster",),
        )
    )

    # --- histograms ---
    registry.define(
        MetricDef(
            names.app_command_duration_seconds,
            "Application command duration in seconds (interaction receipt to completion).",
            MetricKind.HISTOGRAM,
            labelnames=("command", "cluster"),
            buckets=DURATION_BUCKETS,
        )
    )
    registry.define(
        MetricDef(
            names.command_duration_seconds,
            "Prefix command duration in seconds (invocation to completion).",
            MetricKind.HISTOGRAM,
            labelnames=("command", "cluster"),
            buckets=DURATION_BUCKETS,
        )
    )

    return names


def bot_info_values() -> dict[str, str]:
    """Static values for the ``discord_bot_info`` metric."""
    import discord

    return {"discord_py_version": discord.__version__, "argus_version": __version__}
