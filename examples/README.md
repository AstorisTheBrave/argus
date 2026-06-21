# Argus examples

Runnable, copy-paste starting points for every setup, plus a production
dos-and-don'ts. Each Python example carries inline `Do:` / `Don't:` notes. For the
in-depth guides, clone the wiki:

```bash
git clone https://github.com/AstorisTheBrave/argus.wiki.git
```

## Which example?

| File | Use it for |
|---|---|
| [`basic_bot.py`](basic_bot.py) | The minimum: `Argus(bot)` on one process. |
| [`production_bot.py`](production_bot.py) | A hardened single bot: minimal intents, token from env, dashboard auth, structured logging, graceful shutdown. |
| [`clustered_bot.py`](clustered_bot.py) | One process per shard range, distinct `cluster_id`/port each. |
| [`otlp_bot.py`](otlp_bot.py) | Push metrics to an OpenTelemetry collector (Datadog, Grafana Cloud, ...). |
| [`analytics_bot.py`](analytics_bot.py) | Per-guild analytics via ClickHouse (the analytical path). |
| [`fleet_member_bot.py`](fleet_member_bot.py) | Opt a bot into a Fleet control plane. |
| [`config_kwargs.py`](config_kwargs.py) | Reference: every config option as kwargs. |
| [`k8s/bot.yaml`](k8s/bot.yaml) | A bot Deployment on Kubernetes. |
| [`k8s/fleet.yaml`](k8s/fleet.yaml) | The Fleet control plane as a StatefulSet. |

Run any Python example with `DISCORD_TOKEN=... python examples/<file>.py`.

## Production dos and don'ts

### Secrets
- **Do** read the bot token from an env var or a mounted secret. **Don't**
  hardcode it or commit it; if it leaks, reset it in the Developer Portal.
- **Do** set `ARGUS_DASHBOARD_AUTH_TOKEN` (and the fleet token) from a secret,
  not inline.

### Intents and memory
- **Do** enable only the intents you use. The `members` intent is required for
  `discord_cached_users` to be meaningful and can cost ~600-800 MB of RAM at
  ~1,000 guilds.
- **Do** give the process a memory limit (container/k8s limit, or systemd) so a
  cache leak restarts the bot instead of OOM-killing the host.

### Sharding and scale
- **Do** move to `AutoShardedBot` (with `shard_count=None` to auto-detect) as you
  approach Discord's **2,500 guilds-per-shard** limit; sharding above it is
  mandatory.
- **Don't** shard a small bot prematurely - it adds cache/operational complexity
  for no benefit.
- **Do** give each process a distinct `cluster_id` the moment you run more than
  one; counter rates aggregate across the `cluster` label, single-process views
  filter by it.

### Reliability
- **Do** run under a restart policy: systemd `Restart=always`, container
  `restart: unless-stopped`, or a k8s Deployment. Production bots crash; restart
  automatically.
- **Don't** block the event loop. Use `await asyncio.sleep(...)`, never
  `time.sleep(...)`; keep heavy work off the loop. (Argus's own hooks are O(1)
  and non-blocking.)
- **Do** rely on the library's built-in rate-limit handling; watch
  `discord_ratelimits_total` for pressure.

### Observability
- **Do** scrape `/metrics` with Prometheus and use the bundled Grafana
  dashboards, or push via OTLP. Use `/healthz` for liveness checks.
- **Do** prefer structured logs to stdout in production (the fleet service has
  `ARGUS_FLEET_LOG_FORMAT=json`).
- **Don't** put `guild_id`/`user_id`/`channel_id` on Prometheus labels - they are
  unbounded. Argus forbids it; route per-entity questions to the analytics path
  (`enable_per_guild` + ClickHouse).

### State and the fleet
- **Do** persist the fleet control plane's state file (`ARGUS_FLEET_STATE`) on
  durable storage so per-fleet numbers survive restarts.
- **Don't** run two fleet control planes against one state file (it refuses) or
  expose it publicly without a token and TLS.
