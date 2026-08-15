from __future__ import annotations

from typing import Any

import httpx
import pytest

from conftest import (
    API_KEY,
    EMAIL_DETAIL,
    EMAIL_ITEM,
    json_response,
    make_client,
)
from tropmail import Email, EmailFrom, InvalidAPIKeyError, TropMail
from tropmail._auth import resolve_api_key


def test_rejects_malformed_api_key() -> None:
    with pytest.raises(InvalidAPIKeyError):
        TropMail("too-short")


def test_reads_key_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TROPMAIL_API_KEY", API_KEY)
    assert resolve_api_key(None) == API_KEY


def test_requires_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TROPMAIL_API_KEY", raising=False)
    with pytest.raises(InvalidAPIKeyError):
        resolve_api_key(None)


def test_sends_bearer_token_and_request_id() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        seen["request_id"] = request.headers.get("X-Request-ID")
        seen["url"] = str(request.url)
        return json_response({"id": "m1", "email": "a@b.dev"})

    with make_client(handler) as client:
        client.mailbox.get()

    assert seen["auth"] == f"Bearer {API_KEY}"
    assert seen["request_id"]
    assert seen["url"].endswith("/api/v1/mailbox")


def test_unwraps_envelope_into_typed_model() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return json_response(
            {
                "id": "m1",
                "email": "user@tropmail.com",
                "opened_count": 3,
                "closed_count": 2,
                "favorite_count": 1,
            }
        )

    with make_client(handler) as client:
        mailbox = client.mailbox.get()

    assert mailbox.email == "user@tropmail.com"
    assert mailbox.opened_count == 3
    assert mailbox.favorite_count == 1


def test_maps_reserved_json_keys() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return json_response({"emails": [EMAIL_ITEM], "total": 5, "limit": 10, "page": 1})

    with make_client(handler) as client:
        page = client.emails.list()

    email = page.emails[0]
    assert email.from_.address == "sender@example.com"
    assert email.attachments_count == 1
    assert email.action_status == "Favorite"


def test_email_detail_parses_attachments() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return json_response(EMAIL_DETAIL)

    with make_client(handler) as client:
        detail = client.emails.get(EMAIL_DETAIL["id"])

    assert detail.subject == "Welcome"
    assert detail.attachments[0].filename == "invoice.pdf"
    assert detail.attachments[0].size == 1024
    assert detail.to[0].address == "me@tropmail.com"


def test_html_view_uses_bare_path_and_other_views_append() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return json_response(EMAIL_DETAIL)

    with make_client(handler) as client:
        client.emails.get("abc")
        client.emails.get("abc", view="text")

    assert paths == ["/api/v1/email/abc", "/api/v1/email/abc/text"]


def test_forwards_timestamp_from_email_object() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["timestamp"] = request.url.params.get("timestamp")
        return json_response(EMAIL_DETAIL)

    email = Email(
        id="abc",
        timestamp="2026-01-01T00:00:00Z",
        from_=EmailFrom(name="", address="a@b.dev"),
    )
    with make_client(handler) as client:
        client.emails.get(email)

    assert captured["timestamp"] == "2026-01-01T00:00:00Z"


def test_records_rate_limit_snapshot() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return json_response(
            {"id": "m1", "email": "a@b.dev"},
            headers={
                "X-RateLimit-Limit": "3",
                "X-RateLimit-Remaining": "2",
                "X-RateLimit-Reset": "1767225600",
            },
        )

    with make_client(handler) as client:
        assert client.rate_limit is None
        client.mailbox.get()
        snapshot = client.rate_limit

    assert snapshot is not None
    assert (snapshot.limit, snapshot.remaining, snapshot.reset) == (3, 2, 1767225600)


def test_health_skips_authorization() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        return json_response({"status": "ok", "version": "1.0.0", "timestamp": "t"})

    with make_client(handler) as client:
        health = client.mailbox.health()

    assert seen["auth"] is None
    assert health.status == "ok"


def test_action_result_parses_block_response() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return json_response({"action_status": "Block", "sender_email": "spam@bad.test"})

    with make_client(handler) as client:
        result = client.emails.block("abc")

    assert result.action_status == "Block"
    assert result.sender_email == "spam@bad.test"


def test_update_requires_at_least_one_field() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return json_response({})

    with make_client(handler) as client, pytest.raises(ValueError):
        client.emails.update("abc")


def test_scan_attachments_returns_list() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return json_response(
            [
                {
                    "attachment_id": "a1",
                    "email_id": "e1",
                    "filename": "f.pdf",
                    "status": "Processing",
                    "scan_status": "Processing",
                    "message": "Attachment scan initiated successfully",
                }
            ]
        )

    with make_client(handler) as client:
        results = client.emails.scan_attachments("e1")

    assert len(results) == 1
    assert results[0].scan_status == "Processing"
    assert results[0].filename == "f.pdf"
