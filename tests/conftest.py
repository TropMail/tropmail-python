from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from tropmail import AsyncTropMail, TropMail

API_KEY = "a" * 32
BASE_URL = "https://api.example.test/api/v1"

Handler = Callable[[httpx.Request], httpx.Response]


def envelope(data: Any, *, message: str = "ok", success: bool = True) -> dict[str, Any]:
    return {"success": success, "message": message, "data": data, "error": None}


def json_response(
    data: Any,
    *,
    status: int = 200,
    headers: dict[str, str] | None = None,
    message: str = "ok",
) -> httpx.Response:
    return httpx.Response(
        status,
        json=envelope(data, message=message),
        headers={"X-Request-ID": "req-123", **(headers or {})},
    )


def error_response(
    status: int,
    message: str,
    *,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    body = {"success": False, "message": message, "data": None, "error": message}
    return httpx.Response(
        status,
        content=json.dumps(body),
        headers={"content-type": "application/json", "X-Request-ID": "req-err", **(headers or {})},
    )


def make_client(handler: Handler, **kwargs: Any) -> TropMail:
    transport = httpx.MockTransport(handler)
    return TropMail(
        API_KEY,
        base_url=BASE_URL,
        throttle=kwargs.pop("throttle", False),
        http_client=httpx.Client(transport=transport),
        **kwargs,
    )


def make_async_client(handler: Handler, **kwargs: Any) -> AsyncTropMail:
    transport = httpx.MockTransport(handler)
    return AsyncTropMail(
        API_KEY,
        base_url=BASE_URL,
        throttle=kwargs.pop("throttle", False),
        http_client=httpx.AsyncClient(transport=transport),
        **kwargs,
    )


EMAIL_ITEM = {
    "id": "11111111-1111-1111-1111-111111111111",
    "timestamp": "2026-01-01T00:00:00Z",
    "subject": "Welcome",
    "from": {"name": "Sender", "address": "sender@example.com"},
    "body": "Preview text",
    "attachmentsCount": 1,
    "status": "Favorite",
    "email_state": "Open",
    "action_status": "Favorite",
}

EMAIL_DETAIL = {
    "id": "11111111-1111-1111-1111-111111111111",
    "from": {"name": "Sender", "address": "sender@example.com"},
    "to": [{"name": "", "address": "me@tropmail.com"}],
    "cc": [],
    "subject": "Welcome",
    "content": "<p>Hello</p>",
    "timestamp": "2026-01-01T00:00:00Z",
    "status": "Open",
    "email_state": "Open",
    "attachments": [
        {
            "attachment_id": "22222222-2222-2222-2222-222222222222",
            "filename": "invoice.pdf",
            "size": 1024,
            "mime_type": "application/pdf",
            "scan_status": "Clean",
        }
    ],
    "headers": {},
    "security": {},
}


@pytest.fixture
def email_item() -> dict[str, Any]:
    return dict(EMAIL_ITEM)


@pytest.fixture
def email_detail() -> dict[str, Any]:
    return dict(EMAIL_DETAIL)
