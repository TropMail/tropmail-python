"""Print a mailbox summary and read the newest message.

    export TROPMAIL_API_KEY=...
    python examples/quickstart.py
"""

from __future__ import annotations

from tropmail import NotFoundError, TropMail, TropMailError


def main() -> None:
    with TropMail() as client:
        boxes = client.mailboxes.list()
        if not boxes:
            print("This API key has no mailboxes.")
            return
        mailbox = boxes[0]
        print(
            f"{mailbox.email} — {mailbox.opened_count} open, "
            f"{mailbox.closed_count} closed, {mailbox.favorite_count} favorite\n"
        )

        page = client.emails.list(mailbox_id=mailbox.id, limit=5)
        if not page.emails:
            print("The mailbox is empty.")
            return

        for email in page.emails:
            print(f"{email.from_.address:<24} {email.subject[:40]:<40} {email.timestamp}")

        newest = page.emails[0]
        try:
            detail = client.emails.get(mailbox.id, newest, view="text")
        except NotFoundError:
            print("\nThat message was deleted between listing and reading it.")
            return
        except TropMailError as error:
            print(f"\nRead failed ({error.status}, request {error.request_id}): {error}")
            return

        print(f"\n--- {detail.subject} ---")
        print(detail.content[:500])


if __name__ == "__main__":
    main()
