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

"""The fleet registry: the source of truth for topology, identity, and health.

Each member has a stable ``identity`` and declares its ``fleet`` (region). The
registry assigns a per-fleet, monotonic ``number`` that is never reused: a dead
cluster keeps its number and is shown ``down``; a new cluster gets the next
number, not the dead one's; a reconnecting identity reclaims its own number.
Health is a lease: a cluster is ``up`` while ``now - last_seen`` is within the
heartbeat TTL, else ``down``. State is persisted to a JSON file so numbers and
history survive a control-plane restart.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

STATUS_UP = "up"
STATUS_DOWN = "down"

# Bump only on an incompatible on-disk format change; load refuses unknown
# versions rather than silently truncating.
SCHEMA_VERSION = 1
_SECONDS_PER_DAY = 86400


@dataclass(slots=True)
class ClusterEntry:
    """One registered cluster (a single Argus-instrumented bot process)."""

    identity: str
    fleet: str
    number: int
    first_seen: float
    last_seen: float
    status: str = STATUS_UP
    version: str = ""
    last_snapshot: dict[str, Any] | None = None


class Registry:
    """In-memory topology with JSON persistence and per-fleet numbering.

    Not thread-safe by design: the fleet server drives it from a single aiohttp
    event loop, so all mutations are serialized on that loop.
    """

    __slots__ = (
        "_counters",
        "_dirty",
        "_entries",
        "_heartbeat_interval",
        "_retention_days",
        "_state_path",
        "_ttl_factor",
    )

    def __init__(
        self,
        state_path: str | Path = "argus-fleet-state.json",
        heartbeat_interval: int = 15,
        ttl_factor: int = 3,
        retention_days: int = 0,
    ) -> None:
        self._state_path = Path(state_path)
        self._heartbeat_interval = heartbeat_interval
        self._ttl_factor = ttl_factor
        self._retention_days = retention_days
        self._counters: dict[str, int] = {}
        self._entries: dict[str, ClusterEntry] = {}
        self._dirty = False
        self.load()

    # -- mutation ---------------------------------------------------------

    def register(
        self, identity: str, fleet: str, version: str = "", now: float | None = None
    ) -> int:
        """Register ``identity`` in ``fleet`` and return its stable number.

        A known identity reclaims its existing number (and refreshes its fleet,
        version, and last_seen). A new identity gets ``counter[fleet] + 1``;
        numbers are monotonic per fleet and never reused.
        """
        stamp = time.time() if now is None else now
        existing = self._entries.get(identity)
        if existing is not None:
            existing.fleet = fleet
            existing.version = version
            existing.last_seen = stamp
            existing.status = STATUS_UP
            self._dirty = True
            return existing.number

        number = self._counters.get(fleet, 0) + 1
        self._counters[fleet] = number
        self._entries[identity] = ClusterEntry(
            identity=identity,
            fleet=fleet,
            number=number,
            first_seen=stamp,
            last_seen=stamp,
            status=STATUS_UP,
            version=version,
        )
        self._dirty = True
        return number

    def heartbeat(
        self,
        identity: str,
        snapshot: dict[str, Any] | None = None,
        now: float | None = None,
    ) -> bool:
        """Refresh ``identity``'s liveness (and snapshot). Return False if unknown."""
        entry = self._entries.get(identity)
        if entry is None:
            return False
        entry.last_seen = time.time() if now is None else now
        entry.status = STATUS_UP
        if snapshot is not None:
            entry.last_snapshot = snapshot
        self._dirty = True
        return True

    def sweep(self, now: float | None = None) -> None:
        """Recompute every entry's ``status`` from its last_seen and the TTL."""
        stamp = time.time() if now is None else now
        ttl = self._heartbeat_interval * self._ttl_factor
        for entry in self._entries.values():
            entry.status = STATUS_UP if stamp - entry.last_seen <= ttl else STATUS_DOWN

    def prune(self, now: float | None = None) -> int:
        """Drop entries down longer than ``retention_days`` (0 = never). Return count.

        Per-fleet counters are untouched, so pruned numbers are still never
        reused. Call after :meth:`sweep` so statuses are current.
        """
        if self._retention_days <= 0:
            return 0
        stamp = time.time() if now is None else now
        cutoff = self._retention_days * _SECONDS_PER_DAY
        stale = [
            identity
            for identity, entry in self._entries.items()
            if entry.status == STATUS_DOWN and stamp - entry.last_seen > cutoff
        ]
        for identity in stale:
            del self._entries[identity]
        if stale:
            self._dirty = True
        return len(stale)

    # -- reads ------------------------------------------------------------

    def knows(self, identity: str) -> bool:
        """True if ``identity`` is already registered (re-register, not new)."""
        return identity in self._entries

    def count(self) -> int:
        """Number of registered clusters (up and down)."""
        return len(self._entries)

    def entries(self) -> list[ClusterEntry]:
        """All entries, ordered by fleet then number for stable display."""
        return sorted(self._entries.values(), key=lambda e: (e.fleet, e.number))

    def fleets(self) -> dict[str, list[ClusterEntry]]:
        """Entries grouped by fleet name, each list ordered by number."""
        grouped: dict[str, list[ClusterEntry]] = {}
        for entry in self.entries():
            grouped.setdefault(entry.fleet, []).append(entry)
        return grouped

    # -- persistence ------------------------------------------------------
    #
    # Mutations mark the registry dirty rather than writing on every call: a
    # per-heartbeat full-file rewrite would block the event loop and amplify disk
    # I/O at scale. The serialization (``_serialize``) runs on the loop for a
    # consistent snapshot with no cross-thread dict race; the caller writes the
    # returned bytes off-loop (``write_payload`` via ``run_in_executor``).
    # Numbers are assigned in memory synchronously, so a crash before the next
    # flush only risks losing a few seconds of recent registrations.

    def _serialize(self) -> str:
        payload = {
            "version": SCHEMA_VERSION,
            "counters": self._counters,
            "entries": [asdict(entry) for entry in self._entries.values()],
        }
        return json.dumps(payload)

    def write_payload(self, data: str) -> None:
        """Write a serialized payload to ``state_path`` atomically (off-loop safe)."""
        tmp = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
        tmp.write_text(data, encoding="utf-8")
        tmp.replace(self._state_path)

    def flush_payload(self) -> str | None:
        """If dirty, clear the flag and return a payload to write; else None."""
        if not self._dirty:
            return None
        self._dirty = False
        return self._serialize()

    def save(self) -> None:
        """Serialize and write immediately (synchronous; tests and forced flush)."""
        self.write_payload(self._serialize())
        self._dirty = False

    def load(self) -> None:
        """Load state from ``state_path`` if present; otherwise start empty."""
        if not self._state_path.exists():
            return
        payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        # Files predating versioning have no "version" key; treat as the current
        # format. An explicit unknown version refuses to load (no truncation).
        version = int(payload.get("version", SCHEMA_VERSION))
        if version != SCHEMA_VERSION:
            raise RuntimeError(
                f"unsupported fleet state schema version {version} "
                f"(expected {SCHEMA_VERSION}); refusing to load {self._state_path}"
            )
        self._counters = {str(k): int(v) for k, v in payload.get("counters", {}).items()}
        self._entries = {}
        for raw in payload.get("entries", []):
            entry = ClusterEntry(**raw)
            self._entries[entry.identity] = entry
