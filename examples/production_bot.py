"""A production-shaped single bot: hardened defaults and the common gotchas.

This is `Argus(bot)` plus the operational practices a real deployment wants. Run
it under a restart policy (systemd Restart=always, container restart:
unless-stopped, or a k8s Deployment) with a memory limit.

Do:
- Read the token from the environment (or a mounted secret), never hardcode it.
- Enable only the intents you use; `members` is needed for cached_users and costs
  memory (~600-800 MB at ~1k guilds).
- Set ARGUS_DASHBOARD_AUTH_TOKEN so the dashboard + /api/* require a token;
  /metrics stays scrapeable for Prometheus.
- Give the process a stable cluster_id once you run more than one.
- Switch to AutoShardedBot as you approach 2,500 guilds/shard.

Don't:
- Block the event loop (use `await asyncio.sleep`, never `time.sleep`).
- Add guild_id/user_id/channel_id anywhere near a Prometheus label.
- Expose the bot/dashboard publicly without a token and a TLS reverse proxy.

Env: DISCORD_TOKEN (required), ARGUS_DASHBOARD_AUTH_TOKEN, ARGUS_CLUSTER_ID,
ARGUS_PORT, GRAFANA_URL (all optional; Argus reads the ARGUS_* ones itself).
"""

from __future__ import annotations

import logging
import os

import discord
from discord.ext import commands

from argus import Argus

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

# Request only what you use. Enable members only if you need member/cache data
# (it is a privileged intent and the biggest memory cost).
intents = discord.Intents.default()
intents.members = True

# Use commands.Bot for a small/medium bot; switch to AutoShardedBot as you near
# 2,500 guilds/shard (Discord requires sharding past it).
bot = commands.Bot(command_prefix="!", intents=intents)

# One line. Token/auth/cluster come from the environment so nothing secret is in
# code; grafana_url just links the dashboard out to your boards if you have them.
Argus(
    bot,
    cluster_id=os.environ.get("ARGUS_CLUSTER_ID", "default"),
    grafana_url=os.environ.get("GRAFANA_URL") or None,
    # dashboard_auth_token is picked up from ARGUS_DASHBOARD_AUTH_TOKEN if set.
)


@bot.event
async def on_ready() -> None:
    logging.getLogger("bot").info("ready as %s (%d guilds)", bot.user, len(bot.guilds))


if __name__ == "__main__":
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("set DISCORD_TOKEN in the environment")
    bot.run(token)
