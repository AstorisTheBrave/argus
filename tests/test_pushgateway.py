"""Optional Prometheus Pushgateway push (additive, fail-open, off the loop)."""

from __future__ import annotations

import asyncio
from typing import Any

from prometheus_client import CollectorRegistry

from argus.exposition.pushgateway import PushgatewayPusher, _build_handler


def test_basic_auth_handler_built_only_with_credentials() -> None:
    assert _build_handler(None, None) is None
    assert callable(_build_handler("user", "pass"))


async def test_pusher_pushes_with_expected_args_and_reports_healthy(monkeypatch: Any) -> None:
    calls: list[tuple[str, str, dict[str, str]]] = []

    def fake_push(
        url: str, *, job: str, registry: Any, grouping_key: dict[str, str], handler: Any
    ) -> None:
        calls.append((url, job, grouping_key))

    monkeypatch.setattr("prometheus_client.push_to_gateway", fake_push)
    flips: list[bool] = []
    pusher = PushgatewayPusher(
        CollectorRegistry(),
        url="http://pg:9091",
        job="argus",
        cluster="a",
        interval=0.01,
        on_health=flips.append,
    )
    await pusher.start()
    await asyncio.sleep(0.05)
    await pusher.aclose()

    assert calls and calls[0] == ("http://pg:9091", "argus", {"cluster": "a"})
    assert True in flips  # a successful push reported healthy


async def test_pusher_reports_unhealthy_on_failure(monkeypatch: Any) -> None:
    def boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("pushgateway down")

    monkeypatch.setattr("prometheus_client.push_to_gateway", boom)
    flips: list[bool] = []
    pusher = PushgatewayPusher(
        CollectorRegistry(),
        url="http://pg:9091",
        job="argus",
        cluster="a",
        interval=0.01,
        on_health=flips.append,
    )
    await pusher.start()
    await asyncio.sleep(0.05)
    await pusher.aclose()

    assert flips and flips[-1] is False  # the outage is reported, not raised
