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

"""The fleet control-plane HTTP surface (aiohttp).

``build_fleet_app`` is a pure factory (no socket bind) so tests can hand it to
the ``aiohttp_client`` fixture. The shared ``token`` gates every route except
``/healthz`` via the dashboard's auth middleware. Members call ``/fleet/register``
and ``/fleet/heartbeat``; the SPA polls ``/api/fleet/view``. A background sweeper
recomputes health each ``heartbeat_interval`` and is cancelled on cleanup.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from aiohttp import web
from aiohttp.typedefs import Middleware

from argus import __version__
from argus.dashboard.auth import make_auth_middleware
from argus.dashboard.server import STATIC_DIR

if TYPE_CHECKING:
    from argus.fleet.config import FleetConfig
    from argus.fleet.registry import Registry
    from argus.fleet.sources.base import FleetDataSource

_Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]

_SWEEPER_KEY: web.AppKey[asyncio.Task[None]] = web.AppKey("argus_fleet_sweeper", asyncio.Task)

# Generic banner: do not leak the Python/aiohttp versions to scanners. The
# reverse proxy is the reliable layer (this signal does not fire on raw parser
# errors), but stripping it here removes the easy fingerprint.
_SERVER_BANNER = "argus-fleet"
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    # Permissive enough for the bundled SPA (charts set inline styles) while
    # blocking framing and foreign script/object sources.
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "object-src 'none'; frame-ancestors 'none'"
    ),
}


async def _harden_response(_request: web.Request, response: web.StreamResponse) -> None:
    """Strip the version banner and add security headers to every response."""
    response.headers["Server"] = _SERVER_BANNER
    for name, value in _SECURITY_HEADERS.items():
        response.headers[name] = value


def _make_cors_middleware(origins: tuple[str, ...]) -> Middleware:
    """Allowlist CORS for a detached UI; preflight is never auth-gated.

    Only the explicitly listed origins are echoed back; no wildcard is ever sent
    for this token-gated surface. With an empty allowlist this is not installed.
    """
    allowed = frozenset(origins)

    @web.middleware
    async def middleware(request: web.Request, handler: _Handler) -> web.StreamResponse:
        origin = request.headers.get("Origin")
        if request.method == "OPTIONS" and origin is not None:
            response: web.StreamResponse = web.Response(status=204)
        else:
            response = await handler(request)
        if origin is not None and origin in allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    return middleware


def ensure_secure_bind(config: FleetConfig) -> None:
    """Refuse to start on a public bind without a token (secure-by-default).

    A non-loopback bind with no token would expose the fleet view and the
    register/heartbeat surface to the open internet. We hard-refuse rather than
    warn; set ``ARGUS_FLEET_TOKEN`` (or ``ARGUS_FLEET_TOKEN_FILE``), bind to
    loopback, or pass ``ARGUS_FLEET_INSECURE=1`` for local testing only.
    """
    if config.token is None and not config.is_loopback() and not config.insecure:
        raise RuntimeError(
            f"refusing to bind {config.host!r} without a token: set ARGUS_FLEET_TOKEN "
            "(or ARGUS_FLEET_TOKEN_FILE), bind to 127.0.0.1, or set ARGUS_FLEET_INSECURE=1 "
            "for local testing only"
        )


async def _read_json(request: web.Request) -> dict[str, object]:
    try:
        payload = await request.json()
    except web.HTTPException:
        raise  # e.g. 413 from the body-size cap; do not mask as 400
    except Exception as exc:  # any malformed body is a 400
        raise web.HTTPBadRequest(text="invalid JSON body\n") from exc
    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(text="expected a JSON object\n")
    return payload


def build_fleet_app(
    config: FleetConfig, registry: Registry, source: FleetDataSource
) -> web.Application:
    """Build the fleet aiohttp app: member, view, and SPA routes."""
    # CORS (if any) sits outside auth so a browser preflight is never gated; the
    # body cap rejects oversized snapshots with 413 before they reach a handler.
    middlewares: list[Middleware] = []
    if config.cors_origins:
        middlewares.append(_make_cors_middleware(config.cors_origins))
    middlewares.append(make_auth_middleware(config.token, frozenset({"/healthz", "/readyz"})))
    app = web.Application(middlewares=middlewares, client_max_size=config.max_body_bytes)
    app.on_response_prepare.append(_harden_response)

    async def health(_request: web.Request) -> web.StreamResponse:
        return web.Response(text="ok\n")

    async def ready(_request: web.Request) -> web.StreamResponse:
        return web.Response(text="ready\n")

    async def api_config(_request: web.Request) -> web.StreamResponse:
        return web.json_response(
            {
                "fleet": True,
                "namespace": config.namespace,
                "version": __version__,
                "auth_required": config.token is not None,
                "interval": config.heartbeat_interval,
            }
        )

    async def register(request: web.Request) -> web.StreamResponse:
        body = await _read_json(request)
        identity = str(body.get("identity") or "")
        if not identity:
            raise web.HTTPBadRequest(text="identity required\n")
        fleet = str(body.get("fleet") or "default")
        version = str(body.get("version") or "")
        number = registry.register(identity, fleet, version)
        return web.json_response({"number": number})

    async def heartbeat(request: web.Request) -> web.StreamResponse:
        body = await _read_json(request)
        identity = str(body.get("identity") or "")
        if not identity:
            raise web.HTTPBadRequest(text="identity required\n")
        snapshot = body.get("snapshot")
        registry.heartbeat(identity, snapshot if isinstance(snapshot, dict) else None)
        return web.Response(status=204)

    # Short-TTL cache + single-flight: N concurrent viewers share one compute /
    # Prometheus query batch instead of each triggering a full recompute.
    ttl = config.view_cache_ms / 1000.0
    cache_at = 0.0
    cache_data: dict[str, Any] | None = None
    view_lock = asyncio.Lock()

    async def _cached_view() -> dict[str, Any]:
        nonlocal cache_at, cache_data
        loop = asyncio.get_running_loop()
        if cache_data is not None and (loop.time() - cache_at) < ttl:
            return cache_data
        async with view_lock:
            # Re-check: another waiter may have refreshed while we waited.
            if cache_data is not None and (loop.time() - cache_at) < ttl:
                return cache_data
            registry.sweep()
            view = await source.fleet_snapshot(registry)
            cache_data = view.to_dict()
            cache_at = loop.time()
            return cache_data

    async def fleet_view(_request: web.Request) -> web.StreamResponse:
        return web.json_response(await _cached_view())

    async def cluster_view(request: web.Request) -> web.StreamResponse:
        fleet = request.query.get("fleet", "")
        raw_number = request.query.get("number", "")
        if not fleet or not raw_number.isdigit():
            raise web.HTTPBadRequest(text="fleet and numeric number required\n")
        number = int(raw_number)
        data = await _cached_view()
        fleets: list[dict[str, Any]] = data.get("fleets", [])
        group = next((f for f in fleets if f.get("name") == fleet), None)
        clusters: list[dict[str, Any]] = group.get("clusters", []) if group else []
        cluster = next((c for c in clusters if c.get("number") == number), None)
        if cluster is None:
            raise web.HTTPNotFound(text="cluster not found\n")
        return web.json_response({"cluster": cluster, "history": []})

    async def index(_request: web.Request) -> web.StreamResponse:
        index_html = STATIC_DIR / "index.html"
        if not index_html.is_file():
            raise web.HTTPNotFound(text="dashboard assets not built\n")
        return web.FileResponse(index_html)

    async def _sweeper(running: web.Application) -> None:
        loop = asyncio.get_running_loop()
        while True:
            await asyncio.sleep(config.heartbeat_interval)
            registry.sweep()
            # Coalesced, off-loop persistence: serialize on the loop, write on a
            # thread so a slow disk never stalls heartbeat handling.
            payload = registry.flush_payload()
            if payload is not None:
                await loop.run_in_executor(None, registry.write_payload, payload)

    async def _on_startup(running: web.Application) -> None:
        running[_SWEEPER_KEY] = asyncio.create_task(_sweeper(running))

    async def _on_cleanup(running: web.Application) -> None:
        task = running.get(_SWEEPER_KEY)
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        # Final flush on shutdown so the latest state is durable.
        await asyncio.get_running_loop().run_in_executor(None, registry.save)
        # Release the data source's resources (e.g. the Prometheus HTTP session).
        await source.aclose()

    app.router.add_get("/healthz", health)
    app.router.add_get("/readyz", ready)
    app.router.add_get("/api/config", api_config)
    app.router.add_post("/fleet/register", register)
    app.router.add_post("/fleet/heartbeat", heartbeat)
    app.router.add_get("/api/fleet/view", fleet_view)
    app.router.add_get("/api/fleet/cluster", cluster_view)
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.is_dir():
        app.router.add_static("/assets/", assets_dir)
    app.router.add_get("/", index)
    app.on_startup.append(_on_startup)
    app.on_cleanup.append(_on_cleanup)
    return app
