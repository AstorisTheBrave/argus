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

"""Detect duplicate identities (two processes sharing one CLUSTER_ID/fleet_id).

If two bot processes register/heartbeat under the same identity from different
remote addresses, the registry's number and health flap between them. This watch
records the last remote seen per identity and reports when it changes, so the
control plane can surface a conflict (a metric + a log warning) rather than
silently flapping. The store is bounded (evicts the oldest tracked identity).
"""

from __future__ import annotations

from collections import OrderedDict


class IdentityWatch:
    """Tracks the last remote per identity and flags a change as a conflict."""

    __slots__ = ("_last", "_max_keys")

    def __init__(self, max_keys: int = 10000) -> None:
        self._max_keys = max_keys
        self._last: OrderedDict[str, str] = OrderedDict()

    def observe(self, identity: str, remote: str | None) -> bool:
        """Record ``remote`` for ``identity``; return True if it changed (a conflict)."""
        if remote is None:
            return False
        previous = self._last.get(identity)
        self._last[identity] = remote
        self._last.move_to_end(identity)
        if len(self._last) > self._max_keys:
            self._last.popitem(last=False)
        return previous is not None and previous != remote
