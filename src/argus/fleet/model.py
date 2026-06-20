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

"""The normalized model the fleet UI consumes, independent of data source.

Every data source (push or Prometheus) produces the same :class:`FleetView`
shape, keyed by a fixed, documented set of metric keys (:data:`METRIC_KEYS`), so
the SPA renders identical cards regardless of where the values came from. All
three dataclasses are plain and JSON-serialisable via :func:`dataclasses.asdict`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# The fixed, documented metric keys the UI knows how to render. Sources MUST
# populate these (missing values default to 0.0) and add no others.
METRIC_KEYS: tuple[str, ...] = (
    "latency_seconds",
    "shards_up",
    "guilds",
    "cached_users",
    "interactions_rate",
    "error_rate",
    "duration_p95_seconds",
    "ratelimits_rate",
    "uptime_seconds",
)


def empty_metrics() -> dict[str, float]:
    """A metrics dict with every key present and zeroed."""
    return dict.fromkeys(METRIC_KEYS, 0.0)


@dataclass(slots=True)
class ClusterView:
    """One cluster (a single bot process) as the UI sees it."""

    number: int
    identity: str
    fleet: str
    status: str
    last_seen: str
    metrics: dict[str, float] = field(default_factory=empty_metrics)


@dataclass(slots=True)
class FleetGroupView:
    """One region: its health counts, a rollup, and its member clusters."""

    name: str
    clusters_up: int
    clusters_total: int
    rollup: dict[str, float] = field(default_factory=empty_metrics)
    clusters: list[ClusterView] = field(default_factory=list)


@dataclass(slots=True)
class FleetView:
    """The whole control plane: a global rollup and every fleet."""

    generated_at: str
    global_: dict[str, float] = field(default_factory=empty_metrics)
    fleets: list[FleetGroupView] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """JSON-serialisable dict; ``global_`` is exposed as ``global``."""
        data = asdict(self)
        data["global"] = data.pop("global_")
        return data
