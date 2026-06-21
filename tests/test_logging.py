"""Opt-in JSON logging for the bot SDK (scoped to the argus logger)."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator

import pytest

from argus import ArgusCog
from argus._logging import JsonFormatter, configure_library_logging, make_handler
from argus.config import ArgusConfig
from tests.conftest import FakeBot


@pytest.fixture
def restore_argus_logger() -> Iterator[None]:
    """Snapshot and restore the argus logger so json tests don't leak global state."""
    logger = logging.getLogger("argus")
    handlers = list(logger.handlers)
    propagate, level = logger.propagate, logger.level
    yield
    logger.handlers = handlers
    logger.propagate = propagate
    logger.level = level


def test_json_formatter_emits_valid_json() -> None:
    record = logging.LogRecord("argus", logging.INFO, __file__, 1, "hello %s", ("world",), None)
    payload = json.loads(JsonFormatter().format(record))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "argus"
    assert payload["message"] == "hello world"


def test_make_handler_picks_formatter() -> None:
    assert isinstance(make_handler("json").formatter, JsonFormatter)
    text = make_handler("text").formatter
    assert isinstance(text, logging.Formatter) and not isinstance(text, JsonFormatter)


def test_text_format_leaves_argus_logger_untouched(restore_argus_logger: None) -> None:
    logger = logging.getLogger("argus")
    before = list(logger.handlers)
    configure_library_logging("text")
    assert logger.handlers == before  # default is a no-op


def test_json_attaches_one_managed_handler_and_stops_propagation(
    restore_argus_logger: None,
) -> None:
    logger = logging.getLogger("argus")
    configure_library_logging("json")
    managed = [h for h in logger.handlers if getattr(h, "_argus_managed", False)]
    assert len(managed) == 1
    assert isinstance(managed[0].formatter, JsonFormatter)
    assert logger.propagate is False

    configure_library_logging("json")  # idempotent: replaces, never duplicates
    managed = [h for h in logger.handlers if getattr(h, "_argus_managed", False)]
    assert len(managed) == 1


def test_cog_with_json_log_format_configures_logging(restore_argus_logger: None) -> None:
    ArgusCog(FakeBot(), ArgusConfig.resolve(log_format="json", dashboard=False, environ={}))
    logger = logging.getLogger("argus")
    assert any(getattr(h, "_argus_managed", False) for h in logger.handlers)
