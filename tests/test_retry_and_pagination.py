from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from conftest import EMAIL_ITEM, error_response, json_response, make_client
from tropmail import NotFoundError, RateLimitError, ServerError


def _page(count: int, *, total: int = 0) -> dict[str, Any]:
    return {
        "emails": [dict(EMAIL_ITEM, id=f"id-{i}") for i in range(count)],
        "total": total,
        "limit": 10,
        "page": 1,
    }


def test_iterate_stops_on_short_page() -> None:
    """`total` describes the whole mailbox, so only a short page ends iteration."""
    pages = [_page(10, total=999), _page(10, total=999), _page(3, total=999)]
    requested_pages: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.read())
        requested_pages.append(payload["page"])
        return json_response(pages[len(requested_pages) - 1])

    with make_client(handler) as client:
        emails = list(client.emails.iterate(limit=10))

    assert len(emails) == 23
    assert requested_pages == [1, 2, 3]


def test_iterate_stops_immediately_on_empty_page() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return json_response(_page(0, total=42))

    with make_client(handler) as client:
        assert list(client.emails.iterate(limit=10)) == []


def test_search_iterate_ignores_zero_total() -> None:
    responses = [_page(5), _page(1)]
    index = {"i": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        response = json_response(responses[index["i"]])
        index["i"] += 1
        return response

    with make_client(handler) as client:
        assert len(list(client.emails.search_iterate("invoice", limit=5))) == 6


def test_retries_then_succeeds_on_429(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _: None)
    attempts = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            return error_response(429, "Rate limit exceeded", headers={"Retry-After": "0"})
        return json_response({"id": "m1", "email": "a@b.dev"})

    with make_client(handler, max_retries=3) as client:
        mailbox = client.mailbox.get()

    assert attempts["n"] == 3
    assert mailbox.id == "m1"


def test_gives_up_after_retry_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _: None)
    attempts = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return error_response(429, "Rate limit exceeded", headers={"Retry-After": "0"})

    with make_client(handler, max_retries=2) as client, pytest.raises(RateLimitError):
        client.mailbox.get()

    assert attempts["n"] == 3


def test_does_not_retry_mutations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _: None)
    attempts = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return error_response(503, "Database unavailable")

    with make_client(handler, max_retries=3) as client:
        with pytest.raises(ServerError):
            client.emails.favorite("abc")

    assert attempts["n"] == 1


def test_does_not_retry_non_retryable_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _: None)
    attempts = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return error_response(404, "Email not found")

    with make_client(handler, max_retries=3) as client, pytest.raises(NotFoundError):
        client.emails.get("abc")

    assert attempts["n"] == 1


def test_markdown_retries_504_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _: None)
    attempts = {"n": 0}
    detail = {
        "id": "abc",
        "from": {"name": "", "address": "a@b.dev"},
        "to": [],
        "cc": [],
        "subject": "s",
        "content": "# Heading",
        "timestamp": "2026-01-01T00:00:00Z",
        "status": "Open",
        "email_state": "Open",
        "attachments": [],
        "headers": {},
        "security": {},
    }

    def handler(_: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            return error_response(504, "Markdown conversion timed out")
        return json_response(detail)

    with make_client(handler) as client:
        result = client.emails.get_markdown("abc", max_retries=3)

    assert attempts["n"] == 3
    assert result.content == "# Heading"
