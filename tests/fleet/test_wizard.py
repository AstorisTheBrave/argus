"""The init wizard: token generation and generated artifacts."""

from __future__ import annotations

from pathlib import Path

from argus.fleet.wizard import (
    InitChoices,
    build_compose,
    build_env,
    generate_token,
    member_snippet,
    prometheus_scrape_config,
    write_artifacts,
)


def test_generate_token_is_unique_and_nonempty() -> None:
    a, b = generate_token(), generate_token()
    assert a and b and a != b


def test_build_env_includes_token_and_optionals() -> None:
    choices = InitChoices(token="sek", prometheus_url="http://prom:9090", cors_origins="https://ui")
    env = build_env(choices)
    assert "ARGUS_FLEET_TOKEN=sek" in env
    assert "ARGUS_FLEET_PROMETHEUS_URL=http://prom:9090" in env
    assert "ARGUS_FLEET_CORS_ORIGINS=https://ui" in env


def test_build_env_omits_unset_optionals() -> None:
    env = build_env(InitChoices(token="sek"))
    assert "ARGUS_FLEET_PROMETHEUS_URL" not in env
    assert "ARGUS_FLEET_CORS_ORIGINS" not in env


def test_build_compose_uses_env_file_and_volume() -> None:
    compose = build_compose(InitChoices(token="sek", port=9191))
    assert "env_file: .env" in compose
    assert "argus-fleet:" in compose
    assert "9191:9191" in compose
    assert "argus-fleet-state:/data" in compose


def test_member_snippet_has_url_token_group() -> None:
    snippet = member_snippet(InitChoices(token="sek", group="asia", public_url="http://f:9190"))
    assert "ARGUS_FLEET_URL=http://f:9190" in snippet
    assert "ARGUS_FLEET_TOKEN=sek" in snippet
    assert "ARGUS_FLEET_GROUP=asia" in snippet


def test_write_artifacts(tmp_path: Path) -> None:
    paths = write_artifacts(InitChoices(token="sek"), tmp_path)
    assert paths["env"].read_text(encoding="utf-8").startswith("# Generated")
    assert "services:" in paths["compose"].read_text(encoding="utf-8")


def test_prometheus_scrape_config() -> None:
    cfg = prometheus_scrape_config(InitChoices(token="sek", public_url="http://f:9190"))
    assert "http_sd_configs:" in cfg
    assert "http://f:9190/api/fleet/targets" in cfg
    assert "credentials: sek" in cfg
