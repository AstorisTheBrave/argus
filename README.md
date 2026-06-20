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

Python 3.10+, `discord.py >= 2.4`. Optional extras: `argus-dpy[otlp]`,
`argus-dpy[clickhouse]`. A reference container is published at
`ghcr.io/astoristhebrave/argus`.

## Behaviour

`Argus(bot)` registers listeners synchronously, then starts an aiohttp server on
the bot's loop once it is running. By default it serves the **dashboard at `/`**
and **metrics at `/metrics`** on port `9191`. Disable the dashboard with
`Argus(bot, dashboard=False)`; everything else is opt-in. Instrumentation is
fail-open: it is counted and swallowed, never raised into your bot.
See [Architecture & invariants](https://github.com/AstorisTheBrave/argus/wiki/Architecture-and-Invariants).

## Configuration

Constructor kwargs override `ARGUS_*` environment variables override defaults.

| kwarg | env | default | meaning |
|---|---|---|---|
| `port` | `ARGUS_PORT` | `9191` | server port |
| `host` | `ARGUS_HOST` | `0.0.0.0` | bind host |
| `metrics_path` | `ARGUS_METRICS_PATH` | `/metrics` | metrics endpoint |
| `cluster_id` | `ARGUS_CLUSTER_ID` | `default` | low-cardinality label for clustered deploys |
| `namespace` | `ARGUS_NAMESPACE` | `discord` | metric name prefix |
| `dashboard` | `ARGUS_DASHBOARD` | `true` | serve the dashboard at `/` |
| `dashboard_path` | `ARGUS_DASHBOARD_PATH` | `/` | dashboard mount path |
| `dashboard_interval` | `ARGUS_DASHBOARD_INTERVAL` | `5` | live-stream seconds |
| `dashboard_auth_token` | `ARGUS_DASHBOARD_AUTH_TOKEN` | — | bearer token gating the dashboard + APIs |
| `grafana_url` | `ARGUS_GRAFANA_URL` | — | link/embed your Grafana boards |
| `enable_per_guild` | `ARGUS_ENABLE_PER_GUILD` | `false` | enable the per-guild analytical path |
| `clickhouse_dsn` | `ARGUS_CLICKHOUSE_DSN` | — | ClickHouse sink/target for analytics |
| `otlp_endpoint` | `ARGUS_OTLP_ENDPOINT` | — | also push metrics via OTLP |

Full reference: [Configuration](https://github.com/AstorisTheBrave/argus/wiki/Configuration).

## Metrics

Aggregate, bounded-cardinality metrics: per-shard latency and up state,
per-cluster guild/user/voice/emoji/sticker/channel counts, uptime, registered
commands, interaction and command rates with success/error split, precise
command-duration histogram, gateway throughput, shard dis/reconnects, log and
rate-limit counters. Every counter and the histogram carry a `cluster` label.

Full list with labels: [Metrics Reference](https://github.com/AstorisTheBrave/argus/wiki/Metrics-Reference).

## Dashboard

A React SPA bundled into the wheel, served at `/`: overview, interactions,
gateway, your Grafana boards, and per-guild analytics. Reads metrics live over
SSE with a polling fallback. Set `dashboard_auth_token` for anything public.
See [Dashboard](https://github.com/AstorisTheBrave/argus/wiki/Dashboard).

## Per-guild analytics

Per-guild, per-user questions never go to Prometheus (cardinality). With
`enable_per_guild` + `clickhouse_dsn`, Argus drains per-guild events to
ClickHouse (batched, non-blocking) and the dashboard's Analytics section serves
per-guild command counts and average durations.
See [History & ClickHouse](https://github.com/AstorisTheBrave/argus/wiki/History-and-ClickHouse).

## Grafana, OTLP, clustering

`docker compose up -d` brings up a provisioned Prometheus + Grafana with three
dashboards. Set `otlp_endpoint` to also push via OpenTelemetry. Run one Argus
per process with a distinct `cluster_id` for clustered bots.
See [Clustering](https://github.com/AstorisTheBrave/argus/wiki/Clustering) and
[OTLP](https://github.com/AstorisTheBrave/argus/wiki/OTLP).

## Why no per-guild Prometheus labels?

`guild_id`/`user_id`/`channel_id` are unbounded; as labels they explode
Prometheus at scale and are useless to visualise. Argus forbids them by
construction and routes per-entity questions to the analytical path instead.

## Contributing & license

Contributions are accepted under the DCO; see [CONTRIBUTING.md](CONTRIBUTING.md).
Licensed under **AGPL-3.0-or-later** (network use counts as distribution) — see
[LICENSE](LICENSE).

---

**See the [full wiki](https://github.com/AstorisTheBrave/argus/wiki) for the in-depth guides and explanations.**
