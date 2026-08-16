"""Fetch several message bodies concurrently with the async client.

    export TROPMAIL_API_KEY=...
    python examples/async_inbox.py
"""

from __future__ import annotations

import asyncio

from tropmail import AsyncTropMail, Email, EmailDetail, TropMailError


async def read(client: AsyncTropMail, mailbox_id: str, email: Email) -> EmailDetail | None:
    """Fetch one body, returning None instead of raising so one failure does
    not sink the whole batch."""
    try:
        return await client.emails.get(mailbox_id, email, view="text")
    except TropMailError as error:
        print(f"{email.id}: {error}")
        return None


async def main() -> None:
    async with AsyncTropMail() as client:
        boxes = await client.mailboxes.list()
        if not boxes:
            print("This API key has no mailboxes.")
            return
        mailbox = boxes[0]
        print(f"{mailbox.email}\n")

        unread: list[Email] = []
        async for email in client.emails.iterate(mailbox_id=mailbox.id, status="Open"):
            unread.append(email)
            if len(unread) == 10:
                break

        if not unread:
            print("Nothing unread.")
            return

        details = await asyncio.gather(
            *(read(client, mailbox.id, email) for email in unread)
        )

        for email, detail in zip(unread, details, strict=True):
            if detail is None:
                continue
            preview = " ".join(detail.content.split())[:80]
            print(f"{email.from_.address:<24} {email.subject[:30]:<30} {preview}")


if __name__ == "__main__":
    asyncio.run(main())
