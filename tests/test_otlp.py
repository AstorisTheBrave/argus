"""OTLP adapter mapping against a fake meter (no opentelemetry required)."""

from __future__ import annotations

from typing import Any

from argus.adapters.otlp import OTLPAdapter
from argus.core.collector import GaugeSample, MetricDef, MetricKind


class FakeInstrument:
    def __init__(self) -> None:
        self.calls: list[tuple[float, dict[str, str]]] = []

    def add(self, amount: float, attributes: dict[str, str] | None = None) -> None:
        self.calls.append((amount, dict(attributes or {})))

    def record(self, value: float, attributes: dict[str, str] | None = None) -> None:
        self.calls.append((value, dict(attributes or {})))


class FakeMeter:
    def __init__(self) -> None:
        self.counters: dict[str, FakeInstrument] = {}
        self.histograms: dict[str, FakeInstrument] = {}
        self.gauges: dict[str, list[Any]] = {}

    def create_counter(self, name: str, description: str = "") -> FakeInstrument:
        self.counters[name] = FakeInstrument()
        return self.counters[name]

    def create_histogram(self, name: str, description: str = "") -> FakeInstrument:
        self.histograms[name] = FakeInstrument()
        return self.histograms[name]

    def create_observable_gauge(
        self, name: str, callbacks: list[Any] | None = None, description: str = ""
    ) -> None:
        self.gauges[name] = callbacks or []


def _adapter() -> tuple[OTLPAdapter, FakeMeter]:
    meter = FakeMeter()
    return OTLPAdapter(meter=meter), meter


def test_counter_add_and_histogram_record() -> None:
    adapter, meter = _adapter()
    adapter.add_metric(MetricDef("c_total", "d", MetricKind.COUNTER, labelnames=("cluster",)))
    adapter.add_metric(MetricDef("h_seconds", "d", MetricKind.HISTOGRAM, buckets=(0.1, 1.0)))
    adapter.inc("c_total", {"cluster": "default"}, 2.0)
    adapter.observe("h_seconds", 0.25, {"cluster": "default"})
    assert meter.counters["c_total"].calls == [(2.0, {"cluster": "default"})]
    assert meter.histograms["h_seconds"].calls == [(0.25, {"cluster": "default"})]


def test_observable_gauge_reads_callback_at_export() -> None:
    adapter, meter = _adapter()
    adapter.add_metric(
        MetricDef(
            "g",
            "d",
            MetricKind.GAUGE,
            labelnames=("shard",),
            callback=lambda: [GaugeSample(("0",), 0.1)],
        )
    )
    callback = meter.gauges["g"][0]
    observations = callback(None)
    assert observations[0].value == 0.1
    assert observations[0].attributes == {"shard": "0"}


def test_info_observable_gauge() -> None:
    adapter, meter = _adapter()
    adapter.add_metric(MetricDef("discord_bot", "d", MetricKind.INFO))
    adapter.set_info("discord_bot", {"argus_version": "9.9"})
    observations = meter.gauges["discord_bot_info"][0](None)
    assert observations[0].value == 1.0
    assert observations[0].attributes == {"argus_version": "9.9"}
