"""Scan and download every attachment on one email.

    export TROPMAIL_API_KEY=...
    python examples/save_attachments.py <mailbox-id> <email-id> [directory]
"""

from __future__ import annotations

import sys
from pathlib import Path

from tropmail import TropMail


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2

    mailbox_id = sys.argv[1]
    email_id = sys.argv[2]
    directory = Path(sys.argv[3] if len(sys.argv) > 3 else ".")
    directory.mkdir(parents=True, exist_ok=True)

    with TropMail() as client:
        for scan in client.emails.scan_attachments(mailbox_id, email_id):
            print(f"{scan.filename:<40} {scan.scan_status}")

        for item in client.emails.download_attachments(mailbox_id, email_id):
            if not item.available:
                print(f"skip {item.filename} (not available)")
                continue
            target = directory / Path(item.filename).name
            saved = client.attachments.download_to(mailbox_id, item.attachment_id, target)
            print(f"saved {saved} ({saved.stat().st_size} bytes)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
