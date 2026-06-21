"""EventSink ABC, NullSink, BatchingSink (plan task 3.1)."""

from __future__ import annotations

import asyncio

from argus.history.sink import BatchingSink, Event, NullSink


class RecordingSink(BatchingSink):
    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.flushed: list[list[Event]] = []

    async def _flush(self, batch: list[Event]) -> None:
        self.flushed.append(list(batch))


async def test_null_sink_is_noop() -> None:
    sink = NullSink()
    await sink.record({"guild_id": "1"})
    await sink.aclose()  # must not raise


async def test_flushes_on_batch_size() -> None:
    sink = RecordingSink(batch_size=3, flush_interval=10.0)
    for i in range(3):
        await sink.record({"i": i})
    await asyncio.sleep(0.05)  # let the worker collect + flush
    await sink.aclose()
    assert [len(b) for b in sink.flushed] == [3]


async def test_flushes_on_interval() -> None:
    sink = RecordingSink(batch_size=100, flush_interval=0.05)
    await sink.record({"i": 0})
    await asyncio.sleep(0.15)  # exceeds the flush interval with one event queued
    await sink.aclose()
    assert sum(len(b) for b in sink.flushed) == 1


async def test_overflow_drops_and_counts() -> None:
    # record() never yields, so the worker cannot drain between these calls;
    # the queue fills deterministically and extra events are dropped.
    sink = RecordingSink(batch_size=100, flush_interval=10.0, max_queue=2)
    for i in range(5):
        await sink.record({"i": i})
    assert sink.dropped == 3
    await sink.aclose()


async def test_overflow_invokes_drop_hook() -> None:
    drops = {"n": 0}
    sink = RecordingSink(batch_size=100, flush_interval=10.0, max_queue=2)
    sink.set_drop_hook(lambda: drops.__setitem__("n", drops["n"] + 1))
    for i in range(5):
        await sink.record({"i": i})
    assert drops["n"] == 3  # one hook call per dropped event
    await sink.aclose()


async def test_aclose_flushes_remainder() -> None:
    sink = RecordingSink(batch_size=100, flush_interval=10.0)
    await sink.record({"i": 1})
    await sink.aclose()
    assert sum(len(b) for b in sink.flushed) == 1
