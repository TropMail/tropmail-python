"""Mailbox and API-key resources."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tropmail._http import execute_request, execute_request_async
from tropmail._models import HealthData, Mailbox, ValidateResponse

if TYPE_CHECKING:
    from tropmail.client import AsyncTropMail, TropMail


class MailboxResource:
    """``GET /mailbox``, ``GET /validate`` and ``GET /health``."""

    def __init__(self, client: TropMail) -> None:
        self._client = client

    def get(self) -> Mailbox:
        """Return the mailbox summary for the authenticated key."""
        return execute_request(
            self._client._http_client,
            self._client._config,
            "GET",
            "/mailbox",
            data_type=Mailbox,
        )

    def validate(self) -> ValidateResponse:
        """Confirm the API key and learn its mailbox id and tier."""
        return execute_request(
            self._client._http_client,
            self._client._config,
            "GET",
            "/validate",
            data_type=ValidateResponse,
        )

    def health(self) -> HealthData:
        """Liveness probe. Requires no authentication."""
        return execute_request(
            self._client._http_client,
            self._client._config,
            "GET",
            "/health",
            auth=False,
            data_type=HealthData,
        )


class AsyncMailboxResource:
    """Async twin of :class:`MailboxResource`."""

    def __init__(self, client: AsyncTropMail) -> None:
        self._client = client

    async def get(self) -> Mailbox:
        return await execute_request_async(
            self._client._http_client,
            self._client._config,
            "GET",
            "/mailbox",
            data_type=Mailbox,
        )

    async def validate(self) -> ValidateResponse:
        return await execute_request_async(
            self._client._http_client,
            self._client._config,
            "GET",
            "/validate",
            data_type=ValidateResponse,
        )

    async def health(self) -> HealthData:
        return await execute_request_async(
            self._client._http_client,
            self._client._config,
            "GET",
            "/health",
            auth=False,
            data_type=HealthData,
        )
