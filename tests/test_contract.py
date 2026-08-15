"""Fails when the SDK stops covering every route in the OpenAPI spec.

The spec lives in this package (``spec/openapi.json``). When ``Docs/`` is checked
out next to ``Sdk/`` in the TropMail workspace, the test also asserts they match.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx
import pytest

from conftest import json_response, make_client

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = PACKAGE_ROOT / "spec" / "openapi.json"
DOC_SPEC_PATH = PACKAGE_ROOT.parents[1] / "Docs" / "Doc" / "openapi.json"

# Superset of every model's required fields, so one payload satisfies any decoder.
ANY_PAYLOAD = {
    "id": "11111111-1111-1111-1111-111111111111",
    "email": "user@tropmail.com",
    "timestamp": "2026-01-01T00:00:00Z",
    "from": {"name": "Sender", "address": "sender@example.com"},
    "attachment_id": "22222222-2222-2222-2222-222222222222",
    "status": "ok",
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
    """Turn a concrete request path back into its OpenAPI template."""
    path = path.removeprefix("/api/v1")
    path = re.sub(r"/email/[^/]+/(text|html|markdown)$", "/email/{id}/{view}", path)
    path = re.sub(r"/email/[^/]+/scan-attachments$", "/email/{id}/scan-attachments", path)
    path = re.sub(
        r"/email/[^/]+/download-attachments$", "/email/{id}/download-attachments", path
    )
    path = re.sub(r"/attachment/[^/]+/scan$", "/attachment/{id}/scan", path)
    path = re.sub(r"/attachment/[^/]+/download$", "/attachment/{id}/download", path)
    path = re.sub(r"/attachment/[^/]+$", "/attachment/{id}", path)
    path = re.sub(r"/email/[^/]+$", "/email/{id}", path)
    return path


def _exercise_every_method() -> set[tuple[str, str]]:
    """Call every SDK method once against a mock and record the routes hit."""
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
        client.mailbox.health()
        client.mailbox.validate()
        client.mailbox.get()
        client.emails.list()
        client.emails.search("q")
        client.emails.get("id")
        client.emails.get("id", view="markdown")
        client.emails.update("id", email_state="Open")
        client.emails.scan_attachments("id")
        client.emails.download_attachments("id")
        client.attachments.get("aid")
        client.attachments.scan("aid")
        client.attachments.download_to("aid", "/tmp/tropmail-contract-aid.pdf")

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
