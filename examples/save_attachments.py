"""Scan and download every attachment on one email.

    export TROPMAIL_API_KEY=...
    python examples/save_attachments.py <email-id> [directory]
"""

from __future__ import annotations

import sys
from pathlib import Path

from tropmail import TropMail


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    email_id = sys.argv[1]
    directory = Path(sys.argv[2] if len(sys.argv) > 2 else ".")
    directory.mkdir(parents=True, exist_ok=True)

    with TropMail() as client:
        # Scanning is asynchronous: a fresh request comes back as Processing
        # and the verdict lands on a later read.
        for scan in client.emails.scan_attachments(email_id):
            print(f"{scan.filename:<40} {scan.scan_status}")

        for item in client.emails.download_attachments(email_id):
            if not item.available:
                print(f"skip {item.filename} (not available)")
                continue
            # Path().name keeps a server-supplied name from escaping the directory.
            target = directory / Path(item.filename).name
            saved = client.attachments.download_to(item.attachment_id, target)
            print(f"saved {saved} ({saved.stat().st_size} bytes)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
