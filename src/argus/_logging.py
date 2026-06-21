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

"""Shared logging helpers for the bot SDK and the fleet service.

The fleet control plane is a standalone process, so it configures the root
logger. The in-process SDK is a guest in someone else's application and must
never reconfigure the host's root logger; it only ever attaches an opt-in handler
to the ``argus`` logger when JSON output is explicitly requested.
"""

from __future__ import annotations

import json
import logging

_TEXT_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


class JsonFormatter(logging.Formatter):
    """Minimal structured log formatter for log pipelines."""

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "time": self.formatTime(record),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
        )


def make_handler(log_format: str) -> logging.StreamHandler:  # type: ignore[type-arg]
    """A stream handler formatted as ``json`` or human-readable ``text``."""
    handler = logging.StreamHandler()
    formatter = JsonFormatter() if log_format == "json" else logging.Formatter(_TEXT_FORMAT)
    handler.setFormatter(formatter)
    return handler


def configure_library_logging(log_format: str) -> None:
    """Opt-in: route the ``argus`` logger through a JSON handler.

    Only acts when ``log_format == "json"``. The default (``text``) is a no-op so
    that, like a well-behaved library, Argus leaves the application's logging
    configuration untouched and its records propagate to whatever the app set up.
    Idempotent: re-calling replaces the handler Argus previously added.
    """
    if log_format != "json":
        return
    logger = logging.getLogger("argus")
    for existing in list(logger.handlers):
        if getattr(existing, "_argus_managed", False):
            logger.removeHandler(existing)
    handler = make_handler("json")
    handler._argus_managed = True  # type: ignore[attr-defined]
    logger.addHandler(handler)
    # Our handler now emits these records; do not also bubble them to the root
    # logger (which would double-log if the app configured one).
    logger.propagate = False
    if logger.level == logging.NOTSET:
        logger.setLevel(logging.INFO)
