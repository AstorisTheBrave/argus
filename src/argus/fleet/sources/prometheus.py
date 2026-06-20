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

"""PrometheusSource: read fleet metric values from an existing Prometheus.

Runs the curated ``by_cluster`` PromQL from :mod:`argus.fleet.promql`, grouping
results by the ``cluster`` label, and maps them onto the fixed metric keys. The
registry still owns topology: values join to entries on ``identity == cluster``
(the bot's ``ARGUS_CLUSTER_ID``). The HTTP query is behind a small client so
tests can inject canned results. Cluster->fleet grouping comes from the registry,
so operational metrics need no extra ``fleet`` label (no added cardinality).
"""

from __future__ import annotations

from typing import Protocol

import aiohttp

from argus.fleet.model import empty_metrics
from argus.fleet.promql import build_queries, error_total_queries
from argus.fleet.registry import Registry
from argus.fleet.sources.base import ClusterValues, FleetDataSource

# A PromQL result row: the metric's labels and its instant value.
QueryResult = list[tuple[dict[str, str], float]]


class PromQueryClient(Protocol):
    """Runs an instant PromQL query, returning ``(labels, value)`` rows."""

    async def query(self, promql: str) -> QueryResult: ...


class HTTPQueryClient:
    """The default client: GET ``{url}/api/v1/query`` and parse the result."""

    __slots__ = ("_url",)

    def __init__(self, url: str) -> None:
        self._url = url.rstrip("/")

    async def query(self, promql: str) -> QueryResult:
        async with (
            aiohttp.ClientSession() as session,
            session.get(f"{self._url}/api/v1/query", params={"query": promql}) as resp,
        ):
            resp.raise_for_status()
            payload = await resp.json()
        rows: QueryResult = []
        for item in payload.get("data", {}).get("result", []):
            labels = {str(k): str(v) for k, v in item.get("metric", {}).items()}
            value = item.get("value", [None, None])[1]
            if value is not None:
                rows.append((labels, float(value)))
        return rows


def _by_cluster(rows: QueryResult) -> dict[str, float]:
    return {labels["cluster"]: value for labels, value in rows if "cluster" in labels}


class PrometheusSource(FleetDataSource):
    """Map curated PromQL results to per-cluster metric values, keyed by cluster."""

    __slots__ = ("_client", "_namespace")

    def __init__(
        self, prometheus_url: str, namespace: str = "discord", client: PromQueryClient | None = None
    ) -> None:
        self._namespace = namespace
        self._client = client if client is not None else HTTPQueryClient(prometheus_url)

    async def cluster_values(self, registry: Registry) -> ClusterValues:
        per_key: dict[str, dict[str, float]] = {}
        for q in build_queries(self._namespace):
            per_key[q.key] = _by_cluster(await self._client.query(q.promql_by_cluster))

        errors_q, commands_q = error_total_queries(self._namespace)
        errors = _by_cluster(await self._client.query(errors_q))
        commands = _by_cluster(await self._client.query(commands_q))

        values = ClusterValues()
        for entry in registry.entries():
            cluster = entry.identity
            metrics = empty_metrics()
            for key, by_cluster in per_key.items():
                metrics[key] = by_cluster.get(cluster, 0.0)
            values.metrics[cluster] = metrics
            values.error_totals[cluster] = (errors.get(cluster, 0.0), commands.get(cluster, 0.0))
        return values
