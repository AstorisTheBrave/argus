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

"""Self-observability for the control plane: monitor the monitor.

Exposes the fleet service's own Prometheus metrics on ``/metrics`` (gated by the
token like every route except health). Cluster gauges are read live from the
registry at scrape time (no background poller, mirroring invariant 4); the
register/heartbeat counters are incremented by the handlers. Labels here are
control-plane self-metrics (``fleet``/``status``), bounded by the operator's
fleet count - never the forbidden guild/user/channel labels.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from prometheus_client import CollectorRegistry, Counter
from prometheus_client.core import GaugeMetricFamily

from argus.fleet.registry import STATUS_UP

if TYPE_CHECKING:
    from collections.abc import Iterator

    from argus.fleet.registry import Registry


class _LiveCollector:
    """Reads the registry at scrape time for cluster up/down gauges."""

    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def collect(self) -> Iterator[Any]:
        fleets = self._registry.fleets()
        clusters = GaugeMetricFamily(
            "argus_fleet_clusters",
            "Registered clusters by fleet and health status.",
            labels=["fleet", "status"],
        )
        total = 0
        for name, entries in fleets.items():
            up = sum(1 for e in entries if e.status == STATUS_UP)
            clusters.add_metric([name, "up"], float(up))
            clusters.add_metric([name, "down"], float(len(entries) - up))
            total += len(entries)
        yield clusters
        yield GaugeMetricFamily(
            "argus_fleet_registry_entries",
            "Total entries in the fleet registry (up and down).",
            value=float(total),
        )


class FleetMetrics:
    """The control plane's own metric registry: live gauges + event counters."""

    __slots__ = ("heartbeats", "registrations", "registry")

    def __init__(self, registry: Registry) -> None:
        self.registry = CollectorRegistry()
        self.registrations = Counter(
            "argus_fleet_registrations_total",
            "Total fleet register calls handled.",
            registry=self.registry,
        )
        self.heartbeats = Counter(
            "argus_fleet_heartbeats_total",
            "Total fleet heartbeat calls handled.",
            registry=self.registry,
        )
        self.registry.register(_LiveCollector(registry))
