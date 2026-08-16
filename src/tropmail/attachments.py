"""Attachment metadata, scanning and download resources."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote

import httpx

from tropmail._errors import ConnectionError, map_http_error
from tropmail._http import execute_request, execute_request_async
from tropmail._models import Attachment, ScanResponse
from tropmail._rate_limit import parse_retry_after
from tropmail.mailboxes import mailbox_path

if TYPE_CHECKING:
    from tropmail.client import AsyncTropMail, TropMail

AttachmentRef = str | Attachment

_DOWNLOAD_CHUNK = 64 * 1024


def resolve_attachment_id(id_or_attachment: AttachmentRef) -> str:
    if isinstance(id_or_attachment, Attachment):
        return id_or_attachment.attachment_id
    return id_or_attachment


def attachment_path(mailbox_id: str, attachment_id: str, *parts: str) -> str:
    return mailbox_path(mailbox_id, "attachments", quote(attachment_id, safe=""), *parts)


def _stream_download(
    client: httpx.Client,
    *,
    base_url: str,
    api_key: str | None,
    mailbox_id: str,
    attachment_id: str,
    destination: Path,
) -> Path:
    url = f"{base_url}{attachment_path(mailbox_id, attachment_id, 'download')}"
    headers = {
        "Accept": "*/*",
        "X-Request-ID": str(uuid.uuid4()),
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with client.stream("GET", url, headers=headers, follow_redirects=True) as response:
            if response.status_code >= 400:
                response.read()
                request_id = response.headers.get("X-Request-ID")
                message = response.text.strip() or f"HTTP {response.status_code}"
                raise map_http_error(
                    response.status_code,
                    message,
                    request_id=request_id,
                    retry_after=parse_retry_after(response.headers),
                )
            with destination.open("wb") as handle:
                for chunk in response.iter_bytes(_DOWNLOAD_CHUNK):
                    handle.write(chunk)
    except httpx.TransportError as exc:
        raise ConnectionError(str(exc)) from exc
    return destination


async def _stream_download_async(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str | None,
    mailbox_id: str,
    attachment_id: str,
    destination: Path,
) -> Path:
    url = f"{base_url}{attachment_path(mailbox_id, attachment_id, 'download')}"
    headers = {
        "Accept": "*/*",
        "X-Request-ID": str(uuid.uuid4()),
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with client.stream(
            "GET", url, headers=headers, follow_redirects=True
        ) as response:
            if response.status_code >= 400:
                await response.aread()
                request_id = response.headers.get("X-Request-ID")
                message = response.text.strip() or f"HTTP {response.status_code}"
                raise map_http_error(
                    response.status_code,
                    message,
                    request_id=request_id,
                    retry_after=parse_retry_after(response.headers),
                )
            with destination.open("wb") as handle:
                async for chunk in response.aiter_bytes(_DOWNLOAD_CHUNK):
                    handle.write(chunk)
    except httpx.TransportError as exc:
        raise ConnectionError(str(exc)) from exc
    return destination


class AttachmentsResource:
    """Endpoints under ``/mailboxes/{id}/attachments/{attId}``."""

    def __init__(self, client: TropMail) -> None:
        self._client = client

    def get(self, mailbox_id: str, id_or_attachment: AttachmentRef) -> Attachment:
        """Fetch attachment metadata."""
        return execute_request(
            self._client._http_client,
            self._client._config,
            "GET",
            attachment_path(mailbox_id, resolve_attachment_id(id_or_attachment)),
            data_type=Attachment,
        )

    def scan(self, mailbox_id: str, id_or_attachment: AttachmentRef) -> ScanResponse:
        """Trigger a malware scan, or return the cached result when already scanned."""
        return execute_request(
            self._client._http_client,
            self._client._config,
            "POST",
            attachment_path(mailbox_id, resolve_attachment_id(id_or_attachment), "scan"),
            retry=False,
            data_type=ScanResponse,
        )

    def download_to(
        self,
        mailbox_id: str,
        id_or_attachment: AttachmentRef,
        path: str | os.PathLike[str],
    ) -> Path:
        """Stream an attachment to disk via authenticated ``GET .../download``."""
        return _stream_download(
            self._client._http_client,
            base_url=self._client._config.base_url,
            api_key=self._client._config.api_key,
            mailbox_id=mailbox_id,
            attachment_id=resolve_attachment_id(id_or_attachment),
            destination=Path(path),
        )


class AsyncAttachmentsResource:
    """Async twin of :class:`AttachmentsResource`."""

    def __init__(self, client: AsyncTropMail) -> None:
        self._client = client

    async def get(self, mailbox_id: str, id_or_attachment: AttachmentRef) -> Attachment:
        return await execute_request_async(
            self._client._http_client,
            self._client._config,
            "GET",
            attachment_path(mailbox_id, resolve_attachment_id(id_or_attachment)),
            data_type=Attachment,
        )

    async def scan(self, mailbox_id: str, id_or_attachment: AttachmentRef) -> ScanResponse:
        return await execute_request_async(
            self._client._http_client,
            self._client._config,
            "POST",
            attachment_path(mailbox_id, resolve_attachment_id(id_or_attachment), "scan"),
            retry=False,
            data_type=ScanResponse,
        )

    async def download_to(
        self,
        mailbox_id: str,
        id_or_attachment: AttachmentRef,
        path: str | os.PathLike[str],
    ) -> Path:
        return await _stream_download_async(
            self._client._http_client,
            base_url=self._client._config.base_url,
            api_key=self._client._config.api_key,
            mailbox_id=mailbox_id,
            attachment_id=resolve_attachment_id(id_or_attachment),
            destination=Path(path),
        )
