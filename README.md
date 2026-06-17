# argus-dpy

**Operational Prometheus / OpenTelemetry metrics for [discord.py](https://github.com/Rapptz/discord.py) bots, in one line.**

```python
from discord.ext import commands
from argus import Argus

bot = commands.AutoShardedBot(command_prefix="!", intents=...)
Argus(bot)          # that's the whole integration
```

`Argus(bot)` instruments shard latency, interaction and command throughput and
outcomes, command duration, gateway throughput, and rate-limit pressure, then
serves a Prometheus `/metrics` endpoint **on the bot's own event loop** — no
extra process, no thread, no glue code. It ships Grafana dashboards and a
one-command compose stack, stays backend-agnostic at the core, and **never puts
a guild, user, or channel id on a metric label**.

> Status: alpha. The metric surface is stable; OTLP push and the per-guild
> analytical sink are planned for 1.1.

---

## Install

```bash
pip install argus-dpy
```

Requires Python 3.10+ and `discord.py >= 2.4`.

## Use it

```python
Argus(bot)
```

Metrics are served at `http://0.0.0.0:9191/metrics` once the bot starts. That is
the entire required integration. You can also load it as a cog if you prefer:

```python
from argus import ArgusCog
await bot.add_cog(ArgusCog(bot))
```

## Dashboards in one command

```bash
docker compose up -d        # Prometheus on :9090, Grafana on :3000 (admin/admin)
```

Compose auto-provisions the Prometheus datasource and three dashboards
(**Overview**, **Interactions**, **Gateway**). Prometheus scrapes the bot at
`host.docker.internal:9191` out of the box — edit `prometheus/prometheus.yml` if
your bot listens elsewhere. The bot itself stays out of compose; it is your
application.

## Configuration

Constructor kwargs override `ARGUS_*` environment variables override defaults.

| Kwarg | Env | Default | Meaning |
|---|---|---|---|
| `port` | `ARGUS_PORT` | `9191` | `/metrics` port |
| `host` | `ARGUS_HOST` | `0.0.0.0` | bind host |
| `metrics_path` | `ARGUS_METRICS_PATH` | `/metrics` | endpoint path |
| `cluster_id` | `ARGUS_CLUSTER_ID` | `default` | low-cardinality label for clustered deploys |
| `namespace` | `ARGUS_NAMESPACE` | `discord` | metric name prefix |
| `enable_per_guild` | `ARGUS_ENABLE_PER_GUILD` | `false` | analytical sink only; never adds a Prometheus label |
| `otlp_endpoint` | `ARGUS_OTLP_ENDPOINT` | — | reserved for the 1.1 OTLP push path |

## Metrics

Names use the `namespace` prefix (default `discord`); `argus_*` internals are
never prefixed.

### State gauges (read live at scrape time)

| Metric | Labels |
|---|---|
| `discord_shard_latency_seconds` | `shard` |
| `discord_shards_connected` | `cluster` |
| `discord_shards_configured` | `cluster` |
| `discord_guilds` | `cluster` |
| `discord_cached_users` | `cluster` |
| `discord_bot_info` | `discord_py_version`, `argus_version` |
| `argus_up` | — |

### Counters

| Metric | Labels |
|---|---|
| `discord_interactions_total` | `type`, `status` |
| `discord_app_commands_total` | `command`, `status` |
| `discord_commands_total` | `command`, `status` |
| `discord_command_errors_total` | `command`, `error_type` |
| `discord_gateway_events_total` | `event` |
| `discord_shard_disconnects_total` | `shard` |
| `discord_shard_reconnects_total` | `shard` |
| `discord_log_records_total` | `logger`, `level` |
| `discord_ratelimits_total` | — |
| `argus_instrumentation_errors_total` | `hook` |

### Histograms

| Metric | Labels |
|---|---|
| `discord_app_command_duration_seconds` | `command` |

> `discord_cached_users` reflects the cache and is only meaningful with the
> members intent enabled. Command duration is approximated from the
> interaction timestamp to completion in this version.

## Why no per-guild metrics?

Cardinality. Every unique label-value combination is its own time series. Shard,
cluster, command, event and status are bounded sets — fine. A `guild_id` on a
bot in tens of thousands of guilds is tens of thousands of series **per metric**,
which is what makes Prometheus fall over at scale, and per-entity series are not
even useful to visualise. So Argus forbids `guild_id`, `user_id` and
`channel_id` as labels by construction. Per-guild, per-user questions belong in
an analytical store (a planned, strictly separate path), never in the
operational metrics.

## Clustered bots

Run one Argus per process, each with a distinct `cluster_id` and port:

```python
Argus(bot, cluster_id="0", port=9191)   # process 0
Argus(bot, cluster_id="1", port=9192)   # process 1
```

List every port in `prometheus/prometheus.yml`. State gauges carry the distinct
`cluster` label; counter rates aggregate across the fleet at query time. See
`examples/clustered_bot.py`.

## Licensing

Argus is licensed under **AGPL-3.0-or-later** — see [LICENSE](LICENSE).

Because the AGPL treats network use as distribution, anyone who runs a modified
version of Argus as a network service must make their modified source available
to that service's users.

Contributions are accepted under the Developer Certificate of Origin; see
[CONTRIBUTING.md](CONTRIBUTING.md).
