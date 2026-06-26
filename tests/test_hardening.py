"""Asset handler hardening: serve bundled files, refuse traversal (A4).

``make_asset_handler`` replaces aiohttp's ``web.static`` for the bundled SPA,
which has carried path-traversal CVEs (CVE-2024-23334, CVE-2025-69226). These
tests prove it serves real files and 404s anything escaping the assets root.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aiohttp import web
from prometheus_client import CollectorRegistry

from argus.exposition.hardening import make_asset_handler


def _app(assets_dir: Path) -> web.Application:
    app = web.Application()
    app.router.add_get("/assets/{path:.*}", make_asset_handler(assets_dir))
    return app


async def test_serves_a_real_asset(aiohttp_client: Any, tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log(1)\n", encoding="utf-8")
    client = await aiohttp_client(_app(assets))

    resp = await client.get("/assets/app.js")
    assert resp.status == 200
    assert "console.log(1)" in await resp.text()


async def test_missing_asset_is_404(aiohttp_client: Any, tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    client = await aiohttp_client(_app(assets))

    assert (await client.get("/assets/nope.js")).status == 404


async def test_traversal_outside_root_is_404(aiohttp_client: Any, tmp_path: Path) -> None:
    # A secret sibling of the assets root must never be reachable by climbing out.
    secret = tmp_path / "secret.txt"
    secret.write_text("token=hunter2\n", encoding="utf-8")
    assets = tmp_path / "assets"
    assets.mkdir()
    client = await aiohttp_client(_app(assets))

    # Both raw and encoded traversal attempts resolve outside root -> 404, not 200.
    for attempt in ("../secret.txt", "..%2Fsecret.txt", "....//secret.txt"):
        resp = await client.get(f"/assets/{attempt}")
        assert resp.status == 404, attempt
        assert "hunter2" not in await resp.text()


async def test_csp_frame_src_allows_configured_grafana(aiohttp_client: Any) -> None:
    # With a frame_src origin the page CSP must allowlist it so the Grafana tab's
    # iframe can load; frame-ancestors stays 'none' (the page is still unframable).
    from argus.exposition.server import build_app

    app = build_app(CollectorRegistry(), csp_frame_src="https://grafana.example:3000")
    client = await aiohttp_client(app)
    csp = (await client.get("/healthz")).headers["Content-Security-Policy"]
    assert "frame-src 'self' https://grafana.example:3000" in csp
    assert "frame-ancestors 'none'" in csp


async def test_csp_frame_src_defaults_to_self(aiohttp_client: Any) -> None:
    from argus.exposition.server import build_app

    app = build_app(CollectorRegistry())
    client = await aiohttp_client(app)
    csp = (await client.get("/healthz")).headers["Content-Security-Policy"]
    assert "frame-src 'self';" in csp


def test_grafana_frame_src_parsing() -> None:
    from argus.cog import _grafana_frame_src

    assert _grafana_frame_src("https://grafana.example:3000/d/x") == "https://grafana.example:3000"
    assert _grafana_frame_src("http://localhost:3000") == "http://localhost:3000"
    assert _grafana_frame_src(None) is None
    assert _grafana_frame_src("not-a-url") is None


async def test_directory_is_not_served(aiohttp_client: Any, tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    (assets / "sub").mkdir(parents=True)
    client = await aiohttp_client(_app(assets))

    assert (await client.get("/assets/sub")).status == 404
