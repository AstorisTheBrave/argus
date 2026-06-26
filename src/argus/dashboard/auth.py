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
import logging
from collections.abc import Awaitable, Callable

from aiohttp import web
from aiohttp.typedefs import Middleware

log = logging.getLogger("argus")

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]

_BEARER_PREFIX = "Bearer "


def _extract_token(request: web.Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith(_BEARER_PREFIX):
        return header[len(_BEARER_PREFIX) :]
    return request.query.get("token")


def _clean(value: str | None) -> str:
    # Strip CR/LF and bound length so an untrusted value cannot forge log lines.
    return (value or "?").replace("\r", "").replace("\n", "")[:128]


def _remote(request: web.Request) -> str:
    return _clean(request.remote)[:64]


def _auth_failure(kind: str, request: web.Request) -> None:
    """Log an auth failure so credential-stuffing / brute force is detectable."""
    log.warning(
        "argus %s auth failure for %s from %s", kind, _clean(request.path), _remote(request)
    )


def make_metrics_auth_middleware(token: str, metrics_path: str) -> Middleware:
    """Gate only ``metrics_path`` with ``token``; pass everything else through.

    For shared-host public binds where even the scrape endpoint should not be
    open. The Prometheus scraper supplies ``Authorization: Bearer <token>`` (or
    ``?token=``). Comparison is constant-time. ``/healthz`` and the dashboard are
    untouched by this middleware.
    """

    @web.middleware
    async def middleware(request: web.Request, handler: Handler) -> web.StreamResponse:
        if request.path == metrics_path:
            provided = _extract_token(request)
            if provided is None or not hmac.compare_digest(provided, token):
                _auth_failure("metrics", request)
                raise web.HTTPUnauthorized(text="unauthorized\n")
        return await handler(request)

    return middleware


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
        _auth_failure("dashboard", request)
        raise web.HTTPUnauthorized(text="unauthorized\n")

    return middleware
