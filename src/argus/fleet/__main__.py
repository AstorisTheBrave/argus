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

"""``python -m argus.fleet``: run the standalone control-plane service.

Builds a :class:`FleetConfig` from the environment, wires the registry and the
data source (Prometheus joined with push when ``prometheus_url`` is set, push
only otherwise), starts the aiohttp app via the shared ``start_server`` helper,
and runs until interrupted. Thin glue by design; the testable pieces live in
``config``, ``registry``, ``sources`` and ``server``.
"""

from __future__ import annotations

import asyncio
import contextlib

from argus.exposition.server import start_server
from argus.fleet.config import FleetConfig
from argus.fleet.registry import Registry
from argus.fleet.server import build_fleet_app
from argus.fleet.sources.base import FleetDataSource
from argus.fleet.sources.push import PushSource


def build_source(config: FleetConfig) -> FleetDataSource:
    """Push only for now; the Prometheus value source is joined here in phase 5."""
    return PushSource(config.namespace)


async def _serve(config: FleetConfig) -> None:
    registry = Registry(config.state_path, config.heartbeat_interval, config.ttl_factor)
    app = build_fleet_app(config, registry, build_source(config))
    runner = await start_server(app, config.host, config.port)
    try:
        await asyncio.Event().wait()  # run until cancelled
    finally:
        await runner.cleanup()


def main() -> None:
    config = FleetConfig.resolve()
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_serve(config))


if __name__ == "__main__":
    main()
