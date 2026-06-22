"""Command-lifecycle tracing: span begin/end, fail-open, and real OTLP spans."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from argus.config import ArgusConfig
from argus.core.collector import MetricRegistry
from argus.core.instrumentation import Instrumentation
from argus.core.metrics import define_metrics
from argus.tracing import CommandTracer
from tests.conftest import CountingBackend, FakeBot


class FakeTracer:
    """Records start/finish calls; can be told to fail to test fail-open."""

    def __init__(self, fail: bool = False) -> None:
        self.started: list[dict[str, Any]] = []
        self.finished: list[dict[str, Any]] = []
        self.fail = fail

    def start(self, name: str, attributes: dict[str, str]) -> Any:
        if self.fail:
            raise RuntimeError("tracer boom")
        span = {"name": name, "attributes": dict(attributes)}
        self.started.append(span)
        return span

    def finish(
        self,
        span: Any,
        attributes: dict[str, str] | None = None,
        error: BaseException | None = None,
    ) -> None:
        self.finished.append({"span": span, "attributes": dict(attributes or {}), "error": error})


def _instr(tracer: Any, *, per_guild: bool = False) -> tuple[Instrumentation, CountingBackend]:
    config = ArgusConfig.resolve(enable_per_guild=per_guild, environ={})
    registry = MetricRegistry()
    names = define_metrics(registry, FakeBot(), config)
    backend = CountingBackend()
    registry.attach(backend)
    return Instrumentation(registry, names, config, tracer=tracer), backend


def _app_interaction(iid: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        id=iid,
        type=SimpleNamespace(name="application_command"),
        command=SimpleNamespace(qualified_name="ping"),
        guild_id=42,
        created_at=None,
    )


def _ctx(mid: int = 7) -> SimpleNamespace:
    return SimpleNamespace(
        message=SimpleNamespace(id=mid, created_at=None),
        command=SimpleNamespace(qualified_name="hello"),
    )


async def test_app_command_opens_and_closes_a_span() -> None:
    tracer = FakeTracer()
    instr, _ = _instr(tracer)
    inter = _app_interaction()
    await instr.on_interaction(inter)
    await instr.on_app_command_completion(inter, SimpleNamespace(qualified_name="ping"))

    assert tracer.started[0]["name"] == "discord.app_command"
    assert tracer.finished[0]["attributes"]["discord.command"] == "ping"
    assert tracer.finished[0]["attributes"]["discord.outcome"] == "success"
    assert tracer.finished[0]["error"] is None


async def test_app_command_error_sets_error_on_span() -> None:
    tracer = FakeTracer()
    instr, _ = _instr(tracer)
    inter = _app_interaction()
    await instr.on_interaction(inter)
    instr.app_command_error(inter, ValueError("nope"))

    assert tracer.finished[0]["attributes"]["discord.outcome"] == "error"
    assert isinstance(tracer.finished[0]["error"], ValueError)


async def test_prefix_command_span_round_trip() -> None:
    tracer = FakeTracer()
    instr, _ = _instr(tracer)
    ctx = _ctx()
    await instr.on_command(ctx)
    await instr.on_command_completion(ctx)

    assert tracer.started[0]["name"] == "discord.command"
    assert tracer.finished[0]["attributes"]["discord.command"] == "hello"


async def test_guild_id_attribute_only_when_per_guild() -> None:
    tracer = FakeTracer()
    instr, _ = _instr(tracer, per_guild=True)
    await instr.on_interaction(_app_interaction())
    assert tracer.started[0]["attributes"]["discord.guild_id"] == "42"

    plain = FakeTracer()
    instr2, _ = _instr(plain)
    await instr2.on_interaction(_app_interaction())
    assert "discord.guild_id" not in plain.started[0]["attributes"]


async def test_non_command_interaction_opens_no_span() -> None:
    tracer = FakeTracer()
    instr, _ = _instr(tracer)
    component = SimpleNamespace(id=2, type=SimpleNamespace(name="component"), created_at=None)
    await instr.on_interaction(component)
    assert tracer.started == []


async def test_tracing_is_fail_open() -> None:
    tracer = FakeTracer(fail=True)
    instr, backend = _instr(tracer)
    await instr.on_interaction(_app_interaction())  # must not raise
    # The metric still recorded even though the span failed to start.
    assert (
        backend.count(
            instr._n.interactions_total,
            type="application_command",
            status="received",
            cluster="default",
        )
        == 1
    )


async def test_no_tracer_is_a_noop() -> None:
    instr, backend = _instr(None)
    inter = _app_interaction()
    await instr.on_interaction(inter)
    await instr.on_app_command_completion(inter, SimpleNamespace(qualified_name="ping"))
    assert (
        backend.count(
            instr._n.app_commands_total, command="ping", status="success", cluster="default"
        )
        == 1
    )


async def test_oldest_span_is_evicted_and_ended(monkeypatch: Any) -> None:
    import argus.core.instrumentation as instr_mod

    monkeypatch.setattr(instr_mod, "_MAX_PENDING", 1)
    tracer = FakeTracer()
    instr, _ = _instr(tracer)
    await instr.on_interaction(_app_interaction(iid=1))
    await instr.on_interaction(_app_interaction(iid=2))  # evicts span 1
    # The evicted span was finished (ended) so it cannot leak.
    assert len(tracer.finished) == 1


# --- CommandTracer wrapper (env-independent: works with or without otel) ---


class _FakeSpan:
    def __init__(self) -> None:
        self.attributes: dict[str, Any] = {}
        self.status: Any = None
        self.ended = False

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def set_status(self, status: Any) -> None:
        self.status = status

    def end(self) -> None:
        self.ended = True


class _FakeOtelTracer:
    def __init__(self) -> None:
        self.span = _FakeSpan()

    def start_span(self, name: str, attributes: dict[str, str] | None = None) -> _FakeSpan:
        self.span.attributes.update(attributes or {})
        return self.span


def test_command_tracer_sets_attributes_and_ends_span() -> None:
    span = CommandTracer(_FakeOtelTracer()).start("discord.app_command", {"cluster": "a"})
    CommandTracer(_FakeOtelTracer()).finish(
        span, {"discord.command": "ping", "discord.outcome": "success"}
    )
    assert span.attributes["discord.command"] == "ping"
    assert span.ended
    # Status recorded either via otel set_status or the no-otel fallback attribute.
    assert span.status is not None or span.attributes.get("otel.status_code") == "OK"


def test_command_tracer_records_error_type() -> None:
    tracer = CommandTracer(_FakeOtelTracer())
    span = tracer.start("x", {})
    tracer.finish(span, error=ValueError("nope"))
    assert span.attributes["error.type"] == "ValueError"
    assert span.ended


def test_real_otlp_span_is_exported() -> None:
    # Proves end-to-end tracing with real OpenTelemetry when it is installed.
    pytest.importorskip("opentelemetry.sdk.trace")
    from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import-not-found]
    from opentelemetry.sdk.trace.export import (  # type: ignore[import-not-found]
        SimpleSpanProcessor,
    )
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # type: ignore[import-not-found]
        InMemorySpanExporter,
    )

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = CommandTracer(provider.get_tracer("argus-test"), provider)

    instr, _ = _instr(tracer)

    async def _run() -> None:
        inter = _app_interaction()
        await instr.on_interaction(inter)
        await instr.on_app_command_completion(inter, SimpleNamespace(qualified_name="ping"))

    import asyncio

    asyncio.run(_run())

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "discord.app_command"
    assert spans[0].attributes["discord.command"] == "ping"
