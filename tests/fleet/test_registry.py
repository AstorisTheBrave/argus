"""Registry: per-fleet monotonic numbering, TTL health, JSON persistence."""

from __future__ import annotations

from pathlib import Path

from argus.fleet.registry import STATUS_DOWN, STATUS_UP, Registry


def _registry(tmp_path: Path, **kwargs: int) -> Registry:
    return Registry(state_path=tmp_path / "state.json", **kwargs)


def test_new_identity_gets_next_number_per_fleet(tmp_path: Path) -> None:
    reg = _registry(tmp_path)
    assert reg.register("a", "asia") == 1
    assert reg.register("b", "asia") == 2
    # Numbering is per-fleet, so europe starts at 1 independently.
    assert reg.register("c", "europe") == 1
    assert reg.register("d", "asia") == 3


def test_known_identity_reclaims_its_number(tmp_path: Path) -> None:
    reg = _registry(tmp_path)
    assert reg.register("a", "asia") == 1
    reg.register("b", "asia")
    # Re-registering "a" keeps its number, does not allocate a new one.
    assert reg.register("a", "asia") == 1


def test_dead_cluster_keeps_number_new_gets_next(tmp_path: Path) -> None:
    reg = _registry(tmp_path, heartbeat_interval=10, ttl_factor=2)
    assert reg.register("a", "asia", now=0.0) == 1
    assert reg.register("b", "asia", now=0.0) == 2
    # "a" goes silent; sweep at t=100 marks it down (TTL = 20).
    reg.sweep(now=100.0)
    entries = {e.identity: e for e in reg.entries()}
    assert entries["a"].status == STATUS_DOWN
    assert entries["b"].status == STATUS_DOWN
    # A brand new identity gets number 3, never the dead one's 1.
    assert reg.register("c", "asia", now=101.0) == 3


def test_reconnect_keeps_number_and_goes_up(tmp_path: Path) -> None:
    reg = _registry(tmp_path, heartbeat_interval=10, ttl_factor=2)
    reg.register("a", "asia", now=0.0)
    reg.sweep(now=100.0)
    assert reg.entries()[0].status == STATUS_DOWN
    # Same identity comes back: same number, status up again.
    assert reg.register("a", "asia", now=101.0) == 1
    assert reg.entries()[0].status == STATUS_UP


def test_heartbeat_refreshes_liveness_and_snapshot(tmp_path: Path) -> None:
    reg = _registry(tmp_path, heartbeat_interval=10, ttl_factor=2)
    reg.register("a", "asia", now=0.0)
    assert reg.heartbeat("a", snapshot={"metrics": {}}, now=50.0) is True
    reg.sweep(now=60.0)  # within TTL of last_seen=50
    entry = reg.entries()[0]
    assert entry.status == STATUS_UP
    assert entry.last_snapshot == {"metrics": {}}


def test_heartbeat_unknown_identity_returns_false(tmp_path: Path) -> None:
    reg = _registry(tmp_path)
    assert reg.heartbeat("ghost") is False


def test_sweep_marks_up_within_ttl(tmp_path: Path) -> None:
    reg = _registry(tmp_path, heartbeat_interval=10, ttl_factor=3)
    reg.register("a", "asia", now=0.0)
    reg.sweep(now=29.0)  # TTL = 30
    assert reg.entries()[0].status == STATUS_UP


def test_fleets_grouping(tmp_path: Path) -> None:
    reg = _registry(tmp_path)
    reg.register("a", "asia")
    reg.register("b", "europe")
    reg.register("c", "asia")
    fleets = reg.fleets()
    assert set(fleets) == {"asia", "europe"}
    assert [e.number for e in fleets["asia"]] == [1, 2]


def test_numbers_never_reused_across_many_cycles(tmp_path: Path) -> None:
    reg = _registry(tmp_path, heartbeat_interval=10, ttl_factor=1)
    seen: set[int] = set()
    for i in range(20):
        number = reg.register(f"id-{i}", "asia", now=float(i * 100))
        assert number not in seen
        seen.add(number)
        reg.sweep(now=float(i * 100 + 1000))  # expire everyone each cycle
    assert seen == set(range(1, 21))


def test_persistence_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    reg = Registry(state_path=path)
    reg.register("a", "asia", now=1.0)
    reg.register("b", "europe", now=2.0)
    reg.heartbeat("a", snapshot={"metrics": {"x": 1}}, now=3.0)
    # A fresh registry over the same file restores counters + entries.
    reloaded = Registry(state_path=path)
    entries = {e.identity: e for e in reloaded.entries()}
    assert entries["a"].number == 1
    assert entries["a"].last_snapshot == {"metrics": {"x": 1}}
    assert entries["b"].fleet == "europe"
    # Counters survive too: next asia identity is 2, not 1.
    assert reloaded.register("c", "asia") == 2


def test_load_no_file_starts_empty(tmp_path: Path) -> None:
    reg = Registry(state_path=tmp_path / "missing.json")
    assert reg.entries() == []
