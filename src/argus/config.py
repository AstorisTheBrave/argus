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

"""ArgusConfig: the single source of truth for configuration (invariant 6).

Precedence is constructor kwargs over environment variables over defaults. All
modules read from one resolved :class:`ArgusConfig` instance; no module reads the
environment or defaults independently.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Defaults live here once, so the public API and the env path agree.
DEFAULT_PORT = 9191
DEFAULT_HOST = "0.0.0.0"
DEFAULT_METRICS_PATH = "/metrics"
DEFAULT_NAMESPACE = "discord"
DEFAULT_DASHBOARD_PATH = "/"
DEFAULT_DASHBOARD_INTERVAL = 5
DEFAULT_FLEET_GROUP = "default"
DEFAULT_FLEET_STATE_DIR = "."

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off", ""})
_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})


def _parse_bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    raise ValueError(f"cannot parse {value!r} as a boolean")


def _normalize_path(path: str) -> str:
    return path if path.startswith("/") else "/" + path


@dataclass(frozen=True, slots=True)
class ArgusConfig:
    """Resolved, immutable configuration.

    Construct via :meth:`resolve`, which applies the kwargs > env > defaults
    precedence. The dataclass fields are the already-resolved values.
    """

    port: int = DEFAULT_PORT
    host: str = DEFAULT_HOST
    metrics_path: str = DEFAULT_METRICS_PATH
    cluster_id: str | None = None
    namespace: str = DEFAULT_NAMESPACE
    enable_per_guild: bool = False
    otlp_endpoint: str | None = None
    dashboard: bool = True
    dashboard_path: str = DEFAULT_DASHBOARD_PATH
    dashboard_interval: int = DEFAULT_DASHBOARD_INTERVAL
    dashboard_auth_token: str | None = None
    grafana_url: str | None = None
    clickhouse_dsn: str | None = None
    # Fleet control plane (opt-in): when fleet_url is unset, no fleet code runs.
    fleet_url: str | None = None
    fleet_token: str | None = None
    fleet_group: str = DEFAULT_FLEET_GROUP
    fleet_id: str | None = None
    fleet_state_dir: str = DEFAULT_FLEET_STATE_DIR
    # Optional reachable "host:port" to advertise for Prometheus auto-discovery
    # via the control plane's /api/fleet/targets (http_sd).
    fleet_scrape_target: str | None = None

    @classmethod
    def resolve(
        cls,
        *,
        port: int | None = None,
        host: str | None = None,
        metrics_path: str | None = None,
        cluster_id: str | None = None,
        namespace: str | None = None,
        enable_per_guild: bool | None = None,
        otlp_endpoint: str | None = None,
        dashboard: bool | None = None,
        dashboard_path: str | None = None,
        dashboard_interval: int | None = None,
        dashboard_auth_token: str | None = None,
        grafana_url: str | None = None,
        clickhouse_dsn: str | None = None,
        fleet_url: str | None = None,
        fleet_token: str | None = None,
        fleet_group: str | None = None,
        fleet_id: str | None = None,
        fleet_state_dir: str | None = None,
        fleet_scrape_target: str | None = None,
        environ: dict[str, str] | None = None,
    ) -> ArgusConfig:
        """Build a config from kwargs, falling back to env, then defaults.

        ``None`` for a kwarg means "not provided"; the value is then taken from
        the matching ``ARGUS_*`` environment variable, and finally the default.
        ``environ`` is injectable for testing.
        """
        env = os.environ if environ is None else environ

        return cls(
            port=cls._pick_int(port, env.get("ARGUS_PORT"), DEFAULT_PORT),
            host=cls._pick_str(host, env.get("ARGUS_HOST"), DEFAULT_HOST),
            metrics_path=_normalize_path(
                cls._pick_str(metrics_path, env.get("ARGUS_METRICS_PATH"), DEFAULT_METRICS_PATH)
            ),
            cluster_id=cls._pick_optional(cluster_id, env.get("ARGUS_CLUSTER_ID")),
            namespace=cls._pick_str(namespace, env.get("ARGUS_NAMESPACE"), DEFAULT_NAMESPACE),
            enable_per_guild=cls._pick_bool(
                enable_per_guild, env.get("ARGUS_ENABLE_PER_GUILD"), False
            ),
            otlp_endpoint=cls._pick_optional(otlp_endpoint, env.get("ARGUS_OTLP_ENDPOINT")),
            dashboard=cls._pick_bool(dashboard, env.get("ARGUS_DASHBOARD"), True),
            dashboard_path=_normalize_path(
                cls._pick_str(
                    dashboard_path, env.get("ARGUS_DASHBOARD_PATH"), DEFAULT_DASHBOARD_PATH
                )
            ),
            dashboard_interval=cls._pick_int(
                dashboard_interval,
                env.get("ARGUS_DASHBOARD_INTERVAL"),
                DEFAULT_DASHBOARD_INTERVAL,
            ),
            dashboard_auth_token=cls._pick_optional(
                dashboard_auth_token, env.get("ARGUS_DASHBOARD_AUTH_TOKEN")
            ),
            grafana_url=cls._pick_optional(grafana_url, env.get("ARGUS_GRAFANA_URL")),
            clickhouse_dsn=cls._pick_optional(clickhouse_dsn, env.get("ARGUS_CLICKHOUSE_DSN")),
            fleet_url=cls._pick_optional(fleet_url, env.get("ARGUS_FLEET_URL")),
            fleet_token=cls._pick_optional(fleet_token, env.get("ARGUS_FLEET_TOKEN")),
            fleet_group=cls._pick_str(
                fleet_group, env.get("ARGUS_FLEET_GROUP"), DEFAULT_FLEET_GROUP
            ),
            fleet_id=cls._pick_optional(fleet_id, env.get("ARGUS_FLEET_ID")),
            fleet_state_dir=cls._pick_str(
                fleet_state_dir, env.get("ARGUS_FLEET_STATE_DIR"), DEFAULT_FLEET_STATE_DIR
            ),
            fleet_scrape_target=cls._pick_optional(
                fleet_scrape_target, env.get("ARGUS_FLEET_SCRAPE_TARGET")
            ),
        )

    def is_loopback(self) -> bool:
        """True if the server binds to a loopback host (not reachable off-host)."""
        return self.host in _LOOPBACK

    @staticmethod
    def _pick_str(kwarg: str | None, env_value: str | None, default: str) -> str:
        if kwarg is not None:
            return kwarg
        if env_value is not None:
            return env_value
        return default

    @staticmethod
    def _pick_optional(kwarg: str | None, env_value: str | None) -> str | None:
        if kwarg is not None:
            return kwarg
        return env_value

    @staticmethod
    def _pick_int(kwarg: int | None, env_value: str | None, default: int) -> int:
        if kwarg is not None:
            return kwarg
        if env_value is not None:
            return int(env_value)
        return default

    @staticmethod
    def _pick_bool(kwarg: bool | None, env_value: str | None, default: bool) -> bool:
        if kwarg is not None:
            return kwarg
        if env_value is not None:
            return _parse_bool(env_value)
        return default
