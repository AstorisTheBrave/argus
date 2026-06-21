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
from argus.core.health import HealthState
from argus.core.hooks import Registration, register
from argus.core.instrumentation import Instrumentation
from argus.core.metrics import bot_info_values, define_metrics
from argus.history.sink import BatchingSink, EventSink, NullSink

log = logging.getLogger("argus")


class ArgusCog(commands.Cog):
    """Holds Argus' state and the exposition server lifecycle."""

    def __init__(self, bot: Any, config: ArgusConfig | None = None) -> None:
        self.bot = bot
        self.config = config if config is not None else ArgusConfig.resolve()
        self.health = HealthState(
            fleet_enabled=bool(self.config.fleet_url),
            sink_enabled=bool(self.config.enable_per_guild and self.config.clickhouse_dsn),
        )
        self.registry = MetricRegistry()
        self.names = define_metrics(self.registry, bot, self.config, health=self.health)
        self.adapter = PrometheusAdapter()
        self.registry.attach(self.adapter)
        if self.config.otlp_endpoint:
            from argus.adapters.otlp import OTLPAdapter

            self.registry.attach(OTLPAdapter(endpoint=self.config.otlp_endpoint))
        self.sink: EventSink = self._build_sink()
        self.instrumentation = Instrumentation(
            self.registry, self.names, self.config, sink=self.sink
        )
        # Isolate scrape-time gauge failures into the error counter (invariant 5).
        self.adapter.set_scrape_error_hook(self.instrumentation.count_error)
        # Surface sink overflow as a counter, and reflect sink health live in
        # argus_subsystem_up{subsystem="sink"} via the circuit breaker.
        if isinstance(self.sink, BatchingSink):
            self.sink.set_drop_hook(self.instrumentation.count_dropped)
            self.sink.set_health_hook(self._set_sink_health)
        self.registry.set_info(self.names.bot_info, bot_info_values())
        self._runner: Any = None
        self._analytics_client: Any = None
        self._fleet_client: Any = None
        # Register listeners synchronously; additive, safe before the bot logs in.
        self._registration: Registration = register(bot, self.instrumentation)

    def _set_sink_health(self, healthy: bool) -> None:
        """Reflect the sink circuit breaker in argus_subsystem_up{subsystem=sink}."""
        self.health.sink_up = healthy

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
        # Fail open (invariant 5): a metrics server that cannot bind (port in
        # use, bad host) must never crash the bot. Swallow, count, mark degraded,
        # and let the bot run without Argus metrics until restart.
        try:
            await self._start_exposition()
            self.health.server_up = True
        except Exception:
            self.health.server_up = False
            self.instrumentation.count_error("cog_load")
            log.exception(
                "argus could not start its metrics server on %s:%d; the bot is "
                "unaffected and will run without Argus metrics until restart "
                "(check the port is free and the bind host is valid)",
                self.config.host,
                self.config.port,
            )
        await self._start_fleet_client()

    async def _start_exposition(self) -> None:
        from argus import __version__
        from argus.dashboard.auth import make_auth_middleware
        from argus.dashboard.server import register_dashboard
        from argus.exposition.server import build_app, start_server

        dashboard = None
        middlewares = []
        if self.config.dashboard:
            self._warn_if_dashboard_exposed()
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

    def _warn_if_dashboard_exposed(self) -> None:
        """Warn (cannot refuse) when the dashboard is reachable off-host untokened.

        Unlike the fleet plane we cannot refuse to start: ``/metrics`` must stay
        open for Prometheus on the same server. But an off-loopback dashboard with
        no token exposes the live SSE view to anyone who can reach the port, so we
        make the operator aware and point at the fix.
        """
        if self.config.dashboard_auth_token is None and not self.config.is_loopback():
            log.warning(
                "argus dashboard is reachable on %s:%d without an auth token; set "
                "dashboard_auth_token (or ARGUS_DASHBOARD_AUTH_TOKEN), or bind to "
                "127.0.0.1 and reverse-proxy it. The %s endpoint stays open for Prometheus.",
                self.config.host,
                self.config.port,
                self.config.metrics_path,
            )

    async def _start_fleet_client(self) -> None:
        """Start the opt-in fleet client (fail-open; no-op unless fleet_url set)."""
        if not self.config.fleet_url:
            return
        from argus.dashboard.snapshot import build_snapshot
        from argus.fleet.client import FleetClient

        try:
            client = FleetClient(self.config)
            await client.start(lambda: build_snapshot(self.adapter.registry))
            self._fleet_client = client
            self.health.fleet_up = True
            log.info("argus fleet client reporting to %s", self.config.fleet_url)
        except Exception:  # never let fleet wiring break the bot (invariant 5)
            self.health.fleet_up = False
            log.debug("argus fleet client failed to start", exc_info=True)
            self._fleet_client = None

    async def cog_unload(self) -> None:
        self._registration.remove()
        if self._fleet_client is not None:
            await self._fleet_client.aclose()
            self._fleet_client = None
        self.health.fleet_up = False
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
        self.health.server_up = False
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
        # Guard against a double application: a second Argus(bot) would register
        # duplicate listeners and chain setup_hook twice, double-counting every
        # event. This is always a mistake, and it happens before the bot runs, so
        # fail fast with a clear message rather than silently corrupt the metrics.
        if getattr(bot, "_argus_attached", False):
            raise RuntimeError(
                "Argus(bot) has already been applied to this bot; remove the duplicate call"
            )
        bot._argus_attached = True
        self.config = ArgusConfig.resolve(**kwargs)
        self.cog = ArgusCog(bot, self.config)

        original_setup_hook = bot.setup_hook

        async def setup_hook(_original: Any = original_setup_hook) -> None:
            await _original()
            await bot.add_cog(self.cog)

        bot.setup_hook = setup_hook
