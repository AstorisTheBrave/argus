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

"""EventSink ABC, a no-op NullSink, and a non-blocking BatchingSink.

``record`` never blocks or raises into the caller (invariant 3/5): events go on
a bounded queue and are flushed in batches by a background task. On overflow,
events are dropped and counted rather than blocking the bot.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from typing import Any

log = logging.getLogger("argus")

Event = Mapping[str, Any]


class EventSink(ABC):
    """A destination for per-guild analytical events."""

    @abstractmethod
    async def record(self, event: Event) -> None:
        """Enqueue one event for the analytical store."""

    async def aclose(self) -> None:
        """Flush and release resources. Default no-op."""
        return


class NullSink(EventSink):
    """Discards everything. The default when analytics is off (zero overhead)."""

    async def record(self, event: Event) -> None:
        return None


class BatchingSink(EventSink):
    """Bounded queue + background flusher. Subclasses implement ``_flush``."""

    def __init__(
        self,
        *,
        batch_size: int = 100,
        flush_interval: float = 5.0,
        max_queue: int = 10_000,
        on_drop: Callable[[], None] | None = None,
        circuit_threshold: int = 5,
        circuit_cooldown: float = 30.0,
    ) -> None:
        self._queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=max_queue)
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._task: asyncio.Task[None] | None = None
        self._wake = asyncio.Event()
        self._closed = False
        self._on_drop = on_drop
        self.dropped = 0
        # Circuit breaker: after this many consecutive flush failures the sink is
        # marked unhealthy and stops attempting flushes for a cooldown, so it does
        # not hammer a down backing store. The bounded queue sheds load meanwhile.
        self._circuit_threshold = circuit_threshold
        self._circuit_cooldown = circuit_cooldown
        self._fail_streak = 0
        self._open_until = 0.0
        self.healthy = True
        self._on_health: Callable[[bool], None] | None = None

    def set_drop_hook(self, on_drop: Callable[[], None]) -> None:
        """Route a dropped event to a counter (wired by the cog)."""
        self._on_drop = on_drop

    def set_health_hook(self, on_health: Callable[[bool], None]) -> None:
        """Report sink health transitions (wired by the cog to argus_subsystem_up)."""
        self._on_health = on_health

    def _set_healthy(self, healthy: bool) -> None:
        if healthy == self.healthy:
            return
        self.healthy = healthy
        if self._on_health is not None:
            with contextlib.suppress(Exception):
                self._on_health(healthy)

    async def record(self, event: Event) -> None:
        if self._closed:
            return
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            self.dropped += 1
            if self._on_drop is not None:
                with contextlib.suppress(Exception):
                    self._on_drop()
            return
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    @abstractmethod
    async def _flush(self, batch: list[Event]) -> None:
        """Write a batch of events to the backing store."""

    async def _run(self) -> None:
        # The worker must outlive any single transient failure: a raised
        # collection or flush is logged and the loop continues, so one bad batch
        # cannot silently kill the drain and turn every later event into a drop.
        while not (self._closed and self._queue.empty()):
            loop = asyncio.get_running_loop()
            # Circuit open: do not hammer a failing sink. Let the bounded queue
            # shed load (drops are counted at record) until the cooldown elapses.
            # On close we fall through and attempt a final drain regardless.
            if not self._closed and self._open_until > loop.time():
                await asyncio.sleep(min(self._flush_interval, self._open_until - loop.time()))
                continue
            try:
                batch = await self._collect_batch()
            except asyncio.CancelledError:
                raise
            except Exception:  # pragma: no cover - defensive
                log.exception("argus history batch collection failed")
                continue
            if not batch:
                continue
            try:
                await self._flush(batch)
            except asyncio.CancelledError:
                raise
            except Exception:  # a sink failure must not kill the worker
                log.exception("argus history flush failed (%d events dropped)", len(batch))
                self._record_failure(loop.time())
            else:
                self._record_success()

    def _record_failure(self, now: float) -> None:
        self._fail_streak += 1
        if self._fail_streak >= self._circuit_threshold:
            self._open_until = now + self._circuit_cooldown
            self._set_healthy(False)

    def _record_success(self) -> None:
        self._fail_streak = 0
        self._open_until = 0.0
        self._set_healthy(True)

    async def _collect_batch(self) -> list[Event]:
        batch: list[Event] = []
        # Wait for either an item or a close signal, bounded by flush_interval.
        get: asyncio.Future[Any] = asyncio.ensure_future(self._queue.get())
        wake: asyncio.Future[Any] = asyncio.ensure_future(self._wake.wait())
        done, _pending = await asyncio.wait(
            {get, wake}, timeout=self._flush_interval, return_when=asyncio.FIRST_COMPLETED
        )
        if get in done:
            batch.append(get.result())
        else:
            get.cancel()  # nothing was dequeued; safe to cancel
        if wake not in done:
            wake.cancel()
        # Single-consumer worker, so empty() -> get_nowait() cannot race.
        while len(batch) < self._batch_size and not self._queue.empty():
            batch.append(self._queue.get_nowait())
        return batch

    async def aclose(self) -> None:
        self._closed = True
        self._wake.set()
        if self._task is not None:
            await self._task
            self._task = None
