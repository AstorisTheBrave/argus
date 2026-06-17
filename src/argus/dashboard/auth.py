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

"""Optional bearer-token auth for the dashboard and its APIs.

When no token is configured the middleware is a pass-through (the dashboard is
as public as ``/metrics`` already is). When a token is set, every route except
``/healthz`` requires it, supplied as ``Authorization: Bearer <token>`` or a
``?token=`` query parameter (EventSource cannot set headers). The comparison is
constant-time.
"""

from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable

from aiohttp import web
from aiohttp.typedefs import Middleware

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]

_BEARER_PREFIX = "Bearer "


def _extract_token(request: web.Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith(_BEARER_PREFIX):
        return header[len(_BEARER_PREFIX) :]
    return request.query.get("token")


def make_auth_middleware(
    token: str | None, open_paths: frozenset[str] = frozenset({"/healthz"})
) -> Middleware:
    """Build an aiohttp middleware enforcing ``token`` (or a no-op if None).

    ``open_paths`` are never gated (health checks, and typically the metrics
    endpoint so a Prometheus scraper need not carry the token).
    """

    @web.middleware
    async def middleware(request: web.Request, handler: Handler) -> web.StreamResponse:
        if token is None or request.path in open_paths:
            return await handler(request)
        provided = _extract_token(request)
        if provided is not None and hmac.compare_digest(provided, token):
            return await handler(request)
        raise web.HTTPUnauthorized(text="unauthorized\n")

    return middleware
