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
from pathlib import Path
from typing import Any

# Defaults live here once, so the public API and the env path agree.
DEFAULT_PORT = 9191
DEFAULT_HOST = "0.0.0.0"
DEFAULT_METRICS_PATH = "/metrics"
DEFAULT_NAMESPACE = "discord"
DEFAULT_DASHBOARD_PATH = "/"
DEFAULT_DASHBOARD_INTERVAL = 5
DEFAULT_FLEET_GROUP = "default"
DEFAULT_FLEET_STATE_DIR = "."
DEFAULT_LOG_FORMAT = "text"
DEFAULT_PUSHGATEWAY_JOB = "argus"
DEFAULT_PUSHGATEWAY_INTERVAL = 15

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
    # Optional Prometheus Pushgateway push (additive; /metrics still served). For
    # locked hosts that can't be scraped but where you keep a pure-Prometheus
    # stack. url empty -> disabled. Auth is optional HTTP basic.
    pushgateway_url: str | None = None
    pushgateway_job: str = DEFAULT_PUSHGATEWAY_JOB
    pushgateway_interval: int = DEFAULT_PUSHGATEWAY_INTERVAL
    pushgateway_username: str | None = None
    pushgateway_password: str | None = None
    dashboard: bool = True
    dashboard_path: str = DEFAULT_DASHBOARD_PATH
    dashboard_interval: int = DEFAULT_DASHBOARD_INTERVAL
    dashboard_auth_token: str | None = None
    # Optional bearer token gating /metrics itself (for shared-host public binds);
    # separate from the dashboard token since the scraper is a different audience.
    metrics_auth_token: str | None = None
    grafana_url: str | None = None
    # "text" (default, leaves the app's logging untouched) or "json" (opt-in
    # structured logs on the argus logger, for log pipelines).
    log_format: str = DEFAULT_LOG_FORMAT
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
        pushgateway_url: str | None = None,
        pushgateway_job: str | None = None,
        pushgateway_interval: int | None = None,
        pushgateway_username: str | None = None,
        pushgateway_password: str | None = None,
        dashboard: bool | None = None,
        dashboard_path: str | None = None,
        dashboard_interval: int | None = None,
        dashboard_auth_token: str | None = None,
        metrics_auth_token: str | None = None,
        grafana_url: str | None = None,
        log_format: str | None = None,
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
            # Port/host fall back to the variables Docker bot hosts inject, so
            # Argus binds the host's allocation with no extra config: Pterodactyl /
            # PebbleHost set SERVER_PORT + SERVER_IP, Railway and other PaaS set
            # PORT. An explicit ARGUS_PORT/ARGUS_HOST (or kwarg) always wins.
            port=cls._pick_int(
                port,
                env.get("ARGUS_PORT") or env.get("SERVER_PORT") or env.get("PORT"),
                DEFAULT_PORT,
            ),
            host=cls._pick_str(host, env.get("ARGUS_HOST") or env.get("SERVER_IP"), DEFAULT_HOST),
            metrics_path=_normalize_path(
                cls._pick_str(metrics_path, env.get("ARGUS_METRICS_PATH"), DEFAULT_METRICS_PATH)
            ),
            cluster_id=cls._pick_optional(cluster_id, env.get("ARGUS_CLUSTER_ID")),
            namespace=cls._pick_str(namespace, env.get("ARGUS_NAMESPACE"), DEFAULT_NAMESPACE),
            enable_per_guild=cls._pick_bool(
                enable_per_guild, env.get("ARGUS_ENABLE_PER_GUILD"), False
            ),
            otlp_endpoint=cls._pick_optional(otlp_endpoint, env.get("ARGUS_OTLP_ENDPOINT")),
            pushgateway_url=cls._pick_optional(pushgateway_url, env.get("ARGUS_PUSHGATEWAY_URL")),
            pushgateway_job=cls._pick_str(
                pushgateway_job, env.get("ARGUS_PUSHGATEWAY_JOB"), DEFAULT_PUSHGATEWAY_JOB
            ),
            pushgateway_interval=cls._pick_int(
                pushgateway_interval,
                env.get("ARGUS_PUSHGATEWAY_INTERVAL"),
                DEFAULT_PUSHGATEWAY_INTERVAL,
            ),
            pushgateway_username=cls._pick_optional(
                pushgateway_username, env.get("ARGUS_PUSHGATEWAY_USERNAME")
            ),
            pushgateway_password=cls._pick_optional(
                pushgateway_password, env.get("ARGUS_PUSHGATEWAY_PASSWORD")
            ),
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
            metrics_auth_token=cls._pick_optional(
                metrics_auth_token, env.get("ARGUS_METRICS_AUTH_TOKEN")
            ),
            grafana_url=cls._pick_optional(grafana_url, env.get("ARGUS_GRAFANA_URL")),
            log_format=cls._pick_str(log_format, env.get("ARGUS_LOG_FORMAT"), DEFAULT_LOG_FORMAT),
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


def load_dotenv_if_available(path: str = ".env") -> bool:
    """Soft-load a ``.env`` into the environment when python-dotenv is installed.

    Returns True if a file was loaded. No-op (returns False) when dotenv is not
    installed or no file exists. Never overrides an existing environment variable,
    so the process environment always wins over the file. This is the only place,
    besides the fleet CLI, where Argus touches a dotenv file - it keeps the
    "one config funnel" rule intact (invariant 6).
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return False
    if not Path(path).is_file():
        return False
    load_dotenv(path, override=False)
    return True


def bootstrap(**kwargs: Any) -> ArgusConfig:
    """Eager startup entry: load ``.env`` once, then resolve the one config object.

    Used by ``Argus(bot)`` so that on hosts where the only way to inject config is
    an uploaded ``.env`` file (some Docker bot panels), everything is loaded before
    any component runs. Resolution still flows through :meth:`ArgusConfig.resolve`,
    so there remains exactly one config funnel and the result is the usual frozen,
    injectable config object - not a global singleton.
    """
    load_dotenv_if_available()
    return ArgusConfig.resolve(**kwargs)
