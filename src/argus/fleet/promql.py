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

"""The readable translation layer: one curated PromQL query per metric key.

This catalog is the single definition of "what a fleet view shows". Each entry
pairs a metric key (:data:`argus.fleet.model.METRIC_KEYS`) with a plain label,
one-line help, unit, optional warn/bad thresholds, and the PromQL to compute it
globally and grouped by the ``cluster`` label. The PrometheusSource runs the
``by_cluster`` queries; the PushSource computes the same keys from snapshots, so
the UI renders identically regardless of source. No PromQL ever reaches the UI.
"""

from __future__ import annotations

from dataclasses import dataclass

from argus.core.metrics import build_names
from argus.fleet.model import METRIC_KEYS


@dataclass(frozen=True, slots=True)
class MetricQuery:
    """A single readable metric: how to compute, name, and judge it."""

    key: str
    label: str
    help: str
    unit: str  # one of: seconds, ratio, count, per_second
    promql_global: str
    promql_by_cluster: str
    warn: float | None = None
    bad: float | None = None
    higher_is_worse: bool = False


def build_queries(namespace: str = "discord") -> list[MetricQuery]:
    """Build the PromQL catalog for ``namespace``; one entry per metric key."""
    n = build_names(namespace)
    rate = "rate({metric}[5m])"

    return [
        MetricQuery(
            key="latency_seconds",
            label="Gateway latency",
            help="Worst per-shard heartbeat latency to Discord.",
            unit="seconds",
            promql_global=f"max({n.shard_latency_seconds})",
            promql_by_cluster=f"max by (cluster) ({n.shard_latency_seconds})",
            warn=0.3,
            bad=1.0,
            higher_is_worse=True,
        ),
        MetricQuery(
            key="shards_up",
            label="Shards up",
            help="Number of shards with an open gateway connection.",
            unit="count",
            promql_global=f"sum({n.shard_up})",
            promql_by_cluster=f"sum by (cluster) ({n.shard_up})",
        ),
        MetricQuery(
            key="guilds",
            label="Guilds",
            help="Guilds the bot is in.",
            unit="count",
            promql_global=f"sum({n.guilds})",
            promql_by_cluster=f"sum by (cluster) ({n.guilds})",
        ),
        MetricQuery(
            key="cached_users",
            label="Cached users",
            help="Users currently in the cache.",
            unit="count",
            promql_global=f"sum({n.cached_users})",
            promql_by_cluster=f"sum by (cluster) ({n.cached_users})",
        ),
        MetricQuery(
            key="interactions_rate",
            label="Interactions/sec",
            help="Interactions received per second (5m average).",
            unit="per_second",
            promql_global=f"sum({rate.format(metric=n.interactions_total)})",
            promql_by_cluster=f"sum by (cluster) ({rate.format(metric=n.interactions_total)})",
        ),
        MetricQuery(
            key="error_rate",
            label="Error rate",
            help="Share of command invocations that errored (5m).",
            unit="ratio",
            promql_global=(
                f"sum({rate.format(metric=n.command_errors_total)}) "
                f"/ sum({rate.format(metric=n.app_commands_total)})"
            ),
            promql_by_cluster=(
                f"sum by (cluster) ({rate.format(metric=n.command_errors_total)}) "
                f"/ sum by (cluster) ({rate.format(metric=n.app_commands_total)})"
            ),
            warn=0.01,
            bad=0.05,
            higher_is_worse=True,
        ),
        MetricQuery(
            key="duration_p95_seconds",
            label="Command p95",
            help="95th percentile application-command duration (5m).",
            unit="seconds",
            promql_global=(
                f"histogram_quantile(0.95, sum by (le) "
                f"(rate({n.app_command_duration_seconds}_bucket[5m])))"
            ),
            promql_by_cluster=(
                f"histogram_quantile(0.95, sum by (le, cluster) "
                f"(rate({n.app_command_duration_seconds}_bucket[5m])))"
            ),
            warn=1.0,
            bad=3.0,
            higher_is_worse=True,
        ),
        MetricQuery(
            key="ratelimits_rate",
            label="Rate limits/sec",
            help="Rate-limit warnings observed per second (5m average).",
            unit="per_second",
            promql_global=f"sum({rate.format(metric=n.ratelimits_total)})",
            promql_by_cluster=f"sum by (cluster) ({rate.format(metric=n.ratelimits_total)})",
            warn=0.1,
            bad=1.0,
            higher_is_worse=True,
        ),
        MetricQuery(
            key="uptime_seconds",
            label="Uptime",
            help="Seconds since the collector started.",
            unit="seconds",
            promql_global=f"max({n.uptime_seconds})",
            promql_by_cluster=f"max by (cluster) ({n.uptime_seconds})",
        ),
    ]


# error_rate is recomputed from totals in rollups, so the source needs the raw
# numerator/denominator per cluster. These name the metrics it sums.
def error_total_queries(namespace: str = "discord") -> tuple[str, str]:
    """Return ``(errors_by_cluster, commands_by_cluster)`` PromQL for rollups."""
    n = build_names(namespace)
    return (
        f"sum by (cluster) ({n.command_errors_total})",
        f"sum by (cluster) ({n.app_commands_total})",
    )


def catalog_keys(namespace: str = "discord") -> set[str]:
    """The metric keys the catalog covers (must equal METRIC_KEYS)."""
    return {q.key for q in build_queries(namespace)}


assert catalog_keys() == set(METRIC_KEYS), "promql catalog must cover every metric key"
