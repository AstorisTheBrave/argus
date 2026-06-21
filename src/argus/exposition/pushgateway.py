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

"""Optional Prometheus Pushgateway push (no inbound port required).

For hosts that cannot be scraped but where you keep a pure-Prometheus stack, this
periodically pushes the same registry that ``/metrics`` serves to a Pushgateway.
It is additive: ``/metrics`` is still served. The push is **blocking** (urllib
under the hood), so it runs in an executor and never on the bot's event loop
(invariant 3); failures are swallowed and reflected in
``argus_subsystem_up{subsystem="pushgateway"}`` rather than raised (invariant 5).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from prometheus_client import CollectorRegistry

log = logging.getLogger("argus")

_Handler = Callable[..., Any]


def _build_handler(username: str | None, password: str | None) -> _Handler | None:
    """An HTTP basic-auth handler when credentials are set, else the default."""
    if not username and not password:
        return None
    from prometheus_client.exposition import basic_auth_handler

    def handler(url: str, method: str, timeout: float | None, headers: Any, data: Any) -> Any:
        return basic_auth_handler(
            url, method, timeout, headers, data, username or "", password or ""
        )

    return handler


class PushgatewayPusher:
    """Background task that pushes the registry to a Pushgateway on an interval."""

    def __init__(
        self,
        registry: CollectorRegistry,
        *,
        url: str,
        job: str,
        cluster: str,
        interval: float,
        username: str | None = None,
        password: str | None = None,
        on_health: Callable[[bool], None] | None = None,
    ) -> None:
        self._registry = registry
        self._url = url
        self._job = job
        # Group by cluster so clustered processes don't overwrite each other's
        # series on the gateway.
        self._grouping = {"cluster": cluster}
        self._interval = interval
        self._handler = _build_handler(username, password)
        self._on_health = on_health
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    def _push(self) -> None:
        from prometheus_client import push_to_gateway

        push_to_gateway(
            self._url,
            job=self._job,
            registry=self._registry,
            grouping_key=self._grouping,
            handler=self._handler,  # type: ignore[arg-type]
        )

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            try:
                # Blocking urllib call -> off the event loop (invariant 3).
                await loop.run_in_executor(None, self._push)
                self._report(True)
            except asyncio.CancelledError:
                raise
            except Exception:  # a gateway outage must never touch the bot loop
                self._report(False)
                log.warning("argus pushgateway push to %s failed", self._url, exc_info=True)
            await asyncio.sleep(self._interval)

    def _report(self, healthy: bool) -> None:
        if self._on_health is not None:
            with contextlib.suppress(Exception):
                self._on_health(healthy)

    async def aclose(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
