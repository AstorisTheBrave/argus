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

"""aiohttp exposition served on the bot's existing loop (grounding sec.3).

``build_app`` is a pure factory (no I/O) so tests can pass it straight to the
``aiohttp_client`` fixture without binding a socket. ``start_server`` wraps
AppRunner/TCPSite and returns the runner so the caller can ``cleanup()`` on
shutdown. ``web.run_app`` is deliberately not used (it would own the loop).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from aiohttp import web
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]


def make_metrics_handler(registry: CollectorRegistry) -> Handler:
    async def metrics(_request: web.Request) -> web.StreamResponse:
        return web.Response(
            body=generate_latest(registry),
            headers={"Content-Type": CONTENT_TYPE_LATEST},
        )

    return metrics


async def health(_request: web.Request) -> web.StreamResponse:
    return web.Response(text="ok\n")


def build_app(registry: CollectorRegistry, metrics_path: str = "/metrics") -> web.Application:
    """Pure factory: build the aiohttp app serving ``metrics_path`` and ``/healthz``."""
    app = web.Application()
    app.router.add_get(metrics_path, make_metrics_handler(registry))
    app.router.add_get("/healthz", health)
    return app


async def start_server(app: web.Application, host: str, port: int) -> web.AppRunner:
    """Start ``app`` on the running loop; return the runner for later cleanup."""
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    return runner
