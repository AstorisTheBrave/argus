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


def test_dashboard_defaults() -> None:
    cfg = ArgusConfig.resolve(environ={})
    assert cfg.dashboard is True
    assert cfg.dashboard_path == "/"
    assert cfg.dashboard_interval == 5
    assert cfg.dashboard_auth_token is None
    assert cfg.grafana_url is None
    assert cfg.clickhouse_dsn is None


def test_dashboard_env_mapping() -> None:
    env = {
        "ARGUS_DASHBOARD": "false",
        "ARGUS_DASHBOARD_PATH": "ui",
        "ARGUS_DASHBOARD_INTERVAL": "10",
        "ARGUS_DASHBOARD_AUTH_TOKEN": "secret",
        "ARGUS_GRAFANA_URL": "http://grafana:3000",
        "ARGUS_CLICKHOUSE_DSN": "http://ch:8123",
    }
    cfg = ArgusConfig.resolve(environ=env)
    assert cfg.dashboard is False
    assert cfg.dashboard_path == "/ui"  # normalized leading slash
    assert cfg.dashboard_interval == 10
    assert cfg.dashboard_auth_token == "secret"
    assert cfg.grafana_url == "http://grafana:3000"
    assert cfg.clickhouse_dsn == "http://ch:8123"


def test_dashboard_kwargs_override_env() -> None:
    env = {"ARGUS_DASHBOARD": "true"}
    cfg = ArgusConfig.resolve(dashboard=False, dashboard_auth_token="t", environ=env)
    assert cfg.dashboard is False
    assert cfg.dashboard_auth_token == "t"


def test_fleet_defaults_are_opt_out() -> None:
    cfg = ArgusConfig.resolve(environ={})
    assert cfg.fleet_url is None
    assert cfg.fleet_token is None
    assert cfg.fleet_group == "default"
    assert cfg.fleet_id is None
    assert cfg.fleet_state_dir == "."


def test_fleet_env_mapping() -> None:
    env = {
        "ARGUS_FLEET_URL": "http://fleet:9190",
        "ARGUS_FLEET_TOKEN": "tok",
        "ARGUS_FLEET_GROUP": "asia",
        "ARGUS_FLEET_ID": "node-1",
        "ARGUS_FLEET_STATE_DIR": "/var/lib/argus",
    }
    cfg = ArgusConfig.resolve(environ=env)
    assert cfg.fleet_url == "http://fleet:9190"
    assert cfg.fleet_token == "tok"
    assert cfg.fleet_group == "asia"
    assert cfg.fleet_id == "node-1"
    assert cfg.fleet_state_dir == "/var/lib/argus"


def test_fleet_kwargs_override_env() -> None:
    env = {"ARGUS_FLEET_GROUP": "asia"}
    cfg = ArgusConfig.resolve(fleet_group="europe", fleet_url="http://x", environ=env)
    assert cfg.fleet_group == "europe"
    assert cfg.fleet_url == "http://x"


def test_fleet_scrape_target() -> None:
    assert ArgusConfig.resolve(environ={}).fleet_scrape_target is None
    cfg = ArgusConfig.resolve(environ={"ARGUS_FLEET_SCRAPE_TARGET": "10.0.0.5:9191"})
    assert cfg.fleet_scrape_target == "10.0.0.5:9191"
