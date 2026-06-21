"""Clustered Argus: one process per shard range, one /metrics per process.

Two separate rules, often confused:
- CLUSTER_ID is ALWAYS distinct per process (it is the `cluster` label).
- The PORT only needs to differ when processes share a host. This example runs
  both on ONE host, so they use 9191 and 9192. On SEPARATE hosts/containers/pods
  each has its own IP, so leave them both at the default 9191 (no collision) and
  Prometheus scrapes host-a:9191, host-b:9191, ...

Co-located example (one host -> distinct ports):

    DISCORD_TOKEN=... CLUSTER_ID=0 ARGUS_PORT=9191 SHARD_IDS=0,1 SHARD_COUNT=4 \
        python examples/clustered_bot.py
    DISCORD_TOKEN=... CLUSTER_ID=1 ARGUS_PORT=9192 SHARD_IDS=2,3 SHARD_COUNT=4 \
        python examples/clustered_bot.py

Point prometheus.yml at every process. Each process' gauges carry its distinct
`cluster` label, so the dashboards' $cluster variable separates them while
counter rates aggregate across the fleet at query time.
"""

from __future__ import annotations

import os

import discord
from discord.ext import commands

from argus import Argus

shard_ids = [int(s) for s in os.environ.get("SHARD_IDS", "0").split(",")]
shard_count = int(os.environ.get("SHARD_COUNT", "1"))
cluster_id = os.environ.get("CLUSTER_ID", "0")
port = int(os.environ.get("ARGUS_PORT", "9191"))

intents = discord.Intents.default()
intents.members = True

bot = commands.AutoShardedBot(
    command_prefix="!",
    intents=intents,
    shard_ids=shard_ids,
    shard_count=shard_count,
)

Argus(bot, cluster_id=cluster_id, port=port)


@bot.event
async def on_ready() -> None:
    print(f"cluster {cluster_id}: shards {shard_ids} — metrics on :{port}")


if __name__ == "__main__":
    bot.run(os.environ["DISCORD_TOKEN"])
