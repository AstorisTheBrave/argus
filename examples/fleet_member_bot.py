"""A bot that opts into an Argus Fleet control plane.

This is a normal Argus bot plus five env vars that make it report to a fleet
control plane (a separate process; see `python -m argus.fleet`). When the fleet
vars are unset the bot behaves exactly like the basic example: nothing fleet
related runs. The control plane assigns this process a stable per-region number
and shows it on the Global/Fleet/Cluster dashboard.

Run the control plane first (on its own host):

    ARGUS_FLEET_TOKEN=secret python -m argus.fleet

Then run one or more members pointing at it:

    DISCORD_TOKEN=...                       \
    ARGUS_FLEET_URL=http://fleet-host:9190  \
    ARGUS_FLEET_TOKEN=secret                \
    ARGUS_FLEET_GROUP=asia                  \
    CLUSTER_ID=asia-0                       \
        python examples/fleet_member_bot.py

`ARGUS_FLEET_GROUP` is the region (the Fleet tier). `CLUSTER_ID` becomes the
Prometheus `cluster` label and, for the push data source, the identity the fleet
joins on. Give each process a distinct one.
"""

from __future__ import annotations

import os

import discord
from discord.ext import commands

from argus import Argus

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Every fleet field also reads from its ARGUS_FLEET_* env var, so this single
# line works whether you configure via kwargs or the environment.
Argus(
    bot,
    cluster_id=os.environ.get("CLUSTER_ID", "node-0"),
    fleet_url=os.environ.get("ARGUS_FLEET_URL"),
    fleet_token=os.environ.get("ARGUS_FLEET_TOKEN"),
    fleet_group=os.environ.get("ARGUS_FLEET_GROUP", "default"),
)


@bot.event
async def on_ready() -> None:
    fleet = os.environ.get("ARGUS_FLEET_URL", "(fleet disabled)")
    print(f"{bot.user} ready; reporting to {fleet}")


if __name__ == "__main__":
    bot.run(os.environ["DISCORD_TOKEN"])
