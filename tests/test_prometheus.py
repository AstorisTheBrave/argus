"""Prometheus adapter: scrape-time gauges + held metrics (D5 gate)."""

from __future__ import annotations

from prometheus_client import generate_latest

from argus.adapters.prometheus import PrometheusAdapter
from argus.config import ArgusConfig
from argus.core.collector import MetricRegistry
from argus.core.metrics import define_metrics
from tests.conftest import FakeBot


def _exposition() -> tuple[str, object]:
    bot = FakeBot()
    config = ArgusConfig.resolve(environ={})
    registry = MetricRegistry()
    names = define_metrics(registry, bot, config)
    adapter = PrometheusAdapter()
    registry.attach(adapter)
    registry.set_info(names.bot_info, {"discord_py_version": "2.7.1", "argus_version": "0.1.0"})
    registry.inc(
        names.interactions_total,
        {"type": "application_command", "status": "received", "cluster": "default"},
    )
    registry.observe(
        names.app_command_duration_seconds, 0.2, {"command": "ping", "cluster": "default"}
    )
    return generate_latest(adapter.registry).decode(), names


def test_gauges_read_live_bot_state() -> None:
    text, _ = _exposition()
    assert 'discord_guilds{cluster="default"} 3.0' in text
    assert 'discord_cached_users{cluster="default"} 5.0' in text
    assert 'discord_shards_connected{cluster="default"} 1.0' in text
    assert 'discord_shard_latency_seconds{shard="0"} 0.1' in text
    assert "argus_up 1.0" in text


def test_nan_shard_latency_is_not_exposed() -> None:
    text, _ = _exposition()
    assert 'discord_shard_latency_seconds{shard="1"}' not in text


def test_histogram_exposes_bucket_sum_count() -> None:
    text, _ = _exposition()
    assert "discord_app_command_duration_seconds_bucket{" in text
    assert "discord_app_command_duration_seconds_sum{" in text
    assert "discord_app_command_duration_seconds_count{" in text


def test_counter_and_info_exposed() -> None:
    text, _ = _exposition()
    assert "discord_interactions_total{" in text
    assert "discord_bot_info{" in text
    assert 'argus_version="0.1.0"' in text
    assert 'discord_py_version="2.7.1"' in text


def test_no_forbidden_label_in_exposition() -> None:
    text, _ = _exposition()
    for forbidden in ("guild_id", "user_id", "channel_id"):
        assert forbidden not in text
