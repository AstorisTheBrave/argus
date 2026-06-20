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

"""In-memory token-bucket rate limiting for the control plane.

A runaway member, a registration flood, or a hostile script must not be able to
drive unbounded work or registry growth. These limiters are per-key (per identity
for heartbeats, per remote IP for registrations), single-instance (matching the
single-writer registry), and themselves bounded: the keyed store evicts the
oldest bucket past ``max_keys`` so a wide IP flood cannot grow memory either.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable

Clock = Callable[[], float]


class TokenBucket:
    """A classic token bucket: ``burst`` capacity, refilled over ``window`` seconds."""

    __slots__ = ("_capacity", "_clock", "_last", "_rate", "_tokens")

    def __init__(self, burst: int, window: float = 60.0, clock: Clock = time.monotonic) -> None:
        self._capacity = float(burst)
        self._rate = burst / window if window > 0 else float("inf")
        self._tokens = float(burst)
        self._clock = clock
        self._last = clock()

    def allow(self, cost: float = 1.0) -> bool:
        now = self._clock()
        self._tokens = min(self._capacity, self._tokens + (now - self._last) * self._rate)
        self._last = now
        if self._tokens >= cost:
            self._tokens -= cost
            return True
        return False


class KeyedRateLimiter:
    """One token bucket per key, with a bounded number of tracked keys."""

    __slots__ = ("_buckets", "_burst", "_clock", "_max_keys", "_window")

    def __init__(
        self,
        burst: int,
        window: float = 60.0,
        *,
        max_keys: int = 10000,
        clock: Clock = time.monotonic,
    ) -> None:
        self._burst = burst
        self._window = window
        self._max_keys = max_keys
        self._clock = clock
        self._buckets: OrderedDict[str, TokenBucket] = OrderedDict()

    def allow(self, key: str) -> bool:
        bucket = self._buckets.get(key)
        if bucket is None:
            if len(self._buckets) >= self._max_keys:
                self._buckets.popitem(last=False)  # evict the oldest tracked key
            bucket = TokenBucket(self._burst, self._window, self._clock)
            self._buckets[key] = bucket
        else:
            self._buckets.move_to_end(key)
        return bucket.allow()
