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


class FailingSink(BatchingSink):
    def __init__(self, fail_times: int, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.fail_times = fail_times
        self.flush_calls = 0

    async def _flush(self, batch: list[Event]) -> None:
        self.flush_calls += 1
        if self.flush_calls <= self.fail_times:
            raise RuntimeError("flush boom")


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


def test_circuit_breaker_state_machine() -> None:
    sink = RecordingSink(circuit_threshold=3, circuit_cooldown=10.0)
    flips: list[bool] = []
    sink.set_health_hook(flips.append)

    assert sink.healthy is True
    sink._record_failure(0.0)
    sink._record_failure(0.0)
    assert sink.healthy is True  # below threshold, still healthy
    sink._record_failure(0.0)  # threshold reached -> open the circuit
    assert sink.healthy is False
    assert sink._open_until == 10.0
    assert flips == [False]

    sink._record_success()  # a good flush closes it again
    assert sink.healthy is True
    assert sink._open_until == 0.0
    assert flips == [False, True]


async def test_failing_flush_marks_sink_unhealthy() -> None:
    sink = FailingSink(
        fail_times=10, batch_size=1, flush_interval=0.01, circuit_threshold=1, circuit_cooldown=10.0
    )
    flips: list[bool] = []
    sink.set_health_hook(flips.append)
    await sink.record({"i": 0})
    for _ in range(50):  # let the worker attempt the (failing) flush
        await asyncio.sleep(0.01)
        if not sink.healthy:
            break
    assert sink.healthy is False
    assert flips and flips[-1] is False
    await sink.aclose()


async def test_aclose_flushes_remainder() -> None:
    sink = RecordingSink(batch_size=100, flush_interval=10.0)
    await sink.record({"i": 1})
    await sink.aclose()
    assert sum(len(b) for b in sink.flushed) == 1
