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

"""Prometheus adapter: one CollectorRegistry, hybrid mechanism (grounding sec.2).

Scrape-time gauges are served by a custom collector that reads the neutral
gauge callbacks live each scrape (invariant 4). Counters, the duration
histogram and the info metric are held ``prometheus_client`` objects mutated by
the event hooks. ``generate_latest`` serialises both together.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable, Iterator, Mapping

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, Info
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector

from argus.adapters.base import Adapter
from argus.core.collector import MetricDef, MetricKind

__all__ = ["CONTENT_TYPE_LATEST", "PrometheusAdapter"]

log = logging.getLogger("argus")


class _GaugeCollector(Collector):
    """Reads neutral gauge callbacks at scrape time (invariant 4).

    Each callback is isolated: if one raises, that single gauge family is skipped
    and the error counted, so a fragile gauge can never fail the whole scrape and
    take every other metric down with it (invariant 5).
    """

    def __init__(self) -> None:
        self._gauges: list[MetricDef] = []
        self._on_error: Callable[[str], None] | None = None

    def add(self, metric: MetricDef) -> None:
        self._gauges.append(metric)

    def set_error_hook(self, on_error: Callable[[str], None]) -> None:
        self._on_error = on_error

    def collect(self) -> Iterator[GaugeMetricFamily]:
        for metric in self._gauges:
            family = GaugeMetricFamily(
                metric.name, metric.documentation, labels=list(metric.labelnames)
            )
            if metric.callback is not None:
                try:
                    samples = list(metric.callback())
                except Exception:
                    log.exception("argus gauge %r failed at scrape; skipping it", metric.name)
                    if self._on_error is not None:
                        with contextlib.suppress(Exception):
                            self._on_error(f"scrape:{metric.name}")
                    samples = []
                for sample in samples:
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

    def set_scrape_error_hook(self, on_error: Callable[[str], None]) -> None:
        """Route scrape-time gauge failures to a counter (wired by the cog)."""
        self._gauge_collector.set_error_hook(on_error)

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
