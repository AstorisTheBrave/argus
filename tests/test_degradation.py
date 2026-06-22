"""Graceful degradation: when Argus' dependencies fail, the bot keeps running.

A single, readable place that proves the fail-open promise end to end - a broken
tracer, a broken analytical sink, a ClickHouse outage, and an unreachable
Pushgateway all degrade quietly instead of touching the bot.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from prometheus_client import CollectorRegistry

from argus.config import ArgusConfig
from argus.core.collector import MetricRegistry
from argus.core.instrumentation import Instrumentation
from argus.core.metrics import define_metrics
from argus.exposition.pushgateway import PushgatewayPusher
from argus.history.sink import BatchingSink, EventSink
from tests.conftest import CountingBackend, FakeBot


class _BrokenTracer:
    def start(self, name: str, attributes: dict[str, str]) -> Any:
        raise RuntimeError("tracing backend down")

    def finish(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError("tracing backend down")


class _BrokenSink(EventSink):
    async def record(self, event: Any) -> None:
        raise RuntimeError("analytical sink down")


class _ClickHouseDownSink(BatchingSink):
    async def _flush(self, batch: list[Any]) -> None:
        raise RuntimeError("clickhouse unreachable")


def _instr(sink: EventSink, tracer: Any) -> tuple[Instrumentation, CountingBackend]:
    config = ArgusConfig.resolve(enable_per_guild=True, environ={})
    registry = MetricRegistry()
    names = define_metrics(registry, FakeBot(), config)
    backend = CountingBackend()
    registry.attach(backend)
    return Instrumentation(registry, names, config, sink=sink, tracer=tracer), backend


def _app_interaction() -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        type=SimpleNamespace(name="application_command"),
        command=SimpleNamespace(qualified_name="ping"),
        guild_id=99,
        created_at=None,
    )


async def test_bot_path_survives_a_broken_tracer_and_sink() -> None:
    instr, backend = _instr(_BrokenSink(), _BrokenTracer())
    inter = _app_interaction()

    # None of these may raise, even though both the tracer and the sink throw.
    await instr.on_interaction(inter)
    await instr.on_app_command_completion(inter, SimpleNamespace(qualified_name="ping"))

    # The operational metric is still recorded...
    assert (
        backend.count(
            instr._n.app_commands_total, command="ping", status="success", cluster="default"
        )
        == 1
    )
    # ...and the sink failure was counted, not raised.
    assert (
        backend.count(
            instr._n.instrumentation_errors_total, hook="sink_interaction", cluster="default"
        )
        >= 1
    )


async def test_clickhouse_outage_sheds_load_and_opens_the_circuit() -> None:
    flips: list[bool] = []
    sink = _ClickHouseDownSink(
        batch_size=1, flush_interval=0.01, circuit_threshold=2, circuit_cooldown=10.0
    )
    sink.set_health_hook(flips.append)

    for i in range(5):
        await sink.record({"i": i})  # record() must never raise on a dead backend
    for _ in range(50):
        await asyncio.sleep(0.01)
        if not sink.healthy:
            break

    assert sink.healthy is False  # circuit opened
    assert flips and flips[-1] is False
    await sink.aclose()


async def test_pushgateway_outage_marks_unhealthy_without_raising(monkeypatch: Any) -> None:
    def boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("pushgateway unreachable")

    monkeypatch.setattr("prometheus_client.push_to_gateway", boom)
    flips: list[bool] = []
    pusher = PushgatewayPusher(
        CollectorRegistry(),
        url="http://pg:9091",
        job="argus",
        cluster="a",
        interval=0.01,
        on_health=flips.append,
    )
    await pusher.start()
    for _ in range(50):
        await asyncio.sleep(0.01)
        if flips:
            break
    await pusher.aclose()

    assert flips and flips[-1] is False  # reported down, never raised into the bot
