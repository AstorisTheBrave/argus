"""ArgusConfig precedence and env mapping (D1 gate, invariant 6)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from argus.config import ArgusConfig


def test_defaults_when_nothing_provided() -> None:
    cfg = ArgusConfig.resolve(environ={})
    assert cfg.port == 9191
    assert cfg.host == "0.0.0.0"
    assert cfg.metrics_path == "/metrics"
    assert cfg.cluster_id is None
    assert cfg.namespace == "discord"
    assert cfg.enable_per_guild is False
    assert cfg.otlp_endpoint is None


def test_env_overrides_defaults() -> None:
    env = {
        "ARGUS_PORT": "9000",
        "ARGUS_HOST": "127.0.0.1",
        "ARGUS_METRICS_PATH": "/m",
        "ARGUS_CLUSTER_ID": "shard-a",
        "ARGUS_NAMESPACE": "bot",
        "ARGUS_ENABLE_PER_GUILD": "true",
        "ARGUS_OTLP_ENDPOINT": "http://otel:4317",
    }
    cfg = ArgusConfig.resolve(environ=env)
    assert cfg.port == 9000
    assert cfg.host == "127.0.0.1"
    assert cfg.metrics_path == "/m"
    assert cfg.cluster_id == "shard-a"
    assert cfg.namespace == "bot"
    assert cfg.enable_per_guild is True
    assert cfg.otlp_endpoint == "http://otel:4317"


def test_kwargs_override_env() -> None:
    env = {"ARGUS_PORT": "9000", "ARGUS_NAMESPACE": "fromenv"}
    cfg = ArgusConfig.resolve(port=1234, namespace="fromkwarg", environ=env)
    assert cfg.port == 1234
    assert cfg.namespace == "fromkwarg"


def test_explicit_false_kwarg_beats_env_true() -> None:
    env = {"ARGUS_ENABLE_PER_GUILD": "true"}
    cfg = ArgusConfig.resolve(enable_per_guild=False, environ=env)
    assert cfg.enable_per_guild is False


def test_metrics_path_normalized_to_leading_slash() -> None:
    cfg = ArgusConfig.resolve(metrics_path="metrics", environ={})
    assert cfg.metrics_path == "/metrics"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1", True), ("yes", True), ("ON", True), ("0", False), ("false", False), ("", False)],
)
def test_bool_env_parsing(raw: str, expected: bool) -> None:
    cfg = ArgusConfig.resolve(environ={"ARGUS_ENABLE_PER_GUILD": raw})
    assert cfg.enable_per_guild is expected


def test_invalid_bool_env_raises() -> None:
    with pytest.raises(ValueError):
        ArgusConfig.resolve(environ={"ARGUS_ENABLE_PER_GUILD": "maybe"})


def test_config_is_frozen() -> None:
    cfg = ArgusConfig.resolve(environ={})
    with pytest.raises(FrozenInstanceError):
        cfg.port = 1  # type: ignore[misc]
