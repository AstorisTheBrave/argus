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
(invariant 5). Listener coroutines are thin async shims over the sync bodies.
"""

from __future__ import annotations

import logging
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
    ) -> None:
        self._registry = registry
        self._n = names
        self._config = config
        self._sink = sink
        self._per_guild = config.enable_per_guild

    # --- fail-open wrapper (invariant 5) ---
    def _count_error(self, hook: str) -> None:
        try:
            self._registry.inc(self._n.instrumentation_errors_total, {"hook": hook})
        except Exception:  # pragma: no cover - the counter itself failed
            pass

    def _safe(self, hook: str, fn: Callable[..., None], *args: Any) -> None:
        try:
            fn(*args)
        except Exception:
            self._count_error(hook)
            log.exception("argus hook %r failed", hook)

    # --- analytical path (invariant 7): per-guild events to the sink, never a label ---
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
                }
            )
        except Exception:
            self._count_error("sink_interaction")
            log.exception("argus sink interaction failed")

    async def _emit_app_command(self, interaction: Any, command: Any) -> None:
        if self._sink is None or not self._per_guild:
            return
        try:
            await self._sink.record(
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "event": "app_command",
                    "guild_id": str(getattr(interaction, "guild_id", "") or ""),
                    "command": _qualified_name(command),
                }
            )
        except Exception:
            self._count_error("sink_app_command")
            log.exception("argus sink app_command failed")

    # --- listener coroutines (what discord.py dispatches to) ---
    async def on_interaction(self, interaction: Any) -> None:
        self._safe("on_interaction", self._interaction, interaction)
        await self._emit_interaction(interaction)

    async def on_app_command_completion(self, interaction: Any, command: Any) -> None:
        self._safe("on_app_command_completion", self._app_command_completion, interaction, command)
        await self._emit_app_command(interaction, command)

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

    # App command errors dispatch to CommandTree.on_error, not a listener; this
    # is called from the chained tree handler in hooks.register.
    def app_command_error(self, interaction: Any, error: BaseException) -> None:
        self._safe("tree_on_error", self._app_command_error, interaction, error)

    # discord log records feed this from the attached logging.Handler.
    def record_log(self, record: logging.LogRecord) -> None:
        self._safe("log_handler", self._record_log, record)

    # --- sync hook bodies ---
    def _interaction(self, interaction: Any) -> None:
        itype = getattr(getattr(interaction, "type", None), "name", _UNKNOWN)
        self._registry.inc(self._n.interactions_total, {"type": itype, "status": "received"})

    def _app_command_completion(self, interaction: Any, command: Any) -> None:
        name = _qualified_name(command)
        self._registry.inc(self._n.app_commands_total, {"command": name, "status": "success"})
        self._observe_duration(interaction, name)

    def _app_command_error(self, interaction: Any, error: BaseException) -> None:
        name = _qualified_name(getattr(interaction, "command", None))
        self._registry.inc(self._n.app_commands_total, {"command": name, "status": "error"})
        self._registry.inc(
            self._n.command_errors_total,
            {"command": name, "error_type": type(error).__name__},
        )

    def _command_completion(self, ctx: Any) -> None:
        name = _qualified_name(getattr(ctx, "command", None))
        self._registry.inc(self._n.commands_total, {"command": name, "status": "success"})

    def _command_error(self, ctx: Any, error: BaseException) -> None:
        name = _qualified_name(getattr(ctx, "command", None))
        self._registry.inc(self._n.commands_total, {"command": name, "status": "error"})
        self._registry.inc(
            self._n.command_errors_total,
            {"command": name, "error_type": type(error).__name__},
        )

    def _socket_event_type(self, event_type: str) -> None:
        self._registry.inc(self._n.gateway_events_total, {"event": str(event_type)})

    def _shard_reconnect(self, shard_id: int) -> None:
        self._registry.inc(self._n.shard_reconnects_total, {"shard": str(shard_id)})

    def _shard_disconnect(self, shard_id: int) -> None:
        self._registry.inc(self._n.shard_disconnects_total, {"shard": str(shard_id)})

    def _observe_duration(self, interaction: Any, command: str) -> None:
        created = getattr(interaction, "created_at", None)
        if created is None:
            return
        seconds = (datetime.now(timezone.utc) - created).total_seconds()
        if seconds >= 0:
            self._registry.observe(
                self._n.app_command_duration_seconds, seconds, {"command": command}
            )

    def _record_log(self, record: logging.LogRecord) -> None:
        self._registry.inc(
            self._n.log_records_total, {"logger": record.name, "level": record.levelname}
        )
        if record.name == "discord.http" and record.levelno >= logging.WARNING:
            if "rate limit" in record.getMessage().lower():
                self._registry.inc(self._n.ratelimits_total)


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
