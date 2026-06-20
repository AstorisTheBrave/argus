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

"""A small, bounded in-memory trend buffer for the cluster drill-down.

Each time the control plane builds a fresh view it appends the per-cluster
metrics here, so the Cluster tab can show a recent sparkline. It is deliberately
tiny and bounded on both axes (points per cluster and number of clusters
tracked) so it cannot grow without limit; it is not a substitute for Prometheus
or the ClickHouse analytical path.
"""

from __future__ import annotations

from collections import OrderedDict, deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

# One recorded point: an ISO timestamp and the metric dict at that time.
TrendPoint = dict[str, object]


class TrendStore:
    """Recent per-identity metric points, bounded in points and series count."""

    __slots__ = ("_max_points", "_max_series", "_series")

    def __init__(self, max_points: int = 60, max_series: int = 10000) -> None:
        self._max_points = max_points
        self._max_series = max_series
        self._series: OrderedDict[str, deque[TrendPoint]] = OrderedDict()

    def record(self, identity: str, when: str, metrics: dict[str, float]) -> None:
        """Append a point for ``identity`` (evicting the oldest series if full)."""
        series = self._series.get(identity)
        if series is None:
            if len(self._series) >= self._max_series:
                self._series.popitem(last=False)
            series = deque(maxlen=self._max_points)
            self._series[identity] = series
        else:
            self._series.move_to_end(identity)
        series.append({"t": when, "metrics": dict(metrics)})

    def record_all(self, clusters: Iterable[tuple[str, str, dict[str, float]]]) -> None:
        """Record many ``(identity, when, metrics)`` points at once."""
        for identity, when, metrics in clusters:
            self.record(identity, when, metrics)

    def history(self, identity: str) -> list[TrendPoint]:
        """The recorded points for ``identity``, oldest first."""
        series = self._series.get(identity)
        return list(series) if series is not None else []
