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

"""OpenTelemetry adapter (the ``otlp`` extra), pushing the neutral registry.

Maps the three neutral kinds to OTel instruments (grounding sec.4): counters to
``Counter.add``, the histogram to ``Histogram.record``, and scrape-time gauges
to an observable gauge whose callback reads the neutral gauge callback at export
time (so gauges stay pull-based, invariant 4). Info is modelled as an observable
gauge of constant 1 carrying the info as attributes.

opentelemetry is imported lazily so the adapter (and its tests, via an injected
meter) work without the optional dependency installed.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import Any

from argus.adapters.base import Adapter
from argus.core.collector import MetricDef, MetricKind

log = logging.getLogger("argus")

# (value, attributes) observation. Falls back to this when opentelemetry is not
# importable (e.g. under test); otherwise the real otel Observation is used.
ObservationFactory = Callable[[float, Mapping[str, str]], Any]


class _Obs:
    __slots__ = ("attributes", "value")

    def __init__(self, value: float, attributes: Mapping[str, str]) -> None:
        self.value = value
        self.attributes = attributes


def _default_observation() -> ObservationFactory:
    try:
        from opentelemetry.metrics import Observation  # type: ignore[import-not-found]
    except Exception:
        return _Obs
    return lambda value, attributes: Observation(value, dict(attributes))


def _build_meter(endpoint: str | None) -> Any:
    from opentelemetry import metrics  # type: ignore[import-not-found]
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (  # type: ignore[import-not-found]
        OTLPMetricExporter,
    )
    from opentelemetry.sdk.metrics import MeterProvider  # type: ignore[import-not-found]
    from opentelemetry.sdk.metrics.export import (  # type: ignore[import-not-found]
        PeriodicExportingMetricReader,
    )

    reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=endpoint))
    metrics.set_meter_provider(MeterProvider(metric_readers=[reader]))
    return metrics.get_meter("argus")


class OTLPAdapter(Adapter):
    def __init__(
        self,
        *,
        endpoint: str | None = None,
        meter: Any = None,
        observation: ObservationFactory | None = None,
    ) -> None:
        self._meter = meter if meter is not None else _build_meter(endpoint)
        self._observation = observation if observation is not None else _default_observation()
        self._counters: dict[str, Any] = {}
        self._histograms: dict[str, Any] = {}
        self._infos: dict[str, dict[str, str]] = {}

    def add_metric(self, metric: MetricDef) -> None:
        if metric.kind is MetricKind.COUNTER:
            self._counters[metric.name] = self._meter.create_counter(
                metric.name, description=metric.documentation
            )
        elif metric.kind is MetricKind.HISTOGRAM:
            self._histograms[metric.name] = self._meter.create_histogram(
                metric.name, description=metric.documentation
            )
        elif metric.kind is MetricKind.GAUGE:
            self._meter.create_observable_gauge(
                metric.name,
                callbacks=[self._gauge_callback(metric)],
                description=metric.documentation,
            )
        elif metric.kind is MetricKind.INFO:
            self._infos.setdefault(metric.name, {})
            self._meter.create_observable_gauge(
                f"{metric.name}_info",
                callbacks=[self._info_callback(metric.name)],
                description=metric.documentation,
            )

    def _gauge_callback(self, metric: MetricDef) -> Callable[[Any], list[Any]]:
        labelnames = metric.labelnames
        source = metric.callback

        def callback(_options: Any) -> list[Any]:
            if source is None:
                return []
            try:
                samples = list(source())
            except Exception:
                # Isolate a fragile gauge: skip it at export rather than break
                # the whole OTLP collection (invariant 5).
                log.exception("argus otlp gauge %r failed at export; skipping it", metric.name)
                return []
            return [
                self._observation(sample.value, dict(zip(labelnames, sample.labels, strict=False)))
                for sample in samples
            ]

        return callback

    def _info_callback(self, name: str) -> Callable[[Any], list[Any]]:
        def callback(_options: Any) -> list[Any]:
            info = self._infos.get(name) or {}
            return [self._observation(1.0, dict(info))] if info else []

        return callback

    def inc(self, name: str, labels: Mapping[str, str] | None = None, amount: float = 1.0) -> None:
        self._counters[name].add(amount, dict(labels or {}))

    def observe(self, name: str, value: float, labels: Mapping[str, str] | None = None) -> None:
        self._histograms[name].record(value, dict(labels or {}))

    def set_info(self, name: str, info: Mapping[str, str]) -> None:
        self._infos[name] = dict(info)
