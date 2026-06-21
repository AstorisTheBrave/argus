"""Property/fuzz test for the dashboard snapshot serializer.

build_snapshot walks the live registry into JSON the SPA consumes. It must never
produce something json.dumps cannot serialise, whatever label values or
observations flow through it (command names and the like are user-controlled).
"""

from __future__ import annotations

import json

from hypothesis import given
from hypothesis import strategies as st
from prometheus_client import CollectorRegistry

from argus.adapters.prometheus import PrometheusAdapter
from argus.core.collector import GaugeSample, MetricDef, MetricKind, MetricRegistry
from argus.dashboard.snapshot import build_snapshot

_DURATION_BUCKETS = (0.05, 0.1, 0.5, 1.0, 5.0)


def _registry() -> tuple[MetricRegistry, CollectorRegistry]:
    reg = MetricRegistry()
    adapter = PrometheusAdapter(CollectorRegistry())
    reg.attach(adapter)
    reg.define(MetricDef("t_counter", "c", MetricKind.COUNTER, labelnames=("label",)))
    reg.define(
        MetricDef(
            "t_hist", "h", MetricKind.HISTOGRAM, labelnames=("label",), buckets=_DURATION_BUCKETS
        )
    )
    reg.define(MetricDef("t_gauge", "g", MetricKind.GAUGE, callback=lambda: [GaugeSample((), 1.0)]))
    return reg, adapter.registry


@given(
    label=st.text(min_size=0, max_size=64),
    amount=st.floats(min_value=0, max_value=1e9, allow_nan=False, allow_infinity=False),
    observation=st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False),
)
def test_snapshot_always_json_serialisable(label: str, amount: float, observation: float) -> None:
    reg, prom = _registry()
    reg.inc("t_counter", {"label": label}, amount)
    reg.observe("t_hist", observation, {"label": label})

    snapshot = build_snapshot(prom)

    # Must round-trip through JSON without raising.
    dumped = json.dumps(snapshot)
    assert json.loads(dumped) == snapshot

    metrics = snapshot["metrics"]
    assert "t_counter" in metrics
    for entry in metrics.values():
        assert "type" in entry
        for sample in entry["samples"]:
            assert isinstance(sample["value"], float)
            assert isinstance(sample["labels"], dict)
