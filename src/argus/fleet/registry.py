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
        "_state_path",
        "_ttl_factor",
    )

    def __init__(
        self,
        state_path: str | Path = "argus-fleet-state.json",
        heartbeat_interval: int = 15,
        ttl_factor: int = 3,
    ) -> None:
        self._state_path = Path(state_path)
        self._heartbeat_interval = heartbeat_interval
        self._ttl_factor = ttl_factor
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
        self._counters = {str(k): int(v) for k, v in payload.get("counters", {}).items()}
        self._entries = {}
        for raw in payload.get("entries", []):
            entry = ClusterEntry(**raw)
            self._entries[entry.identity] = entry
