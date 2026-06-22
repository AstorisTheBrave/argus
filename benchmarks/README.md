# Benchmarks

A small, dependency-free suite that proves Argus adds minimal overhead to a
discord.py bot. Everything runs in-process against a fake bot, so there is no
Discord connection and no network: the numbers isolate Argus' own cost.

```bash
python -m benchmarks.run             # single-call micro-costs
python -m benchmarks.run -n 100000   # heavier run
python -m benchmarks.load            # sustained throughput + latency percentiles
python -m benchmarks.load -n 1000000 # heavier load
```

`run.py` measures single-call costs; `load.py` drives a **sustained** event stream
and reports throughput, mean/p50/p99 latency, and peak allocation - the answer to
"what does it cost under load?". Both are in-process (no Discord), so they isolate
Argus' own overhead; pair `load.py` with a real bot for end-to-end numbers.

## What it measures

| Benchmark | What it tells you | When it runs in production |
|---|---|---|
| `on_socket_event_type` / `on_interaction` | per-event hook latency vs a no-op listener (baseline) | on the bot's hot path, once per event |
| `registry.inc` | raw counter mutation cost | inside each hook |
| `generate_latest` | `/metrics` render time | once per Prometheus scrape (~15s) |
| `build_snapshot` | dashboard payload build | once per dashboard tick (~5s) |
| startup | `define_metrics` + adapter attach | once, at bot start |
| memory | collector + 50 command series | resident for the process |

The "baseline" column is the identical workload with no instrumentation
attached, so the printed delta is exactly what Argus costs.

## Representative results

Measured on a Windows 11 laptop, CPython 3.13, `-n 50000`. Absolute numbers are
machine-dependent; the **ratios and orders of magnitude** are the point.

| Metric | Result |
|---|---|
| `on_socket_event_type` hook | ~3 us/event (baseline no-op ~0.1 us) |
| `on_interaction` hook | ~16 us/event (also does bounded timer bookkeeping) |
| `registry.inc` (counter) | ~3 us |
| `generate_latest` (`/metrics`) | ~3.7 ms per scrape |
| `build_snapshot` (dashboard) | ~1.3 ms per tick |
| startup | ~1 ms |
| memory | ~450 KiB |

Sustained load (`benchmarks/load.py`, same machine, 100k events): ~55k events/s
through `on_socket_event_type`/`on_interaction`, **~17 us overhead per event**
(p99 well under 100 us), ~3 MiB peak allocation. A bot doing thousands of
events/sec spends a low single-digit percentage of one core in Argus, and the
hooks never block.

## How to read it

- **Hooks are the only cost on the bot's hot path.** At low single-digit
  microseconds per event, a bot doing 1,000 events/sec spends well under 2% of a
  single core in Argus, and the hooks never block (no I/O, no awaits, invariant
  3): they enqueue and return. A real bot is dominated by network and gateway
  latency that dwarfs these figures.
- **Scrape and snapshot are amortised.** `generate_latest` and `build_snapshot`
  run once per Prometheus scrape (~15s) and dashboard tick (~5s) respectively,
  not per event, and the dashboard snapshot is cached and shared across viewers.
- **Startup and memory are one-time and tiny.** Constructing the whole collector
  is ~1 ms and the resident series cost is sub-megabyte even with a realistic
  command catalogue.

These are micro-benchmarks: they bound Argus' own cost, not end-to-end bot
throughput. Re-run on your target hardware for absolute figures.
