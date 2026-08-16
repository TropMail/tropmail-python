from __future__ import annotations

import os
import re

_LEGACY_KEY = re.compile(r"^[A-Za-z0-9]{32}$")
_LIVE_KEY = re.compile(r"^tm_live_[A-Za-z0-9]{32}$")


class InvalidAPIKeyError(ValueError):
    """Raised when an API key fails local format validation."""


def validate_api_key(key: str) -> str:
    if not _LEGACY_KEY.match(key) and not _LIVE_KEY.match(key):
        raise InvalidAPIKeyError(
            "API key must be 32 alphanumeric characters, optionally prefixed with tm_live_"
        )
    return key


def resolve_api_key(api_key: str | None) -> str:
    key = api_key or os.environ.get("TROPMAIL_API_KEY")
    if not key:
        raise InvalidAPIKeyError(
            "API key is required: pass api_key= or set TROPMAIL_API_KEY"
        )
    return validate_api_key(key)
