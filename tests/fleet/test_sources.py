"""PushSource and CompositeSource map registry + snapshots to a FleetView."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from argus.fleet.model import empty_metrics
from argus.fleet.registry import STATUS_DOWN, Registry
from argus.fleet.sources.base import ClusterValues, FleetDataSource, assemble
from argus.fleet.sources.composite import CompositeSource
from argus.fleet.sources.push import PushSource, derive_metrics, derive_shards


def _gauge(name: str, value: float, **labels: str) -> dict[str, Any]:
    return {"name": name, "labels": labels, "value": value}


def _snapshot(
    *,
    guilds: float = 0.0,
    users: float = 0.0,
    shards_up: int = 0,
    latency: float = 0.0,
    errors: float = 0.0,
    app_commands: float = 0.0,
    duration_buckets: dict[str, int] | None = None,
) -> dict[str, Any]:
    """A snapshot shaped like dashboard.snapshot.build_snapshot output."""
    metrics: dict[str, Any] = {
        "discord_guilds": {
            "type": "gauge",
            "samples": [_gauge("discord_guilds", guilds, cluster="default")],
        },
        "discord_cached_users": {
            "type": "gauge",
            "samples": [_gauge("discord_cached_users", users, cluster="default")],
        },
        "discord_shard_up": {
            "type": "gauge",
            "samples": [_gauge("discord_shard_up", 1.0, shard=str(i)) for i in range(shards_up)],
        },
        "discord_shard_latency_seconds": {
            "type": "gauge",
            "samples": [_gauge("discord_shard_latency_seconds", latency, shard="0")],
        },
        "discord_command_errors_total": {
            "type": "counter",
            "samples": [
                _gauge("discord_command_errors_total", errors, command="x", cluster="default")
            ],
        },
        "discord_app_commands_total": {
            "type": "counter",
            "samples": [
                _gauge("discord_app_commands_total", app_commands, command="x", cluster="default")
            ],
        },
    }
    if duration_buckets:
        metrics["discord_app_command_duration_seconds"] = {
            "type": "histogram",
            "samples": [
                _gauge("discord_app_command_duration_seconds_bucket", count, le=le)
                for le, count in duration_buckets.items()
            ],
        }
    return {"metrics": metrics}


def test_derive_metrics_reads_gauges_and_counts() -> None:
    snap = _snapshot(guilds=12, users=300, shards_up=3, latency=0.08)
    metrics, totals = derive_metrics(snap, "discord")
    assert metrics["guilds"] == 12
    assert metrics["cached_users"] == 300
    assert metrics["shards_up"] == 3
    assert metrics["latency_seconds"] == 0.08
    assert totals == (0.0, 0.0)
    # Rates with no second sample stay zero (v1 limitation).
    assert metrics["interactions_rate"] == 0.0
    assert metrics["ratelimits_rate"] == 0.0


def test_derive_metrics_error_rate_from_totals() -> None:
    snap = _snapshot(errors=4, app_commands=100)
    metrics, totals = derive_metrics(snap, "discord")
    assert metrics["error_rate"] == pytest.approx(0.04)
    assert totals == (4.0, 100.0)


def test_derive_metrics_no_snapshot_is_zeroed() -> None:
    metrics, totals = derive_metrics(None, "discord")
    assert all(v == 0.0 for v in metrics.values())
    assert totals == (0.0, 0.0)


def test_derive_metrics_p95_from_histogram() -> None:
    # Cumulative buckets: 95th percentile of 100 obs sits in the 1.0 bucket.
    buckets = {"0.05": 10, "0.1": 50, "0.5": 90, "1.0": 99, "2.5": 100, "+Inf": 100}
    snap = _snapshot(duration_buckets=buckets)
    metrics, _ = derive_metrics(snap, "discord")
    assert metrics["duration_p95_seconds"] == 1.0


@pytest.mark.parametrize(
    "garbage",
    [
        {},
        {"metrics": None},
        {"metrics": {"discord_guilds": None}},
        {"metrics": {"discord_guilds": {"samples": "nope"}}},
        {"metrics": {"x": {"samples": [{"name": "discord_guilds"}]}}},  # no value key
        {"metrics": {"x": {"samples": [{"name": "discord_guilds", "value": "NaNish"}]}}},
        {"metrics": {"x": {"samples": [{"labels": {"le": "oops"}, "value": 1}]}}},
        {"unexpected": [1, 2, 3]},
    ],
)
def test_derive_metrics_is_fuzz_safe(garbage: dict[str, Any]) -> None:
    # A malformed or hostile snapshot must never raise; it yields zeroed metrics.
    try:
        metrics, totals = derive_metrics(garbage, "discord")
    except (KeyError, TypeError, ValueError, AttributeError) as exc:  # pragma: no cover
        raise AssertionError(f"derive_metrics raised on garbage input: {exc!r}") from exc
    assert set(metrics) == set(empty_metrics())
    assert totals == (0.0, 0.0)


def test_derive_shards_from_snapshot() -> None:
    snap = _snapshot(shards_up=3, latency=0.08)
    shards = derive_shards(snap, "discord")
    assert [s.shard_id for s in shards] == ["0", "1", "2"]
    assert all(s.status == "up" for s in shards)
    assert shards[0].latency_seconds == 0.08  # latency sample only on shard 0
    assert shards[1].latency_seconds == 0.0


def test_derive_shards_empty_without_data() -> None:
    assert derive_shards(None, "discord") == []
    assert derive_shards({"metrics": {}}, "discord") == []


async def test_push_source_attaches_shards(tmp_path: Path) -> None:
    reg = Registry(state_path=tmp_path / "s.json")
    reg.register("a", "asia", now=0.0)
    reg.heartbeat("a", snapshot=_snapshot(shards_up=2, latency=0.05), now=1.0)
    view = await PushSource("discord").fleet_snapshot(reg)
    cluster = view.fleets[0].clusters[0]
    assert [s.shard_id for s in cluster.shards] == ["0", "1"]


async def test_push_source_builds_fleet_view(tmp_path: Path) -> None:
    reg = Registry(state_path=tmp_path / "s.json")
    reg.register("a", "asia", now=0.0)
    reg.register("b", "asia", now=0.0)
    reg.register("c", "europe", now=0.0)
    reg.heartbeat("a", snapshot=_snapshot(guilds=10, shards_up=2), now=1.0)
    reg.heartbeat("b", snapshot=_snapshot(guilds=5, shards_up=1), now=1.0)
    reg.heartbeat("c", snapshot=_snapshot(guilds=7, shards_up=1), now=1.0)

    view = await PushSource("discord").fleet_snapshot(reg)

    assert {f.name for f in view.fleets} == {"asia", "europe"}
    asia = next(f for f in view.fleets if f.name == "asia")
    assert asia.clusters_total == 2
    assert asia.rollup["guilds"] == 15  # summed
    assert asia.rollup["shards_up"] == 3
    assert view.global_["guilds"] == 22  # 10 + 5 + 7


async def test_push_source_error_rate_rollup_from_totals(tmp_path: Path) -> None:
    reg = Registry(state_path=tmp_path / "s.json")
    reg.register("a", "asia", now=0.0)
    reg.register("b", "asia", now=0.0)
    # 1/10 and 9/10: summed -> 10/20 = 0.5, not the 0.5 average coincidence.
    reg.heartbeat("a", snapshot=_snapshot(errors=1, app_commands=10), now=1.0)
    reg.heartbeat("b", snapshot=_snapshot(errors=9, app_commands=90), now=1.0)
    view = await PushSource("discord").fleet_snapshot(reg)
    asia = view.fleets[0]
    assert asia.rollup["error_rate"] == pytest.approx(10 / 100)


async def test_down_clusters_appear_with_status_down(tmp_path: Path) -> None:
    reg = Registry(state_path=tmp_path / "s.json", heartbeat_interval=10, ttl_factor=2)
    reg.register("a", "asia", now=0.0)
    reg.sweep(now=1000.0)
    view = await PushSource("discord").fleet_snapshot(reg)
    asia = view.fleets[0]
    assert asia.clusters_up == 0
    assert asia.clusters[0].status == STATUS_DOWN


class _StubSource(FleetDataSource):
    def __init__(self, values: ClusterValues) -> None:
        self._values = values

    async def cluster_values(self, registry: Registry) -> ClusterValues:
        return self._values


async def test_composite_first_source_wins_per_cluster(tmp_path: Path) -> None:
    reg = Registry(state_path=tmp_path / "s.json")
    reg.register("a", "asia", now=0.0)
    reg.register("b", "asia", now=0.0)
    primary = ClusterValues(metrics={"a": {"guilds": 1.0}}, error_totals={"a": (0.0, 0.0)})
    fallback = ClusterValues(
        metrics={"a": {"guilds": 999.0}, "b": {"guilds": 2.0}},
        error_totals={"b": (0.0, 0.0)},
    )
    composite = CompositeSource(_StubSource(primary), _StubSource(fallback))
    merged = await composite.cluster_values(reg)
    assert merged.metrics["a"]["guilds"] == 1.0  # primary wins
    assert merged.metrics["b"]["guilds"] == 2.0  # filled from fallback


def test_composite_requires_a_source() -> None:
    with pytest.raises(ValueError, match="at least one source"):
        CompositeSource()


async def test_assemble_handles_missing_values(tmp_path: Path) -> None:
    reg = Registry(state_path=tmp_path / "s.json")
    reg.register("a", "asia", now=0.0)
    view = assemble(reg, ClusterValues())
    assert view.fleets[0].clusters[0].metrics["guilds"] == 0.0
