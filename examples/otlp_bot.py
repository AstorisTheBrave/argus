"""Export Argus metrics to an OpenTelemetry collector (the [otlp] extra).

OTLP is additive: /metrics and the dashboard keep working; this just pushes the
same metrics to a collector, which forwards them to Datadog, Grafana Cloud,
Honeycomb, etc. Install with: pip install "argus-dpy[otlp]".

Do:
- Point at the collector's gRPC endpoint (usually :4317); route to vendors in the
  collector, not the bot, so credentials live in one place.
- Keep cluster_id/namespace consistent with your Prometheus setup so series line
  up across both paths.

Don't:
- Try to read OTLP data back into Argus - it is a one-way export; view it in the
  backend you pushed to.
- Use https:// unless the collector terminates TLS.

Env: DISCORD_TOKEN (required), ARGUS_OTLP_ENDPOINT (e.g. http://localhost:4317).
"""

from __future__ import annotations

import os

import discord
from discord.ext import commands

from argus import Argus

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

Argus(
    bot,
    otlp_endpoint=os.environ.get("ARGUS_OTLP_ENDPOINT", "http://localhost:4317"),
)


if __name__ == "__main__":
    bot.run(os.environ["DISCORD_TOKEN"])
