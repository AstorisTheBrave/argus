"""Observability-completeness metrics: process, event-loop lag, ws rate-limit."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from prometheus_client import generate_latest

from argus.adapters.prometheus import PrometheusAdapter
from argus.config import ArgusConfig
from argus.core.collector import MetricRegistry
from argus.core.loop_monitor import LoopMonitor
from argus.core.metrics import define_metrics
from tests.conftest import FakeBot


def _text(adapter: PrometheusAdapter) -> str:
    return generate_latest(adapter.registry).decode()


def test_process_metrics_registered_when_enabled() -> None:
    adapter = PrometheusAdapter(process_metrics=True)
    text = _text(adapter)
    # PlatformCollector + GCCollector are cross-platform; ProcessCollector's
    # process_* series are Linux-only (no-op on Windows), so assert the portable
    # ones to prove the collectors registered.
    assert "python_info" in text
    assert "python_gc_" in text


def test_process_metrics_absent_by_default() -> None:
    assert "python_info" not in _text(PrometheusAdapter())


def test_event_loop_lag_gauge_reflects_monitor() -> None:
    bot = FakeBot()
    config = ArgusConfig.resolve(environ={})
    registry = MetricRegistry()
    monitor = LoopMonitor()
    monitor.lag = 0.25
    define_metrics(registry, bot, config, loop_monitor=monitor)
    adapter = PrometheusAdapter()
    registry.attach(adapter)
    assert 'discord_event_loop_lag_seconds{cluster="default"} 0.25' in _text(adapter)


def test_no_loop_lag_gauge_without_monitor() -> None:
    bot = FakeBot()
    registry = MetricRegistry()
    define_metrics(registry, bot, ArgusConfig.resolve(environ={}))
    adapter = PrometheusAdapter()
    registry.attach(adapter)
    assert "event_loop_lag_seconds" not in _text(adapter)


def test_shard_ws_ratelimited_gauge() -> None:
    from typing import cast

    bot = FakeBot()
    # A shard that reports it is being gateway rate-limited.
    rl_shard = SimpleNamespace(is_closed=lambda: False, is_ws_ratelimited=lambda: True)
    bot.shards = cast(Any, {0: rl_shard})
    registry = MetricRegistry()
    define_metrics(registry, bot, ArgusConfig.resolve(environ={}))
    adapter = PrometheusAdapter()
    registry.attach(adapter)
    assert 'discord_shard_ws_ratelimited{shard="0"} 1.0' in _text(adapter)


def test_shard_ws_ratelimited_defaults_zero_when_unavailable() -> None:
    # The default FakeShard lacks is_ws_ratelimited; the gauge must not error.
    bot = FakeBot()
    registry = MetricRegistry()
    define_metrics(registry, bot, ArgusConfig.resolve(environ={}))
    adapter = PrometheusAdapter()
    registry.attach(adapter)
    assert 'discord_shard_ws_ratelimited{shard="0"} 0.0' in _text(adapter)


async def test_loop_monitor_samples_and_stops() -> None:
    monitor = LoopMonitor(interval=0.01)
    await monitor.start()
    await asyncio.sleep(0.05)  # let it take a few samples
    assert monitor.lag >= 0.0  # a real, non-negative sample
    await monitor.aclose()
    assert monitor._task is None


def test_process_metrics_config_default_and_env() -> None:
    assert ArgusConfig.resolve(environ={}).process_metrics is True
    assert ArgusConfig.resolve(environ={"ARGUS_PROCESS_METRICS": "0"}).process_metrics is False


def test_cog_passes_process_metrics_flag(monkeypatch: Any) -> None:
    from argus import ArgusCog

    cog = ArgusCog(FakeBot(), ArgusConfig.resolve(dashboard=False, environ={}))
    text = generate_latest(cog.adapter.registry).decode()
    assert "python_info" in text  # process metrics on by default
