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
    mailbox = client.mailbox.get()
    print(f"{mailbox.email}: {mailbox.opened_count} opened")

    for email in client.emails.iterate(status="Open"):
        print(email.timestamp, email.from_.address, email.subject)
```

Pass the key explicitly if you prefer:

```python
client = TropMail("your32charalphanumericapikeyhere")
```

## Async

```python
import asyncio
from tropmail import AsyncTropMail

async def main() -> None:
    async with AsyncTropMail() as client:
        async for email in client.emails.iterate(status="Favorite"):
            print(email.subject)

asyncio.run(main())
```

## Reading an email

`get()` returns the HTML view by default. Pass the email object you already have
instead of a bare id and the SDK forwards its timestamp for a faster lookup.

```python
page = client.emails.list(limit=10)
email = page.emails[0]

detail = client.emails.get(email, view="text")
print(detail.content)

for attachment in detail.attachments:
    print(attachment.filename, attachment.size, attachment.scan_status)
```

### Markdown

The markdown view is generated on demand and the server can block for up to a
minute before answering `504`. `get_markdown()` handles that retry for you:

```python
detail = client.emails.get_markdown(email)
print(detail.content)
```

## Actions

```python
client.emails.favorite(email)
client.emails.close(email)
client.emails.block(email)          # also blocks the sender for future mail
client.emails.clear_action(email)   # clears the action, unblocking the sender
```

All of them are shorthands for `update()`:

```python
client.emails.update(email, email_state="Open", action_status="Favorite")
```

## Attachments

```python
info = client.attachments.get(attachment_id)
print(info.filename, info.scan_status)

client.attachments.scan(attachment_id)
path = client.attachments.download_to(attachment_id, "/tmp/invoice.pdf")
```

The download URL lives on a separate host, so no API credentials are ever sent to it.

## Search

```python
page = client.emails.search("invoice", limit=25)
for email in client.emails.search_iterate("invoice"):
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
    client.emails.get("does-not-exist")
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

Budgets are per mailbox, per second: Pro 3, Ultimate 10, Enterprise 50.

The client reads the limit from response headers and paces itself with a token
bucket so you stay under the budget instead of collecting `429`s. Inspect the
current window at any time:

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

Retries use exponential backoff with full jitter on 429, 502, 503, 504, and
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
