from __future__ import annotations

from typing import Any

import httpx
import pytest

from conftest import EMAIL_DETAIL, EMAIL_ITEM, error_response, json_response, make_async_client
from tropmail import NotFoundError


def _page(count: int) -> dict[str, Any]:
    return {
        "emails": [dict(EMAIL_ITEM, id=f"id-{i}") for i in range(count)],
        "total": 0,
        "limit": 10,
        "page": 1,
    }


async def test_async_mailbox_get() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return json_response({"id": "m1", "email": "user@tropmail.com", "opened_count": 7})

    async with make_async_client(handler) as client:
        mailbox = await client.mailbox.get()

    assert mailbox.opened_count == 7


async def test_async_iterate_pages_until_short_page() -> None:
    pages = [_page(10), _page(4)]
    index = {"i": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        response = json_response(pages[index["i"]])
        index["i"] += 1
        return response

    async with make_async_client(handler) as client:
        collected = [email async for email in client.emails.iterate(limit=10)]

    assert len(collected) == 14


async def test_async_errors_are_typed() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return error_response(404, "Email not found")

    async with make_async_client(handler, max_retries=0) as client:
        with pytest.raises(NotFoundError):
            await client.emails.get("missing")


async def test_async_get_detail() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return json_response(EMAIL_DETAIL)

    async with make_async_client(handler) as client:
        detail = await client.emails.get("abc", view="text")

    assert detail.content == "<p>Hello</p>"
