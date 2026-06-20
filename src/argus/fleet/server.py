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
from dataclasses import asdict
from typing import TYPE_CHECKING

from aiohttp import web

from argus import __version__
from argus.dashboard.auth import make_auth_middleware
from argus.dashboard.server import STATIC_DIR

if TYPE_CHECKING:
    from argus.fleet.config import FleetConfig
    from argus.fleet.registry import Registry
    from argus.fleet.sources.base import FleetDataSource

_SWEEPER_KEY: web.AppKey[asyncio.Task[None]] = web.AppKey("argus_fleet_sweeper", asyncio.Task)


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
    except Exception as exc:  # any malformed body is a 400
        raise web.HTTPBadRequest(text="invalid JSON body\n") from exc
    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(text="expected a JSON object\n")
    return payload


def build_fleet_app(
    config: FleetConfig, registry: Registry, source: FleetDataSource
) -> web.Application:
    """Build the fleet aiohttp app: member, view, and SPA routes."""
    app = web.Application(middlewares=[make_auth_middleware(config.token)])

    async def health(_request: web.Request) -> web.StreamResponse:
        return web.Response(text="ok\n")

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

    async def fleet_view(_request: web.Request) -> web.StreamResponse:
        registry.sweep()
        view = await source.fleet_snapshot(registry)
        return web.json_response(view.to_dict())

    async def cluster_view(request: web.Request) -> web.StreamResponse:
        fleet = request.query.get("fleet", "")
        raw_number = request.query.get("number", "")
        if not fleet or not raw_number.isdigit():
            raise web.HTTPBadRequest(text="fleet and numeric number required\n")
        number = int(raw_number)
        registry.sweep()
        view = await source.fleet_snapshot(registry)
        group = next((f for f in view.fleets if f.name == fleet), None)
        cluster = next((c for c in group.clusters if c.number == number), None) if group else None
        if cluster is None:
            raise web.HTTPNotFound(text="cluster not found\n")
        return web.json_response({"cluster": asdict(cluster), "history": []})

    async def index(_request: web.Request) -> web.StreamResponse:
        index_html = STATIC_DIR / "index.html"
        if not index_html.is_file():
            raise web.HTTPNotFound(text="dashboard assets not built\n")
        return web.FileResponse(index_html)

    async def _sweeper(running: web.Application) -> None:
        while True:
            await asyncio.sleep(config.heartbeat_interval)
            registry.sweep()

    async def _on_startup(running: web.Application) -> None:
        running[_SWEEPER_KEY] = asyncio.create_task(_sweeper(running))

    async def _on_cleanup(running: web.Application) -> None:
        task = running.get(_SWEEPER_KEY)
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app.router.add_get("/healthz", health)
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
