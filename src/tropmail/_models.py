"""Typed models mirroring the Api handler response structs."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Generic, TypeVar

import msgspec

T = TypeVar("T")


class EmailFrom(msgspec.Struct):
    """An email address with an optional display name."""

    name: str = ""
    address: str = ""


class Email(msgspec.Struct):
    """A list item from ``GET /mailbox/{id}/emails`` or search."""

    id: str
    timestamp: str
    from_: EmailFrom = msgspec.field(name="from")
    subject: str = ""
    preview: str = ""
    attachments_count: int = msgspec.field(name="attachmentsCount", default=0)
    status: str = ""
    email_state: str = ""
    action_status: str | None = None


class ScanFileHashes(msgspec.Struct):
    """Content hashes captured during malware scan."""

    sha256: str | None = None
    sha1: str | None = None
    md5: str | None = None


class ScanEngineResult(msgspec.Struct):
    """One AV engine verdict inside a ScanReport."""

    engine: str = ""
    category: str = "undetected"
    result: str | None = None


class ScanReportStats(msgspec.Struct):
    """Aggregated engine verdict counts."""

    harmless: int = 0
    malicious: int = 0
    suspicious: int = 0
    undetected: int = 0


class ScanReport(msgspec.Struct):
    """Shaped malware report stored in ``scan_result`` (no provider branding)."""

    status: str = "Unknown"
    scannedAt: str = ""
    stats: ScanReportStats = msgspec.field(default_factory=ScanReportStats)
    engines: list[ScanEngineResult] = msgspec.field(default_factory=list)
    hashes: ScanFileHashes | None = None
    error: str | None = None


class EmailAttachment(msgspec.Struct):
    """An attachment as embedded in an email detail response."""

    attachment_id: str
    filename: str | None = None
    size: int | None = None
    mime_type: str | None = None
    content_id: str | None = None
    disposition: str | None = None
    scan_status: str = "NotScanned"
    scan_result: ScanReport | None = None
    scanned_at: str | None = None


class EmailParts(msgspec.Struct):
    """Optional extras from inbound (newer mail only)."""

    listUnsubscribe: dict[str, Any] | None = None
    calendar: dict[str, Any] | None = None
    inlineCids: dict[str, str] | None = None


class EmailDetail(msgspec.Struct):
    """Full email detail from ``GET /mailbox/{id}/emails/{emailId}``."""

    id: str
    from_: EmailFrom = msgspec.field(name="from")
    to: list[EmailFrom] = msgspec.field(default_factory=list)
    cc: list[EmailFrom] = msgspec.field(default_factory=list)
    subject: str = ""
    content: str = ""
    timestamp: str = ""
    status: str = ""
    email_state: str = ""
    action_status: str | None = None
    attachments: list[EmailAttachment] = msgspec.field(default_factory=list)
    parts: EmailParts | None = None
    headers: dict[str, Any] = msgspec.field(default_factory=dict)
    security: dict[str, Any] = msgspec.field(default_factory=dict)


class EmailActionResult(msgspec.Struct):
    """Result of ``POST /mailbox/{id}/emails/{emailId}``.

    The handler returns a dynamic object: state/action updates echo the fields that
    changed, while a ``Block`` action returns ``action_status`` plus ``sender_email``.
    """

    email_id: str | None = None
    email_state: str | None = None
    action_status: str | None = None
    sender_email: str | None = None


class Mailbox(msgspec.Struct):
    """Mailbox summary from ``GET /mailbox/{id}``."""

    id: str
    email: str
    opened_count: int = 0
    closed_count: int = 0
    favorite_count: int = 0


class MailboxList(msgspec.Struct):
    """Payload of ``GET /mailboxes``.

    Sequence-like so ``client.mailboxes.list()[0]`` works alongside
    ``.mailboxes[0]``.
    """

    mailboxes: list[Mailbox] = msgspec.field(default_factory=list)

    def __iter__(self) -> Iterator[Mailbox]:
        return iter(self.mailboxes)

    def __len__(self) -> int:
        return len(self.mailboxes)

    def __getitem__(self, index: int) -> Mailbox:
        return self.mailboxes[index]


class Attachment(msgspec.Struct):
    """Attachment metadata from ``GET /mailbox/{id}/attachments/{attId}``."""

    attachment_id: str
    email_id: str = ""
    filename: str = ""
    size: int | None = None
    mime_type: str | None = None
    content_id: str | None = None
    disposition: str | None = None
    scan_status: str = "NotScanned"
    scan_result: ScanReport | None = None
    scanned_at: str | None = None
    created_at: str = ""


class DownloadResponse(msgspec.Struct):
    """Metadata from ``GET /mailbox/{id}/emails/{emailId}/download-attachments``.

    Fetch bytes with :meth:`AttachmentsResource.download_to`.
    """

    attachment_id: str = ""
    email_id: str = ""
    filename: str = ""
    size: int | None = None
    mime_type: str | None = None
    scan_status: str = "NotScanned"
    scanned_at: str | None = None
    available: bool = False
    message: str = ""


class ScanResponse(msgspec.Struct):
    """Response from ``POST /mailbox/{id}/attachments/{attId}/scan``.

    A new scan is ``Processing``. Call ``attachments.get`` for ``scan_result``.
    """

    attachment_id: str = ""
    email_id: str = ""
    filename: str = ""
    status: str = ""
    message: str = ""
    size: int | None = None
    mime_type: str | None = None
    scan_status: str = "NotScanned"
    scanned_at: str | None = None


class HealthData(msgspec.Struct):
    """Service health from ``GET /health``."""

    status: str = ""
    version: str = ""
    timestamp: str = ""


class ListEmailsData(msgspec.Struct):
    """Paginated email list.

    ``total`` on list is ``opened_count + closed_count``. ``total`` on search is
    the match count. Iterators still stop on a short page.
    """

    emails: list[Email] = msgspec.field(default_factory=list)
    total: int = 0
    limit: int = 10
    page: int = 1


class Envelope(msgspec.Struct, Generic[T]):
    """The standard response envelope, decoded in a single pass."""

    success: bool = False
    message: str = ""
    data: T | None = None
    error: Any = None


class ErrorEnvelope(msgspec.Struct):
    """Lenient envelope used to extract a message from a failed response."""

    success: bool = False
    message: str = ""
    error: Any = None
