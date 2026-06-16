"""Shared test fixtures: a counting backend and a FakeBot."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import pytest

from argus.config import ArgusConfig
from argus.core.collector import MetricDef, MetricRegistry
from argus.core.instrumentation import Instrumentation
from argus.core.metrics import MetricNames, define_metrics


class CountingBackend:
    """An in-memory MetricBackend that tracks counts, observations and info."""

    def __init__(self) -> None:
        self.added: list[str] = []
        self.counts: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self.observations: dict[str, list[float]] = {}
        self.infos: dict[str, dict[str, str]] = {}

    @staticmethod
    def _key(
        name: str, labels: Mapping[str, str] | None
    ) -> tuple[str, tuple[tuple[str, str], ...]]:
        return name, tuple(sorted((labels or {}).items()))

    def add_metric(self, metric: MetricDef) -> None:
        self.added.append(metric.name)

    def inc(self, name: str, labels: Mapping[str, str] | None = None, amount: float = 1.0) -> None:
        key = self._key(name, labels)
        self.counts[key] = self.counts.get(key, 0.0) + amount

    def observe(self, name: str, value: float, labels: Mapping[str, str] | None = None) -> None:
        self.observations.setdefault(name, []).append(value)

    def set_info(self, name: str, info: Mapping[str, str]) -> None:
        self.infos[name] = dict(info)

    def count(self, name: str, **labels: str) -> float:
        return self.counts.get(self._key(name, labels), 0.0)


class FakeShard:
    def __init__(self, closed: bool) -> None:
        self._closed = closed

    def is_closed(self) -> bool:
        return self._closed


class FakeTree:
    """Stand-in for discord.app_commands.CommandTree."""

    def __init__(self) -> None:
        self.errors: list[tuple[Any, BaseException]] = []

    async def on_error(self, interaction: Any, error: BaseException) -> None:
        self.errors.append((interaction, error))


class FakeBot:
    """Minimal stand-in exposing the surface Argus reads."""

    def __init__(self) -> None:
        self.listeners: dict[str, list[Any]] = {}
        self.tree = FakeTree()
        self.latencies: list[tuple[int, float]] = [(0, 0.1), (1, float("nan"))]
        self.shards = {0: FakeShard(False), 1: FakeShard(True)}
        self.shard_count = 2
        self.guilds = [object(), object(), object()]
        self.users = [object()] * 5

    def add_listener(self, fn: Any, name: str) -> None:
        self.listeners.setdefault(name, []).append(fn)

    def remove_listener(self, fn: Any, name: str) -> None:
        self.listeners.get(name, []).remove(fn)

    def is_closed(self) -> bool:
        return False


@dataclass(slots=True)
class Env:
    bot: FakeBot
    config: ArgusConfig
    registry: MetricRegistry
    names: MetricNames
    backend: CountingBackend
    instr: Instrumentation
    extra: dict[str, Any] = field(default_factory=dict)


@pytest.fixture
def env() -> Env:
    bot = FakeBot()
    config = ArgusConfig.resolve(environ={})
    registry = MetricRegistry()
    names = define_metrics(registry, bot, config)
    backend = CountingBackend()
    registry.attach(backend)
    instr = Instrumentation(registry, names, config)
    return Env(bot, config, registry, names, backend, instr)
