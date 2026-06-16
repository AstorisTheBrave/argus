"""Neutral metric model and registry (invariant 1).

The registry knows metric *definitions* and dispatches mutations to attached
backends through the :class:`MetricBackend` protocol. It imports no backend
client library, so adding or removing an adapter can never touch this module.

Three kinds carry all of Argus' signal (grounding sec.2 and sec.4):

* ``GAUGE``     live state, read at scrape time via a callback (invariant 4).
* ``COUNTER``   monotonic, mutated by event hooks with :meth:`MetricRegistry.inc`.
* ``HISTOGRAM`` distributions, fed by :meth:`MetricRegistry.observe`.
* ``INFO``      a single static-label series whose value is always 1.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Protocol, runtime_checkable


class MetricKind(Enum):
    GAUGE = "gauge"
    COUNTER = "counter"
    HISTOGRAM = "histogram"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class GaugeSample:
    """One scrape-time gauge reading: label values (in ``labelnames`` order)."""

    labels: tuple[str, ...]
    value: float


# A gauge callback is invoked at scrape time and yields current samples.
GaugeCallback = Callable[[], Iterable[GaugeSample]]


@dataclass(frozen=True, slots=True)
class MetricDef:
    """A backend-neutral metric definition."""

    name: str
    documentation: str
    kind: MetricKind
    labelnames: tuple[str, ...] = ()
    buckets: tuple[float, ...] | None = None  # HISTOGRAM only
    callback: GaugeCallback | None = None  # GAUGE only

    def __post_init__(self) -> None:
        if self.kind is MetricKind.HISTOGRAM and self.buckets is None:
            raise ValueError(f"histogram {self.name!r} requires buckets")
        if self.kind is MetricKind.GAUGE and self.callback is None:
            raise ValueError(f"gauge {self.name!r} requires a scrape-time callback")
        if self.kind is not MetricKind.HISTOGRAM and self.buckets is not None:
            raise ValueError(f"buckets only valid for a histogram, not {self.name!r}")


@runtime_checkable
class MetricBackend(Protocol):
    """The seam adapters implement. Defined in core so core imports no adapter."""

    def add_metric(self, metric: MetricDef) -> None: ...

    def inc(
        self, name: str, labels: Mapping[str, str] | None = None, amount: float = 1.0
    ) -> None: ...

    def observe(self, name: str, value: float, labels: Mapping[str, str] | None = None) -> None: ...

    def set_info(self, name: str, info: Mapping[str, str]) -> None: ...


@dataclass(slots=True)
class MetricRegistry:
    """Holds metric definitions and fans mutations out to attached backends."""

    _metrics: dict[str, MetricDef] = field(default_factory=dict)
    _backends: list[MetricBackend] = field(default_factory=list)

    @property
    def metrics(self) -> Mapping[str, MetricDef]:
        return MappingProxyType(self._metrics)

    def define(self, metric: MetricDef) -> MetricDef:
        if metric.name in self._metrics:
            raise ValueError(f"metric {metric.name!r} already defined")
        self._metrics[metric.name] = metric
        for backend in self._backends:
            backend.add_metric(metric)
        return metric

    def attach(self, backend: MetricBackend) -> None:
        """Attach a backend and replay every metric already defined."""
        self._backends.append(backend)
        for metric in self._metrics.values():
            backend.add_metric(metric)

    def inc(self, name: str, labels: Mapping[str, str] | None = None, amount: float = 1.0) -> None:
        self._require(name, MetricKind.COUNTER)
        for backend in self._backends:
            backend.inc(name, labels, amount)

    def observe(self, name: str, value: float, labels: Mapping[str, str] | None = None) -> None:
        self._require(name, MetricKind.HISTOGRAM)
        for backend in self._backends:
            backend.observe(name, value, labels)

    def set_info(self, name: str, info: Mapping[str, str]) -> None:
        self._require(name, MetricKind.INFO)
        for backend in self._backends:
            backend.set_info(name, info)

    def _require(self, name: str, kind: MetricKind) -> MetricDef:
        try:
            metric = self._metrics[name]
        except KeyError:
            raise KeyError(f"unknown metric {name!r}") from None
        if metric.kind is not kind:
            raise TypeError(f"metric {name!r} is {metric.kind.value}, not {kind.value}")
        return metric
