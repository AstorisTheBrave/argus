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

"""The data-source seam: every source yields the same normalized values.

A source's only job is to produce per-cluster metric values keyed by identity
(:class:`ClusterValues`). The registry owns topology (number, fleet, health,
last_seen). :func:`assemble` joins the two into a :class:`FleetView` and computes
rollups by fixed rules, so every source renders identically. error_rate is
recomputed from summed totals (never averaged), which is why sources carry the
raw error/command totals alongside the display metrics.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

from argus.fleet.model import (
    METRIC_KEYS,
    ClusterView,
    FleetGroupView,
    FleetView,
    empty_metrics,
)
from argus.fleet.registry import STATUS_UP, Registry

# Rollup rules: how each metric key aggregates across clusters in a group.
_SUM_KEYS = ("shards_up", "guilds", "cached_users", "interactions_rate", "ratelimits_rate")
_MAX_KEYS = ("latency_seconds", "duration_p95_seconds", "uptime_seconds")


@dataclass(slots=True)
class ClusterValues:
    """Per-cluster metric values produced by a source, keyed by identity.

    ``metrics`` maps identity -> a full :data:`METRIC_KEYS` dict (for display).
    ``error_totals`` maps identity -> ``(errors, commands)`` raw counts so the
    rollup can recompute error_rate from summed totals rather than averaging.
    """

    metrics: dict[str, dict[str, float]] = field(default_factory=dict)
    error_totals: dict[str, tuple[float, float]] = field(default_factory=dict)


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _rollup(
    metrics: list[dict[str, float]], error_totals: list[tuple[float, float]]
) -> dict[str, float]:
    out = empty_metrics()
    if not metrics:
        return out
    for key in _SUM_KEYS:
        out[key] = sum(m.get(key, 0.0) for m in metrics)
    for key in _MAX_KEYS:
        out[key] = max(m.get(key, 0.0) for m in metrics)
    errors = sum(e for e, _ in error_totals)
    commands = sum(c for _, c in error_totals)
    out["error_rate"] = errors / commands if commands else 0.0
    return out


def assemble(registry: Registry, values: ClusterValues) -> FleetView:
    """Join registry topology with source ``values`` into a FleetView."""
    fleets: list[FleetGroupView] = []
    all_metrics: list[dict[str, float]] = []
    all_totals: list[tuple[float, float]] = []

    for name, entries in registry.fleets().items():
        clusters: list[ClusterView] = []
        group_metrics: list[dict[str, float]] = []
        group_totals: list[tuple[float, float]] = []
        up = 0
        for entry in entries:
            metrics = values.metrics.get(entry.identity) or empty_metrics()
            totals = values.error_totals.get(entry.identity, (0.0, 0.0))
            errors, commands = totals
            metrics["error_rate"] = errors / commands if commands else 0.0
            clusters.append(
                ClusterView(
                    number=entry.number,
                    identity=entry.identity,
                    fleet=entry.fleet,
                    status=entry.status,
                    last_seen=_iso(entry.last_seen),
                    metrics={k: metrics.get(k, 0.0) for k in METRIC_KEYS},
                )
            )
            if entry.status == STATUS_UP:
                up += 1
            group_metrics.append(metrics)
            group_totals.append(totals)
        fleets.append(
            FleetGroupView(
                name=name,
                clusters_up=up,
                clusters_total=len(entries),
                rollup=_rollup(group_metrics, group_totals),
                clusters=clusters,
            )
        )
        all_metrics.extend(group_metrics)
        all_totals.extend(group_totals)

    return FleetView(
        generated_at=_iso(datetime.now(tz=timezone.utc).timestamp()),
        global_=_rollup(all_metrics, all_totals),
        fleets=fleets,
    )


class FleetDataSource(ABC):
    """A source of per-cluster metric values; topology comes from the registry."""

    @abstractmethod
    async def cluster_values(self, registry: Registry) -> ClusterValues:
        """Return per-cluster metric values keyed by identity."""

    async def fleet_snapshot(self, registry: Registry) -> FleetView:
        """Produce a complete FleetView by joining values with registry topology."""
        return assemble(registry, await self.cluster_values(registry))
