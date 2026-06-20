"""FleetConfig precedence and env mapping (mirrors ArgusConfig, invariant 6)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from argus.fleet.config import FleetConfig


def test_defaults_when_nothing_provided() -> None:
    cfg = FleetConfig.resolve(environ={})
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 9190
    assert cfg.token is None
    assert cfg.heartbeat_interval == 15
    assert cfg.ttl_factor == 3
    assert cfg.state_path == "argus-fleet-state.json"
    assert cfg.prometheus_url is None
    assert cfg.namespace == "discord"


def test_env_overrides_defaults() -> None:
    env = {
        "ARGUS_FLEET_HOST": "127.0.0.1",
        "ARGUS_FLEET_PORT": "9999",
        "ARGUS_FLEET_TOKEN": "secret",
        "ARGUS_FLEET_HEARTBEAT_INTERVAL": "30",
        "ARGUS_FLEET_TTL_FACTOR": "5",
        "ARGUS_FLEET_STATE": "/data/state.json",
        "ARGUS_FLEET_PROMETHEUS_URL": "http://prom:9090",
        "ARGUS_NAMESPACE": "bot",
    }
    cfg = FleetConfig.resolve(environ=env)
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 9999
    assert cfg.token == "secret"
    assert cfg.heartbeat_interval == 30
    assert cfg.ttl_factor == 5
    assert cfg.state_path == "/data/state.json"
    assert cfg.prometheus_url == "http://prom:9090"
    assert cfg.namespace == "bot"


def test_kwargs_override_env() -> None:
    env = {"ARGUS_FLEET_PORT": "9999", "ARGUS_FLEET_TOKEN": "fromenv"}
    cfg = FleetConfig.resolve(port=1234, token="fromkwarg", environ=env)
    assert cfg.port == 1234
    assert cfg.token == "fromkwarg"


def test_int_env_parsing() -> None:
    cfg = FleetConfig.resolve(environ={"ARGUS_FLEET_HEARTBEAT_INTERVAL": "42"})
    assert cfg.heartbeat_interval == 42


def test_config_is_frozen() -> None:
    cfg = FleetConfig.resolve(environ={})
    with pytest.raises(FrozenInstanceError):
        cfg.port = 1  # type: ignore[misc]
