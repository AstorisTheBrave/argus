"""The advisory state lock: one holder at a time, re-acquire after release."""

from __future__ import annotations

from pathlib import Path

import pytest

from argus.fleet.lock import StateLock, StateLockError


def test_second_acquire_is_refused(tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    first = StateLock(state)
    first.acquire()
    try:
        with pytest.raises(StateLockError, match="another argus-fleet process"):
            StateLock(state).acquire()
    finally:
        first.release()


def test_release_allows_reacquire(tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    lock = StateLock(state)
    lock.acquire()
    lock.release()
    again = StateLock(state)
    again.acquire()  # no raise now that the first released
    again.release()


def test_context_manager(tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    with StateLock(state):
        with pytest.raises(StateLockError):
            StateLock(state).acquire()
    # Released on exit; a fresh lock acquires cleanly.
    StateLock(state).acquire()
