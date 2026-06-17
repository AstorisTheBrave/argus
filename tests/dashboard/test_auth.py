"""Bearer-token auth middleware (plan task 1.2)."""

from __future__ import annotations

from typing import Any

from aiohttp import web

from argus.dashboard.auth import make_auth_middleware


def _app(token: str | None) -> web.Application:
    app = web.Application(middlewares=[make_auth_middleware(token)])

    async def ok(_request: web.Request) -> web.StreamResponse:
        return web.Response(text="ok")

    app.router.add_get("/", ok)
    app.router.add_get("/healthz", ok)
    return app


async def test_no_token_is_open(aiohttp_client: Any) -> None:
    client = await aiohttp_client(_app(None))
    assert (await client.get("/")).status == 200


async def test_token_required_rejects_missing(aiohttp_client: Any) -> None:
    client = await aiohttp_client(_app("secret"))
    assert (await client.get("/")).status == 401


async def test_token_accepts_bearer_header(aiohttp_client: Any) -> None:
    client = await aiohttp_client(_app("secret"))
    resp = await client.get("/", headers={"Authorization": "Bearer secret"})
    assert resp.status == 200


async def test_token_accepts_query_param(aiohttp_client: Any) -> None:
    client = await aiohttp_client(_app("secret"))
    assert (await client.get("/", params={"token": "secret"})).status == 200


async def test_wrong_token_rejected(aiohttp_client: Any) -> None:
    client = await aiohttp_client(_app("secret"))
    resp = await client.get("/", headers={"Authorization": "Bearer nope"})
    assert resp.status == 401


async def test_healthz_always_open(aiohttp_client: Any) -> None:
    client = await aiohttp_client(_app("secret"))
    assert (await client.get("/healthz")).status == 200
