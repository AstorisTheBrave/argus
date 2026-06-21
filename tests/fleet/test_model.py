"""The normalized fleet model: shape, defaults, JSON-serialisability."""

from __future__ import annotations

import json
from dataclasses import asdict

from argus.fleet.model import (
    METRIC_KEYS,
    ClusterView,
    FleetGroupView,
    FleetView,
    empty_metrics,
)


def test_empty_metrics_has_every_key_zeroed() -> None:
    metrics = empty_metrics()
    assert set(metrics) == set(METRIC_KEYS)
    assert all(v == 0.0 for v in metrics.values())


def test_cluster_view_defaults() -> None:
    cv = ClusterView(number=1, identity="a", fleet="asia", status="up", last_seen="t")
    assert cv.metrics == empty_metrics()
    assert cv.shards == []


def test_cluster_view_with_shards_serialises() -> None:
    from dataclasses import asdict

    from argus.fleet.model import ShardView

    cv = ClusterView(
        number=1,
        identity="a",
        fleet="asia",
        status="up",
        last_seen="t",
        shards=[ShardView(shard_id="0", status="up", latency_seconds=0.1)],
    )
    assert asdict(cv)["shards"][0] == {"shard_id": "0", "status": "up", "latency_seconds": 0.1}


def test_fleet_view_to_dict_exposes_global_key() -> None:
    view = FleetView(
        generated_at="t",
        fleets=[
            FleetGroupView(
                name="asia",
                clusters_up=1,
                clusters_total=1,
                clusters=[ClusterView(1, "a", "asia", "up", "t")],
            )
        ],
    )
    data = view.to_dict()
    assert "global" in data
    assert "global_" not in data
    # Whole structure round-trips through JSON.
    assert json.loads(json.dumps(data))["fleets"][0]["name"] == "asia"


def test_dataclasses_are_asdict_serialisable() -> None:
    view = FleetView(generated_at="t")
    assert asdict(view)["global_"] == empty_metrics()
