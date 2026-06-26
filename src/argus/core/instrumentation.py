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

"""Hook bodies + the fail-open wrapper (invariants 3 and 5).

Every hook body is O(1) and synchronous (no I/O, no await on the hot path,
invariant 3) and runs inside :meth:`Instrumentation._safe`, which counts and
swallows any error so instrumentation can never raise into the bot loop
(invariant 5). Every counter carries the process ``cluster`` label. Command
duration is timed precisely from interaction receipt to completion via a bounded
start-time map (falling back to the interaction timestamp), so the map can never
grow without bound.
"""

from __future__ import annotations

import contextlib
import logging
import time
from collections import OrderedDict
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from argus.config import ArgusConfig
    from argus.core.collector import MetricRegistry
    from argus.core.metrics import MetricNames
    from argus.history.sink import EventSink

log = logging.getLogger("argus")

_UNKNOWN = "unknown"


def _qualified_name(obj: Any) -> str:
    return getattr(obj, "qualified_name", None) or _UNKNOWN


class Instrumentation:
    """Translates discord.py events into neutral registry mutations."""

    def __init__(
        self,
        registry: MetricRegistry,
        names: MetricNames,
        config: ArgusConfig,
        sink: EventSink | None = None,
        tracer: Any = None,
    ) -> None:
        self._registry = registry
        self._n = names
        self._config = config
        self._sink = sink
        self._tracer = tracer
        self._per_guild = config.enable_per_guild
        self._cluster = config.cluster_id or "default"
        self._max_pending = config.timer_cap
        self._starts: OrderedDict[int, float] = OrderedDict()
        self._command_starts: OrderedDict[int, float] = OrderedDict()
        # Open spans keyed by interaction / message id, bounded like the timers.
        self._spans: OrderedDict[int, Any] = OrderedDict()
        self._command_spans: OrderedDict[int, Any] = OrderedDict()

    def _labels(self, **labels: str) -> dict[str, str]:
        labels["cluster"] = self._cluster
        return labels

    # --- fail-open wrapper (invariant 5) ---
    def _count_error(self, hook: str) -> None:
        with contextlib.suppress(Exception):  # pragma: no cover - the counter itself failed
            self._registry.inc(self._n.instrumentation_errors_total, self._labels(hook=hook))

    def count_error(self, hook: str) -> None:
        """Public hook to record an instrumentation error (e.g. scrape-time isolation)."""
        self._count_error(hook)

    def count_dropped(self) -> None:
        """Public hook to record one dropped analytical event (sink overflow)."""
        with contextlib.suppress(Exception):  # pragma: no cover - the counter itself failed
            self._registry.inc(self._n.history_events_dropped_total, self._labels())

    def _count_eviction(self) -> None:
        with contextlib.suppress(Exception):  # pragma: no cover - the counter itself failed
            self._registry.inc(self._n.timers_evicted_total, self._labels())

    def _safe(self, hook: str, fn: Callable[..., None], *args: Any) -> None:
        try:
            fn(*args)
        except Exception:
            self._count_error(hook)
            log.exception("argus hook %r failed", hook)

    # --- precise duration timing (bounded) ---
    def _start_timer(self, interaction: Any) -> None:
        iid = getattr(interaction, "id", None)
        if iid is None:
            return
        self._starts[iid] = time.monotonic()
        if len(self._starts) > self._max_pending:
            self._starts.popitem(last=False)  # evict the oldest in-flight timer
            self._count_eviction()

    def _take_duration(self, interaction: Any) -> float | None:
        iid = getattr(interaction, "id", None)
        start = self._starts.pop(iid, None) if iid is not None else None
        if start is not None:
            return max(0.0, time.monotonic() - start)
        created = getattr(interaction, "created_at", None)  # fallback approximation
        if created is not None:
            seconds = (datetime.now(timezone.utc) - created).total_seconds()
            return seconds if seconds >= 0 else None
        return None

    # Prefix commands time invocation (on_command) to completion, keyed by the
    # invoking message id, with the same bounded-map + timestamp-fallback pattern.
    def _command_message_id(self, ctx: Any) -> int | None:
        return getattr(getattr(ctx, "message", None), "id", None)

    def _start_command_timer(self, ctx: Any) -> None:
        mid = self._command_message_id(ctx)
        if mid is None:
            return
        self._command_starts[mid] = time.monotonic()
        if len(self._command_starts) > self._max_pending:
            self._command_starts.popitem(last=False)
            self._count_eviction()

    def _take_command_duration(self, ctx: Any) -> float | None:
        mid = self._command_message_id(ctx)
        start = self._command_starts.pop(mid, None) if mid is not None else None
        if start is not None:
            return max(0.0, time.monotonic() - start)
        created = getattr(getattr(ctx, "message", None), "created_at", None)
        if created is not None:
            seconds = (datetime.now(timezone.utc) - created).total_seconds()
            return seconds if seconds >= 0 else None
        return None

    # --- command-lifecycle spans (bounded, fail-open; invariants 3 and 5) ---
    def _span_begin(
        self, store: OrderedDict[int, Any], key: int | None, name: str, attributes: dict[str, str]
    ) -> None:
        if self._tracer is None or key is None:
            return
        try:
            span = self._tracer.start(name, attributes)
        except Exception:  # tracing must never raise into the bot loop
            return
        if span is None:
            return
        store[key] = span
        if len(store) > self._max_pending:
            _, evicted = store.popitem(last=False)  # end the oldest so it cannot leak
            with contextlib.suppress(Exception):
                self._tracer.finish(evicted)

    def _span_end(
        self,
        store: OrderedDict[int, Any],
        key: int | None,
        attributes: dict[str, str] | None = None,
        error: BaseException | None = None,
    ) -> None:
        if self._tracer is None or key is None:
            return
        span = store.pop(key, None)
        if span is None:
            return
        with contextlib.suppress(Exception):
            self._tracer.finish(span, attributes=attributes, error=error)

    # --- listener coroutines (what discord.py dispatches to) ---
    async def on_interaction(self, interaction: Any) -> None:
        self._safe("on_interaction", self._interaction, interaction)
        await self._emit_interaction(interaction)

    async def on_app_command_completion(self, interaction: Any, command: Any) -> None:
        duration: float | None = None
        try:
            duration = self._take_duration(interaction)
        except Exception:  # pragma: no cover - defensive
            duration = None
        self._safe(
            "on_app_command_completion",
            self._app_command_completion,
            interaction,
            command,
            duration,
        )
        await self._emit_app_command(interaction, command, duration)

    async def on_command(self, ctx: Any) -> None:
        self._safe("on_command", self._command_start, ctx)

    async def on_command_completion(self, ctx: Any) -> None:
        self._safe("on_command_completion", self._command_completion, ctx)

    async def on_command_error(self, ctx: Any, error: BaseException) -> None:
        self._safe("on_command_error", self._command_error, ctx, error)

    async def on_socket_event_type(self, event_type: str) -> None:
        self._safe("on_socket_event_type", self._socket_event_type, event_type)

    async def on_shard_connect(self, shard_id: int) -> None:
        self._safe("on_shard_connect", self._shard_reconnect, shard_id)

    async def on_shard_resumed(self, shard_id: int) -> None:
        self._safe("on_shard_resumed", self._shard_reconnect, shard_id)

    async def on_shard_disconnect(self, shard_id: int) -> None:
        self._safe("on_shard_disconnect", self._shard_disconnect, shard_id)

    # App command errors dispatch to CommandTree.on_error, not a listener.
    def app_command_error(self, interaction: Any, error: BaseException) -> None:
        self._safe("tree_on_error", self._app_command_error, interaction, error)

    # discord log records feed this from the attached logging.Handler.
    def record_log(self, record: logging.LogRecord) -> None:
        self._safe("log_handler", self._record_log, record)

    # --- analytical path (invariant 7): per-guild events, never a Prometheus label ---
    async def _emit_interaction(self, interaction: Any) -> None:
        if self._sink is None or not self._per_guild:
            return
        try:
            itype = getattr(getattr(interaction, "type", None), "name", _UNKNOWN)
            await self._sink.record(
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "event": "interaction",
                    "guild_id": str(getattr(interaction, "guild_id", "") or ""),
                    "type": itype,
                    "command": "",
                    "duration_ms": 0.0,
                    "cluster_id": self._cluster,
                }
            )
        except Exception:
            self._count_error("sink_interaction")
            log.exception("argus sink interaction failed")

    async def _emit_app_command(
        self, interaction: Any, command: Any, duration: float | None
    ) -> None:
        if self._sink is None or not self._per_guild:
            return
        try:
            await self._sink.record(
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "event": "app_command",
                    "guild_id": str(getattr(interaction, "guild_id", "") or ""),
                    "type": "",
                    "command": _qualified_name(command),
                    "duration_ms": round((duration or 0.0) * 1000.0, 3),
                    "cluster_id": self._cluster,
                }
            )
        except Exception:
            self._count_error("sink_app_command")
            log.exception("argus sink app_command failed")

    # --- sync hook bodies ---
    def _interaction(self, interaction: Any) -> None:
        self._start_timer(interaction)
        itype = getattr(getattr(interaction, "type", None), "name", _UNKNOWN)
        self._registry.inc(self._n.interactions_total, self._labels(type=itype, status="received"))
        # Open a span only for application commands (components/modals are noise);
        # it is closed in completion/error.
        if itype == "application_command":
            attrs = {"discord.interaction_type": itype, "cluster": self._cluster}
            if self._per_guild:
                attrs["discord.guild_id"] = str(getattr(interaction, "guild_id", "") or "")
            self._span_begin(
                self._spans, getattr(interaction, "id", None), "discord.app_command", attrs
            )

    def _app_command_completion(
        self, interaction: Any, command: Any, duration: float | None
    ) -> None:
        name = _qualified_name(command)
        self._registry.inc(self._n.app_commands_total, self._labels(command=name, status="success"))
        if duration is not None:
            self._registry.observe(
                self._n.app_command_duration_seconds, duration, self._labels(command=name)
            )
        self._span_end(
            self._spans,
            getattr(interaction, "id", None),
            {"discord.command": name, "discord.outcome": "success"},
        )

    def _app_command_error(self, interaction: Any, error: BaseException) -> None:
        name = _qualified_name(getattr(interaction, "command", None))
        self._take_duration(interaction)  # drop any pending timer for this interaction
        self._registry.inc(self._n.app_commands_total, self._labels(command=name, status="error"))
        self._registry.inc(
            self._n.command_errors_total,
            self._labels(command=name, error_type=type(error).__name__),
        )
        self._span_end(
            self._spans,
            getattr(interaction, "id", None),
            {"discord.command": name, "discord.outcome": "error"},
            error=error,
        )

    def _command_start(self, ctx: Any) -> None:
        self._start_command_timer(ctx)
        self._span_begin(
            self._command_spans,
            self._command_message_id(ctx),
            "discord.command",
            {"cluster": self._cluster},
        )

    def _command_completion(self, ctx: Any) -> None:
        name = _qualified_name(getattr(ctx, "command", None))
        self._registry.inc(self._n.commands_total, self._labels(command=name, status="success"))
        duration = self._take_command_duration(ctx)
        if duration is not None:
            self._registry.observe(
                self._n.command_duration_seconds, duration, self._labels(command=name)
            )
        self._span_end(
            self._command_spans,
            self._command_message_id(ctx),
            {"discord.command": name, "discord.outcome": "success"},
        )

    def _command_error(self, ctx: Any, error: BaseException) -> None:
        name = _qualified_name(getattr(ctx, "command", None))
        self._take_command_duration(ctx)  # drop any pending timer for this invocation
        self._registry.inc(self._n.commands_total, self._labels(command=name, status="error"))
        self._registry.inc(
            self._n.command_errors_total,
            self._labels(command=name, error_type=type(error).__name__),
        )
        self._span_end(
            self._command_spans,
            self._command_message_id(ctx),
            {"discord.command": name, "discord.outcome": "error"},
            error=error,
        )

    def _socket_event_type(self, event_type: str) -> None:
        self._registry.inc(self._n.gateway_events_total, self._labels(event=str(event_type)))

    def _shard_reconnect(self, shard_id: int) -> None:
        self._registry.inc(self._n.shard_reconnects_total, self._labels(shard=str(shard_id)))

    def _shard_disconnect(self, shard_id: int) -> None:
        self._registry.inc(self._n.shard_disconnects_total, self._labels(shard=str(shard_id)))

    def _record_log(self, record: logging.LogRecord) -> None:
        self._registry.inc(
            self._n.log_records_total, self._labels(logger=record.name, level=record.levelname)
        )
        if (
            record.name == "discord.http"
            and record.levelno >= logging.WARNING
            and "rate limit" in record.getMessage().lower()
        ):
            self._registry.inc(self._n.ratelimits_total, self._labels())


class DiscordLogHandler(logging.Handler):
    """Feeds every ``discord.*`` log record into the registry (grounding sec.1)."""

    def __init__(self, instrumentation: Instrumentation) -> None:
        super().__init__()
        self._instrumentation = instrumentation

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._instrumentation.record_log(record)
        except Exception:  # pragma: no cover - logging must never raise
            self.handleError(record)
