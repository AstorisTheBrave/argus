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

"""FleetConfig: the single config object for the control-plane service.

Mirrors :class:`argus.config.ArgusConfig`: precedence is constructor kwargs over
environment variables over defaults, and nothing else reads the environment. This
is the server-side config; member-side fleet fields live on ``ArgusConfig``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_FLEET_HOST = "0.0.0.0"
DEFAULT_FLEET_PORT = 9190
DEFAULT_HEARTBEAT_INTERVAL = 15
DEFAULT_TTL_FACTOR = 3
DEFAULT_STATE_PATH = "argus-fleet-state.json"
DEFAULT_NAMESPACE = "discord"


@dataclass(frozen=True, slots=True)
class FleetConfig:
    """Resolved, immutable configuration for the fleet service.

    Construct via :meth:`resolve`, which applies the kwargs > env > defaults
    precedence. The dataclass fields are the already-resolved values.
    """

    host: str = DEFAULT_FLEET_HOST
    port: int = DEFAULT_FLEET_PORT
    token: str | None = None
    heartbeat_interval: int = DEFAULT_HEARTBEAT_INTERVAL
    ttl_factor: int = DEFAULT_TTL_FACTOR
    state_path: str = DEFAULT_STATE_PATH
    prometheus_url: str | None = None
    namespace: str = DEFAULT_NAMESPACE

    @classmethod
    def resolve(
        cls,
        *,
        host: str | None = None,
        port: int | None = None,
        token: str | None = None,
        heartbeat_interval: int | None = None,
        ttl_factor: int | None = None,
        state_path: str | None = None,
        prometheus_url: str | None = None,
        namespace: str | None = None,
        environ: dict[str, str] | None = None,
    ) -> FleetConfig:
        """Build a config from kwargs, falling back to env, then defaults.

        ``None`` for a kwarg means "not provided"; the value is then taken from
        the matching environment variable, and finally the default. ``environ``
        is injectable for testing.
        """
        env = os.environ if environ is None else environ

        return cls(
            host=cls._pick_str(host, env.get("ARGUS_FLEET_HOST"), DEFAULT_FLEET_HOST),
            port=cls._pick_int(port, env.get("ARGUS_FLEET_PORT"), DEFAULT_FLEET_PORT),
            token=cls._pick_optional(token, env.get("ARGUS_FLEET_TOKEN")),
            heartbeat_interval=cls._pick_int(
                heartbeat_interval,
                env.get("ARGUS_FLEET_HEARTBEAT_INTERVAL"),
                DEFAULT_HEARTBEAT_INTERVAL,
            ),
            ttl_factor=cls._pick_int(
                ttl_factor, env.get("ARGUS_FLEET_TTL_FACTOR"), DEFAULT_TTL_FACTOR
            ),
            state_path=cls._pick_str(state_path, env.get("ARGUS_FLEET_STATE"), DEFAULT_STATE_PATH),
            prometheus_url=cls._pick_optional(
                prometheus_url, env.get("ARGUS_FLEET_PROMETHEUS_URL")
            ),
            namespace=cls._pick_str(namespace, env.get("ARGUS_NAMESPACE"), DEFAULT_NAMESPACE),
        )

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
