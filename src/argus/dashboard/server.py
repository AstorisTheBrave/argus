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

if TYPE_CHECKING:
    from prometheus_client import CollectorRegistry

    from argus.config import ArgusConfig
    from argus.exposition.server import DashboardRegistrar

STATIC_DIR = Path(__file__).parent / "static"


def register_dashboard(
    config: ArgusConfig,
    *,
    registry: CollectorRegistry,
    version: str,
    analytics_enabled: bool = False,
) -> DashboardRegistrar:
    """Build a registrar that mounts the SPA + /api/config onto an app."""
    if config.dashboard_path == config.metrics_path:
        raise ValueError(f"dashboard_path {config.dashboard_path!r} collides with metrics_path")

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
                payload = json.dumps(build_snapshot(registry))
                await response.write(f"data: {payload}\n\n".encode())
                await asyncio.sleep(config.dashboard_interval)
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        return response

    def registrar(app: web.Application) -> None:
        mount = config.dashboard_path.rstrip("/")
        app.router.add_get("/api/config", api_config)
        app.router.add_get("/api/stream", stream)
        assets_dir = STATIC_DIR / "assets"
        if assets_dir.is_dir():
            app.router.add_static(f"{mount}/assets/", assets_dir)
        app.router.add_get(config.dashboard_path, index)

    return registrar
