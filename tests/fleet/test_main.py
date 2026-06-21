"""Entrypoint glue: source selection, CLI dispatch, and .env autoload."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from argus.fleet.__main__ import (
    build_source,
    configure_logging,
    load_dotenv_if_available,
    main,
)
from argus.fleet.config import FleetConfig
from argus.fleet.sources.composite import CompositeSource
from argus.fleet.sources.push import PushSource


def test_build_source_is_push_by_default() -> None:
    source = build_source(FleetConfig.resolve(environ={}))
    assert isinstance(source, PushSource)


def test_build_source_composite_with_prometheus() -> None:
    source = build_source(FleetConfig.resolve(prometheus_url="http://prom:9090", environ={}))
    assert isinstance(source, CompositeSource)


def test_init_writes_artifacts(tmp_path: Path) -> None:
    code = main(["init", "--out-dir", str(tmp_path), "--token", "tok", "--group", "asia"])
    assert code == 0
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "ARGUS_FLEET_TOKEN=tok" in env
    assert (tmp_path / "docker-compose.fleet.yml").is_file()


def test_load_dotenv_from_explicit_file(tmp_path: Path) -> None:
    envfile = tmp_path / "fleet.env"
    envfile.write_text("ARGUS_FLEET_TEST_MARKER=loaded\n", encoding="utf-8")
    try:
        loaded = load_dotenv_if_available(environ={"ARGUS_FLEET_ENV_FILE": str(envfile)})
        assert loaded is True
        assert os.environ["ARGUS_FLEET_TEST_MARKER"] == "loaded"
    finally:
        os.environ.pop("ARGUS_FLEET_TEST_MARKER", None)


def test_load_dotenv_missing_file_is_noop() -> None:
    assert load_dotenv_if_available(environ={"ARGUS_FLEET_ENV_FILE": "/no/such/file.env"}) is False


def test_configure_logging_json_emits_json(capsys: object) -> None:
    try:
        configure_logging("json")
        logging.getLogger("argus.fleet").warning("hello %s", "world")
    finally:
        logging.getLogger().handlers.clear()
    err = capsys.readouterr().err  # type: ignore[attr-defined]
    payload = json.loads(err.strip().splitlines()[-1])
    assert payload["message"] == "hello world"
    assert payload["level"] == "WARNING"


def test_configure_logging_text_is_not_json() -> None:
    try:
        configure_logging("text")
        handler = logging.getLogger().handlers[0]
        assert not isinstance(handler.formatter, type(None))
    finally:
        logging.getLogger().handlers.clear()
