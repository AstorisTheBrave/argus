"""Every Argus configuration option, shown as constructor kwargs.

Argus needs no configuration: `Argus(bot)` is enough. This file is a reference
for the full surface. Each kwarg here maps to one ARGUS_* environment variable
(see .env.example); kwargs win over the environment, which wins over defaults.

Nothing here is required. Pass only the options you care about.
"""

from __future__ import annotations

import discord
from discord.ext import commands

from argus import Argus
from argus.fleet.config import FleetConfig

intents = discord.Intents.default()
intents.members = True  # needed for cached_users to be meaningful
bot = commands.Bot(command_prefix="!", intents=intents)

# --- the per-bot SDK: all kwargs shown with their defaults -------------------
Argus(
    bot,
    # exposition server
    host="0.0.0.0",
    port=9191,
    metrics_path="/metrics",
    # identity / labelling
    cluster_id="default",  # becomes the bounded `cluster` Prometheus label
    namespace="discord",  # metric prefix, e.g. discord_guilds
    # built-in dashboard
    dashboard=True,
    dashboard_path="/",
    dashboard_interval=5,
    dashboard_auth_token=None,  # set to require a bearer token on the UI + APIs
    grafana_url=None,  # optional link-out shown in the dashboard
    # OpenTelemetry export (needs the [otlp] extra)
    otlp_endpoint=None,
    # per-guild analytics, the analytical path (needs the [clickhouse] extra)
    enable_per_guild=False,
    clickhouse_dsn=None,
    # opt into a Fleet control plane (member side); None disables all fleet code
    fleet_url=None,
    fleet_token=None,
    fleet_group="default",
    fleet_id=None,  # stable identity; auto-UUID persisted if unset
    fleet_state_dir=".",
)


# --- the Fleet control plane: resolved the same way (kwargs > env > default) --
# This is the server-side config, used by `python -m argus.fleet`. Shown here so
# the full surface lives in one place; you would normally set these via env.
fleet_config = FleetConfig.resolve(
    host="0.0.0.0",
    port=9190,
    token=None,  # shared secret; gates every route except /healthz
    heartbeat_interval=15,
    ttl_factor=3,  # down after interval * ttl_factor seconds of silence
    state_path="argus-fleet-state.json",
    prometheus_url=None,  # set to also read values from an existing Prometheus
    namespace="discord",  # must match the members' namespace
)


if __name__ == "__main__":
    print("Argus configured. Fleet defaults:", fleet_config)
    bot.run("YOUR_DISCORD_TOKEN")
