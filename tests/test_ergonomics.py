"""Ergonomic wrappers: argus.timed / timer / count_exceptions / span."""

from __future__ import annotations

from typing import Any

import pytest

from argus.config import ArgusConfig
from argus.core.collector import MetricRegistry
from argus.ergonomics import DEFAULT_BUCKETS, Telemetry
from tests.conftest import CountingBackend


def _telemetry(tracer: Any = None) -> tuple[Telemetry, CountingBackend]:
    registry = MetricRegistry()
    backend = CountingBackend()
    registry.attach(backend)
    config = ArgusConfig.resolve(environ={})
    return Telemetry(registry, config.namespace, "default", tracer=tracer), backend


def test_default_buckets_are_otel_recommended() -> None:
    assert DEFAULT_BUCKETS[0] == 0.005 and DEFAULT_BUCKETS[-1] == 10.0


def test_timer_records_duration() -> None:
    tel, backend = _telemetry()
    with tel.timer("work"):
        pass
    assert backend.observations.get("discord_work_duration_seconds")


def test_timed_decorator_sync() -> None:
    tel, backend = _telemetry()

    @tel.timed("job")
    def f(x: int) -> int:
        return x * 2

    assert f(3) == 6
    assert len(backend.observations["discord_job_duration_seconds"]) == 1


async def test_timed_decorator_async() -> None:
    tel, backend = _telemetry()

    @tel.timed("ajob")
    async def f(x: int) -> int:
        return x + 1

    assert await f(41) == 42
    assert len(backend.observations["discord_ajob_duration_seconds"]) == 1


def test_count_exceptions_sync() -> None:
    tel, backend = _telemetry()

    @tel.count_exceptions("risky")
    def boom() -> None:
        raise ValueError("nope")

    with pytest.raises(ValueError):
        boom()
    assert (
        backend.count(
            "discord_risky_exceptions_total", exception_type="ValueError", cluster="default"
        )
        == 1
    )


async def test_count_exceptions_async_reraises() -> None:
    tel, backend = _telemetry()

    @tel.count_exceptions("arisky")
    async def boom() -> None:
        raise KeyError("k")

    with pytest.raises(KeyError):
        await boom()
    assert (
        backend.count(
            "discord_arisky_exceptions_total", exception_type="KeyError", cluster="default"
        )
        == 1
    )


def test_timed_reused_name_defines_metric_once() -> None:
    tel, backend = _telemetry()
    tel.timed("dup")
    tel.timed("dup")  # second use must not raise on re-definition
    with tel.timer("dup"):
        pass
    assert len(backend.observations["discord_dup_duration_seconds"]) == 1


def test_span_is_noop_without_tracer() -> None:
    tel, _ = _telemetry(tracer=None)
    with tel.span("unit"):  # must not raise when tracing is disabled
        pass


def test_span_uses_tracer_and_records_error() -> None:
    class FakeTracer:
        def __init__(self) -> None:
            self.started: list[str] = []
            self.finished: list[Any] = []

        def start(self, name: str, attributes: dict[str, str]) -> dict[str, Any]:
            self.started.append(name)
            return {"name": name}

        def finish(self, span: Any, attributes: Any = None, error: Any = None) -> None:
            self.finished.append(error)

    tracer = FakeTracer()
    tel, _ = _telemetry(tracer=tracer)
    with pytest.raises(RuntimeError):
        with tel.span("op"):
            raise RuntimeError("x")
    assert tracer.started == ["op"]
    assert isinstance(tracer.finished[0], RuntimeError)


def test_argus_exposes_helpers() -> None:
    from argus import Argus
    from tests.conftest import FakeBot

    argus = Argus(FakeBot(), dashboard=False)

    @argus.timed("via_facade")
    def f() -> int:
        return 1

    assert f() == 1
    text_registry = argus.cog.registry.metrics
    assert "discord_via_facade_duration_seconds" in text_registry
