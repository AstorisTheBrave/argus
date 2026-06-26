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

"""Dashboard route registration: SPA index, static assets, and /api/config.

``register_dashboard`` returns a registrar callable for
``exposition.build_app(dashboard=...)``, keeping exposition free of dashboard
detail. The SPA itself is the built React bundle under ``static/``; the live
data routes (SSE, analytics) are added by later phases.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aiohttp import web

from argus.dashboard.snapshot import build_snapshot
from argus.exposition.hardening import make_asset_handler

if TYPE_CHECKING:
    from prometheus_client import CollectorRegistry

    from argus.config import ArgusConfig
    from argus.exposition.server import DashboardRegistrar
    from argus.history.query import AnalyticsQuery

STATIC_DIR = Path(__file__).parent / "static"

# Bound concurrent SSE streams so an open-by-default dashboard cannot be turned
# into a resource-exhaustion vector by opening many never-closing connections.
_MAX_SSE_CONNECTIONS = 64
# Coalesce snapshot builds: many viewers within this window share one build.
_SNAPSHOT_TTL = 1.0


def _dumps(obj: Any) -> str:
    return json.dumps(obj, default=str)


def register_dashboard(
    config: ArgusConfig,
    *,
    registry: CollectorRegistry,
    version: str,
    analytics: AnalyticsQuery | None = None,
) -> DashboardRegistrar:
    """Build a registrar that mounts the SPA + /api/config (+ analytics) onto an app."""
    if config.dashboard_path == config.metrics_path:
        raise ValueError(f"dashboard_path {config.dashboard_path!r} collides with metrics_path")

    analytics_enabled = analytics is not None

    # Shared snapshot cache + single-flight, and a concurrent-stream cap, so N
    # viewers cost one build per window rather than one full scrape each.
    sse = {"active": 0}
    snap_at = 0.0
    snap_val: dict[str, Any] | None = None
    snap_lock = asyncio.Lock()

    async def cached_snapshot() -> dict[str, Any]:
        nonlocal snap_at, snap_val
        loop = asyncio.get_running_loop()
        if snap_val is not None and (loop.time() - snap_at) < _SNAPSHOT_TTL:
            return snap_val
        async with snap_lock:
            if snap_val is not None and (loop.time() - snap_at) < _SNAPSHOT_TTL:
                return snap_val
            snap_val = build_snapshot(registry)
            snap_at = loop.time()
            return snap_val

    async def index(_request: web.Request) -> web.StreamResponse:
        index_html = STATIC_DIR / "index.html"
        if not index_html.is_file():
            raise web.HTTPNotFound(text="dashboard assets not built\n")
        return web.FileResponse(index_html)

    async def api_config(_request: web.Request) -> web.StreamResponse:
        payload: dict[str, Any] = {
            "namespace": config.namespace,
            "metrics_path": config.metrics_path,
            "grafana_url": config.grafana_url,
            "analytics_enabled": analytics_enabled,
            "version": version,
            "auth_required": config.dashboard_auth_token is not None,
        }
        return web.json_response(payload)

    async def stream(request: web.Request) -> web.StreamResponse:
        if sse["active"] >= _MAX_SSE_CONNECTIONS:
            raise web.HTTPServiceUnavailable(text="too many dashboard streams\n")
        sse["active"] += 1
        response = web.StreamResponse(
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
        await response.prepare(request)
        try:
            while True:
                payload = json.dumps(await cached_snapshot())
                await response.write(f"data: {payload}\n\n".encode())
                await asyncio.sleep(config.dashboard_interval)
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        finally:
            sse["active"] -= 1
        return response

    def _guild_id(request: web.Request) -> str:
        # Fail closed: the per-guild path is sensitive and must not be served
        # without a token (the auth middleware only gates when one is set).
        if config.dashboard_auth_token is None:
            raise web.HTTPForbidden(text="analytics requires dashboard_auth_token\n")
        guild_id = request.query.get("guild_id", "")
        if not guild_id:
            raise web.HTTPBadRequest(text="guild_id required\n")
        return guild_id

    async def analytics_volume(request: web.Request) -> web.StreamResponse:
        assert analytics is not None
        rows = await analytics.interaction_volume(_guild_id(request))
        return web.json_response({"rows": [list(row) for row in rows]}, dumps=_dumps)

    async def analytics_top_commands(request: web.Request) -> web.StreamResponse:
        assert analytics is not None
        rows = await analytics.top_commands(_guild_id(request))
        return web.json_response({"rows": [list(row) for row in rows]}, dumps=_dumps)

    async def analytics_command_stats(request: web.Request) -> web.StreamResponse:
        assert analytics is not None
        rows = await analytics.command_stats(_guild_id(request))
        return web.json_response({"rows": [list(row) for row in rows]}, dumps=_dumps)

    async def analytics_avg_duration(request: web.Request) -> web.StreamResponse:
        assert analytics is not None
        avg_ms = await analytics.avg_duration(_guild_id(request))
        return web.json_response({"avg_ms": avg_ms}, dumps=_dumps)

    def registrar(app: web.Application) -> None:
        mount = config.dashboard_path.rstrip("/")
        app.router.add_get("/api/config", api_config)
        app.router.add_get("/api/stream", stream)
        if analytics is not None:
            app.router.add_get("/api/analytics/interaction-volume", analytics_volume)
            app.router.add_get("/api/analytics/top-commands", analytics_top_commands)
            app.router.add_get("/api/analytics/command-stats", analytics_command_stats)
            app.router.add_get("/api/analytics/avg-duration", analytics_avg_duration)
        assets_dir = STATIC_DIR / "assets"
        if assets_dir.is_dir():
            app.router.add_get(f"{mount}/assets/{{path:.*}}", make_asset_handler(assets_dir))
        app.router.add_get(config.dashboard_path, index)

    return registrar
