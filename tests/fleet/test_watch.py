"""IdentityWatch: flag an identity reappearing from a different remote."""

from __future__ import annotations

from argus.fleet.watch import IdentityWatch


def test_first_sighting_is_not_a_conflict() -> None:
    watch = IdentityWatch()
    assert watch.observe("a", "1.1.1.1") is False


def test_same_remote_is_not_a_conflict() -> None:
    watch = IdentityWatch()
    watch.observe("a", "1.1.1.1")
    assert watch.observe("a", "1.1.1.1") is False


def test_changed_remote_is_a_conflict() -> None:
    watch = IdentityWatch()
    watch.observe("a", "1.1.1.1")
    assert watch.observe("a", "2.2.2.2") is True  # duplicate identity, two hosts


def test_none_remote_never_conflicts() -> None:
    watch = IdentityWatch()
    watch.observe("a", "1.1.1.1")
    assert watch.observe("a", None) is False


def test_distinct_identities_are_independent() -> None:
    watch = IdentityWatch()
    assert watch.observe("a", "1.1.1.1") is False
    assert watch.observe("b", "2.2.2.2") is False


def test_store_is_bounded() -> None:
    watch = IdentityWatch(max_keys=2)
    watch.observe("a", "1.1.1.1")
    watch.observe("b", "1.1.1.1")
    watch.observe("c", "1.1.1.1")  # evicts "a"
    # "a" was evicted, so its history is gone: a new remote is a fresh first sight.
    assert watch.observe("a", "9.9.9.9") is False
