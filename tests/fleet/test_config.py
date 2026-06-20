"""FleetConfig precedence and env mapping (mirrors ArgusConfig, invariant 6)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

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


def test_hardening_defaults() -> None:
    cfg = FleetConfig.resolve(environ={})
    assert cfg.insecure is False
    assert cfg.max_body_bytes == 262144
    assert cfg.cors_origins == ()
    assert cfg.view_cache_ms == 1000


def test_hardening_env_mapping() -> None:
    env = {
        "ARGUS_FLEET_INSECURE": "1",
        "ARGUS_FLEET_MAX_BODY_BYTES": "1024",
        "ARGUS_FLEET_CORS_ORIGINS": "https://a.example, https://b.example ,",
        "ARGUS_FLEET_VIEW_CACHE_MS": "250",
    }
    cfg = FleetConfig.resolve(environ=env)
    assert cfg.insecure is True
    assert cfg.max_body_bytes == 1024
    # Trims whitespace and drops empty entries.
    assert cfg.cors_origins == ("https://a.example", "https://b.example")
    assert cfg.view_cache_ms == 250


def test_token_from_file(tmp_path: Path) -> None:
    secret = tmp_path / "tok"
    secret.write_text("  filesecret\n", encoding="utf-8")
    cfg = FleetConfig.resolve(environ={"ARGUS_FLEET_TOKEN_FILE": str(secret)})
    assert cfg.token == "filesecret"


def test_token_env_beats_token_file(tmp_path: Path) -> None:
    secret = tmp_path / "tok"
    secret.write_text("fromfile", encoding="utf-8")
    cfg = FleetConfig.resolve(
        environ={"ARGUS_FLEET_TOKEN": "fromenv", "ARGUS_FLEET_TOKEN_FILE": str(secret)}
    )
    assert cfg.token == "fromenv"


def test_split_tokens_env_and_effective() -> None:
    env = {"ARGUS_FLEET_INGEST_TOKEN": "ing", "ARGUS_FLEET_VIEWER_TOKEN": "view"}
    cfg = FleetConfig.resolve(environ=env)
    assert cfg.effective_ingest_token() == "ing"
    assert cfg.effective_viewer_token() == "view"


def test_shared_token_is_fallback_for_both() -> None:
    cfg = FleetConfig.resolve(token="shared", environ={})
    assert cfg.effective_ingest_token() == "shared"
    assert cfg.effective_viewer_token() == "shared"


def test_specific_token_beats_shared_per_surface() -> None:
    cfg = FleetConfig.resolve(token="shared", ingest_token="ing", environ={})
    assert cfg.effective_ingest_token() == "ing"
    assert cfg.effective_viewer_token() == "shared"


def test_is_loopback() -> None:
    assert FleetConfig.resolve(host="127.0.0.1", environ={}).is_loopback() is True
    assert FleetConfig.resolve(host="localhost", environ={}).is_loopback() is True
    assert FleetConfig.resolve(host="0.0.0.0", environ={}).is_loopback() is False
