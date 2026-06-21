"""Per-guild analytics via ClickHouse (the analytical path, [clickhouse] extra).

Per-guild/per-user questions are high cardinality and never go to Prometheus.
With enable_per_guild + clickhouse_dsn, Argus drains per-guild events to
ClickHouse (batched, non-blocking) and the dashboard's Analytics section serves
per-guild command counts and average durations. Install with:
pip install "argus-dpy[clickhouse]".

Do:
- Set dashboard_auth_token: the analytics API fails closed without it (the data
  is sensitive).
- Run ClickHouse on its own host with durable storage; one ClickHouse can serve a
  whole fleet (all bots write to it).
- Add a ClickHouse TTL on the events table so it stays bounded.

Don't:
- Expect per-guild figures in Prometheus - they are intentionally not there.
- Block the bot on ClickHouse: the sink is a bounded queue that drops-and-counts
  on overflow, so a ClickHouse outage never stalls the bot.

Env: DISCORD_TOKEN, ARGUS_CLICKHOUSE_DSN, ARGUS_DASHBOARD_AUTH_TOKEN (required for
the analytics API), ARGUS_ENABLE_PER_GUILD=true.
"""

from __future__ import annotations

import os

import discord
from discord.ext import commands

from argus import Argus

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

Argus(
    bot,
    enable_per_guild=True,
    clickhouse_dsn=os.environ.get("ARGUS_CLICKHOUSE_DSN", "http://localhost:8123"),
    # dashboard_auth_token is read from ARGUS_DASHBOARD_AUTH_TOKEN; the analytics
    # API returns 403 without it.
)


if __name__ == "__main__":
    bot.run(os.environ["DISCORD_TOKEN"])
