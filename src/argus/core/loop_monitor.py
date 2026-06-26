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

"""Event-loop lag sampler.

Loop lag - how late a timer actually fires versus when it was scheduled - is the
single most useful health signal for an async bot: it catches the "alive but
blocked" failure mode (a sync call hogging the loop) that the gateway heartbeat
alone misses. It is inherently temporal, so unlike Argus' other gauges it needs a
tiny background sampler rather than a pure scrape-time read; the
``argus_event_loop_lag_seconds`` gauge then reports the latest sample live. The
sampler is a single cheap task, fail-open, and cancelled on shutdown.
"""

from __future__ import annotations

import asyncio
import contextlib


class LoopMonitor:
    """Samples event-loop scheduling lag into ``lag`` (seconds)."""

    def __init__(self, interval: float = 1.0) -> None:
        self._interval = interval
        self.lag = 0.0
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            scheduled = loop.time() + self._interval
            await asyncio.sleep(self._interval)
            # How long past the scheduled wake-up we actually resumed: that delay
            # is the loop's scheduling lag at this moment.
            self.lag = max(0.0, loop.time() - scheduled)

    async def aclose(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
