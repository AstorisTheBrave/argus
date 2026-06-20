"""Entrypoint glue: source selection for python -m argus.fleet."""

from __future__ import annotations

from argus.fleet.__main__ import build_source
from argus.fleet.config import FleetConfig
from argus.fleet.sources.push import PushSource


def test_build_source_is_push_by_default() -> None:
    source = build_source(FleetConfig.resolve(environ={}))
    assert isinstance(source, PushSource)
