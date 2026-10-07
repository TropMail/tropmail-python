"""Sync and async TropMail clients."""

from __future__ import annotations

from types import TracebackType

import httpx

from tropmail import mailboxes as mailbox_routes
from tropmail._auth import resolve_api_key
from tropmail._http import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    RequestConfig,
)
from tropmail._models import HealthData
from tropmail._rate_limit import RateLimitInfo
from tropmail._version import __version__
from tropmail.attachments import AsyncAttachmentsResource, AttachmentsResource
from tropmail.emails import AsyncEmailsResource, EmailsResource
from tropmail.mailboxes import AsyncMailboxesResource, MailboxesResource

_USER_AGENT = f"tropmail-python/{__version__}"

# The API allows 3-50 requests/sec depending on tier; a small pool is plenty and
# keeps connections warm so repeated calls skip the TLS handshake.
_LIMITS = httpx.Limits(max_connections=20, max_keepalive_connections=10)


class TropMail:
    """Synchronous client for the TropMail API.

    Args:
        api_key: API key from the dashboard (starts with ``tm_live_``).
            Falls back to ``TROPMAIL_API_KEY``.
        base_url: API base URL including the ``/api/v1`` path.
        timeout: Per-request timeout in seconds. The markdown view can block ~60s.
        max_retries: Retry budget for idempotent requests.
        throttle: Pace requests to the tier budget advertised by the server.
        http_client: Bring your own ``httpx.Client``.

    Example:
        >>> with TropMail() as client:
        ...     boxes = client.mailboxes.list()
        ...     for email in client.emails.iterate(mailbox_id=boxes[0].id, status="Open"):
        ...         print(email.subject)
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        throttle: bool = True,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._config = RequestConfig(
            base_url=base_url,
            api_key=resolve_api_key(api_key),
            max_retries=max_retries,
            timeout=timeout,
            throttle=throttle,
        )
        self._owns_client = http_client is None
        self._http_client = http_client or httpx.Client(
            timeout=timeout,
            limits=_LIMITS,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=False,
        )

        self.mailboxes = MailboxesResource(self)
        self.emails = EmailsResource(self)
        self.attachments = AttachmentsResource(self)

    def health(self) -> HealthData:
        """Liveness probe. Requires no authentication."""
        return mailbox_routes.health(self)

    @property
    def rate_limit(self) -> RateLimitInfo | None:
        """Rate-limit window reported by the most recent response."""
        return self._config.rate_limit

    @property
    def base_url(self) -> str:
        return self._config.base_url

    def close(self) -> None:
        if self._owns_client:
            self._http_client.close()

    def __enter__(self) -> TropMail:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


class AsyncTropMail:
    """Asynchronous client for the TropMail API.

    Example:
        >>> async with AsyncTropMail() as client:
        ...     boxes = await client.mailboxes.list()
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        throttle: bool = True,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = RequestConfig(
            base_url=base_url,
            api_key=resolve_api_key(api_key),
            max_retries=max_retries,
            timeout=timeout,
            throttle=throttle,
        )
        self._owns_client = http_client is None
        self._http_client = http_client or httpx.AsyncClient(
            timeout=timeout,
            limits=_LIMITS,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=False,
        )

        self.mailboxes = AsyncMailboxesResource(self)
        self.emails = AsyncEmailsResource(self)
        self.attachments = AsyncAttachmentsResource(self)

    async def health(self) -> HealthData:
        return await mailbox_routes.health_async(self)

    @property
    def rate_limit(self) -> RateLimitInfo | None:
        return self._config.rate_limit

    @property
    def base_url(self) -> str:
        return self._config.base_url

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http_client.aclose()

    async def __aenter__(self) -> AsyncTropMail:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()
