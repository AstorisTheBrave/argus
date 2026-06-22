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

"""Sustained-throughput load harness for Argus' hot path.

Unlike ``benchmarks/run.py`` (single-call micro-costs), this drives a *sustained*
stream of events through the instrumentation and reports throughput, latency
percentiles, and peak allocation - the numbers you cite when someone asks "what
does it cost under load?". Still in-process (no Discord), so it isolates Argus'
own overhead; pair it with a real bot for end-to-end figures.

    python -m benchmarks.load                 # ~200k events
    python -m benchmarks.load -n 1000000      # heavier
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import statistics
import time
import tracemalloc
from collections.abc import Awaitable, Callable

from benchmarks.run import _build_instrumentation, _Interaction


def _percentile(samples: list[float], pct: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    index = min(len(ordered) - 1, int(pct / 100.0 * len(ordered)))
    return ordered[index]


async def _drive(n: int, body: Callable[[int], Awaitable[None]]) -> tuple[float, list[float]]:
    """Run ``body`` n times; return (total seconds, per-event latencies)."""
    gc.collect()
    latencies: list[float] = []
    start = time.perf_counter()
    for i in range(n):
        t0 = time.perf_counter()
        await body(i)
        latencies.append(time.perf_counter() - t0)
    return time.perf_counter() - start, latencies


def _report(label: str, n: int, elapsed: float, latencies: list[float]) -> None:
    throughput = n / elapsed if elapsed else float("inf")
    p50 = _percentile(latencies, 50) * 1e6
    p99 = _percentile(latencies, 99) * 1e6
    mean = (statistics.fmean(latencies) * 1e6) if latencies else 0.0
    print(
        f"  {label:<26} {throughput:>12,.0f} ev/s   "
        f"mean {mean:6.2f} us   p50 {p50:6.2f} us   p99 {p99:6.2f} us"
    )


async def _run(n: int) -> None:
    print("=" * 78)
    print(f"Argus sustained-load benchmark (in-process, no Discord)  n={n:,} events")
    print("=" * 78)

    _, instr, _ = _build_instrumentation()

    async def noop(_i: int) -> None:
        return None

    async def socket(_i: int) -> None:
        await instr.on_socket_event_type("MESSAGE_CREATE")

    async def interaction(i: int) -> None:
        await instr.on_interaction(_Interaction(i))

    base_elapsed, base_lat = await _drive(n, noop)
    _report("baseline (no-op)", n, base_elapsed, base_lat)

    tracemalloc.start()
    sock_elapsed, sock_lat = await _drive(n, socket)
    _, peak_socket = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    _report("on_socket_event_type", n, sock_elapsed, sock_lat)

    int_elapsed, int_lat = await _drive(n, interaction)
    _report("on_interaction", n, int_elapsed, int_lat)

    overhead = (statistics.fmean(sock_lat) - statistics.fmean(base_lat)) * 1e6
    print("-" * 78)
    print(f"  Argus overhead per event (socket): ~{overhead:.2f} us")
    print(f"  Peak allocation during {n:,} socket events: {peak_socket / 1024:.1f} KiB")
    print("  Hooks are O(1), non-blocking, and fail-open; this bounds Argus' own cost.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Argus sustained-load benchmark")
    parser.add_argument("-n", type=int, default=200_000, help="number of events to drive")
    args = parser.parse_args()
    asyncio.run(_run(args.n))


if __name__ == "__main__":
    main()
