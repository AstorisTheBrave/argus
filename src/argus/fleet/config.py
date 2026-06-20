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
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_FLEET_HOST = "0.0.0.0"
DEFAULT_FLEET_PORT = 9190
DEFAULT_HEARTBEAT_INTERVAL = 15
DEFAULT_TTL_FACTOR = 3
DEFAULT_STATE_PATH = "argus-fleet-state.json"
DEFAULT_NAMESPACE = "discord"
# A normal heartbeat snapshot is a few KiB; cap the body well above that but far
# below aiohttp's 1 MiB default so a hostile member cannot push large payloads.
DEFAULT_MAX_BODY_BYTES = 262144
# Short cache so N concurrent viewers share one view computation / Prometheus
# query batch instead of each triggering a recompute.
DEFAULT_VIEW_CACHE_MS = 1000
# Abuse caps. Bursts are token-bucket capacities refilled over 60s; the cluster
# cap bounds registry growth from a registration flood. Generous by default.
DEFAULT_MAX_CLUSTERS = 5000
DEFAULT_REGISTER_BURST = 60
DEFAULT_HEARTBEAT_BURST = 60
# Optional: prune clusters down longer than this many days (0 = never, default).
DEFAULT_RETENTION_DAYS = 0

# Hosts that are safe to serve without a token (a token is still recommended).
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off", ""})


def _parse_bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    raise ValueError(f"cannot parse {value!r} as a boolean")


def _read_secret_file(path: str) -> str:
    """Read and strip a secret from a file (for *_TOKEN_FILE env vars)."""
    return Path(path).read_text(encoding="utf-8").strip()


@dataclass(frozen=True, slots=True)
class FleetConfig:
    """Resolved, immutable configuration for the fleet service.

    Construct via :meth:`resolve`, which applies the kwargs > env > defaults
    precedence. The dataclass fields are the already-resolved values.
    """

    host: str = DEFAULT_FLEET_HOST
    port: int = DEFAULT_FLEET_PORT
    token: str | None = None
    # Optional split-token model: a low-privilege ingest token (on every bot) and
    # a viewer token (operators). Either falls back to the shared `token`.
    ingest_token: str | None = None
    viewer_token: str | None = None
    heartbeat_interval: int = DEFAULT_HEARTBEAT_INTERVAL
    ttl_factor: int = DEFAULT_TTL_FACTOR
    state_path: str = DEFAULT_STATE_PATH
    prometheus_url: str | None = None
    namespace: str = DEFAULT_NAMESPACE
    # Hardening (Day-2 slice 1). Secure-by-default: a non-loopback bind with no
    # token refuses to start unless `insecure` is explicitly set.
    insecure: bool = False
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES
    cors_origins: tuple[str, ...] = field(default_factory=tuple)
    view_cache_ms: int = DEFAULT_VIEW_CACHE_MS
    max_clusters: int = DEFAULT_MAX_CLUSTERS
    register_burst: int = DEFAULT_REGISTER_BURST
    heartbeat_burst: int = DEFAULT_HEARTBEAT_BURST
    retention_days: int = DEFAULT_RETENTION_DAYS
    # Trust X-Forwarded-For (only when behind a known reverse proxy) so rate
    # limits and conflict detection key on the real client IP, not the proxy's.
    trusted_proxy: bool = False

    @classmethod
    def resolve(
        cls,
        *,
        host: str | None = None,
        port: int | None = None,
        token: str | None = None,
        ingest_token: str | None = None,
        viewer_token: str | None = None,
        heartbeat_interval: int | None = None,
        ttl_factor: int | None = None,
        state_path: str | None = None,
        prometheus_url: str | None = None,
        namespace: str | None = None,
        insecure: bool | None = None,
        max_body_bytes: int | None = None,
        cors_origins: tuple[str, ...] | None = None,
        view_cache_ms: int | None = None,
        max_clusters: int | None = None,
        register_burst: int | None = None,
        heartbeat_burst: int | None = None,
        retention_days: int | None = None,
        trusted_proxy: bool | None = None,
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
            token=cls._pick_secret(
                token, env.get("ARGUS_FLEET_TOKEN"), env.get("ARGUS_FLEET_TOKEN_FILE")
            ),
            ingest_token=cls._pick_secret(
                ingest_token,
                env.get("ARGUS_FLEET_INGEST_TOKEN"),
                env.get("ARGUS_FLEET_INGEST_TOKEN_FILE"),
            ),
            viewer_token=cls._pick_secret(
                viewer_token,
                env.get("ARGUS_FLEET_VIEWER_TOKEN"),
                env.get("ARGUS_FLEET_VIEWER_TOKEN_FILE"),
            ),
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
            insecure=cls._pick_bool(insecure, env.get("ARGUS_FLEET_INSECURE"), False),
            max_body_bytes=cls._pick_int(
                max_body_bytes, env.get("ARGUS_FLEET_MAX_BODY_BYTES"), DEFAULT_MAX_BODY_BYTES
            ),
            cors_origins=cls._pick_csv(cors_origins, env.get("ARGUS_FLEET_CORS_ORIGINS")),
            view_cache_ms=cls._pick_int(
                view_cache_ms, env.get("ARGUS_FLEET_VIEW_CACHE_MS"), DEFAULT_VIEW_CACHE_MS
            ),
            max_clusters=cls._pick_int(
                max_clusters, env.get("ARGUS_FLEET_MAX_CLUSTERS"), DEFAULT_MAX_CLUSTERS
            ),
            register_burst=cls._pick_int(
                register_burst, env.get("ARGUS_FLEET_REGISTER_BURST"), DEFAULT_REGISTER_BURST
            ),
            heartbeat_burst=cls._pick_int(
                heartbeat_burst, env.get("ARGUS_FLEET_HEARTBEAT_BURST"), DEFAULT_HEARTBEAT_BURST
            ),
            retention_days=cls._pick_int(
                retention_days, env.get("ARGUS_FLEET_RETENTION_DAYS"), DEFAULT_RETENTION_DAYS
            ),
            trusted_proxy=cls._pick_bool(
                trusted_proxy, env.get("ARGUS_FLEET_TRUSTED_PROXY"), False
            ),
        )

    def is_loopback(self) -> bool:
        """True if the bind host is a loopback address (safe without a token)."""
        return self.host in _LOOPBACK_HOSTS

    def effective_ingest_token(self) -> str | None:
        """Token required for register/heartbeat (specific, else the shared one)."""
        return self.ingest_token or self.token

    def effective_viewer_token(self) -> str | None:
        """Token required for the UI and read APIs (specific, else the shared one)."""
        return self.viewer_token or self.token

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

    @staticmethod
    def _pick_secret(
        kwarg: str | None, env_value: str | None, file_env_value: str | None
    ) -> str | None:
        """Resolve a secret: kwarg, else env value, else the contents of a file."""
        if kwarg is not None:
            return kwarg
        if env_value is not None:
            return env_value
        if file_env_value:
            return _read_secret_file(file_env_value)
        return None

    @staticmethod
    def _pick_csv(kwarg: tuple[str, ...] | None, env_value: str | None) -> tuple[str, ...]:
        """Resolve a comma-separated list to a tuple, dropping empty entries."""
        if kwarg is not None:
            return kwarg
        if env_value is not None:
            return tuple(part.strip() for part in env_value.split(",") if part.strip())
        return ()
