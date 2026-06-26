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

"""Shared HTTP hardening for every Argus surface (bot server and fleet plane).

One source of truth for the security headers and the version-banner strip, so the
in-process bot dashboard gets the same treatment the fleet control plane already
has. The reverse proxy remains the reliable enforcement layer for a public
deployment (these headers do not fire on raw parser errors); stripping the banner
and sending the headers here removes the easy fingerprint either way.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from pathlib import Path

from aiohttp import web

# Default body cap for surfaces that accept no large uploads. aiohttp's own
# default is 1 MiB; the bot server has no POST surface, so a tighter cap is free
# hygiene against a hostile client.
DEFAULT_MAX_BODY_BYTES = 256 * 1024


def _content_security_policy(frame_src: str | None) -> str:
    # Permissive enough for the bundled SPA (charts set inline styles) while
    # blocking foreign script/object sources and refusing to be framed itself
    # (frame-ancestors 'none'). frame-src is 'self' by default; an explicit
    # origin (the configured Grafana) is added so the dashboard can embed it.
    frame = f"frame-src 'self' {frame_src}" if frame_src else "frame-src 'self'"
    return (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        f"{frame}; object-src 'none'; frame-ancestors 'none'"
    )


_ResponsePrepare = Callable[[web.Request, web.StreamResponse], Awaitable[None]]


def make_asset_handler(
    assets_dir: Path,
) -> Callable[[web.Request], Awaitable[web.StreamResponse]]:
    """Serve a file from ``assets_dir`` by path, refusing traversal outside it.

    Used instead of ``web.static()`` for the bundled SPA: aiohttp's static helper
    has carried path-disclosure / traversal CVEs (CVE-2024-23334, CVE-2025-69226),
    so we resolve the request against the assets root and 404 anything that
    escapes it.

    The containment check uses ``os.path`` deliberately: realpath (to collapse
    symlinks and ``..``) followed by a ``startswith`` guard against the root plus a
    separator, co-located with the sink, is the canonical path-traversal
    remediation static analysers recognise. The trailing separator defeats the
    sibling-prefix bug (``/assetsX`` must not pass for root ``/assets``). The path
    ops are bounded string/stat work, no different from what ``FileResponse``
    itself does.
    """
    root = os.path.realpath(assets_dir)
    root_prefix = root + os.sep

    async def handler(request: web.Request) -> web.StreamResponse:
        requested = request.match_info.get("path", "")
        target = os.path.realpath(os.path.join(root, requested))  # noqa: ASYNC240, PTH118
        if not target.startswith(root_prefix):
            raise web.HTTPNotFound(text="not found\n")
        if not os.path.isfile(target):  # noqa: ASYNC240, PTH113
            raise web.HTTPNotFound(text="not found\n")
        return web.FileResponse(Path(target))

    return handler


def make_harden_response(banner: str, *, frame_src: str | None = None) -> _ResponsePrepare:
    """Build an ``on_response_prepare`` hook: strip the banner, add the headers.

    ``frame_src`` adds one trusted origin to the CSP ``frame-src`` (the dashboard
    uses it to embed the configured Grafana); ``None`` keeps the default of
    ``'self'`` only.
    """
    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": _content_security_policy(frame_src),
    }

    async def harden(_request: web.Request, response: web.StreamResponse) -> None:
        response.headers["Server"] = banner
        for name, value in headers.items():
            response.headers[name] = value

    return harden
