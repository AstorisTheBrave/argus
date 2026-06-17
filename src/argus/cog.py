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

"""The public surface: ``ArgusCog`` and the one-line ``Argus(bot)`` convenience.

``ArgusCog`` owns the registry, the Prometheus adapter, the instrumentation and
the exposition server lifecycle. Listeners are registered synchronously at
construction (safe before login); ``cog_load`` starts the server on the bot's
loop and ``cog_unload`` tears everything down (grounding sec.1).

``Argus(bot)`` constructs the cog and chains the bot's ``setup_hook`` so the cog
is added (and the server started) once the loop is running. The only line a
user writes is ``Argus(bot)``.
"""

from __future__ import annotations

import logging
from typing import Any

from discord.ext import commands

from argus.adapters.prometheus import PrometheusAdapter
from argus.config import ArgusConfig
from argus.core.collector import MetricRegistry
from argus.core.hooks import Registration, register
from argus.core.instrumentation import Instrumentation
from argus.core.metrics import bot_info_values, define_metrics
from argus.history.sink import EventSink, NullSink

log = logging.getLogger("argus")


class ArgusCog(commands.Cog):
    """Holds Argus' state and the exposition server lifecycle."""

    def __init__(self, bot: Any, config: ArgusConfig | None = None) -> None:
        self.bot = bot
        self.config = config if config is not None else ArgusConfig.resolve()
        self.registry = MetricRegistry()
        self.names = define_metrics(self.registry, bot, self.config)
        self.adapter = PrometheusAdapter()
        self.registry.attach(self.adapter)
        self.sink: EventSink = self._build_sink()
        self.instrumentation = Instrumentation(
            self.registry, self.names, self.config, sink=self.sink
        )
        self.registry.set_info(self.names.bot_info, bot_info_values())
        self._runner: Any = None
        self._analytics_client: Any = None
        # Register listeners synchronously; additive, safe before the bot logs in.
        self._registration: Registration = register(bot, self.instrumentation)

    def _build_sink(self) -> EventSink:
        """Select the analytical sink. NullSink unless per-guild analytics is on."""
        if self.config.enable_per_guild and self.config.clickhouse_dsn:
            from argus.history.clickhouse import ClickHouseSink

            return ClickHouseSink(self.config.clickhouse_dsn)
        return NullSink()

    async def _build_analytics(self) -> Any:
        """Build the analytics read layer when per-guild analytics is configured."""
        if not (self.config.enable_per_guild and self.config.clickhouse_dsn):
            return None
        import clickhouse_connect  # type: ignore[import-not-found]

        from argus.history.query import AnalyticsQuery

        self._analytics_client = await clickhouse_connect.get_async_client(
            dsn=self.config.clickhouse_dsn
        )
        return AnalyticsQuery(self._analytics_client)

    async def cog_load(self) -> None:
        from argus import __version__
        from argus.dashboard.auth import make_auth_middleware
        from argus.dashboard.server import register_dashboard
        from argus.exposition.server import build_app, start_server

        dashboard = None
        middlewares = []
        if self.config.dashboard:
            analytics = await self._build_analytics()
            dashboard = register_dashboard(
                self.config,
                registry=self.adapter.registry,
                version=__version__,
                analytics=analytics,
            )
            if self.config.dashboard_auth_token is not None:
                middlewares.append(
                    make_auth_middleware(
                        self.config.dashboard_auth_token,
                        frozenset({"/healthz", self.config.metrics_path}),
                    )
                )

        app = build_app(
            self.adapter.registry,
            self.config.metrics_path,
            dashboard=dashboard,
            middlewares=middlewares,
        )
        self._runner = await start_server(app, self.config.host, self.config.port)
        log.info(
            "argus serving metrics on %s:%d%s",
            self.config.host,
            self.config.port,
            self.config.metrics_path,
        )

    async def cog_unload(self) -> None:
        self._registration.remove()
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
        await self.sink.aclose()
        if self._analytics_client is not None:
            await self._analytics_client.close()
            self._analytics_client = None


class Argus:
    """One-line integration: ``Argus(bot)``.

    Constructs an :class:`ArgusCog` (registering listeners now) and chains the
    bot's ``setup_hook`` so the cog is added and the metrics server starts once
    the event loop is running.
    """

    def __init__(self, bot: Any, **kwargs: Any) -> None:
        self.config = ArgusConfig.resolve(**kwargs)
        self.cog = ArgusCog(bot, self.config)

        original_setup_hook = bot.setup_hook

        async def setup_hook(_original: Any = original_setup_hook) -> None:
            await _original()
            await bot.add_cog(self.cog)

        bot.setup_hook = setup_hook
