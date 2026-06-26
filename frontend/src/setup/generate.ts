// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 AstorisTheBrave

// Pure config-artifact generation for the no-code setup wizard. No DOM, no
// network: every output is derived deterministically from the user's choices so
// it is trivially unit-testable and so a bot token entered in the browser is
// only ever written into the .env the user downloads -- never sent anywhere.

export type HostTarget = "docker" | "railway" | "pterodactyl" | "local";

export interface SetupChoices {
  /** Discord bot token. Optional: left blank, the .env carries a placeholder. */
  token: string;
  /** Metric name prefix (and a friendly label for the bot). */
  namespace: string;
  /** Serve the live dashboard + /metrics on a port. */
  dashboard: boolean;
  /** Password gating the dashboard; blank = open (only safe on a private host). */
  dashboardPassword: string;
  /** Per-guild analytics (needs a ClickHouse database). */
  analytics: boolean;
  clickhouseDsn: string;
  /** Export a span per command to an OpenTelemetry collector. */
  tracing: boolean;
  tracingEndpoint: string;
  host: HostTarget;
}

export interface GeneratedFile {
  name: string;
  /** Hint for display / copy button labelling, not used for execution. */
  language: string;
  content: string;
}

export interface SetupOutput {
  files: GeneratedFile[];
  steps: string[];
}

export const defaultChoices: SetupChoices = {
  token: "",
  namespace: "discord",
  dashboard: true,
  dashboardPassword: "",
  analytics: false,
  clickhouseDsn: "",
  tracing: false,
  tracingEndpoint: "",
  host: "docker",
};

const DASHBOARD_PORT = 9191;
const TOKEN_PLACEHOLDER = "paste-your-discord-bot-token-here";

// A Prometheus metric prefix must be a bare identifier; sanitise whatever the
// user typed so the generated config can never produce invalid metric names.
export function sanitizeNamespace(raw: string): string {
  const cleaned = raw
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return cleaned || "discord";
}

// The pip requirement, with only the extras the chosen features actually need.
// [dotenv] is always included so Argus(bot) loads the generated .env itself.
function requirement(choices: SetupChoices): string {
  const extras = ["dotenv"];
  if (choices.analytics) extras.push("clickhouse");
  if (choices.tracing) extras.push("otlp");
  return `argus-dpy[${extras.join(",")}]`;
}

function envFile(choices: SetupChoices): GeneratedFile {
  const ns = sanitizeNamespace(choices.namespace);
  const lines: string[] = [
    "# Argus configuration. Keep this file secret and never commit it.",
    "# The token below stays on your machine -- it was never uploaded anywhere.",
    `DISCORD_TOKEN=${choices.token || TOKEN_PLACEHOLDER}`,
  ];
  if (ns !== "discord") lines.push(`ARGUS_NAMESPACE=${ns}`);
  if (!choices.dashboard) {
    lines.push("ARGUS_DASHBOARD=0");
  } else if (choices.dashboardPassword) {
    lines.push(`ARGUS_DASHBOARD_AUTH_TOKEN=${choices.dashboardPassword}`);
  }
  if (choices.analytics) {
    lines.push("ARGUS_ENABLE_PER_GUILD=1");
    lines.push(`ARGUS_CLICKHOUSE_DSN=${choices.clickhouseDsn || "clickhouse://user:pass@host:8123/db"}`);
  }
  if (choices.tracing) {
    lines.push("ARGUS_ENABLE_TRACING=1");
    lines.push(`ARGUS_TRACING_ENDPOINT=${choices.tracingEndpoint || "http://your-collector:4317"}`);
  }
  return { name: ".env", language: "ini", content: lines.join("\n") + "\n" };
}

function botFile(): GeneratedFile {
  // Mirrors examples/basic_bot.py. Argus(bot) bootstraps the .env (the [dotenv]
  // extra) before bot.run, so DISCORD_TOKEN is populated by the time we read it.
  const content = `"""Your Discord bot, with Argus observability. Run: python bot.py"""

import os

import discord
from discord.ext import commands

from argus import Argus

intents = discord.Intents.default()
intents.members = True  # makes the cached-users metric meaningful

bot = commands.AutoShardedBot(command_prefix="!", intents=intents)

Argus(bot)  # the whole integration; reads your .env automatically


@bot.event
async def on_ready() -> None:
    print(f"logged in as {bot.user}")


if __name__ == "__main__":
    bot.run(os.environ["DISCORD_TOKEN"])
`;
  return { name: "bot.py", language: "python", content };
}

function requirementsFile(choices: SetupChoices): GeneratedFile {
  return { name: "requirements.txt", language: "text", content: requirement(choices) + "\n" };
}

function dockerfile(): GeneratedFile {
  const content = `FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py .
CMD ["python", "bot.py"]
`;
  return { name: "Dockerfile", language: "dockerfile", content };
}

function composeFile(choices: SetupChoices): GeneratedFile {
  const ports = choices.dashboard
    ? `\n    ports:\n      - "${DASHBOARD_PORT}:${DASHBOARD_PORT}"`
    : "";
  const content = `services:
  bot:
    build: .
    env_file: .env
    restart: unless-stopped${ports}
`;
  return { name: "docker-compose.yml", language: "yaml", content };
}

function railwayFile(): GeneratedFile {
  // Mirrors examples/hosting/railway.json. Nixpacks detects Python from
  // requirements.txt; Argus auto-detects Railway's $PORT.
  const content = `{
  "$schema": "https://railway.com/railway.schema.json",
  "build": { "builder": "NIXPACKS" },
  "deploy": {
    "startCommand": "python bot.py",
    "restartPolicyType": "ALWAYS",
    "numReplicas": 1
  }
}
`;
  return { name: "railway.json", language: "json", content };
}

function stepsFor(choices: SetupChoices): string[] {
  const fillToken = choices.token
    ? "Your token is already filled into .env."
    : `Open .env and replace ${TOKEN_PLACEHOLDER} with your bot token from the Discord Developer Portal.`;
  switch (choices.host) {
    case "docker":
      return [
        "Install Docker Desktop (docker.com) if you do not have it.",
        "Put the downloaded files in one new folder.",
        fillToken,
        "Open a terminal in that folder and run: docker compose up -d",
        choices.dashboard
          ? `Open http://localhost:${DASHBOARD_PORT}/ to see your dashboard.`
          : "Argus is now collecting metrics for your bot.",
      ];
    case "railway":
      return [
        "Create a project at railway.app and connect a new empty service.",
        "Upload bot.py, requirements.txt and railway.json to the repo Railway deploys.",
        "In the Railway Variables tab, add the values from .env (DISCORD_TOKEN, ARGUS_*).",
        fillToken,
        "Deploy. Railway runs python bot.py and assigns a public URL automatically.",
      ];
    case "pterodactyl":
      return [
        "In your panel, create a server using a generic Python egg (or import the Argus egg from the project's examples/hosting/pterodactyl-egg.json).",
        "Upload bot.py and requirements.txt to the server's files.",
        "Upload .env to the same folder (the [dotenv] extra makes Argus load it).",
        fillToken,
        "Set the start command to: python bot.py, then start the server.",
      ];
    case "local":
      return [
        "Install Python 3.10+ from python.org.",
        "Put the downloaded files in one folder and open a terminal there.",
        "Run: pip install -r requirements.txt",
        fillToken,
        "Run: python bot.py",
      ];
  }
}

export function generate(choices: SetupChoices): SetupOutput {
  const files: GeneratedFile[] = [envFile(choices), botFile(), requirementsFile(choices)];
  switch (choices.host) {
    case "docker":
      files.push(dockerfile(), composeFile(choices));
      break;
    case "railway":
      files.push(railwayFile());
      break;
    case "pterodactyl":
    case "local":
      break;
  }
  return { files, steps: stepsFor(choices) };
}
