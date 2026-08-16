"""Transport layer: envelope decoding, retries, throttling and error mapping."""

from __future__ import annotations

import asyncio
import random
import time
import uuid
from collections.abc import Mapping
from typing import Any, TypeVar, cast

import httpx
import msgspec

from tropmail._errors import (
    ConnectionError,
    TropMailError,
    map_http_error,
)
from tropmail._models import Envelope, ErrorEnvelope
from tropmail._rate_limit import (
    RateLimitInfo,
    parse_rate_limit_headers,
    parse_retry_after,
)
from tropmail._throttle import TokenBucket

T = TypeVar("T")

DEFAULT_BASE_URL = "https://api.tropmail.com/api/v1"
DEFAULT_MAX_RETRIES = 3
DEFAULT_TIMEOUT = 120.0

RETRYABLE_STATUSES = frozenset({429, 502, 503, 504})

_ERROR_DECODER = msgspec.json.Decoder(ErrorEnvelope)
_decoder_cache: dict[Any, msgspec.json.Decoder[Any]] = {}


def _decoder_for(data_type: Any) -> msgspec.json.Decoder[Any]:
    """Return a cached single-pass decoder for ``Envelope[data_type]``."""
    decoder = _decoder_cache.get(data_type)
    if decoder is None:
        decoder = msgspec.json.Decoder(Envelope[data_type])
        _decoder_cache[data_type] = decoder
    return decoder


def full_jitter_delay(attempt: int, base: float = 0.5, cap: float = 30.0) -> float:
    """Exponential backoff with full jitter."""
    ceiling = min(cap, base * (2**attempt))
    return random.uniform(0, ceiling)


def _is_retryable_request(method: str, path: str, retry: bool) -> bool:
    del path
    if not retry:
        return False
    return method.upper() == "GET"


class RequestConfig:
    """Per-client request settings and mutable rate-limit state."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        max_retries: int,
        timeout: float,
        throttle: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.max_retries = max_retries
        self.timeout = timeout
        self.rate_limit: RateLimitInfo | None = None
        self.bucket = TokenBucket() if throttle else None


def _build_headers(
    config: RequestConfig,
    *,
    auth: bool,
    request_id: str | None,
    has_body: bool,
) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "X-Request-ID": request_id or str(uuid.uuid4()),
    }
    if auth and config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    if has_body:
        headers["Content-Type"] = "application/json"
    return headers


def _record_rate_limit(config: RequestConfig, headers: Mapping[str, str]) -> None:
    snapshot = parse_rate_limit_headers(headers)
    if snapshot is None:
        return
    config.rate_limit = snapshot
    if config.bucket is not None:
        config.bucket.observe_limit(snapshot.limit)


def _raise_for_error(response: httpx.Response) -> None:
    """Map a non-2xx response to a typed error.

    Tolerates non-JSON bodies: unknown protected routes answer with plain text.
    """
    request_id = response.headers.get("X-Request-ID")
    raw = response.content
    message = ""
    try:
        envelope = _ERROR_DECODER.decode(raw)
        if envelope.message:
            message = envelope.message
        elif isinstance(envelope.error, str):
            message = envelope.error
    except msgspec.DecodeError:
        message = response.text.strip()

    if not message:
        message = response.text.strip() or f"HTTP {response.status_code}"

    raise map_http_error(
        response.status_code,
        message,
        request_id=request_id,
        retry_after=parse_retry_after(response.headers),
    )


def _decode_success(response: httpx.Response, data_type: type[T]) -> T:
    request_id = response.headers.get("X-Request-ID")

    try:
        envelope = _decoder_for(data_type).decode(response.content)
    except msgspec.DecodeError as exc:
        raise TropMailError(
            f"Failed to decode response: {exc}",
            status=response.status_code,
            request_id=request_id,
        ) from exc

    if not envelope.success:
        error = envelope.error
        detail = envelope.message or (error if isinstance(error, str) else "") or "Request failed"
        raise map_http_error(response.status_code, detail, request_id=request_id)

    if envelope.data is None:
        raise TropMailError(
            envelope.message or "Response data is null",
            status=response.status_code,
            request_id=request_id,
        )
    return cast(T, envelope.data)


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    if response.status_code == 429:
        retry_after = parse_retry_after(response.headers)
        if retry_after is not None:
            return retry_after + random.uniform(0, 0.25)
    return full_jitter_delay(attempt)


def execute_request(
    client: httpx.Client,
    config: RequestConfig,
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    params: dict[str, str] | None = None,
    auth: bool = True,
    retry: bool = True,
    data_type: type[T],
    request_id: str | None = None,
) -> T:
    """Perform a request, unwrap the envelope, and return typed ``data``."""
    url = f"{config.base_url}{path}"
    headers = _build_headers(
        config, auth=auth, request_id=request_id, has_body=json is not None
    )
    retryable = _is_retryable_request(method, path, retry)
    attempts = config.max_retries + 1 if retryable else 1
    last_error: Exception | None = None

    for attempt in range(attempts):
        if config.bucket is not None:
            config.bucket.acquire()
        try:
            response = client.request(method, url, headers=headers, json=json, params=params)
        except httpx.TransportError as exc:
            last_error = exc
            if not retryable or attempt >= attempts - 1:
                raise ConnectionError(str(exc)) from exc
            time.sleep(full_jitter_delay(attempt))
            continue

        _record_rate_limit(config, response.headers)

        if response.status_code >= 400:
            if (
                retryable
                and attempt < attempts - 1
                and response.status_code in RETRYABLE_STATUSES
            ):
                time.sleep(_retry_delay(response, attempt))
                continue
            _raise_for_error(response)

        return _decode_success(response, data_type)

    if last_error is not None:
        raise ConnectionError(str(last_error)) from last_error
    raise ConnectionError("Request failed after retries")


async def execute_request_async(
    client: httpx.AsyncClient,
    config: RequestConfig,
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    params: dict[str, str] | None = None,
    auth: bool = True,
    retry: bool = True,
    data_type: type[T],
    request_id: str | None = None,
) -> T:
    """Async twin of :func:`execute_request`."""
    url = f"{config.base_url}{path}"
    headers = _build_headers(
        config, auth=auth, request_id=request_id, has_body=json is not None
    )
    retryable = _is_retryable_request(method, path, retry)
    attempts = config.max_retries + 1 if retryable else 1
    last_error: Exception | None = None

    for attempt in range(attempts):
        if config.bucket is not None:
            await config.bucket.acquire_async()
        try:
            response = await client.request(
                method, url, headers=headers, json=json, params=params
            )
        except httpx.TransportError as exc:
            last_error = exc
            if not retryable or attempt >= attempts - 1:
                raise ConnectionError(str(exc)) from exc
            await asyncio.sleep(full_jitter_delay(attempt))
            continue

        _record_rate_limit(config, response.headers)

        if response.status_code >= 400:
            if (
                retryable
                and attempt < attempts - 1
                and response.status_code in RETRYABLE_STATUSES
            ):
                await asyncio.sleep(_retry_delay(response, attempt))
                continue
            _raise_for_error(response)

        return _decode_success(response, data_type)

    if last_error is not None:
        raise ConnectionError(str(last_error)) from last_error
    raise ConnectionError("Request failed after retries")
