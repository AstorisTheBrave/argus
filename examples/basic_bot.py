"""Minimal Argus integration: one bot, one line.

    DISCORD_TOKEN=... python examples/basic_bot.py

Metrics are then served at http://localhost:9191/metrics.
"""

from __future__ import annotations

import os

import discord
from discord.ext import commands

from argus import Argus

intents = discord.Intents.default()
intents.members = True  # makes discord_cached_users meaningful

bot = commands.AutoShardedBot(command_prefix="!", intents=intents)

Argus(bot)  # the whole integration; serves /metrics and the dashboard on :9191


@bot.event
async def on_ready() -> None:
    print(f"logged in as {bot.user}. dashboard on http://localhost:9191/")


if __name__ == "__main__":
    bot.run(os.environ["DISCORD_TOKEN"])
