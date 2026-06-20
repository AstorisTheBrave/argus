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

"""A cross-platform advisory lock on the registry state file.

The registry is not safe for two control-plane processes sharing one state file:
concurrent writers would corrupt it. This takes an OS advisory lock on a sibling
``<state>.lock`` and refuses to start if another process already holds it. The
lock is held by the open file descriptor and released by the OS on process exit,
so there is no stale-lock problem after a crash. Uses ``fcntl`` on POSIX and
``msvcrt`` on Windows; if neither is available it degrades to a no-op.
"""

from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path

if sys.platform == "win32":  # pragma: no cover - platform dependent
    import msvcrt
else:
    import fcntl


class StateLockError(RuntimeError):
    """Raised when the state file is already locked by another process."""


class StateLock:
    """An advisory exclusive lock on ``<state_path>.lock``."""

    __slots__ = ("_fd", "_path")

    def __init__(self, state_path: str | Path) -> None:
        self._path = Path(f"{state_path}.lock")
        self._fd: int | None = None

    def acquire(self) -> None:
        """Take the lock, or raise :class:`StateLockError` if already held."""
        fd = os.open(self._path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            self._lock(fd)
        except OSError as exc:
            os.close(fd)
            raise StateLockError(
                f"another argus-fleet process holds {self._path}; "
                "run a single control plane per state file"
            ) from exc
        self._fd = fd

    def release(self) -> None:
        """Release the lock if held (the OS also releases it on process exit)."""
        if self._fd is None:
            return
        with contextlib.suppress(OSError):
            self._unlock(self._fd)
            os.close(self._fd)
        self._fd = None

    def __enter__(self) -> StateLock:
        self.acquire()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.release()

    @staticmethod
    def _lock(fd: int) -> None:
        if sys.platform == "win32":  # pragma: no cover - platform dependent
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _unlock(fd: int) -> None:
        if sys.platform == "win32":  # pragma: no cover - platform dependent
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(fd, fcntl.LOCK_UN)
