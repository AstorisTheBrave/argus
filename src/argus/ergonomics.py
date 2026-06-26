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

"""Convenience wrappers for instrumenting arbitrary code.

``argus.timed`` / ``argus.timer`` / ``argus.count_exceptions`` / ``argus.span``
let users instrument their own functions without touching the registry, matching
what mature SDKs offer (prometheus_client's ``@histogram.time()``, OTel's
``start_as_current_span``). Everything is fail-open (an instrumentation error
never propagates into the user's code) and works on both sync and ``async def``
callables, since the bot hot path is async.
"""

from __future__ import annotations

import contextlib
import inspect
import time
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any

from argus.core.collector import MetricDef, MetricKind

if TYPE_CHECKING:
    from argus.core.collector import MetricRegistry

# OpenTelemetry's recommended default latency buckets (seconds).
DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0)

_F = Callable[..., Any]


class Telemetry:
    """User-facing custom-metric + span helpers bound to one registry."""

    def __init__(
        self, registry: MetricRegistry, namespace: str, cluster: str, tracer: Any = None
    ) -> None:
        self._registry = registry
        self._ns = namespace
        self._cluster = cluster
        self._tracer = tracer
        self._defined: set[str] = set()

    # --- lazy metric definition (idempotent) ---
    def _histogram(self, name: str) -> str:
        full = f"{self._ns}_{name}_duration_seconds"
        if full not in self._defined:
            with contextlib.suppress(ValueError):
                self._registry.define(
                    MetricDef(
                        full,
                        f"Duration of {name} in seconds.",
                        MetricKind.HISTOGRAM,
                        labelnames=("cluster",),
                        buckets=DEFAULT_BUCKETS,
                    )
                )
            self._defined.add(full)
        return full

    def _counter(self, name: str) -> str:
        full = f"{self._ns}_{name}_exceptions_total"
        if full not in self._defined:
            with contextlib.suppress(ValueError):
                self._registry.define(
                    MetricDef(
                        full,
                        f"Exceptions raised in {name}.",
                        MetricKind.COUNTER,
                        labelnames=("exception_type", "cluster"),
                    )
                )
            self._defined.add(full)
        return full

    def _observe(self, full: str, seconds: float) -> None:
        with contextlib.suppress(Exception):  # never break the user's code
            self._registry.observe(full, seconds, {"cluster": self._cluster})

    def _count(self, full: str, exc: BaseException) -> None:
        with contextlib.suppress(Exception):
            self._registry.inc(
                full, {"exception_type": type(exc).__name__, "cluster": self._cluster}
            )

    # --- timing ---
    def timer(self, name: str) -> _Timer:
        """Context manager timing the enclosed block into a histogram."""
        return _Timer(self, self._histogram(name))

    def timed(self, name: str) -> Callable[[_F], _F]:
        """Decorator timing a sync or async callable into a histogram."""
        full = self._histogram(name)

        def decorate(fn: _F) -> _F:
            if inspect.iscoroutinefunction(fn):

                @wraps(fn)
                async def awrapper(*args: Any, **kwargs: Any) -> Any:
                    start = time.perf_counter()
                    try:
                        return await fn(*args, **kwargs)
                    finally:
                        self._observe(full, time.perf_counter() - start)

                return awrapper

            @wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                start = time.perf_counter()
                try:
                    return fn(*args, **kwargs)
                finally:
                    self._observe(full, time.perf_counter() - start)

            return wrapper

        return decorate

    # --- exception counting ---
    def count_exceptions(self, name: str) -> Callable[[_F], _F]:
        """Decorator counting exceptions raised by a sync or async callable."""
        full = self._counter(name)

        def decorate(fn: _F) -> _F:
            if inspect.iscoroutinefunction(fn):

                @wraps(fn)
                async def awrapper(*args: Any, **kwargs: Any) -> Any:
                    try:
                        return await fn(*args, **kwargs)
                    except Exception as exc:
                        self._count(full, exc)
                        raise

                return awrapper

            @wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:
                    self._count(full, exc)
                    raise

            return wrapper

        return decorate

    # --- tracing ---
    def span(self, name: str) -> _Span:
        """Context manager opening a span (no-op if tracing is disabled)."""
        return _Span(self._tracer, name, self._cluster)


class _Timer:
    __slots__ = ("_full", "_start", "_telemetry")

    def __init__(self, telemetry: Telemetry, full: str) -> None:
        self._telemetry = telemetry
        self._full = full
        self._start = 0.0

    def __enter__(self) -> _Timer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> None:
        self._telemetry._observe(self._full, time.perf_counter() - self._start)


class _Span:
    __slots__ = ("_cluster", "_name", "_span", "_tracer")

    def __init__(self, tracer: Any, name: str, cluster: str) -> None:
        self._tracer = tracer
        self._name = name
        self._cluster = cluster
        self._span: Any = None

    def __enter__(self) -> _Span:
        if self._tracer is not None:
            with contextlib.suppress(Exception):
                self._span = self._tracer.start(self._name, {"cluster": self._cluster})
        return self

    def __exit__(self, exc_type: object, exc: BaseException | None, tb: object) -> None:
        if self._span is not None:
            with contextlib.suppress(Exception):
                self._tracer.finish(self._span, error=exc)
