"""Token-bucket rate limiting with an injected clock for determinism."""

from __future__ import annotations

from argus.fleet.ratelimit import KeyedRateLimiter, TokenBucket


class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def test_bucket_allows_burst_then_denies() -> None:
    clock = _Clock()
    bucket = TokenBucket(burst=3, window=60.0, clock=clock)
    assert [bucket.allow() for _ in range(3)] == [True, True, True]
    assert bucket.allow() is False  # burst exhausted, no time passed


def test_bucket_refills_over_time() -> None:
    clock = _Clock()
    bucket = TokenBucket(burst=2, window=60.0, clock=clock)
    assert bucket.allow() and bucket.allow()
    assert bucket.allow() is False
    clock.t = 30.0  # half the window -> one token back (rate = 2/60)
    assert bucket.allow() is True


def test_keyed_limiter_is_per_key() -> None:
    clock = _Clock()
    limiter = KeyedRateLimiter(burst=1, window=60.0, clock=clock)
    assert limiter.allow("a") is True
    assert limiter.allow("a") is False  # a exhausted
    assert limiter.allow("b") is True  # b independent


def test_keyed_limiter_evicts_oldest_past_max_keys() -> None:
    clock = _Clock()
    limiter = KeyedRateLimiter(burst=1, window=60.0, max_keys=2, clock=clock)
    assert limiter.allow("a") and limiter.allow("b")
    limiter.allow("c")  # evicts "a" (oldest)
    # "a" is a fresh bucket again (was evicted), so it allows once more.
    assert limiter.allow("a") is True
