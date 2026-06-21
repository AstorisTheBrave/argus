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

import asyncio
from typing import Protocol

import aiohttp

from argus.fleet.model import ShardView, empty_metrics
from argus.fleet.promql import build_queries, error_total_queries, shard_queries
from argus.fleet.registry import STATUS_DOWN, STATUS_UP, Registry
from argus.fleet.sources.base import ClusterValues, FleetDataSource

# A PromQL result row: the metric's labels and its instant value.
QueryResult = list[tuple[dict[str, str], float]]

# Bound every Prometheus call so a slow/hung Prometheus cannot tie up a view
# request for aiohttp's 5-minute client default.
DEFAULT_QUERY_TIMEOUT = 10.0


class PromQueryClient(Protocol):
    """Runs an instant PromQL query, returning ``(labels, value)`` rows."""

    async def query(self, promql: str) -> QueryResult:
        """Run ``promql`` and return ``(labels, value)`` rows."""

    async def aclose(self) -> None:
        """Release any held resources (e.g. an HTTP session)."""


class HTTPQueryClient:
    """The default client: GET ``{url}/api/v1/query``, reusing one session."""

    __slots__ = ("_session", "_timeout", "_url")

    def __init__(self, url: str, timeout: float = DEFAULT_QUERY_TIMEOUT) -> None:
        self._url = url.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None

    def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self._session

    async def query(self, promql: str) -> QueryResult:
        session = self._ensure_session()
        async with session.get(f"{self._url}/api/v1/query", params={"query": promql}) as resp:
            resp.raise_for_status()
            payload = await resp.json()
        rows: QueryResult = []
        for item in payload.get("data", {}).get("result", []):
            labels = {str(k): str(v) for k, v in item.get("metric", {}).items()}
            value = item.get("value", [None, None])[1]
            if value is not None:
                rows.append((labels, float(value)))
        return rows

    async def aclose(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None


def _by_cluster(rows: QueryResult) -> dict[str, float]:
    return {labels["cluster"]: value for labels, value in rows if "cluster" in labels}


def _by_cluster_shard(rows: QueryResult) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for labels, value in rows:
        if "cluster" in labels and "shard" in labels:
            out.setdefault(labels["cluster"], {})[labels["shard"]] = value
    return out


def _build_shards(up: dict[str, float], latency: dict[str, float]) -> list[ShardView]:
    shard_ids = sorted(set(up) | set(latency), key=lambda x: (len(x), x))
    return [
        ShardView(
            shard_id=shard,
            status=STATUS_UP if up.get(shard, 0.0) >= 1.0 else STATUS_DOWN,
            latency_seconds=latency.get(shard, 0.0),
        )
        for shard in shard_ids
    ]


class PrometheusSource(FleetDataSource):
    """Map curated PromQL results to per-cluster metric values, keyed by cluster."""

    __slots__ = ("_client", "_namespace")

    def __init__(
        self, prometheus_url: str, namespace: str = "discord", client: PromQueryClient | None = None
    ) -> None:
        self._namespace = namespace
        self._client = client if client is not None else HTTPQueryClient(prometheus_url)

    async def cluster_values(self, registry: Registry) -> ClusterValues:
        queries = build_queries(self._namespace)
        errors_q, commands_q = error_total_queries(self._namespace)
        shard_up_q, shard_latency_q = shard_queries(self._namespace)
        # Run the whole catalog concurrently: one round-trip of latency, not ~13.
        results = await asyncio.gather(
            *(self._client.query(q.promql_by_cluster) for q in queries),
            self._client.query(errors_q),
            self._client.query(commands_q),
            self._client.query(shard_up_q),
            self._client.query(shard_latency_q),
        )
        per_key = {q.key: _by_cluster(results[i]) for i, q in enumerate(queries)}
        errors = _by_cluster(results[len(queries)])
        commands = _by_cluster(results[len(queries) + 1])
        shard_up = _by_cluster_shard(results[len(queries) + 2])
        shard_latency = _by_cluster_shard(results[len(queries) + 3])

        values = ClusterValues()
        for entry in registry.entries():
            cluster = entry.identity
            metrics = empty_metrics()
            for key, by_cluster in per_key.items():
                metrics[key] = by_cluster.get(cluster, 0.0)
            values.metrics[cluster] = metrics
            values.error_totals[cluster] = (errors.get(cluster, 0.0), commands.get(cluster, 0.0))
            values.shards[cluster] = _build_shards(
                shard_up.get(cluster, {}), shard_latency.get(cluster, {})
            )
        return values

    async def aclose(self) -> None:
        await self._client.aclose()
