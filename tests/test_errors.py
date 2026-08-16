from __future__ import annotations

import httpx
import pytest

from conftest import MAILBOX_ID, error_response, make_client
from tropmail import (
    AuthenticationError,
    MarkdownTimeoutError,
    NotFoundError,
    RateLimitError,
    ServerError,
    TierError,
    TropMailError,
    ValidationError,
)
from tropmail import ConnectionError as TropMailConnectionError


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (400, ValidationError),
        (401, AuthenticationError),
        (403, TierError),
        (404, NotFoundError),
        (500, ServerError),
        (503, ServerError),
    ],
)
def test_maps_status_codes_to_error_types(status: int, expected: type[TropMailError]) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return error_response(status, "boom")

    with make_client(handler, max_retries=0) as client, pytest.raises(expected) as info:
        client.mailboxes.get(MAILBOX_ID)

    assert info.value.status == status
    assert info.value.message == "boom"
    assert info.value.request_id == "req-err"


def test_plain_text_404_is_still_typed() -> None:
    """Unknown protected routes answer with plain text, not the JSON envelope."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="Not Found")

    with make_client(handler, max_retries=0) as client, pytest.raises(NotFoundError) as info:
        client.mailboxes.get(MAILBOX_ID)

    assert info.value.message == "Not Found"


def test_rate_limit_error_exposes_retry_after() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return error_response(429, "Rate limit exceeded", headers={"Retry-After": "2"})

    with make_client(handler, max_retries=0) as client, pytest.raises(RateLimitError) as info:
        client.mailboxes.get(MAILBOX_ID)

    assert info.value.retry_after == 2.0


def test_markdown_timeout_is_its_own_type() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return error_response(504, "Markdown conversion timed out")

    with make_client(handler, max_retries=0) as client:
        with pytest.raises(MarkdownTimeoutError):
            client.emails.get_markdown(MAILBOX_ID, "abc", max_retries=0)


def test_transport_failure_becomes_connection_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    with make_client(handler, max_retries=0) as client:
        with pytest.raises(TropMailConnectionError):
            client.mailboxes.get(MAILBOX_ID)


def test_success_false_envelope_raises() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"success": False, "message": "nope", "data": None, "error": "nope"},
        )

    with make_client(handler, max_retries=0) as client, pytest.raises(TropMailError) as info:
        client.mailboxes.get(MAILBOX_ID)

    assert info.value.message == "nope"
