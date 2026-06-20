"""Per-guild capture wiring behind enable_per_guild (plan task 3.2, invariant 7)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from argus.config import ArgusConfig
from argus.core.collector import MetricRegistry
from argus.core.instrumentation import Instrumentation
from argus.core.metrics import define_metrics
from argus.history.sink import Event, EventSink
from tests.conftest import CountingBackend, FakeBot


class CapturingSink(EventSink):
    def __init__(self) -> None:
        self.events: list[Event] = []

    async def record(self, event: Event) -> None:
        self.events.append(event)


def _instr(
    sink: EventSink, *, enable_per_guild: bool
) -> tuple[Instrumentation, CountingBackend, Any]:
    bot = FakeBot()
    config = ArgusConfig.resolve(enable_per_guild=enable_per_guild, environ={})
    registry = MetricRegistry()
    names = define_metrics(registry, bot, config)
    backend = CountingBackend()
    registry.attach(backend)
    return Instrumentation(registry, names, config, sink=sink), backend, names


def _interaction(guild_id: int = 42) -> SimpleNamespace:
    return SimpleNamespace(type=SimpleNamespace(name="application_command"), guild_id=guild_id)


async def test_per_guild_on_emits_event_with_guild_id() -> None:
    sink = CapturingSink()
    instr, backend, names = _instr(sink, enable_per_guild=True)
    await instr.on_interaction(_interaction(guild_id=42))
    assert len(sink.events) == 1
    assert sink.events[0]["guild_id"] == "42"
    assert sink.events[0]["event"] == "interaction"
    # Invariant 7: the Prometheus counter carries no guild_id label.
    assert (
        backend.count(
            names.interactions_total,
            type="application_command",
            status="received",
            cluster="default",
        )
        == 1
    )
    for key in backend.counts:
        assert "guild_id" not in dict(key[1])


async def test_per_guild_off_emits_nothing() -> None:
    sink = CapturingSink()
    instr, _backend, _names = _instr(sink, enable_per_guild=False)
    await instr.on_interaction(_interaction())
    assert sink.events == []
