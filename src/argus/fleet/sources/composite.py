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

"""CompositeSource: join registry topology with one or more value sources.

Sources are consulted in order; the first to supply values for a given cluster
identity wins. This lets an operator run Prometheus as the primary value source
and push as a fallback (or vice versa) while the registry remains the single
source of topology and health. With one source it is a thin pass-through.
"""

from __future__ import annotations

from argus.fleet.registry import Registry
from argus.fleet.sources.base import ClusterValues, FleetDataSource


class CompositeSource(FleetDataSource):
    """Merge several value sources, earlier sources taking precedence per cluster."""

    __slots__ = ("_sources",)

    def __init__(self, *sources: FleetDataSource) -> None:
        if not sources:
            raise ValueError("CompositeSource needs at least one source")
        self._sources = sources

    async def cluster_values(self, registry: Registry) -> ClusterValues:
        merged = ClusterValues()
        for source in self._sources:
            values = await source.cluster_values(registry)
            for identity, metrics in values.metrics.items():
                if identity not in merged.metrics:
                    merged.metrics[identity] = metrics
                    merged.error_totals[identity] = values.error_totals.get(identity, (0.0, 0.0))
        return merged
