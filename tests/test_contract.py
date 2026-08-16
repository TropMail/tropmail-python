"""Fails when the SDK stops covering every canonical route in the OpenAPI spec.

Docs list inboxes at ``/mailboxes`` and every other operation at ``/mailbox/{id}``.
The client still calls the ``/mailboxes/{id}`` alias; those requests are mapped
onto the documented singular templates.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx
import pytest

from conftest import MAILBOX_ID, json_response, make_client

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = PACKAGE_ROOT / "spec" / "openapi.json"
DOC_SPEC_PATH = PACKAGE_ROOT.parents[1] / "Docs" / "Doc" / "openapi.json"

ANY_PAYLOAD = {
    "id": "11111111-1111-1111-1111-111111111111",
    "email": "user@tropmail.com",
    "timestamp": "2026-01-01T00:00:00Z",
    "from": {"name": "Sender", "address": "sender@example.com"},
    "attachment_id": "22222222-2222-2222-2222-222222222222",
    "status": "ok",
    "mailboxes": [],
}


def _load_spec() -> dict[str, Any]:
    return json.loads(SPEC_PATH.read_text())


def _spec_operations() -> set[tuple[str, str]]:
    spec = _load_spec()
    return {
        (method.upper(), path)
        for path, operations in spec["paths"].items()
        for method in operations
        if method.lower() in {"get", "post", "put", "patch", "delete"}
    }


def _templatize(path: str) -> str:
    path = path.removeprefix("/api/v1")
    if path.startswith("/mailboxes/"):
        path = "/mailbox/" + path[len("/mailboxes/") :]
    rules = [
        (
            r"/mailbox/[^/]+/emails/[^/]+/(text|html|markdown)$",
            "/mailbox/{id}/emails/{emailId}/{view}",
        ),
        (r"/mailbox/[^/]+/emails/search$", "/mailbox/{id}/emails/search"),
        (
            r"/mailbox/[^/]+/emails/[^/]+/scan-attachments$",
            "/mailbox/{id}/emails/{emailId}/scan-attachments",
        ),
        (
            r"/mailbox/[^/]+/emails/[^/]+/download-attachments$",
            "/mailbox/{id}/emails/{emailId}/download-attachments",
        ),
        (r"/mailbox/[^/]+/attachments/[^/]+/scan$", "/mailbox/{id}/attachments/{attId}/scan"),
        (
            r"/mailbox/[^/]+/attachments/[^/]+/download$",
            "/mailbox/{id}/attachments/{attId}/download",
        ),
        (r"/mailbox/[^/]+/attachments/[^/]+$", "/mailbox/{id}/attachments/{attId}"),
        (r"/mailbox/[^/]+/emails/[^/]+$", "/mailbox/{id}/emails/{emailId}"),
        (r"/mailbox/[^/]+/emails$", "/mailbox/{id}/emails"),
        (r"/mailbox/[^/]+$", "/mailbox/{id}"),
    ]
    for pattern, template in rules:
        if re.search(pattern, path):
            return re.sub(pattern, template, path, count=1)
    return path


def _exercise_every_method() -> set[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()

    def handler(request: httpx.Request) -> httpx.Response:
        seen.add((request.method, _templatize(request.url.path)))
        if request.url.path.endswith("/download"):
            return httpx.Response(
                200,
                content=b"%PDF-1.4 mock",
                headers={
                    "Content-Type": "application/pdf",
                    "Content-Disposition": 'attachment; filename="invoice.pdf"',
                },
            )
        if request.url.path.endswith(("/scan-attachments", "/download-attachments")):
            return json_response([])
        return json_response(ANY_PAYLOAD)

    with make_client(handler) as client:
        client.health()
        client.mailboxes.list()
        client.mailboxes.get(MAILBOX_ID)
        client.emails.list(mailbox_id=MAILBOX_ID)
        client.emails.search("q", mailbox_id=MAILBOX_ID)
        client.emails.get(MAILBOX_ID, "id")
        client.emails.get(MAILBOX_ID, "id", view="markdown")
        client.emails.update(MAILBOX_ID, "id", email_state="Open")
        client.emails.scan_attachments(MAILBOX_ID, "id")
        client.emails.download_attachments(MAILBOX_ID, "id")
        client.attachments.get(MAILBOX_ID, "aid")
        client.attachments.scan(MAILBOX_ID, "aid")
        client.attachments.download_to(MAILBOX_ID, "aid", "/tmp/tropmail-contract-aid.pdf")

    return seen


def test_spec_file_exists() -> None:
    assert SPEC_PATH.exists(), f"missing spec at {SPEC_PATH}"


def test_spec_matches_the_published_doc_site() -> None:
    if not DOC_SPEC_PATH.exists():
        pytest.skip("Docs is not checked out next to the SDK")
    assert json.loads(DOC_SPEC_PATH.read_text()) == _load_spec(), (
        "spec/openapi.json drifted from Docs/Doc/openapi.json — run 'make sync-spec'"
    )


def test_every_spec_route_has_a_client_method() -> None:
    missing = _spec_operations() - _exercise_every_method()
    assert not missing, f"SDK does not cover: {sorted(missing)}"


def test_client_calls_no_route_outside_the_spec() -> None:
    extra = _exercise_every_method() - _spec_operations()
    assert not extra, f"SDK calls undocumented routes: {sorted(extra)}"
