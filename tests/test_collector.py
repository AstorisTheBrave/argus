"""MetricRegistry model + invariant 1 enforcement (D2 gate)."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

import argus.core
from argus.core.collector import (
    GaugeSample,
    MetricBackend,
    MetricDef,
    MetricKind,
    MetricRegistry,
)


class RecordingBackend:
    """A tiny in-memory MetricBackend for asserting dispatch."""

    def __init__(self) -> None:
        self.added: list[str] = []
        self.incs: list[tuple[str, Mapping[str, str] | None, float]] = []
        self.observes: list[tuple[str, float, Mapping[str, str] | None]] = []
        self.infos: list[tuple[str, Mapping[str, str]]] = []

    def add_metric(self, metric: MetricDef) -> None:
        self.added.append(metric.name)

    def inc(self, name: str, labels: Mapping[str, str] | None = None, amount: float = 1.0) -> None:
        self.incs.append((name, labels, amount))

    def observe(self, name: str, value: float, labels: Mapping[str, str] | None = None) -> None:
        self.observes.append((name, value, labels))

    def set_info(self, name: str, info: Mapping[str, str]) -> None:
        self.infos.append((name, info))


def _counter() -> MetricDef:
    return MetricDef("c_total", "doc", MetricKind.COUNTER, labelnames=("status",))


def _histogram() -> MetricDef:
    return MetricDef("h_seconds", "doc", MetricKind.HISTOGRAM, buckets=(0.1, 1.0))


def _gauge() -> MetricDef:
    return MetricDef("g", "doc", MetricKind.GAUGE, callback=lambda: [GaugeSample((), 1.0)])


def _info() -> MetricDef:
    return MetricDef("i", "doc", MetricKind.INFO)


def test_model_holds_all_kinds() -> None:
    reg = MetricRegistry()
    for metric in (_counter(), _histogram(), _gauge(), _info()):
        reg.define(metric)
    kinds = {m.kind for m in reg.metrics.values()}
    assert kinds == {MetricKind.COUNTER, MetricKind.HISTOGRAM, MetricKind.GAUGE, MetricKind.INFO}


def test_backend_is_a_protocol() -> None:
    assert isinstance(RecordingBackend(), MetricBackend)


def test_define_replays_to_attached_backend_and_new_ones() -> None:
    reg = MetricRegistry()
    early = RecordingBackend()
    reg.attach(early)
    reg.define(_counter())  # forwarded live
    late = RecordingBackend()
    reg.attach(late)  # replayed on attach
    assert early.added == ["c_total"]
    assert late.added == ["c_total"]


def test_mutations_fan_out_to_backends() -> None:
    reg = MetricRegistry()
    backend = RecordingBackend()
    reg.attach(backend)
    reg.define(_counter())
    reg.define(_histogram())
    reg.define(_info())
    reg.inc("c_total", {"status": "ok"})
    reg.observe("h_seconds", 0.5)
    reg.set_info("i", {"v": "1"})
    assert backend.incs == [("c_total", {"status": "ok"}, 1.0)]
    assert backend.observes == [("h_seconds", 0.5, None)]
    assert backend.infos == [("i", {"v": "1"})]


def test_duplicate_definition_rejected() -> None:
    reg = MetricRegistry()
    reg.define(_counter())
    with pytest.raises(ValueError, match="already defined"):
        reg.define(_counter())


def test_kind_mismatch_rejected() -> None:
    reg = MetricRegistry()
    reg.define(_counter())
    with pytest.raises(TypeError):
        reg.observe("c_total", 1.0)  # counter, not histogram


def test_unknown_metric_rejected() -> None:
    with pytest.raises(KeyError):
        MetricRegistry().inc("nope")


def test_histogram_requires_buckets() -> None:
    with pytest.raises(ValueError, match="requires buckets"):
        MetricDef("x_seconds", "d", MetricKind.HISTOGRAM)


def test_gauge_requires_callback() -> None:
    with pytest.raises(ValueError, match="requires a scrape-time callback"):
        MetricDef("x", "d", MetricKind.GAUGE)


# --- Invariant 1: core imports no adapter / backend client (build guide E.1) ---

_FORBIDDEN_PREFIXES = ("prometheus_client", "opentelemetry", "clickhouse")


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_core_imports_no_backend_or_adapter() -> None:
    core_dir = Path(argus.core.__file__).parent
    offenders: dict[str, set[str]] = {}
    for py in core_dir.rglob("*.py"):
        bad = {
            mod
            for mod in _imported_modules(py)
            if mod.startswith(_FORBIDDEN_PREFIXES) or mod.startswith("argus.adapters")
        }
        if bad:
            offenders[py.name] = bad
    assert offenders == {}, f"core must not import backends/adapters: {offenders}"
