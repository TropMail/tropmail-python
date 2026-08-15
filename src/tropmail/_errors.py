from __future__ import annotations

from typing import Any


class TropMailError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.request_id = request_id

    def __str__(self) -> str:
        parts = [self.message]
        if self.status is not None:
            parts.append(f"status={self.status}")
        if self.request_id:
            parts.append(f"request_id={self.request_id}")
        return " ".join(parts)


class AuthenticationError(TropMailError):
    pass


class TierError(TropMailError):
    pass


class NotFoundError(TropMailError):
    pass


class ValidationError(TropMailError):
    pass


class RateLimitError(TropMailError):
    def __init__(
        self,
        message: str,
        *,
        status: int | None = 429,
        request_id: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, status=status, request_id=request_id)
        self.retry_after = retry_after


class MarkdownTimeoutError(TropMailError):
    pass


class ServerError(TropMailError):
    pass


class ConnectionError(TropMailError):
    pass


def map_http_error(
    status: int,
    message: str,
    *,
    request_id: str | None = None,
    retry_after: float | None = None,
) -> TropMailError:
    if status == 400:
        return ValidationError(message, status=status, request_id=request_id)
    if status == 401:
        return AuthenticationError(message, status=status, request_id=request_id)
    if status == 403:
        return TierError(message, status=status, request_id=request_id)
    if status == 404:
        return NotFoundError(message, status=status, request_id=request_id)
    if status == 429:
        return RateLimitError(
            message,
            status=status,
            request_id=request_id,
            retry_after=retry_after,
        )
    if status == 504:
        return MarkdownTimeoutError(message, status=status, request_id=request_id)
    if status >= 500:
        return ServerError(message, status=status, request_id=request_id)
    return TropMailError(message, status=status, request_id=request_id)


def envelope_error_message(body: dict[str, Any], raw_text: str) -> str:
    message = body.get("message")
    if isinstance(message, str) and message:
        return message
    error = body.get("error")
    if isinstance(error, str) and error:
        return error
    return raw_text or "Unknown error"
