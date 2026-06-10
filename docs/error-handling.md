# Error Handling

When a response has a status code of **400 or greater**, the endpoint raises
`HttpError` instead of returning a parsed value.

```python
from clientcraft import HttpError

try:
    user = client.get_user(GetUserRequest(user_id="does-not-exist"))
except HttpError as err:
    print(err.status_code)   # e.g. 404
    print(err.content)       # raw response body as bytes
    print(err.headers)       # response headers as dict[str, str]
```

## `HttpError`

`HttpError` carries everything you need to inspect a failed request:

- **`status_code`** — the HTTP status code (`int`).
- **`content`** — the raw response body (`bytes`).
- **`headers`** — response headers (`dict[str, str]`).

Its string form includes the status and a best-effort UTF-8 decode of the body,
so logging the exception directly is informative:

```python
except HttpError as err:
    logger.error("request failed: %s", err)   # HTTP 404: {"detail": "not found"}
```

## Handling specific statuses

There is currently a single exception type; branch on `status_code` for
different cases:

```python
try:
    user = client.get_user(req)
except HttpError as err:
    if err.status_code == 404:
        user = None
    elif err.status_code == 429:
        # back off and retry
        ...
    else:
        raise
```

!!! tip "Successful responses below 400"
    Only `>= 400` raises. A `204 No Content` (or any 2xx/3xx) is treated as
    success and parsed according to the [response type](requests-responses.md#response-types) —
    e.g. a `None` response model yields `None`.
