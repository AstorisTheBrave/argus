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
