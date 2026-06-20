"""Registry: per-fleet monotonic numbering, TTL health, JSON persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

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
    reg.save()  # mutations coalesce; persistence happens on flush/save
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


def test_mutations_coalesce_no_write_until_flush(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    reg = Registry(state_path=path)
    reg.register("a", "asia", now=0.0)
    # Registration does not touch disk; it only marks the registry dirty.
    assert not path.exists()
    payload = reg.flush_payload()
    assert payload is not None
    reg.write_payload(payload)
    assert path.exists()
    # A second flush with no new mutation returns None (nothing to write).
    assert reg.flush_payload() is None


def test_flush_payload_none_when_clean(tmp_path: Path) -> None:
    reg = Registry(state_path=tmp_path / "state.json")
    assert reg.flush_payload() is None  # nothing registered, not dirty


def test_prune_off_by_default(tmp_path: Path) -> None:
    reg = Registry(state_path=tmp_path / "s.json", heartbeat_interval=10, ttl_factor=1)
    reg.register("a", "asia", now=0.0)
    reg.sweep(now=1_000_000.0)  # long down
    assert reg.prune(now=1_000_000.0) == 0  # retention_days=0 -> never prune
    assert reg.count() == 1


def test_prune_drops_long_dead_keeps_numbers_monotonic(tmp_path: Path) -> None:
    reg = Registry(
        state_path=tmp_path / "s.json", heartbeat_interval=10, ttl_factor=1, retention_days=1
    )
    reg.register("a", "asia", now=0.0)
    reg.register("b", "asia", now=0.0)
    # Two days later both are down and past retention.
    later = 2 * 86400.0
    reg.sweep(now=later)
    assert reg.prune(now=later) == 2
    assert reg.count() == 0
    # Numbers are never reused: the next asia identity is 3, not 1.
    assert reg.register("c", "asia") == 3


def test_prune_keeps_up_clusters(tmp_path: Path) -> None:
    reg = Registry(
        state_path=tmp_path / "s.json", heartbeat_interval=10, ttl_factor=3, retention_days=1
    )
    reg.register("a", "asia", now=2 * 86400.0)  # seen recently relative to now below
    reg.sweep(now=2 * 86400.0)
    assert reg.prune(now=2 * 86400.0) == 0  # still up
    assert reg.count() == 1


def test_state_schema_version_persisted_and_loaded(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    reg = Registry(state_path=path)
    reg.register("a", "asia", now=1.0)
    reg.save()

    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 1
    Registry(state_path=path)  # reloads without error


def test_unknown_schema_version_refuses_to_load(tmp_path: Path) -> None:

    path = tmp_path / "s.json"
    path.write_text(json.dumps({"version": 99, "counters": {}, "entries": []}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="unsupported fleet state schema version"):
        Registry(state_path=path)
