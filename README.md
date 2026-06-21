# argus-dpy

[![CI](https://github.com/AstorisTheBrave/argus/actions/workflows/ci.yml/badge.svg)](https://github.com/AstorisTheBrave/argus/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/argus-dpy)](https://pypi.org/project/argus-dpy/)
[![Python](https://img.shields.io/pypi/pyversions/argus-dpy)](https://pypi.org/project/argus-dpy/)
[![License: AGPL-3.0-or-later](https://img.shields.io/badge/license-AGPL--3.0--or--later-blue)](LICENSE)

**Operational Prometheus / OpenTelemetry metrics for [discord.py](https://github.com/Rapptz/discord.py) bots, in one line.**

```python
from discord.ext import commands
from argus import Argus

bot = commands.AutoShardedBot(command_prefix="!", intents=...)
Argus(bot)          # the whole integration
```

`Argus(bot)` instruments shard latency, interaction/command throughput and
outcomes, precise command duration, gateway throughput, rate-limit pressure and
cache sizes, then serves a Prometheus `/metrics` endpoint **and a live web
dashboard** on the bot's own event loop. It can also push to OpenTelemetry and
drain per-guild events to ClickHouse. It never puts a guild, user, or channel id
on a Prometheus label.

## Install

```bash
pip install argus-dpy
```

Python 3.10+, `discord.py >= 2.4`. Optional extras: `argus-dpy[otlp]`
(OpenTelemetry push), `argus-dpy[clickhouse]` (per-guild analytics),
`argus-dpy[fleet]` (`.env` autoload for the control plane). A reference container is published at
`ghcr.io/astoristhebrave/argus`, and the [Fleet control plane](#fleet-control-plane-opt-in)
at `ghcr.io/astoristhebrave/argus-fleet`.

**Compatibility.** Argus targets upstream **discord.py 2.x** and uses its
asynchronous cog lifecycle (`await bot.add_cog`, async `cog_load`/`cog_unload`)
and `setup_hook` chaining. Forks that vendor the `discord` namespace and follow
the same async-cog semantics may work but are untested; Pycord differs (a
synchronous `add_cog` and a non-coroutine `cog_unload`) and is not supported
unmodified. Because every fork ships the same `discord` import name, only one can
be installed at a time, and `pip install argus-dpy` pulls upstream discord.py.
See [Compatibility](https://github.com/AstorisTheBrave/argus/wiki/Compatibility).

**New here?** Follow a tutorial end to end:
[Single bot](https://github.com/AstorisTheBrave/argus/wiki/Tutorial-Single-Bot)
or [Fleet at scale](https://github.com/AstorisTheBrave/argus/wiki/Tutorial-Fleet).

## Behaviour

`Argus(bot)` registers listeners synchronously, then starts an aiohttp server on
the bot's loop once it is running. By default it serves the **dashboard at `/`**
and **metrics at `/metrics`** on port `9191`. Disable the dashboard with
`Argus(bot, dashboard=False)`; everything else is opt-in. Instrumentation is
fail-open: it is counted and swallowed, never raised into your bot.
See [Architecture & invariants](https://github.com/AstorisTheBrave/argus/wiki/Architecture-and-Invariants).

## Minimal setup

The minimum is one line; everything else is opt-in via kwargs or `ARGUS_*`
environment variables (kwargs override env override defaults).

```python
Argus(bot)   # metrics at /metrics, dashboard at /, on port 9191
```

To protect the dashboard, set **one env var** on the host that runs the bot —
Argus picks it up automatically. The dashboard is served *by* Argus in the same
process, so there is nothing separate to host or wire up:

```bash
ARGUS_DASHBOARD_AUTH_TOKEN=your-secret   # gates / and /api/*; /metrics stays scrapeable
```

Open the dashboard once with the token and it is remembered in the browser:
`http://your-host:9191/?token=your-secret`.

### Common options

| kwarg / env | default | meaning |
|---|---|---|
| `port` / `ARGUS_PORT` | `9191` | server port |
| `dashboard_auth_token` / `ARGUS_DASHBOARD_AUTH_TOKEN` | — | gate the dashboard + APIs |
| `grafana_url` / `ARGUS_GRAFANA_URL` | — | link/embed your Grafana boards |
| `cluster_id` / `ARGUS_CLUSTER_ID` | `default` | label for clustered deploys |
| `enable_per_guild` / `ARGUS_ENABLE_PER_GUILD` | `false` | per-guild analytics path |
| `otlp_endpoint` / `ARGUS_OTLP_ENDPOINT` | — | also push metrics via OTLP |

Every option, precedence and parsing rule is in
[Configuration](https://github.com/AstorisTheBrave/argus/wiki/Configuration).
New here? Start with the [FAQ](https://github.com/AstorisTheBrave/argus/wiki/FAQ).

## Metrics

Aggregate, bounded-cardinality metrics: per-shard latency and up state,
per-cluster guild/user/voice/emoji/sticker/channel counts, uptime, registered
commands, interaction and command rates with success/error split, precise
app- and prefix-command duration histograms, gateway throughput, shard
dis/reconnects, log and rate-limit counters. Every counter and histogram carry a
`cluster` label.

Full list with labels: [Metrics Reference](https://github.com/AstorisTheBrave/argus/wiki/Metrics-Reference).

## Dashboard

A React SPA bundled into the wheel, served at `/`: overview, interactions,
gateway, your Grafana boards, and per-guild analytics. Reads metrics live over
SSE with a polling fallback. Set `dashboard_auth_token` for anything public.
See [Dashboard](https://github.com/AstorisTheBrave/argus/wiki/Dashboard).

## Per-guild analytics

Per-guild, per-user questions never go to Prometheus (cardinality). With
`enable_per_guild` + `clickhouse_dsn` (the `argus-dpy[clickhouse]` extra), Argus
drains per-guild events to ClickHouse (batched, non-blocking) and the dashboard's
Analytics section serves per-guild command counts and average durations.
Step-by-step: [Per-guild analytics tutorial](https://github.com/AstorisTheBrave/argus/wiki/Tutorial-Analytics);
internals: [History & ClickHouse](https://github.com/AstorisTheBrave/argus/wiki/History-and-ClickHouse).

## Grafana, OTLP, clustering

`docker compose up -d` brings up a provisioned Prometheus + Grafana with three
dashboards. Set `otlp_endpoint` (the `argus-dpy[otlp]` extra) to also push via
OpenTelemetry to Datadog, Grafana Cloud, Honeycomb, and the like. Run one Argus
per process with a distinct `cluster_id` for clustered bots.
See the [OTLP tutorial](https://github.com/AstorisTheBrave/argus/wiki/Tutorial-OTLP),
[Clustering](https://github.com/AstorisTheBrave/argus/wiki/Clustering), and
[OTLP internals](https://github.com/AstorisTheBrave/argus/wiki/OTLP).

## Fleet control plane (opt-in)

Running many bot processes across regions? The **Argus Fleet** control plane is a
separate, opt-in service that aggregates them into one readable, multi-tier view:
**Global** (everything) -> **Fleet** (a region, e.g. `asia`) -> **Cluster** (one
process) -> **Shard** (per-shard up/latency). It renders plain, colour-graded
panels with no PromQL or Grafana setup,
and reads from two interchangeable sources: a self-contained **push** path (zero
infra; members heartbeat to it) and an existing **Prometheus**.

Bots are unchanged unless they opt in. The fastest path is the setup wizard,
which mints a token and writes a ready `.env` + `docker-compose.fleet.yml` and
prints the exact member snippet:

```bash
python -m argus.fleet init        # scaffold; then: docker compose -f docker-compose.fleet.yml up -d
python -m argus.fleet doctor --url http://fleet-host:9190 --token secret   # diagnose
```

Or wire it by hand:

```bash
# the control plane (its own process / container)
ARGUS_FLEET_TOKEN=secret python -m argus.fleet          # serves :9190

# each bot opts in with a few env vars (or kwargs)
ARGUS_FLEET_URL=http://fleet-host:9190 \
ARGUS_FLEET_TOKEN=secret ARGUS_FLEET_GROUP=asia \
    python bot.py
```

**Secure by default:** a non-loopback bind with no token refuses to start; set a
token (or `ARGUS_FLEET_TOKEN_FILE`). It assigns each process a stable per-region
number (never reused; a dead cluster keeps its slot, shown **down**), persists
topology across restarts, caps request bodies, strips its version banner, and
exposes its own `/metrics` and `/readyz`. The member side is fail-open: a fleet
outage never touches your bot loop. Full guide and deployment:
[Fleet](https://github.com/AstorisTheBrave/argus/wiki/Fleet) and the
[Fleet tutorial](https://github.com/AstorisTheBrave/argus/wiki/Tutorial-Fleet).

## Why no per-guild Prometheus labels?

`guild_id`/`user_id`/`channel_id` are unbounded; as labels they explode
Prometheus at scale and are useless to visualise. Argus forbids them by
construction and routes per-entity questions to the analytical path instead.

## Security

Set `dashboard_auth_token` for any non-localhost bot; the fleet control plane
refuses to start on a public bind without a token and is hardened by default
(rate limits, body caps, security headers, non-root images, SBOM/provenance). The
no-PII-label guarantee means per-entity data never reaches Prometheus. Full
guidance: [Security](https://github.com/AstorisTheBrave/argus/wiki/Security).
Report vulnerabilities privately via [SECURITY.md](SECURITY.md).

## Examples

Runnable examples in [`examples/`](examples/):

- [`basic_bot.py`](examples/basic_bot.py) — one bot, one line.
- [`clustered_bot.py`](examples/clustered_bot.py) — one process per shard range.
- [`fleet_member_bot.py`](examples/fleet_member_bot.py) — opting into a fleet.
- [`config_kwargs.py`](examples/config_kwargs.py) — every option, as kwargs.
- [`k8s/fleet.yaml`](examples/k8s/fleet.yaml) — the control plane on Kubernetes.

## Contributing & license

Contributions are accepted under the DCO; see [CONTRIBUTING.md](CONTRIBUTING.md).
Licensed under **AGPL-3.0-or-later** (network use counts as distribution) — see
[LICENSE](LICENSE). Release notes: [CHANGELOG.md](CHANGELOG.md) /
[Releases](https://github.com/AstorisTheBrave/argus/releases).

---

**See the [full wiki](https://github.com/AstorisTheBrave/argus/wiki) for the in-depth guides and explanations.**
