"""Bearer-token auth middleware (plan task 1.2)."""

from __future__ import annotations

from typing import Any

from aiohttp import web

from argus.dashboard.auth import make_auth_middleware, make_metrics_auth_middleware


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


def _metrics_app() -> web.Application:
    app = web.Application(middlewares=[make_metrics_auth_middleware("scrape-secret", "/metrics")])

    async def ok(_request: web.Request) -> web.StreamResponse:
        return web.Response(text="ok")

    app.router.add_get("/metrics", ok)
    app.router.add_get("/healthz", ok)
    app.router.add_get("/", ok)
    return app


async def test_metrics_auth_gates_only_metrics(aiohttp_client: Any) -> None:
    client = await aiohttp_client(_metrics_app())
    assert (await client.get("/metrics")).status == 401  # gated
    assert (await client.get("/healthz")).status == 200  # untouched
    assert (await client.get("/")).status == 200  # untouched


async def test_metrics_auth_accepts_bearer_and_query(aiohttp_client: Any) -> None:
    client = await aiohttp_client(_metrics_app())
    bearer = await client.get("/metrics", headers={"Authorization": "Bearer scrape-secret"})
    assert bearer.status == 200
    assert (await client.get("/metrics", params={"token": "scrape-secret"})).status == 200
    assert (await client.get("/metrics", params={"token": "nope"})).status == 401
