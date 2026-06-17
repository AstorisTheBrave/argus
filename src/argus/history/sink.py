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
import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

log = logging.getLogger("argus")

Event = Mapping[str, Any]


class EventSink(ABC):
    """A destination for per-guild analytical events."""

    @abstractmethod
    async def record(self, event: Event) -> None: ...

    async def aclose(self) -> None:
        """Flush and release resources. Default no-op."""
        return None


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
    ) -> None:
        self._queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=max_queue)
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._task: asyncio.Task[None] | None = None
        self._wake = asyncio.Event()
        self._closed = False
        self.dropped = 0

    async def record(self, event: Event) -> None:
        if self._closed:
            return
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            self.dropped += 1
            return
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    @abstractmethod
    async def _flush(self, batch: list[Event]) -> None: ...

    async def _run(self) -> None:
        while not (self._closed and self._queue.empty()):
            batch = await self._collect_batch()
            if not batch:
                continue
            try:
                await self._flush(batch)
            except Exception:  # pragma: no cover - a sink failure must not kill the worker
                log.exception("argus history flush failed (%d events dropped)", len(batch))

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
        while len(batch) < self._batch_size:
            try:
                batch.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return batch

    async def aclose(self) -> None:
        self._closed = True
        self._wake.set()
        if self._task is not None:
            await self._task
            self._task = None
