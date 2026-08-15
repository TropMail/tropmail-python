from __future__ import annotations

from tropmail._throttle import TokenBucket


def test_bucket_is_inert_until_a_limit_is_observed() -> None:
    bucket = TokenBucket()
    assert bucket.rate is None
    for _ in range(100):
        assert bucket._reserve() == 0.0


def test_bucket_spends_its_budget_then_makes_callers_wait() -> None:
    bucket = TokenBucket()
    bucket.observe_limit(3)

    assert [bucket._reserve() for _ in range(3)] == [0.0, 0.0, 0.0]
    delay = bucket._reserve()
    assert 0 < delay <= 1 / 3


def test_observing_the_same_limit_does_not_refill() -> None:
    bucket = TokenBucket()
    bucket.observe_limit(2)
    bucket._reserve()
    bucket._reserve()
    bucket.observe_limit(2)
    assert bucket._reserve() > 0


def test_a_tier_change_resizes_the_bucket() -> None:
    bucket = TokenBucket()
    bucket.observe_limit(1)
    bucket._reserve()
    bucket.observe_limit(50)
    assert bucket.rate == 50.0
    assert bucket._reserve() == 0.0


def test_ignores_nonsense_limits() -> None:
    bucket = TokenBucket()
    bucket.observe_limit(0)
    bucket.observe_limit(-5)
    assert bucket.rate is None
