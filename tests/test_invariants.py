"""Cross-cutting invariant checks (build guide E)."""

from __future__ import annotations

from prometheus_client import generate_latest

from argus.adapters.prometheus import PrometheusAdapter
from argus.config import ArgusConfig
from argus.core.collector import MetricRegistry
from argus.core.metrics import FORBIDDEN_LABELS, define_metrics
from argus.exposition.server import build_app
from tests.conftest import FakeBot


def _exposition(*, enable_per_guild: bool) -> str:
    bot = FakeBot()
    config = ArgusConfig.resolve(enable_per_guild=enable_per_guild, environ={})
    registry = MetricRegistry()
    define_metrics(registry, bot, config)
    adapter = PrometheusAdapter()
    registry.attach(adapter)
    return generate_latest(adapter.registry).decode()


def test_invariant_2_no_forbidden_labels_defined() -> None:
    bot = FakeBot()
    registry = MetricRegistry()
    define_metrics(registry, bot, ArgusConfig.resolve(environ={}))
    for metric in registry.metrics.values():
        assert FORBIDDEN_LABELS.isdisjoint(metric.labelnames), metric.name


def test_invariant_7_enable_per_guild_adds_no_guild_label_to_prometheus() -> None:
    # Turning the analytical flag on must never leak guild_id into the metrics.
    text = _exposition(enable_per_guild=True)
    for forbidden in FORBIDDEN_LABELS:
        assert forbidden not in text


def test_metrics_path_is_isolated_from_healthz() -> None:
    # Exposition wiring sanity: build_app is pure and routes both paths.
    bot = FakeBot()
    registry = MetricRegistry()
    define_metrics(registry, bot, ArgusConfig.resolve(environ={}))
    adapter = PrometheusAdapter()
    registry.attach(adapter)
    app = build_app(adapter.registry, "/metrics")
    routes = {
        route.resource.canonical for route in app.router.routes() if route.resource is not None
    }
    assert "/metrics" in routes
    assert "/healthz" in routes
