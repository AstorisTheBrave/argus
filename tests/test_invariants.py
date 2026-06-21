"""Cross-cutting invariant checks (build guide E)."""

from __future__ import annotations

import ast
from pathlib import Path

from prometheus_client import generate_latest

import argus
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


def _reads_environment(path: Path) -> bool:
    """True if the module reads os.environ / os.getenv (a raw config read)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in {"environ", "getenv"}:
            value = node.value
            if isinstance(value, ast.Name) and value.id == "os":
                return True
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "os"
            and any(alias.name in {"environ", "getenv"} for alias in node.names)
        ):
            return True
    return False


def test_invariant_6_only_config_reads_the_environment() -> None:
    # One config funnel: no module reads env directly except the config objects
    # and the fleet CLI bootstrap. Everything else receives a resolved config.
    root = Path(argus.__file__).parent
    allowed = {
        root / "config.py",
        root / "fleet" / "config.py",
        root / "fleet" / "__main__.py",
    }
    offenders = sorted(
        py.relative_to(root).as_posix()
        for py in root.rglob("*.py")
        if py not in allowed and _reads_environment(py)
    )
    assert offenders == [], f"only config may read the environment (invariant 6): {offenders}"


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
