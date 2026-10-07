# tropmail

Official Python SDK for the [TropMail API](https://api.tropmail.com).

Sync and async clients, fully typed, with automatic pagination, retries, and
client-side rate-limit pacing.

```bash
pip install tropmail
```

Requires Python 3.10+. The client reads `TROPMAIL_API_KEY` unless you pass the key.

## Quick start

```python
from tropmail import TropMail

with TropMail() as client:           # reads TROPMAIL_API_KEY
    boxes = client.mailboxes.list()
    mailbox = boxes[0]
    print(f"{mailbox.email}: {mailbox.opened_count} opened")

    for email in client.emails.iterate(mailbox_id=mailbox.id, status="Open"):
        print(email.timestamp, email.from_.address, email.subject)
```

Pass the key explicitly if you prefer:

```python
client = TropMail("YOUR_API_KEY")
```

## Async

```python
import asyncio
from tropmail import AsyncTropMail

async def main() -> None:
    async with AsyncTropMail() as client:
        boxes = await client.mailboxes.list()
        mailbox = boxes[0]
        async for email in client.emails.iterate(mailbox_id=mailbox.id, status="Favorite"):
            print(email.subject)

asyncio.run(main())
```

## Reading an email

`get()` returns the HTML view by default. Pass the email object you already have
instead of a bare id and the SDK forwards its timestamp for a faster lookup.

```python
page = client.emails.list(mailbox_id=mailbox.id, limit=10)
email = page.emails[0]

detail = client.emails.get(mailbox.id, email, view="text")
print(detail.content)

for attachment in detail.attachments:
    print(attachment.filename, attachment.size, attachment.scan_status)
```

### Markdown

The markdown view is generated on demand and the server can block for up to a
minute before answering `504`. `get_markdown()` handles that retry for you:

```python
detail = client.emails.get_markdown(mailbox.id, email)
print(detail.content)
```

## Actions

```python
client.emails.favorite(mailbox.id, email)
client.emails.close(mailbox.id, email)
client.emails.block(mailbox.id, email)          # also blocks the sender for future mail
client.emails.clear_action(mailbox.id, email)   # clears the action, unblocking the sender
```

All of them are shorthands for `update()`:

```python
client.emails.update(mailbox.id, email, email_state="Open", action_status="Favorite")
```

## Attachments

```python
info = client.attachments.get(mailbox.id, attachment_id)
print(info.filename, info.scan_status)

client.attachments.scan(mailbox.id, attachment_id)
path = client.attachments.download_to(mailbox.id, attachment_id, "/tmp/invoice.pdf")
```

Downloads use your API key on the same host as the rest of the API.

## Search

```python
page = client.emails.search("invoice", mailbox_id=mailbox.id, limit=25)
for email in client.emails.search_iterate("invoice", mailbox_id=mailbox.id):
    print(email.subject)
```

Note that the API always reports `total: 0` for search results. The iterators
page until they see a short page rather than trusting `total`.

## Errors

```python
from tropmail import (
    AuthenticationError, NotFoundError, RateLimitError,
    TierError, TropMailError,
)

try:
    client.emails.get(mailbox.id, "does-not-exist")
except NotFoundError as exc:
    print(exc.status, exc.request_id)
except RateLimitError as exc:
    print("retry after", exc.retry_after)
except TropMailError as exc:
    print("request failed:", exc)
```

Every error carries `status`, `message`, and the `request_id` echoed by the API,
which is what support needs to trace a call.

| Exception | HTTP |
|---|---|
| `ValidationError` | 400 |
| `AuthenticationError` | 401 |
| `TierError` | 403 |
| `NotFoundError` | 404 |
| `RateLimitError` | 429 |
| `MarkdownTimeoutError` | 504 |
| `ServerError` | 5xx |
| `ConnectionError` | transport failure |

## Rate limits

Budgets are per account, per second: Pro 3, Ultimate 10, Enterprise 50.

The client reads the limit from response headers and stays within your
account budget. Inspect the current window at any time:

```python
print(client.rate_limit)   # RateLimitInfo(limit=3, remaining=2, reset=1767225600)
```

Disable pacing with `TropMail(throttle=False)` if you manage concurrency yourself.

## Configuration

```python
client = TropMail(
    api_key=None,                                  # else TROPMAIL_API_KEY
    base_url="https://api.tropmail.com/api/v1",
    timeout=120.0,                                 # markdown can block ~60s
    max_retries=3,
    throttle=True,
)
```

Retries with backoff on 429, 502, 503, 504, and
transport errors. Reads retry automatically; mutations never do.

## Examples

Runnable scripts live in [`examples/`](examples/): a quickstart, a concurrent
async inbox reader, and attachment downloading.

## Development

```bash
make install
make test
make lint
make typecheck
```

## Docs

Guides and API reference: [docs.tropmail.com](https://docs.tropmail.com/sdks/python/).

## License

MIT
