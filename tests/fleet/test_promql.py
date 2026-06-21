"""The PromQL catalog covers every metric key and is well-formed."""

from __future__ import annotations

from argus.fleet.model import METRIC_KEYS
from argus.fleet.promql import build_queries, catalog_keys, error_total_queries


def test_catalog_covers_every_metric_key() -> None:
    assert catalog_keys() == set(METRIC_KEYS)


def test_queries_are_namespaced_and_grouped() -> None:
    for q in build_queries("mybot"):
        assert q.promql_global  # non-empty
        # Grouped by the cluster label (p95 also groups by le).
        assert "cluster)" in q.promql_by_cluster
        # Each query references the configured namespace, not the default.
        assert "mybot_" in q.promql_by_cluster


def test_thresholds_present_where_meaningful() -> None:
    by_key = {q.key: q for q in build_queries()}
    assert by_key["error_rate"].higher_is_worse is True
    assert by_key["error_rate"].bad == 0.05
    assert by_key["guilds"].warn is None  # counts are not thresholded


def test_shard_queries_group_by_cluster_and_shard() -> None:
    from argus.fleet.promql import shard_queries

    up, latency = shard_queries("mybot")
    assert "by (cluster, shard)" in up
    assert "mybot_shard_up" in up
    assert "mybot_shard_latency_seconds" in latency


def test_error_total_queries_group_by_cluster() -> None:
    errors, commands = error_total_queries("mybot")
    assert "mybot_command_errors_total" in errors
    assert "mybot_app_commands_total" in commands
    assert "by (cluster)" in errors
