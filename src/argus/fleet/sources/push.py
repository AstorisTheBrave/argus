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

"""PushSource: derive fleet metrics from member-pushed snapshots (zero infra).

Each member POSTs ``build_snapshot(...)`` on every heartbeat; the registry keeps
the latest snapshot per cluster. This source parses that snapshot into the fixed
metric keys. Gauges and counts are read directly; error_rate is computed as a
ratio of current totals. Per-second rates (interactions, ratelimits) need two
samples to differentiate and are 0 in v1 - a documented limitation, not a TODO.
"""

from __future__ import annotations

import math
from typing import Any

from argus.core.metrics import build_names
from argus.fleet.model import empty_metrics
from argus.fleet.registry import Registry
from argus.fleet.sources.base import ClusterValues, FleetDataSource


def _num(value: Any) -> float | None:
    """Coerce a snapshot value to float, or None if it is missing/non-numeric."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _samples(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    # Defensive: a pushed snapshot is untrusted; tolerate any malformed shape.
    out: list[dict[str, Any]] = []
    metrics = snapshot.get("metrics")
    if not isinstance(metrics, dict):
        return out
    for family in metrics.values():
        if not isinstance(family, dict):
            continue
        samples = family.get("samples")
        if isinstance(samples, list):
            out.extend(s for s in samples if isinstance(s, dict))
    return out


def _sum_by_name(samples: list[dict[str, Any]], name: str) -> float:
    total = 0.0
    for s in samples:
        if s.get("name") == name:
            value = _num(s.get("value"))
            if value is not None:
                total += value
    return total


def _max_by_name(samples: list[dict[str, Any]], name: str) -> float:
    values = [
        v for s in samples if s.get("name") == name and (v := _num(s.get("value"))) is not None
    ]
    return max(values) if values else 0.0


def _percentile_from_histogram(
    samples: list[dict[str, Any]], family: str, quantile: float
) -> float:
    """Estimate a quantile from cumulative histogram buckets (sum over series)."""
    buckets: dict[float, float] = {}
    for s in samples:
        if s.get("name") != f"{family}_bucket":
            continue
        labels = s.get("labels")
        raw = labels.get("le") if isinstance(labels, dict) else None
        bound = float("inf") if raw in ("+Inf", "Inf") else _num(raw)
        value = _num(s.get("value"))
        if bound is None or value is None:
            continue
        buckets[bound] = buckets.get(bound, 0.0) + value
    if not buckets:
        return 0.0
    ordered = sorted(buckets.items())
    total = ordered[-1][1]
    if total <= 0:
        return 0.0
    target = quantile * total
    for bound, cumulative in ordered:
        if cumulative >= target:
            return 0.0 if bound == float("inf") else bound
    return 0.0


def derive_metrics(
    snapshot: dict[str, Any] | None, namespace: str
) -> tuple[dict[str, float], tuple[float, float]]:
    """Return ``(display_metrics, (errors_total, commands_total))`` from a snapshot."""
    metrics = empty_metrics()
    if not snapshot:
        return metrics, (0.0, 0.0)

    names = build_names(namespace)
    samples = _samples(snapshot)

    metrics["latency_seconds"] = _max_by_name(samples, names.shard_latency_seconds)
    metrics["shards_up"] = _sum_by_name(samples, names.shard_up)
    metrics["guilds"] = _sum_by_name(samples, names.guilds)
    metrics["cached_users"] = _sum_by_name(samples, names.cached_users)
    metrics["uptime_seconds"] = _max_by_name(samples, names.uptime_seconds)
    metrics["duration_p95_seconds"] = _percentile_from_histogram(
        samples, names.app_command_duration_seconds, 0.95
    )

    errors = _sum_by_name(samples, names.command_errors_total)
    commands = _sum_by_name(samples, names.app_commands_total) + _sum_by_name(
        samples, names.commands_total
    )
    metrics["error_rate"] = errors / commands if commands else 0.0
    # interactions_rate / ratelimits_rate stay 0.0 (need two samples; v1 limit).
    return metrics, (errors, commands)


class PushSource(FleetDataSource):
    """Build fleet values from the latest snapshot the registry holds per cluster."""

    __slots__ = ("_namespace",)

    def __init__(self, namespace: str = "discord") -> None:
        self._namespace = namespace

    async def cluster_values(self, registry: Registry) -> ClusterValues:
        values = ClusterValues()
        for entry in registry.entries():
            metrics, totals = derive_metrics(entry.last_snapshot, self._namespace)
            values.metrics[entry.identity] = metrics
            values.error_totals[entry.identity] = totals
        return values
