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
- **`endpoint_info`** — the [`EndpointInfo`](api-reference.md) for the call that
  failed (`path`, `method`, …), or `None` if unavailable. Handy for branching on
  *which* endpoint errored.

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

## Domain errors

Rather than wrapping every call site in `try`/`except` on status codes, you can
translate HTTP errors into your own **domain exceptions** declaratively. This is
fully **opt-in**: a client that declares no mapping behaves exactly as above,
raising `HttpError` on any `>= 400`.

There are three cooperating layers, from most declarative to most flexible.

### 1. Declare the errors your endpoints raise

Define exceptions as subclasses of `DomainError`, then map status codes to them.
Per-endpoint mappings use `Raises(status, ExcType)` as annotation metadata;
client-wide mappings use the `errors` attribute — an `ErrorMap` (a read-only
mapping, so the declaration stays immutable). A status code is resolved
**per-endpoint first, then the client `errors`, then a raw `HttpError`**.

```python
from typing import Annotated, Literal
from clientcraft import DomainError, ErrorMap, Get, Raises
from clientcraft.client import APIClient


class UserNotFound(DomainError):
    pass


class RateLimited(DomainError):
    pass


class UserAPI(APIClient):
    get_user: Annotated[
        Get[GetUserRequest, User, Literal["/users/{user_id}"]],
        Raises(404, UserNotFound),              # per-endpoint
    ]

    errors = ErrorMap({429: RateLimited})       # applies to every endpoint
```

You can list several `Raises(...)` items for one endpoint — Python flattens the
nested `Annotated`, so each maps one status. Declaring the same status twice on
one endpoint is rejected at class-definition time.

Use the `DEFAULT` key as a **catch-all** for any error status without an exact
mapping — both per-endpoint and client-wide:

```python
from clientcraft import DEFAULT

class UserAPI(APIClient):
    get_user: Annotated[
        Get[GetUserRequest, User, Literal["/users/{user_id}"]],
        Raises(404, UserNotFound),
        Raises(DEFAULT, ApiError),          # any other error on this endpoint
    ]

    errors = ErrorMap({429: RateLimited, DEFAULT: ApiError})   # client-wide fallback
```

An exact status always wins over `DEFAULT`; within the same specificity, a
per-endpoint mapping wins over the client-wide one. Full order:
**per-endpoint exact → client exact → per-endpoint `DEFAULT` → client `DEFAULT`**,
then `handle_error`.

Callers now catch *domain* errors:

```python
try:
    user = client.get_user(GetUserRequest(user_id="does-not-exist"))
except UserNotFound:
    user = None
```

Each domain error carries the original `HttpError` on `.http_error` (with its
`status_code`, `content`, `headers`, and `endpoint_info`).

### 2. Parse the response body on the exception

When constructing the domain error needs the response body (e.g. an error
envelope), override `from_http_error` on the exception — the parsing logic lives
on the type, reusable across every client that maps to it:

```python
import json
from clientcraft import HttpError


class ValidationError(DomainError):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

    @classmethod
    def from_http_error(cls, error: HttpError) -> DomainError:
        payload = json.loads(error.content)
        exc = cls(payload["message"])
        exc.http_error = error
        return exc
```

The default `DomainError.from_http_error` just builds `cls(str(error))` and
attaches `.http_error`; override it only when you need the body or a custom
constructor.

### 3. Full control with `handle_error`

For anything the declarative maps don't cover, override `handle_error(self, error)`
on the client. It is the fallback, called for every `>= 400` that no mapping
matched, on both sync and async clients. The default implementation raises the
`HttpError`.

```python
class UserAPI(APIClient):
    def handle_error(self, error: HttpError) -> None:
        if error.status_code >= 500:
            raise ServiceUnavailable(error.endpoint_info.path) from error
        super().handle_error(error)   # default: re-raise HttpError
```

!!! warning "Always raise"
    `handle_error` is only invoked on failures and is expected to raise. If it
    returns normally the error is suppressed and the endpoint returns `None`,
    which is rarely what you want — call `super().handle_error(error)` for any
    case you don't explicitly handle.

!!! tip "Resolution order"
    On a `>= 400` response: per-endpoint exact `Raises` → client exact `errors` →
    per-endpoint `DEFAULT` → client `DEFAULT` → `handle_error` (whose default
    raises `HttpError`). All of it works identically for `AsyncAPIClient`.

See [`example_error_handling.py`](https://github.com/SunBright-Technologies/clientcraft/blob/main/example_error_handling.py)
for a complete runnable example against a live API.
