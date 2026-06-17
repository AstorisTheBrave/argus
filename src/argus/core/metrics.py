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

"""The metric catalogue (spec sec.8).

``define_metrics`` populates a :class:`MetricRegistry` and returns the resolved,
namespaced metric names so hooks never hard-code strings. Gauge callbacks read
live bot state at scrape time (invariant 4) and are NaN-guarded; no metric here
carries a ``guild_id``/``user_id``/``channel_id`` label (invariant 2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from argus import __version__
from argus.core.collector import GaugeSample, MetricDef, MetricKind, MetricRegistry

if TYPE_CHECKING:
    from argus.config import ArgusConfig

# Duration buckets suited to Discord command flows (grounding sec.2): deferral,
# follow-ups, slow handlers. +Inf is appended by the backend.
DURATION_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

# Labels that must never appear on an operational metric (invariant 2).
FORBIDDEN_LABELS = frozenset({"guild_id", "user_id", "channel_id"})


@dataclass(frozen=True, slots=True)
class MetricNames:
    """Resolved metric names, so hooks reference fields rather than strings."""

    # gauges
    shard_latency_seconds: str
    shards_connected: str
    shards_configured: str
    guilds: str
    cached_users: str
    bot_info: str
    argus_up: str
    # counters
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
    # histograms
    app_command_duration_seconds: str


def build_names(namespace: str) -> MetricNames:
    """Build namespaced names. ``argus_*`` internals are never namespaced."""
    ns = namespace
    return MetricNames(
        shard_latency_seconds=f"{ns}_shard_latency_seconds",
        shards_connected=f"{ns}_shards_connected",
        shards_configured=f"{ns}_shards_configured",
        guilds=f"{ns}_guilds",
        cached_users=f"{ns}_cached_users",
        bot_info=f"{ns}_bot",  # backend appends `_info` -> discord_bot_info
        argus_up="argus_up",
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
        app_command_duration_seconds=f"{ns}_app_command_duration_seconds",
    )


def define_metrics(registry: MetricRegistry, bot: Any, config: ArgusConfig) -> MetricNames:
    """Define every v1 metric into ``registry``; return the resolved names."""
    names = build_names(config.namespace)
    cluster = config.cluster_id or "default"

    # --- scrape-time gauges (invariant 4) ---
    def shard_latency() -> list[GaugeSample]:
        out: list[GaugeSample] = []
        for shard_id, latency in getattr(bot, "latencies", []):
            value = float(latency)
            if not math.isnan(value):  # latency is NaN before a shard is ready
                out.append(GaugeSample((str(shard_id),), value))
        return out

    def shards_connected() -> list[GaugeSample]:
        shards = getattr(bot, "shards", None)
        if shards:
            count = sum(1 for s in shards.values() if not s.is_closed())
        else:
            count = 0 if getattr(bot, "is_closed", lambda: True)() else 1
        return [GaugeSample((cluster,), float(count))]

    def shards_configured() -> list[GaugeSample]:
        return [GaugeSample((cluster,), float(getattr(bot, "shard_count", None) or 1))]

    def guilds() -> list[GaugeSample]:
        return [GaugeSample((cluster,), float(len(getattr(bot, "guilds", []))))]

    def cached_users() -> list[GaugeSample]:
        return [GaugeSample((cluster,), float(len(getattr(bot, "users", []))))]

    def up() -> list[GaugeSample]:
        return [GaugeSample((), 1.0)]

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
            callback=guilds,
        )
    )
    registry.define(
        MetricDef(
            names.cached_users,
            "Number of users in the cache (requires the members intent to be meaningful).",
            MetricKind.GAUGE,
            labelnames=("cluster",),
            callback=cached_users,
        )
    )
    registry.define(
        MetricDef(
            names.argus_up,
            "1 while the Argus collector is alive.",
            MetricKind.GAUGE,
            callback=up,
        )
    )
    registry.define(
        MetricDef(
            names.bot_info,
            "Bot and library version info.",
            MetricKind.INFO,
        )
    )

    # --- event-driven counters (invariant 3) ---
    registry.define(
        MetricDef(
            names.interactions_total,
            "Total interactions received.",
            MetricKind.COUNTER,
            labelnames=("type", "status"),
        )
    )
    registry.define(
        MetricDef(
            names.app_commands_total,
            "Total application command invocations by outcome.",
            MetricKind.COUNTER,
            labelnames=("command", "status"),
        )
    )
    registry.define(
        MetricDef(
            names.commands_total,
            "Total prefix command invocations by outcome.",
            MetricKind.COUNTER,
            labelnames=("command", "status"),
        )
    )
    registry.define(
        MetricDef(
            names.command_errors_total,
            "Total command errors by error type.",
            MetricKind.COUNTER,
            labelnames=("command", "error_type"),
        )
    )
    registry.define(
        MetricDef(
            names.gateway_events_total,
            "Total gateway dispatch events by type.",
            MetricKind.COUNTER,
            labelnames=("event",),
        )
    )
    registry.define(
        MetricDef(
            names.shard_disconnects_total,
            "Total shard disconnects.",
            MetricKind.COUNTER,
            labelnames=("shard",),
        )
    )
    registry.define(
        MetricDef(
            names.shard_reconnects_total,
            "Total shard connects/resumes.",
            MetricKind.COUNTER,
            labelnames=("shard",),
        )
    )
    registry.define(
        MetricDef(
            names.log_records_total,
            "Total discord log records by logger and level.",
            MetricKind.COUNTER,
            labelnames=("logger", "level"),
        )
    )
    registry.define(
        MetricDef(
            names.ratelimits_total,
            "Total rate-limit warnings observed on the discord.http logger.",
            MetricKind.COUNTER,
        )
    )
    registry.define(
        MetricDef(
            names.instrumentation_errors_total,
            "Total instrumentation hook failures (swallowed, never raised).",
            MetricKind.COUNTER,
            labelnames=("hook",),
        )
    )

    # --- histograms ---
    registry.define(
        MetricDef(
            names.app_command_duration_seconds,
            "Approximate application command duration in seconds.",
            MetricKind.HISTOGRAM,
            labelnames=("command",),
            buckets=DURATION_BUCKETS,
        )
    )

    return names


def bot_info_values() -> dict[str, str]:
    """Static values for the ``discord_bot_info`` metric."""
    import discord

    return {"discord_py_version": discord.__version__, "argus_version": __version__}
