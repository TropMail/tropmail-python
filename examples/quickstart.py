"""Print a mailbox summary and read the newest message.

    export TROPMAIL_API_KEY=...
    python examples/quickstart.py
"""

from __future__ import annotations

from tropmail import NotFoundError, TropMail, TropMailError


def main() -> None:
    # No api_key argument: the client reads TROPMAIL_API_KEY and validates the
    # format locally, so a malformed key fails before spending a round trip.
    with TropMail() as client:
        mailbox = client.mailbox.get()
        print(
            f"{mailbox.email} — {mailbox.opened_count} open, "
            f"{mailbox.closed_count} closed, {mailbox.favorite_count} favorite\n"
        )

        page = client.emails.list(limit=5)
        if not page.emails:
            print("The mailbox is empty.")
            return

        for email in page.emails:
            print(f"{email.from_.address:<24} {email.subject[:40]:<40} {email.timestamp}")

        # Passing the email object rather than its id forwards the timestamp
        # for a faster lookup.
        newest = page.emails[0]
        try:
            detail = client.emails.get(newest, view="text")
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
