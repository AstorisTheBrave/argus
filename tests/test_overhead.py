"""Per-event overhead benchmark (invariant 3)."""

from __future__ import annotations

import time

from argus.adapters.prometheus import PrometheusAdapter
from argus.config import ArgusConfig
from argus.core.collector import MetricRegistry
from argus.core.instrumentation import Instrumentation
from argus.core.metrics import define_metrics
from tests.conftest import FakeBot

# Generous ceiling: real cost is sub-microsecond; this only guards against an
# accidental I/O/await sneaking onto the hot path (it would blow past this).
_MAX_SECONDS_PER_EVENT = 5e-4


async def test_event_hook_overhead_is_negligible() -> None:
    bot = FakeBot()
    registry = MetricRegistry()
    names = define_metrics(registry, bot, ArgusConfig.resolve(environ={}))
    registry.attach(PrometheusAdapter())  # realistic: held prometheus counters
    instr = Instrumentation(registry, names, ArgusConfig.resolve(environ={}))

    n = 20_000
    start = time.perf_counter()
    for _ in range(n):
        await instr.on_socket_event_type("MESSAGE_CREATE")
    per_event = (time.perf_counter() - start) / n

    assert per_event < _MAX_SECONDS_PER_EVENT, f"{per_event * 1e6:.2f} us/event"
