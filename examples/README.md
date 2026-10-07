# Python examples

```bash
pip install tropmail
export TROPMAIL_API_KEY=YOUR_API_KEY
```

| File | What it shows |
|---|---|
| [`quickstart.py`](quickstart.py) | mailbox summary, listing, reading one message, typed errors |
| [`async_inbox.py`](async_inbox.py) | `AsyncTropMail`, auto-paging `async for`, concurrent reads under the rate limit |
| [`save_attachments.py`](save_attachments.py) | scanning attachments and streaming them to disk |

```bash
python examples/quickstart.py
python examples/async_inbox.py
python examples/save_attachments.py <email-id> ./downloads
```

These are type-checked in CI (`make lint typecheck`), so they cannot drift from
the SDK.
