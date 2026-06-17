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

"""Serialize the live registry into a compact JSON snapshot for the dashboard.

Walking ``CollectorRegistry.collect()`` reuses prometheus_client's collection,
so gauges are still read live at scrape time (invariant 4) and the snapshot
automatically covers every metric Argus exposes. The dashboard SPA computes
rates and histogram quantiles client-side from successive snapshots.
"""

from __future__ import annotations

from typing import Any

from prometheus_client import CollectorRegistry


def build_snapshot(registry: CollectorRegistry) -> dict[str, Any]:
    """Return ``{"metrics": {name: {"type", "samples": [{labels, value}]}}}``."""
    metrics: dict[str, Any] = {}
    for family in registry.collect():
        samples = [
            {"name": sample.name, "labels": dict(sample.labels), "value": sample.value}
            for sample in family.samples
        ]
        metrics[family.name] = {"type": family.type, "samples": samples}
    return {"metrics": metrics}
