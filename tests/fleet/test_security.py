"""ensure_secure_bind: hard-refuse a public bind without a token."""

from __future__ import annotations

from pathlib import Path

import pytest

from argus.fleet.config import FleetConfig
from argus.fleet.server import ensure_secure_bind


def test_public_bind_without_token_refuses() -> None:
    cfg = FleetConfig.resolve(host="0.0.0.0", environ={})
    with pytest.raises(RuntimeError, match="refusing to bind"):
        ensure_secure_bind(cfg)


def test_public_bind_with_token_is_allowed() -> None:
    cfg = FleetConfig.resolve(host="0.0.0.0", token="secret", environ={})
    ensure_secure_bind(cfg)  # no raise


def test_loopback_without_token_is_allowed() -> None:
    cfg = FleetConfig.resolve(host="127.0.0.1", environ={})
    ensure_secure_bind(cfg)  # no raise


def test_insecure_override_allows_public_bind() -> None:
    cfg = FleetConfig.resolve(host="0.0.0.0", insecure=True, environ={})
    ensure_secure_bind(cfg)  # no raise


def test_token_file_satisfies_secure_bind(tmp_path: Path) -> None:
    secret = tmp_path / "tok"
    secret.write_text("s3cret", encoding="utf-8")
    cfg = FleetConfig.resolve(host="0.0.0.0", environ={"ARGUS_FLEET_TOKEN_FILE": str(secret)})
    ensure_secure_bind(cfg)  # token came from the file, so the bind is allowed


def test_refuse_when_only_ingest_token_set() -> None:
    # The viewer surface would be open; refuse.
    cfg = FleetConfig.resolve(host="0.0.0.0", ingest_token="ing", environ={})
    with pytest.raises(RuntimeError, match="refusing to bind"):
        ensure_secure_bind(cfg)


def test_allowed_with_both_split_tokens() -> None:
    cfg = FleetConfig.resolve(host="0.0.0.0", ingest_token="ing", viewer_token="view", environ={})
    ensure_secure_bind(cfg)  # both surfaces protected
