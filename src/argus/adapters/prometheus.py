"""Prometheus adapter: one CollectorRegistry, hybrid mechanism (grounding sec.2).

Scrape-time gauges are served by a custom collector that reads the neutral
gauge callbacks live each scrape (invariant 4). Counters, the duration
histogram and the info metric are held ``prometheus_client`` objects mutated by
the event hooks. ``generate_latest`` serialises both together.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, Info
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector

from argus.adapters.base import Adapter
from argus.core.collector import MetricDef, MetricKind

__all__ = ["CONTENT_TYPE_LATEST", "PrometheusAdapter"]


class _GaugeCollector(Collector):
    """Reads neutral gauge callbacks at scrape time (invariant 4)."""

    def __init__(self) -> None:
        self._gauges: list[MetricDef] = []

    def add(self, metric: MetricDef) -> None:
        self._gauges.append(metric)

    def collect(self) -> Iterator[GaugeMetricFamily]:
        for metric in self._gauges:
            family = GaugeMetricFamily(
                metric.name, metric.documentation, labels=list(metric.labelnames)
            )
            if metric.callback is not None:
                for sample in metric.callback():
                    family.add_metric(list(sample.labels), sample.value)
            yield family


class PrometheusAdapter(Adapter):
    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self.registry = registry if registry is not None else CollectorRegistry()
        self._counters: dict[str, Counter] = {}
        self._histograms: dict[str, Histogram] = {}
        self._infos: dict[str, Info] = {}
        self._gauge_collector = _GaugeCollector()
        self.registry.register(self._gauge_collector)

    def add_metric(self, metric: MetricDef) -> None:
        labels = list(metric.labelnames)
        if metric.kind is MetricKind.GAUGE:
            self._gauge_collector.add(metric)
        elif metric.kind is MetricKind.COUNTER:
            self._counters[metric.name] = Counter(
                metric.name, metric.documentation, labels, registry=self.registry
            )
        elif metric.kind is MetricKind.HISTOGRAM:
            assert metric.buckets is not None  # guaranteed by MetricDef
            self._histograms[metric.name] = Histogram(
                metric.name,
                metric.documentation,
                labels,
                buckets=metric.buckets,
                registry=self.registry,
            )
        elif metric.kind is MetricKind.INFO:
            self._infos[metric.name] = Info(
                metric.name, metric.documentation, registry=self.registry
            )

    def inc(self, name: str, labels: Mapping[str, str] | None = None, amount: float = 1.0) -> None:
        counter = self._counters[name]
        (counter.labels(**labels) if labels else counter).inc(amount)

    def observe(self, name: str, value: float, labels: Mapping[str, str] | None = None) -> None:
        histogram = self._histograms[name]
        (histogram.labels(**labels) if labels else histogram).observe(value)

    def set_info(self, name: str, info: Mapping[str, str]) -> None:
        self._infos[name].info(dict(info))
