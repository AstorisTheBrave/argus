"""TrendStore: bounded per-cluster history for the drill-down sparkline."""

from __future__ import annotations

from argus.fleet.trend import TrendStore


def test_record_and_history_oldest_first() -> None:
    store = TrendStore()
    store.record("a", "t1", {"guilds": 1.0})
    store.record("a", "t2", {"guilds": 2.0})
    hist = store.history("a")
    assert [p["t"] for p in hist] == ["t1", "t2"]
    assert hist[1]["metrics"] == {"guilds": 2.0}


def test_history_unknown_is_empty() -> None:
    assert TrendStore().history("nope") == []


def test_points_are_capped() -> None:
    store = TrendStore(max_points=3)
    for i in range(5):
        store.record("a", f"t{i}", {"guilds": float(i)})
    hist = store.history("a")
    assert len(hist) == 3
    assert [p["t"] for p in hist] == ["t2", "t3", "t4"]  # oldest dropped


def test_series_count_is_capped() -> None:
    store = TrendStore(max_series=2)
    store.record("a", "t", {})
    store.record("b", "t", {})
    store.record("c", "t", {})  # evicts "a" (oldest)
    assert store.history("a") == []
    assert store.history("c") != []


def test_record_all() -> None:
    store = TrendStore()
    store.record_all([("a", "t", {"guilds": 1.0}), ("b", "t", {"guilds": 2.0})])
    assert store.history("a")[0]["metrics"] == {"guilds": 1.0}
    assert store.history("b")[0]["metrics"] == {"guilds": 2.0}


def test_recorded_metrics_are_copied() -> None:
    store = TrendStore()
    metrics = {"guilds": 1.0}
    store.record("a", "t", metrics)
    metrics["guilds"] = 99.0  # mutating the source must not change the record
    assert store.history("a")[0]["metrics"] == {"guilds": 1.0}
