# Argus — discord.py observability SDK
# Copyright (C) 2026 AstorisTheBrave
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Argus overhead benchmark suite.

Proves Argus adds minimal overhead to a discord.py bot. Everything here runs
in-process against a fake bot, so there is no Discord connection and no network:
the numbers isolate Argus' own cost (hook latency, scrape/serialise time,
startup, memory). Run with::

    python -m benchmarks.run            # default iteration counts
    python -m benchmarks.run -n 100000  # heavier run

The "baseline" column is the same workload with no instrumentation attached, so
the delta is exactly what Argus costs.
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

from prometheus_client import generate_latest

from argus.adapters.prometheus import PrometheusAdapter
from argus.config import ArgusConfig
from argus.core.collector import MetricRegistry
from argus.core.health import HealthState
from argus.core.instrumentation import Instrumentation
from argus.core.metrics import define_metrics
from argus.dashboard.snapshot import build_snapshot


class _Shard:
    def __init__(self, closed: bool) -> None:
        self._closed = closed

    def is_closed(self) -> bool:
        return self._closed


class _Tree:
    def get_commands(self) -> list[object]:
        return [object() for _ in range(25)]


class FakeBot:
    """A bot-shaped object exposing only the surface Argus reads (no network)."""

    def __init__(self, guilds: int = 500) -> None:
        self.latencies = [(0, 0.1), (1, 0.12)]
        self.shards = {0: _Shard(False), 1: _Shard(False)}
        self.shard_count = 2
        self.guilds = [object() for _ in range(guilds)]
        self.users = [object() for _ in range(guilds * 20)]
        self.voice_clients = [object() for _ in range(5)]
        self.emojis = [object() for _ in range(50)]
        self.stickers = [object() for _ in range(10)]
        self.private_channels = [object() for _ in range(3)]
        self.tree = _Tree()

    def is_closed(self) -> bool:
        return False


class _Interaction:
    """Minimal interaction for the hot-path hooks."""

    def __init__(self, iid: int) -> None:
        self.id = iid
        self.type = type("T", (), {"name": "application_command"})()
        self.created_at = None


def _build_instrumentation() -> tuple[MetricRegistry, Instrumentation, Any]:
    bot = FakeBot()
    config = ArgusConfig.resolve(environ={})
    registry = MetricRegistry()
    names = define_metrics(registry, bot, config, health=HealthState(server_up=True))
    adapter = PrometheusAdapter()
    registry.attach(adapter)
    instr = Instrumentation(registry, names, config)
    return registry, instr, adapter.registry


def _time_loop(n: int, body: Callable[[int], None]) -> float:
    """Return seconds per iteration for a synchronous body."""
    gc.collect()
    start = time.perf_counter()
    for i in range(n):
        body(i)
    return (time.perf_counter() - start) / n


async def _time_async_loop(n: int, body: Callable[[int], Any]) -> float:
    gc.collect()
    start = time.perf_counter()
    for i in range(n):
        await body(i)
    return (time.perf_counter() - start) / n


def _fmt_ns(seconds: float) -> str:
    return f"{seconds * 1e9:8.1f} ns"


def _row(label: str, baseline: float | None, argus: float) -> str:
    if baseline is None:
        return f"  {label:<34} {_fmt_ns(argus)}"
    delta = argus - baseline
    return f"  {label:<34} {_fmt_ns(baseline)} -> {_fmt_ns(argus)}  (+{_fmt_ns(delta)})"


async def bench_hooks(n: int) -> None:
    print(f"\nPer-event hook latency (n={n:,} each)")
    _, instr, _ = _build_instrumentation()

    # Baseline: dispatching a listener that does nothing (what discord.py costs
    # without Argus attached).
    async def noop(_i: int) -> None:
        return None

    async def socket(_i: int) -> None:
        await instr.on_socket_event_type("MESSAGE_CREATE")

    async def interaction(i: int) -> None:
        await instr.on_interaction(_Interaction(i))

    base = await _time_async_loop(n, noop)
    print(_row("on_socket_event_type", base, await _time_async_loop(n, socket)))
    print(_row("on_interaction", base, await _time_async_loop(n, interaction)))


def bench_recording(n: int) -> None:
    print(f"\nMetric recording cost (n={n:,} each)")
    registry, _, _ = _build_instrumentation()
    labels = {"event": "MESSAGE_CREATE", "cluster": "default"}
    name = "discord_gateway_events_total"
    print(
        _row("registry.inc (counter)", None, _time_loop(n, lambda _i: registry.inc(name, labels)))
    )


def bench_scrape_and_snapshot(n: int) -> None:
    print(f"\nScrape and snapshot cost (n={n:,} each)")
    registry, _, prom = _build_instrumentation()
    # Warm the series with realistic cardinality (25 commands x success/error).
    for c in range(25):
        registry.inc(
            "discord_app_commands_total",
            {"command": f"c{c}", "status": "success", "cluster": "default"},
        )
        registry.observe(
            "discord_app_command_duration_seconds", 0.2, {"command": f"c{c}", "cluster": "default"}
        )
    print(_row("generate_latest (/metrics)", None, _time_loop(n, lambda _i: generate_latest(prom))))
    print(_row("build_snapshot (dashboard)", None, _time_loop(n, lambda _i: build_snapshot(prom))))


def bench_startup(n: int) -> None:
    print(f"\nStartup cost (n={n:,})")
    print(
        _row(
            "define_metrics + attach adapter",
            None,
            _time_loop(n, lambda _i: _build_instrumentation()),
        )
    )


def bench_memory() -> None:
    print("\nMemory footprint")
    gc.collect()
    tracemalloc.start()
    before = tracemalloc.take_snapshot()
    registry, _, _ = _build_instrumentation()
    # Exercise to allocate the labelled series a busy bot would hold.
    for c in range(50):
        registry.inc(
            "discord_app_commands_total",
            {"command": f"c{c}", "status": "success", "cluster": "default"},
        )
        registry.observe(
            "discord_app_command_duration_seconds", 0.2, {"command": f"c{c}", "cluster": "default"}
        )
    after = tracemalloc.take_snapshot()
    tracemalloc.stop()
    total = sum(s.size_diff for s in after.compare_to(before, "filename"))
    print(f"  {'collector + 50 command series':<34} {total / 1024:8.1f} KiB")


def main() -> None:
    parser = argparse.ArgumentParser(description="Argus overhead benchmarks")
    parser.add_argument("-n", type=int, default=50_000, help="iterations for the hot-path loops")
    args = parser.parse_args()
    n = args.n

    print("=" * 64)
    print("Argus benchmark suite (in-process, no Discord connection)")
    print("=" * 64)
    bench_startup(max(200, n // 500))
    bench_memory()
    bench_recording(n)
    asyncio.run(bench_hooks(n))
    bench_scrape_and_snapshot(max(200, n // 100))
    print("\nLower is better. Hook cost is the only number on the bot's hot path;")
    print("scrape/snapshot run once per Prometheus scrape or dashboard tick.")


if __name__ == "__main__":
    main()
