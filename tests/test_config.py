"""ArgusConfig precedence and env mapping (D1 gate, invariant 6)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest

from argus.config import ArgusConfig, bootstrap, load_dotenv_if_available


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


def test_tracing_defaults_and_env() -> None:
    cfg = ArgusConfig.resolve(environ={})
    assert cfg.enable_tracing is False
    assert cfg.tracing_endpoint is None
    cfg2 = ArgusConfig.resolve(
        environ={"ARGUS_ENABLE_TRACING": "1", "ARGUS_TRACING_ENDPOINT": "http://otel:4317"}
    )
    assert cfg2.enable_tracing is True
    assert cfg2.tracing_endpoint == "http://otel:4317"


def test_pushgateway_defaults_and_env() -> None:
    cfg = ArgusConfig.resolve(environ={})
    assert cfg.pushgateway_url is None
    assert cfg.pushgateway_job == "argus"
    assert cfg.pushgateway_interval == 15
    assert cfg.pushgateway_username is None
    assert cfg.pushgateway_password is None
    env = {
        "ARGUS_PUSHGATEWAY_URL": "http://pg:9091",
        "ARGUS_PUSHGATEWAY_JOB": "bots",
        "ARGUS_PUSHGATEWAY_INTERVAL": "30",
        "ARGUS_PUSHGATEWAY_USERNAME": "u",
        "ARGUS_PUSHGATEWAY_PASSWORD": "p",
    }
    cfg2 = ArgusConfig.resolve(environ=env)
    assert cfg2.pushgateway_url == "http://pg:9091"
    assert cfg2.pushgateway_job == "bots"
    assert cfg2.pushgateway_interval == 30
    assert cfg2.pushgateway_username == "u"
    assert cfg2.pushgateway_password == "p"


def test_metrics_auth_token_default_and_env() -> None:
    assert ArgusConfig.resolve(environ={}).metrics_auth_token is None
    assert ArgusConfig.resolve(environ={"ARGUS_METRICS_AUTH_TOKEN": "s"}).metrics_auth_token == "s"
    assert ArgusConfig.resolve(metrics_auth_token="k", environ={}).metrics_auth_token == "k"


def test_log_format_default_and_env() -> None:
    assert ArgusConfig.resolve(environ={}).log_format == "text"
    assert ArgusConfig.resolve(environ={"ARGUS_LOG_FORMAT": "json"}).log_format == "json"
    assert ArgusConfig.resolve(log_format="json", environ={}).log_format == "json"


def test_port_falls_back_to_host_injected_vars() -> None:
    # Pterodactyl/PebbleHost set SERVER_PORT; Railway/PaaS set PORT.
    assert ArgusConfig.resolve(environ={"SERVER_PORT": "25570"}).port == 25570
    assert ArgusConfig.resolve(environ={"PORT": "8080"}).port == 8080
    # Precedence: ARGUS_PORT > SERVER_PORT > PORT > default.
    env = {"ARGUS_PORT": "9000", "SERVER_PORT": "25570", "PORT": "8080"}
    assert ArgusConfig.resolve(environ=env).port == 9000
    assert ArgusConfig.resolve(environ={"SERVER_PORT": "25570", "PORT": "8080"}).port == 25570
    # An explicit kwarg still wins over everything.
    assert ArgusConfig.resolve(port=1234, environ=env).port == 1234
    assert ArgusConfig.resolve(environ={}).port == 9191  # default unchanged


def test_host_falls_back_to_server_ip() -> None:
    assert ArgusConfig.resolve(environ={"SERVER_IP": "10.0.0.5"}).host == "10.0.0.5"
    explicit = ArgusConfig.resolve(environ={"ARGUS_HOST": "127.0.0.1", "SERVER_IP": "10.0.0.5"})
    assert explicit.host == "127.0.0.1"  # ARGUS_HOST wins over SERVER_IP
    assert ArgusConfig.resolve(environ={}).host == "0.0.0.0"


def test_bootstrap_loads_dotenv_then_resolves(tmp_path: Path, monkeypatch: Any) -> None:
    (tmp_path / ".env").write_text("ARGUS_CLUSTER_ID=from-dotenv\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ARGUS_CLUSTER_ID", raising=False)
    try:
        cfg = bootstrap()
        assert cfg.cluster_id == "from-dotenv"
    finally:
        # load_dotenv mutates os.environ directly; undo the leak.
        import os

        os.environ.pop("ARGUS_CLUSTER_ID", None)


def test_load_dotenv_is_noop_without_file(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.chdir(tmp_path)  # no .env here
    assert load_dotenv_if_available() is False


def test_is_loopback() -> None:
    assert ArgusConfig.resolve(host="127.0.0.1", environ={}).is_loopback() is True
    assert ArgusConfig.resolve(host="localhost", environ={}).is_loopback() is True
    assert ArgusConfig.resolve(host="0.0.0.0", environ={}).is_loopback() is False
