"""Email listing, search, detail and action resources."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import quote

from tropmail._errors import MarkdownTimeoutError
from tropmail._http import execute_request, execute_request_async, full_jitter_delay
from tropmail._models import (
    DownloadResponse,
    Email,
    EmailActionResult,
    EmailDetail,
    ListEmailsData,
    ScanResponse,
)
from tropmail.mailboxes import mailbox_path

if TYPE_CHECKING:
    from tropmail.client import AsyncTropMail, TropMail

EmailRef = str | Email | EmailDetail

StatusFilter = Literal[
    "all",
    "Open",
    "Close",
    "Favorite",
    "Delete",
    "Block",
    "Phishing",
    "Scam",
    "Malicious",
]
EmailView = Literal["text", "html", "markdown"]
EmailState = Literal["Open", "Close"]
ActionStatus = Literal["Favorite", "Delete", "Block", "Phishing", "Scam", "Malicious", ""]

ScanResponseList = list[ScanResponse]
DownloadResponseList = list[DownloadResponse]


def resolve_email_ref(
    id_or_email: EmailRef,
    timestamp: str | None = None,
) -> tuple[str, str | None]:
    """Resolve an id or email object into ``(id, timestamp)``.

    Passing the email object you already have forwards its timestamp for a
    faster lookup than a bare id.
    """
    if isinstance(id_or_email, (Email, EmailDetail)):
        return id_or_email.id, timestamp or id_or_email.timestamp or None
    return id_or_email, timestamp


def emails_path(mailbox_id: str, *parts: str) -> str:
    quoted = tuple(quote(part, safe="") for part in parts)
    return mailbox_path(mailbox_id, "emails", *quoted)


def detail_path(mailbox_id: str, email_id: str, view: EmailView) -> str:
    if view == "html":
        return emails_path(mailbox_id, email_id)
    return emails_path(mailbox_id, email_id, view)


def _action_body(
    email_state: EmailState | None,
    action_status: ActionStatus | None,
    timestamp: str | None,
) -> dict[str, Any]:
    if email_state is None and action_status is None:
        raise ValueError("Provide at least one of email_state or action_status")
    body: dict[str, Any] = {}
    if email_state is not None:
        body["email_state"] = email_state
    if action_status is not None:
        body["action_status"] = action_status
    if timestamp:
        body["timestamp"] = timestamp
    return body


class EmailsResource:
    """Endpoints under ``/mailboxes/{id}/emails``."""

    def __init__(self, client: TropMail) -> None:
        self._client = client

    def list(
        self,
        *,
        mailbox_id: str,
        limit: int = 10,
        page: int = 1,
        status: StatusFilter = "all",
    ) -> ListEmailsData:
        """Return one page of emails."""
        return execute_request(
            self._client._http_client,
            self._client._config,
            "GET",
            emails_path(mailbox_id),
            params={"limit": str(limit), "page": str(page), "status": status},
            data_type=ListEmailsData,
        )

    def search(
        self,
        query: str,
        *,
        mailbox_id: str,
        limit: int = 10,
        page: int = 1,
    ) -> ListEmailsData:
        """Full-text search. ``data.total`` is always 0 for search."""
        return execute_request(
            self._client._http_client,
            self._client._config,
            "GET",
            emails_path(mailbox_id, "search"),
            params={"query": query, "limit": str(limit), "page": str(page)},
            data_type=ListEmailsData,
        )

    def iterate(
        self,
        *,
        mailbox_id: str,
        limit: int = 100,
        status: StatusFilter = "all",
        start_page: int = 1,
    ) -> Iterator[Email]:
        """Yield every email, paging automatically.

        Stops on the first short page: ``total`` counts the whole mailbox and cannot
        be used to detect the end of a filtered result set.
        """
        page = start_page
        while True:
            data = self.list(mailbox_id=mailbox_id, limit=limit, page=page, status=status)
            yield from data.emails
            if len(data.emails) < limit:
                return
            page += 1

    def search_iterate(
        self,
        query: str,
        *,
        mailbox_id: str,
        limit: int = 100,
    ) -> Iterator[Email]:
        """Yield every search hit, paging automatically."""
        page = 1
        while True:
            data = self.search(query, mailbox_id=mailbox_id, limit=limit, page=page)
            yield from data.emails
            if len(data.emails) < limit:
                return
            page += 1

    def get(
        self,
        mailbox_id: str,
        id_or_email: EmailRef,
        *,
        view: EmailView = "html",
        timestamp: str | None = None,
    ) -> EmailDetail:
        """Fetch a single email in the requested view."""
        email_id, ts = resolve_email_ref(id_or_email, timestamp)
        return execute_request(
            self._client._http_client,
            self._client._config,
            "GET",
            detail_path(mailbox_id, email_id, view),
            params={"timestamp": ts} if ts else None,
            data_type=EmailDetail,
        )

    def get_markdown(
        self,
        mailbox_id: str,
        id_or_email: EmailRef,
        *,
        timestamp: str | None = None,
        max_retries: int | None = None,
    ) -> EmailDetail:
        """Fetch the markdown view, retrying the 504 the conversion can return.

        The server blocks up to ~60s while converting, then answers 504 and expects
        the same GET to be retried.
        """
        email_id, ts = resolve_email_ref(id_or_email, timestamp)
        attempts = (self._client._config.max_retries if max_retries is None else max_retries) + 1
        for attempt in range(attempts):
            try:
                return execute_request(
                    self._client._http_client,
                    self._client._config,
                    "GET",
                    emails_path(mailbox_id, email_id, "markdown"),
                    params={"timestamp": ts} if ts else None,
                    retry=False,
                    data_type=EmailDetail,
                )
            except MarkdownTimeoutError:
                if attempt >= attempts - 1:
                    raise
                time.sleep(full_jitter_delay(attempt))
        raise MarkdownTimeoutError("Markdown conversion timed out", status=504)

    def update(
        self,
        mailbox_id: str,
        id_or_email: EmailRef,
        *,
        email_state: EmailState | None = None,
        action_status: ActionStatus | None = None,
        timestamp: str | None = None,
    ) -> EmailActionResult:
        """Update ``email_state`` and/or ``action_status``.

        Pass ``action_status=""`` to clear a previous action.
        """
        email_id, ts = resolve_email_ref(id_or_email, timestamp)
        return execute_request(
            self._client._http_client,
            self._client._config,
            "POST",
            emails_path(mailbox_id, email_id),
            json=_action_body(email_state, action_status, ts),
            retry=False,
            data_type=EmailActionResult,
        )

    def open(self, mailbox_id: str, id_or_email: EmailRef, **kwargs: Any) -> EmailActionResult:
        """Mark an email as opened."""
        return self.update(mailbox_id, id_or_email, email_state="Open", **kwargs)

    def close(self, mailbox_id: str, id_or_email: EmailRef, **kwargs: Any) -> EmailActionResult:
        """Mark an email as closed."""
        return self.update(mailbox_id, id_or_email, email_state="Close", **kwargs)

    def favorite(self, mailbox_id: str, id_or_email: EmailRef, **kwargs: Any) -> EmailActionResult:
        """Flag an email as a favorite."""
        return self.update(mailbox_id, id_or_email, action_status="Favorite", **kwargs)

    def block(self, mailbox_id: str, id_or_email: EmailRef, **kwargs: Any) -> EmailActionResult:
        """Block the sender and stop future inbound mail from them."""
        return self.update(mailbox_id, id_or_email, action_status="Block", **kwargs)

    def delete(self, mailbox_id: str, id_or_email: EmailRef, **kwargs: Any) -> EmailActionResult:
        """Soft-delete an email."""
        return self.update(mailbox_id, id_or_email, action_status="Delete", **kwargs)

    def clear_action(
        self, mailbox_id: str, id_or_email: EmailRef, **kwargs: Any
    ) -> EmailActionResult:
        """Clear any action status, unblocking the sender if it was blocked."""
        return self.update(mailbox_id, id_or_email, action_status="", **kwargs)

    def scan_attachments(self, mailbox_id: str, id_or_email: EmailRef) -> ScanResponseList:
        """Kick off scans for every unscanned attachment on an email."""
        email_id, _ = resolve_email_ref(id_or_email)
        return execute_request(
            self._client._http_client,
            self._client._config,
            "POST",
            emails_path(mailbox_id, email_id, "scan-attachments"),
            retry=False,
            data_type=ScanResponseList,
        )

    def download_attachments(self, mailbox_id: str, id_or_email: EmailRef) -> DownloadResponseList:
        """List attachments for authenticated download (use attachments.download_to)."""
        email_id, _ = resolve_email_ref(id_or_email)
        return execute_request(
            self._client._http_client,
            self._client._config,
            "GET",
            emails_path(mailbox_id, email_id, "download-attachments"),
            data_type=DownloadResponseList,
        )


class AsyncEmailsResource:
    """Async twin of :class:`EmailsResource`."""

    def __init__(self, client: AsyncTropMail) -> None:
        self._client = client

    async def list(
        self,
        *,
        mailbox_id: str,
        limit: int = 10,
        page: int = 1,
        status: StatusFilter = "all",
    ) -> ListEmailsData:
        return await execute_request_async(
            self._client._http_client,
            self._client._config,
            "GET",
            emails_path(mailbox_id),
            params={"limit": str(limit), "page": str(page), "status": status},
            data_type=ListEmailsData,
        )

    async def search(
        self,
        query: str,
        *,
        mailbox_id: str,
        limit: int = 10,
        page: int = 1,
    ) -> ListEmailsData:
        return await execute_request_async(
            self._client._http_client,
            self._client._config,
            "GET",
            emails_path(mailbox_id, "search"),
            params={"query": query, "limit": str(limit), "page": str(page)},
            data_type=ListEmailsData,
        )

    async def iterate(
        self,
        *,
        mailbox_id: str,
        limit: int = 100,
        status: StatusFilter = "all",
        start_page: int = 1,
    ) -> AsyncIterator[Email]:
        page = start_page
        while True:
            data = await self.list(
                mailbox_id=mailbox_id, limit=limit, page=page, status=status
            )
            for email in data.emails:
                yield email
            if len(data.emails) < limit:
                return
            page += 1

    async def search_iterate(
        self,
        query: str,
        *,
        mailbox_id: str,
        limit: int = 100,
    ) -> AsyncIterator[Email]:
        page = 1
        while True:
            data = await self.search(query, mailbox_id=mailbox_id, limit=limit, page=page)
            for email in data.emails:
                yield email
            if len(data.emails) < limit:
                return
            page += 1

    async def get(
        self,
        mailbox_id: str,
        id_or_email: EmailRef,
        *,
        view: EmailView = "html",
        timestamp: str | None = None,
    ) -> EmailDetail:
        email_id, ts = resolve_email_ref(id_or_email, timestamp)
        return await execute_request_async(
            self._client._http_client,
            self._client._config,
            "GET",
            detail_path(mailbox_id, email_id, view),
            params={"timestamp": ts} if ts else None,
            data_type=EmailDetail,
        )

    async def get_markdown(
        self,
        mailbox_id: str,
        id_or_email: EmailRef,
        *,
        timestamp: str | None = None,
        max_retries: int | None = None,
    ) -> EmailDetail:
        email_id, ts = resolve_email_ref(id_or_email, timestamp)
        attempts = (self._client._config.max_retries if max_retries is None else max_retries) + 1
        for attempt in range(attempts):
            try:
                return await execute_request_async(
                    self._client._http_client,
                    self._client._config,
                    "GET",
                    emails_path(mailbox_id, email_id, "markdown"),
                    params={"timestamp": ts} if ts else None,
                    retry=False,
                    data_type=EmailDetail,
                )
            except MarkdownTimeoutError:
                if attempt >= attempts - 1:
                    raise
                await asyncio.sleep(full_jitter_delay(attempt))
        raise MarkdownTimeoutError("Markdown conversion timed out", status=504)

    async def update(
        self,
        mailbox_id: str,
        id_or_email: EmailRef,
        *,
        email_state: EmailState | None = None,
        action_status: ActionStatus | None = None,
        timestamp: str | None = None,
    ) -> EmailActionResult:
        email_id, ts = resolve_email_ref(id_or_email, timestamp)
        return await execute_request_async(
            self._client._http_client,
            self._client._config,
            "POST",
            emails_path(mailbox_id, email_id),
            json=_action_body(email_state, action_status, ts),
            retry=False,
            data_type=EmailActionResult,
        )

    async def open(
        self, mailbox_id: str, id_or_email: EmailRef, **kwargs: Any
    ) -> EmailActionResult:
        return await self.update(mailbox_id, id_or_email, email_state="Open", **kwargs)

    async def close(
        self, mailbox_id: str, id_or_email: EmailRef, **kwargs: Any
    ) -> EmailActionResult:
        return await self.update(mailbox_id, id_or_email, email_state="Close", **kwargs)

    async def favorite(
        self, mailbox_id: str, id_or_email: EmailRef, **kwargs: Any
    ) -> EmailActionResult:
        return await self.update(mailbox_id, id_or_email, action_status="Favorite", **kwargs)

    async def block(
        self, mailbox_id: str, id_or_email: EmailRef, **kwargs: Any
    ) -> EmailActionResult:
        return await self.update(mailbox_id, id_or_email, action_status="Block", **kwargs)

    async def delete(
        self, mailbox_id: str, id_or_email: EmailRef, **kwargs: Any
    ) -> EmailActionResult:
        return await self.update(mailbox_id, id_or_email, action_status="Delete", **kwargs)

    async def clear_action(
        self, mailbox_id: str, id_or_email: EmailRef, **kwargs: Any
    ) -> EmailActionResult:
        return await self.update(mailbox_id, id_or_email, action_status="", **kwargs)

    async def scan_attachments(
        self, mailbox_id: str, id_or_email: EmailRef
    ) -> ScanResponseList:
        email_id, _ = resolve_email_ref(id_or_email)
        return await execute_request_async(
            self._client._http_client,
            self._client._config,
            "POST",
            emails_path(mailbox_id, email_id, "scan-attachments"),
            retry=False,
            data_type=ScanResponseList,
        )

    async def download_attachments(
        self, mailbox_id: str, id_or_email: EmailRef
    ) -> DownloadResponseList:
        email_id, _ = resolve_email_ref(id_or_email)
        return await execute_request_async(
            self._client._http_client,
            self._client._config,
            "GET",
            emails_path(mailbox_id, email_id, "download-attachments"),
            data_type=DownloadResponseList,
        )
