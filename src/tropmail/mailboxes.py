"""Mailbox listing and summary resources."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from tropmail._http import execute_request, execute_request_async
from tropmail._models import HealthData, Mailbox, MailboxList

if TYPE_CHECKING:
    from tropmail.client import AsyncTropMail, TropMail


def mailbox_path(mailbox_id: str, *parts: str) -> str:
    if not mailbox_id:
        raise ValueError("mailbox_id is required")
    path = "/mailboxes/" + quote(mailbox_id, safe="")
    if parts:
        path += "/" + "/".join(parts)
    return path


class MailboxesResource:
    """``GET /mailboxes`` and ``GET /mailboxes/{id}``."""

    def __init__(self, client: TropMail) -> None:
        self._client = client

    def list(self) -> MailboxList:
        """Return every inbox this API key may see.

        Empty key scope means all current and future inboxes for the account.
        """
        return execute_request(
            self._client._http_client,
            self._client._config,
            "GET",
            "/mailboxes",
            data_type=MailboxList,
        )

    def get(self, mailbox_id: str) -> Mailbox:
        """Return the summary for one mailbox UUID."""
        return execute_request(
            self._client._http_client,
            self._client._config,
            "GET",
            mailbox_path(mailbox_id),
            data_type=Mailbox,
        )


class AsyncMailboxesResource:
    """Async twin of :class:`MailboxesResource`."""

    def __init__(self, client: AsyncTropMail) -> None:
        self._client = client

    async def list(self) -> MailboxList:
        return await execute_request_async(
            self._client._http_client,
            self._client._config,
            "GET",
            "/mailboxes",
            data_type=MailboxList,
        )

    async def get(self, mailbox_id: str) -> Mailbox:
        return await execute_request_async(
            self._client._http_client,
            self._client._config,
            "GET",
            mailbox_path(mailbox_id),
            data_type=Mailbox,
        )


def health(client: TropMail) -> HealthData:
    """Liveness probe. Requires no authentication."""
    return execute_request(
        client._http_client,
        client._config,
        "GET",
        "/health",
        auth=False,
        data_type=HealthData,
    )


async def health_async(client: AsyncTropMail) -> HealthData:
    return await execute_request_async(
        client._http_client,
        client._config,
        "GET",
        "/health",
        auth=False,
        data_type=HealthData,
    )
