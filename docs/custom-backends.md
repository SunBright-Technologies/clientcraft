# Custom Backends

Backends are **protocol-based** (structural typing) — no base class to inherit.
Any object with a matching `request` method is a valid backend, and any object
with `status_code` / `content` / `headers` is a valid response. This makes it
easy to plug in a custom transport, a test double, or a caching/instrumentation
layer.

## The protocols

### `HttpResponse`

What a backend's `request` must return:

```python
class HttpResponse(Protocol):
    @property
    def status_code(self) -> int: ...
    @property
    def content(self) -> bytes: ...
    @property
    def headers(self) -> dict[str, str]: ...
```

Most HTTP libraries' response objects already satisfy this.

### `HttpBackend` (sync)

```python
class HttpBackend(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse: ...
```

### `AsyncHttpBackend` (async)

Identical, but `request` is `async`:

```python
class AsyncHttpBackend(Protocol):
    async def request(
        self,
        method: str,
        url: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse: ...
```

## A minimal custom backend

```python
from dataclasses import dataclass
import httpx


@dataclass
class MyResponse:
    status_code: int
    content: bytes
    headers: dict[str, str]


class MyBackend:
    def __init__(self) -> None:
        self._client = httpx.Client()

    def request(
        self,
        method: str,
        url: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> MyResponse:
        r = self._client.request(
            method, url, content=content, headers=headers, timeout=timeout
        )
        return MyResponse(r.status_code, r.content, dict(r.headers))


client = UserAPI(base_url="https://api.example.com", backend=MyBackend())
```

## A test double

A custom backend is the cleanest way to test a client without network calls —
capture the request and return canned responses:

```python
from dataclasses import dataclass


@dataclass
class FakeResponse:
    status_code: int
    content: bytes
    headers: dict[str, str]


class FakeBackend:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.body = body
        self.status = status
        self.last_url: str | None = None

    def request(self, method, url, *, content=None, headers=None, timeout=None):
        self.last_url = url
        return FakeResponse(self.status, self.body, {})


backend = FakeBackend(b'{"id": "1", "name": "Ada", "email": "a@x.com"}')
client = UserAPI(base_url="https://api.example.com", backend=backend)

user = client.get_user(GetUserRequest(user_id="1"))
assert user.name == "Ada"
assert backend.last_url == "https://api.example.com/users/1"
```

!!! tip "Type your backend against the protocol"
    Annotating with `HttpBackend` / `AsyncHttpBackend` lets your type checker
    confirm the shape is correct:

    ```python
    from clientcraft.backends import HttpBackend

    def make_client(backend: HttpBackend) -> UserAPI:
        return UserAPI(base_url="https://api.example.com", backend=backend)
    ```
