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

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off", ""})


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

    @staticmethod
    def _pick_bool(kwarg: bool | None, env_value: str | None, default: bool) -> bool:
        if kwarg is not None:
            return kwarg
        if env_value is not None:
            return _parse_bool(env_value)
        return default
