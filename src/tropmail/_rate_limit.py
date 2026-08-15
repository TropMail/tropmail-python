"""Parsing for the server's rate-limit headers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitInfo:
    """Snapshot of the mailbox rate-limit window from the last response."""

    limit: int
    remaining: int
    reset: int


def parse_rate_limit_headers(headers: Mapping[str, str]) -> RateLimitInfo | None:
    limit_raw = headers.get("X-RateLimit-Limit")
    remaining_raw = headers.get("X-RateLimit-Remaining")
    reset_raw = headers.get("X-RateLimit-Reset")
    if limit_raw is None or remaining_raw is None or reset_raw is None:
        return None
    try:
        return RateLimitInfo(
            limit=int(limit_raw),
            remaining=int(remaining_raw),
            reset=int(reset_raw),
        )
    except ValueError:
        return None


def parse_retry_after(headers: Mapping[str, str]) -> float | None:
    value = headers.get("Retry-After")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None
