"""Metric catalogue matches spec sec.8; invariant 2 enforced (D3 gate)."""

from __future__ import annotations

import math

from argus.config import ArgusConfig
from argus.core.collector import MetricKind, MetricRegistry
from argus.core.metrics import (
    DURATION_BUCKETS,
    FORBIDDEN_LABELS,
    define_metrics,
)

# Expected (name -> (kind, labelnames)) for the default `discord` namespace.
EXPECTED: dict[str, tuple[MetricKind, tuple[str, ...]]] = {
    "discord_shard_latency_seconds": (MetricKind.GAUGE, ("shard",)),
    "discord_shards_connected": (MetricKind.GAUGE, ("cluster",)),
    "discord_shards_configured": (MetricKind.GAUGE, ("cluster",)),
    "discord_guilds": (MetricKind.GAUGE, ("cluster",)),
    "discord_cached_users": (MetricKind.GAUGE, ("cluster",)),
    "discord_bot": (MetricKind.INFO, ()),
    "argus_up": (MetricKind.GAUGE, ()),
    "discord_interactions_total": (MetricKind.COUNTER, ("type", "status")),
    "discord_app_commands_total": (MetricKind.COUNTER, ("command", "status")),
    "discord_commands_total": (MetricKind.COUNTER, ("command", "status")),
    "discord_command_errors_total": (MetricKind.COUNTER, ("command", "error_type")),
    "discord_gateway_events_total": (MetricKind.COUNTER, ("event",)),
    "discord_shard_disconnects_total": (MetricKind.COUNTER, ("shard",)),
    "discord_shard_reconnects_total": (MetricKind.COUNTER, ("shard",)),
    "discord_log_records_total": (MetricKind.COUNTER, ("logger", "level")),
    "discord_ratelimits_total": (MetricKind.COUNTER, ()),
    "argus_instrumentation_errors_total": (MetricKind.COUNTER, ("hook",)),
    "discord_app_command_duration_seconds": (MetricKind.HISTOGRAM, ("command",)),
}


class _Shard:
    def __init__(self, closed: bool) -> None:
        self._closed = closed

    def is_closed(self) -> bool:
        return self._closed


class _Bot:
    def __init__(self) -> None:
        self.latencies = [(0, 0.1), (1, math.nan)]
        self.shards = {0: _Shard(False), 1: _Shard(True)}
        self.shard_count = 2
        self.guilds = [object(), object(), object()]
        self.users = [object()] * 5

    def is_closed(self) -> bool:
        return False


def _build() -> MetricRegistry:
    reg = MetricRegistry()
    define_metrics(reg, _Bot(), ArgusConfig.resolve(environ={}))
    return reg


def test_catalogue_names_kinds_labels_match_spec() -> None:
    reg = _build()
    got = {name: (m.kind, m.labelnames) for name, m in reg.metrics.items()}
    assert got == EXPECTED


def test_no_forbidden_labels_anywhere() -> None:
    reg = _build()
    for metric in reg.metrics.values():
        assert FORBIDDEN_LABELS.isdisjoint(metric.labelnames), metric.name


def test_namespace_is_applied_and_argus_internals_are_not() -> None:
    reg = MetricRegistry()
    define_metrics(reg, _Bot(), ArgusConfig.resolve(namespace="bot", environ={}))
    names = set(reg.metrics)
    assert "bot_guilds" in names
    assert "bot_app_command_duration_seconds" in names
    # argus_* internals stay un-namespaced
    assert "argus_up" in names
    assert "argus_instrumentation_errors_total" in names


def test_duration_histogram_buckets() -> None:
    reg = _build()
    hist = reg.metrics["discord_app_command_duration_seconds"]
    assert hist.buckets == DURATION_BUCKETS


def test_gauge_callbacks_read_live_state_with_nan_guard() -> None:
    reg = _build()
    m = reg.metrics

    latency = list(m["discord_shard_latency_seconds"].callback())  # type: ignore[misc]
    assert latency == [latency[0]] and len(latency) == 1  # NaN shard dropped
    assert latency[0].labels == ("0",)
    assert latency[0].value == 0.1

    connected = list(m["discord_shards_connected"].callback())  # type: ignore[misc]
    assert connected[0].value == 1.0 and connected[0].labels == ("default",)

    assert list(m["discord_shards_configured"].callback())[0].value == 2.0  # type: ignore[misc]
    assert list(m["discord_guilds"].callback())[0].value == 3.0  # type: ignore[misc]
    assert list(m["discord_cached_users"].callback())[0].value == 5.0  # type: ignore[misc]
    assert list(m["argus_up"].callback())[0].value == 1.0  # type: ignore[misc]


def test_cluster_label_uses_configured_id() -> None:
    reg = MetricRegistry()
    define_metrics(reg, _Bot(), ArgusConfig.resolve(cluster_id="c7", environ={}))
    connected = list(reg.metrics["discord_shards_connected"].callback())  # type: ignore[misc]
    assert connected[0].labels == ("c7",)
