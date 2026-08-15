"""Official Python SDK for the TropMail API.

Quick start::

    from tropmail import TropMail

    with TropMail() as client:
        for email in client.emails.iterate(status="Open"):
            print(email.subject, email.from_.address)
"""

from __future__ import annotations

from tropmail._auth import InvalidAPIKeyError, validate_api_key
from tropmail._errors import (
    AuthenticationError,
    ConnectionError,
    MarkdownTimeoutError,
    NotFoundError,
    RateLimitError,
    ServerError,
    TierError,
    TropMailError,
    ValidationError,
)
from tropmail._http import DEFAULT_BASE_URL
from tropmail._models import (
    Attachment,
    DownloadResponse,
    Email,
    EmailActionResult,
    EmailAttachment,
    EmailDetail,
    EmailFrom,
    HealthData,
    ListEmailsData,
    Mailbox,
    ScanReport,
    ScanResponse,
    ValidateResponse,
)
from tropmail._rate_limit import RateLimitInfo
from tropmail._version import __version__
from tropmail.client import AsyncTropMail, TropMail
from tropmail.emails import ActionStatus, EmailState, EmailView, StatusFilter

__all__ = [
    "DEFAULT_BASE_URL",
    "ActionStatus",
    "AsyncTropMail",
    "Attachment",
    "AuthenticationError",
    "ConnectionError",
    "DownloadResponse",
    "Email",
    "EmailActionResult",
    "EmailAttachment",
    "EmailDetail",
    "EmailFrom",
    "EmailState",
    "EmailView",
    "HealthData",
    "InvalidAPIKeyError",
    "ListEmailsData",
    "Mailbox",
    "MarkdownTimeoutError",
    "NotFoundError",
    "RateLimitError",
    "RateLimitInfo",
    "ScanReport",
    "ScanResponse",
    "ServerError",
    "StatusFilter",
    "TierError",
    "TropMail",
    "TropMailError",
    "ValidateResponse",
    "ValidationError",
    "__version__",
    "validate_api_key",
]
