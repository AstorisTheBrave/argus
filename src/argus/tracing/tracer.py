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

"""Command-lifecycle tracing over OpenTelemetry (the ``otlp`` extra).

A span is opened when a command/interaction is received and closed when it
completes or errors, carrying the command name, outcome, and cluster, then
exported over OTLP (Jaeger/Tempo/Grafana). This is intentionally a *lifecycle*
span (receipt -> completion); it does not wrap the user's own handler, so the SDK
stays non-invasive. Span export is batched on OpenTelemetry's own background
thread, so nothing here runs on the bot's event loop, and the instrumentation
layer wraps every call so a tracing fault can never reach the bot (invariant 5).

opentelemetry is imported lazily, so the base package needs no tracing
dependency; install ``argus-dpy[otlp]`` to enable it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class CommandTracer:
    """Thin wrapper over an OpenTelemetry tracer: start a span, finish it later.

    Spans are started in one event handler and finished in another (completion or
    error), so the non-context-manager ``start_span``/``end`` form is used. The
    caller (the instrumentation layer) is responsible for fail-open behaviour; the
    methods here keep the contract small and otel-specific.
    """

    def __init__(self, tracer: Any, provider: Any = None) -> None:
        self._tracer = tracer
        self._provider = provider

    def start(self, name: str, attributes: Mapping[str, str]) -> Any:
        return self._tracer.start_span(name, attributes=dict(attributes))

    def finish(
        self,
        span: Any,
        attributes: Mapping[str, str] | None = None,
        error: BaseException | None = None,
    ) -> None:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        if error is not None:
            span.set_attribute("error.type", type(error).__name__)
        try:
            from opentelemetry.trace import Status, StatusCode  # type: ignore[import-not-found]

            code = StatusCode.ERROR if error is not None else StatusCode.OK  # pragma: no cover
            span.set_status(Status(code))  # pragma: no cover
        except ImportError:
            # Tracing without opentelemetry installed is only reachable under test
            # (production tracing requires the otlp extra); record status plainly.
            span.set_attribute("otel.status_code", "ERROR" if error is not None else "OK")
        finally:
            span.end()

    def shutdown(self) -> None:
        if self._provider is not None:
            self._provider.shutdown()


def build_command_tracer(
    endpoint: str | None, service_name: str
) -> CommandTracer:  # pragma: no cover
    """Build a CommandTracer backed by an OTLP span exporter (needs the otlp extra)."""
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # type: ignore[import-not-found]
        OTLPSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource  # type: ignore[import-not-found]
    from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import-not-found]
    from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore[import-not-found]

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    return CommandTracer(provider.get_tracer("argus"), provider)
