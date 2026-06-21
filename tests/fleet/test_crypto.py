"""Lease-secret crypto: CSPRNG generation, HMAC-SHA256 hashing, constant-time verify."""

from __future__ import annotations

from argus.fleet.crypto import generate_secret, hash_secret, verify_secret


def test_generate_secret_is_unique_and_long() -> None:
    a, b = generate_secret(), generate_secret()
    assert a != b
    assert len(a) >= 40  # 32 bytes url-safe base64 -> ~43 chars


def test_hash_is_deterministic_and_not_the_secret() -> None:
    s = "topsecret"
    assert hash_secret(s, "pep") == hash_secret(s, "pep")
    assert hash_secret(s, "pep") != s
    assert len(hash_secret(s, "pep")) == 64  # sha256 hex


def test_pepper_changes_the_digest() -> None:
    s = "topsecret"
    assert hash_secret(s, "pep-a") != hash_secret(s, "pep-b")
    assert hash_secret(s, None) != hash_secret(s, "pep")  # no pepper differs


def test_verify_round_trip() -> None:
    s = generate_secret()
    digest = hash_secret(s, "pep")
    assert verify_secret(s, digest, "pep") is True
    assert verify_secret("wrong", digest, "pep") is False
    assert verify_secret(s, digest, "other-pepper") is False


def test_verify_rejects_empty() -> None:
    digest = hash_secret("x", None)
    assert verify_secret("", digest, None) is False
    assert verify_secret("x", "", None) is False
